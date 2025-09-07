#!/usr/bin/env python3
import os
import sys
import subprocess
from pathlib import Path
from datetime import datetime, timezone
from dateutil import parser as dateparser
import urllib.parse as up
import feedparser

# feed_util は以前のものをそのまま使います
from feed_util import load_or_create_feed, save_feed, FEED_PATH, SITE_URL

POD_DIR = Path("podcasts")
POD_DIR.mkdir(exist_ok=True)

# === 設定（環境変数） ==========================================
RAINDROP_RSS   = os.getenv("RAINDROP_RSS", "").strip()   # 例: https://raindrop.io/collection/xxxxxx/feed
SINGLE_URL     = os.getenv("SINGLE_URL", "").strip()     # 手動投入用（共有シート→workflow_dispatch）
USE_BROWSER    = os.getenv("USE_BROWSER_COOKIES") == "1" # self-hosted runner でブラウザCookie使用時
BROWSER_NAME   = os.getenv("BROWSER_NAME", "chrome")     # chrome / brave / edge など
COOKIES_TXT    = "cookies.txt"                           # Actions で書き出しているファイル
AUDIO_Q        = "96K"                                   # まず 96kbps で作成
MAX_BYTES      = 95 * 1024 * 1024                        # 95MB超なら縮小（GitHub 100MB制限の安全マージン）

# === ユーティリティ ===========================================

def log(msg: str):
    print(msg, flush=True)

def extract_video_id(url: str) -> str:
    if "youtu.be/" in url:
        return url.rstrip("/").split("/")[-1].split("?")[0]
    u = up.urlparse(url)
    v = up.parse_qs(u.query).get("v", [""])[0]
    return v or url

def get_title_via_ytdlp(url: str) -> str:
    try:
        r = subprocess.run(
            ["yt-dlp", "-O", "%(title)s", url],
            capture_output=True, text=True, timeout=60
        )
        if r.returncode == 0:
            return (r.stdout or "").strip() or extract_video_id(url)
    except Exception:
        pass
    return extract_video_id(url)

def ytdlp_auth_args() -> list:
    # 常に無認証で実行（Cookieを使わない）
    return []

def shrink_if_needed(mp3_path: Path):
    size = mp3_path.stat().st_size
    if size <= MAX_BYTES:
        return
    tmp = mp3_path.with_suffix(".mp3.tmp")
    # トーク用途向けに 64kbps / mono に再エンコード
    subprocess.run(
        ["ffmpeg", "-y", "-i", str(mp3_path), "-b:a", "64k", "-ac", "1", str(tmp)],
        check=True, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT
    )
    tmp.replace(mp3_path)

def download_mp3(url: str) -> tuple[str, bool]:
    """URL を MP3 化。戻り値: (video_id, 生成したかどうか)"""
    vid = extract_video_id(url)
    mp3 = POD_DIR / f"{vid}.mp3"
    if mp3.exists():
        return vid, False

    outtmpl = str(POD_DIR / f"{vid}.%(ext)s")
    base = [
        "yt-dlp",
        *ytdlp_auth_args(),
        "--extract-audio", "--audio-format", "mp3",
        "--audio-quality", AUDIO_Q,
        "-o", outtmpl, url,
    ]

    # まず認証付きで
    r = subprocess.run(base, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
    if r.returncode != 0:
        err = r.stderr or ""
        # Cookie失効/CAPTCHA っぽい時は非ログインで再試行（公開動画は通ることがある）
        if ("no longer valid" in err) or ("confirm you’re not a bot" in err):
            base_noauth = [a for a in base if a not in ytdlp_auth_args()]
            r2 = subprocess.run(base_noauth, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            if r2.returncode != 0:
                log(f"[skip] {vid}: cookie invalid/captcha")
                return vid, False
        else:
            log(f"[skip] {vid}: yt-dlp error")
            return vid, False

    shrink_if_needed(mp3)
    return vid, True

def add_feed_entry(fg, *, vid: str, title: str, published: datetime | None, page_url: str):
    fe = fg.add_entry(order="prepend")
    fe.id(vid)
    fe.title(title)
    fe.link(href=page_url)
    fe.enclosure(
        url=f"{SITE_URL}{vid}.mp3",
        length=str((POD_DIR / f"{vid}.mp3").stat().st_size),
        type="audio/mpeg",
    )
    fe.pubDate(published or datetime.now(timezone.utc))

def existing_ids_from_feed() -> set[str]:
    if FEED_PATH.exists():
        try:
            parsed = feedparser.parse(FEED_PATH.read_text())
            return {getattr(e, "id", "") for e in parsed.entries if getattr(e, "id", "")}
        except Exception:
            pass
    return set()

# === 入力（Raindrop RSS / 単発URL） ============================

def iter_source_items():
    """(url, title, published_datetime) を yield"""
    if SINGLE_URL:
        url = SINGLE_URL
        title = get_title_via_ytdlp(url)
        return [(url, title, None)]

    if not RAINDROP_RSS:
        log("No input specified. Set RAINDROP_RSS or SINGLE_URL.")
        return []

    feed = feedparser.parse(RAINDROP_RSS)
    items = []
    for e in feed.entries:
        url = getattr(e, "link", "")
        if ("youtube.com" in url) or ("youtu.be/" in url):
            title = getattr(e, "title", "") or extract_video_id(url)
            # published/updated のどれかをパース
            pub_str = getattr(e, "published", "") or getattr(e, "updated", "")
            pub_dt = None
            if pub_str:
                try:
                    pub_dt = dateparser.parse(pub_str)
                    if pub_dt.tzinfo is None:
                        pub_dt = pub_dt.replace(tzinfo=timezone.utc)
                except Exception:
                    pub_dt = None
            items.append((url, title, pub_dt))
    return items

# === メイン =====================================================

def main():
    changed_any = False
    fg = load_or_create_feed()
    already = existing_ids_from_feed()

    for url, title, pub_dt in iter_source_items():
        vid, created = download_mp3(url)
        if not created:
            # すでに mp3 がある or 失敗。feed に未登録なら登録だけする
            if vid in already:
                continue
        if vid in already:
            continue
        add_feed_entry(fg, vid=vid, title=title or vid, published=pub_dt, page_url=url)
        changed_any = True

    if changed_any:
        save_feed(fg)
        log("feed.xml updated")
    else:
        log("no changes")

if __name__ == "__main__":
    try:
        main()
    except subprocess.CalledProcessError as e:
        log(f"subprocess error: {e}")
        sys.exit(1)
