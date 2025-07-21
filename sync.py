import os, subprocess, json
from pathlib import Path
from googleapiclient.discovery import build
from feed_util import load_or_create_feed, add_entry, save_feed

PLAYLIST_ID = os.environ['PLAYLIST_ID']
API_KEY     = os.environ['API_KEY']

pod_dir = Path("podcasts")
pod_dir.mkdir(exist_ok=True)

def download_mp3(video_id):
    outtmpl = str(pod_dir / f"{video_id}.%(ext)s")
    if (pod_dir / f"{video_id}.mp3").exists():
        return False
    cmd = [
        "yt-dlp",
        "--extract-audio",
        "--audio-format", "mp3",
        "--audio-quality", "192K",
        "-o", outtmpl,
        f"https://www.youtube.com/watch?v={video_id}"
    ]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL)
    return True

def main():
    youtube = build('youtube', 'v3', developerKey=API_KEY)
    res = youtube.playlistItems().list(
        part='snippet',
        playlistId=PLAYLIST_ID,
        maxResults=50
    ).execute()

    fg = load_or_create_feed()
    new_download = False

    for item in res.get('items', []):
        vid = item['snippet']['resourceId']['videoId']
        if download_mp3(vid):
            add_entry(fg, item, f"{vid}.mp3")
            new_download = True
            print(f"✔ {vid} downloaded")

    if new_download:
        save_feed(fg)
        print("feed.xml updated")
    else:
        print("No new videos; nothing to do.")

if __name__ == "__main__":
    main()
