from feedgen.feed import FeedGenerator
from pathlib import Path
from dateutil import parser as dateparser
import feedparser                     # ★ 追加

SITE_URL  = "https://masdaq.github.io/yt2pc/podcasts/"
FEED_PATH = Path("podcasts/feed.xml")

def load_or_create_feed():
    fg = FeedGenerator()
    if FEED_PATH.exists():
        # 既存 feed を読み込み → エントリをコピー
        parsed = feedparser.parse(FEED_PATH.read_text())
        fg.id(parsed.feed.get("id", SITE_URL))
        fg.title(parsed.feed.get("title", "YT Podcast"))
        fg.link(href=SITE_URL, rel="alternate")
        fg.language(parsed.feed.get("language", "ja"))
        fg.description(parsed.feed.get("description", "YT Playlist Podcast"))

        for entry in parsed.entries:
            fe = fg.add_entry(order="append")
            fe.id(entry.id)
            fe.title(entry.title)
            fe.pubDate(entry.published)
            fe.enclosure(
                url = entry.enclosures[0].href,
                length = entry.enclosures[0].length,
                type = entry.enclosures[0].type
            )
        return fg
    
    # ---- 新規 feed ----
    fg.id(SITE_URL)
    fg.title("YouTube Playlist Podcast")
    fg.link(href=SITE_URL, rel="alternate")
    fg.language("ja")
    fg.description("Auto-generated audio feed from YouTube playlist")
    return fg

def add_entry(fg, item, mp3_name):
    fe = fg.add_entry(order="prepend")
    fe.id(item["snippet"]["resourceId"]["videoId"])
    fe.title(item["snippet"]["title"])
    published = dateparser.parse(item["snippet"]["publishedAt"])
    fe.pubDate(published)
    fe.enclosure(
        url = SITE_URL + mp3_name,
        length = "0",
        type = "audio/mpeg",
    )

def save_feed(fg):
    FEED_PATH.write_text(fg.rss_str(pretty=True).decode("utf-8"))
