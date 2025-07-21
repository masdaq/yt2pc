# feed_util.py（丸ごと置き換えて大丈夫です）
from feedgen.feed import FeedGenerator
from pathlib import Path
from dateutil import parser as dateparser

# GitHub Pages を有効化した URL に必ず合わせる
SITE_URL  = "https://masdaq.github.io/yt2pc/podcasts/"
FEED_PATH = Path("podcasts/feed.xml")

def load_or_create_feed():
    if FEED_PATH.exists():
        fg = FeedGenerator()
        fg.load_extension('podcast')
        fg.parse_feed(FEED_PATH.read_text())
        return fg

    fg = FeedGenerator()
    fg.id(SITE_URL)
    fg.title("YouTube Playlist Podcast")
    fg.link(href=SITE_URL, rel="alternate")
    fg.language("ja")
    fg.description("Auto-generated audio feed from YouTube playlihst")
    return fg

def add_entry(fg, item, mp3_name):
    fe = fg.add_entry()
    fe.id(item["snippet"]["resourceId"]["videoId"])
    fe.title(item["snippet"]["title"])
    published = dateparser.parse(item["snippet"]["publishedAt"])
    fe.pubDate(published)
    fe.enclosure(
        url=SITE_URL + mp3_name,
        length="0",
        type="audio/mpeg",
    )

def save_feed(fg):
    FEED_PATH.write_text(fg.rss_str(pretty=True).decode("utf-8"))
