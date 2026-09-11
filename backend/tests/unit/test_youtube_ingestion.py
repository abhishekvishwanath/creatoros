import pytest

from app.domain.ingestion.youtube import (
    YoutubeResolutionError,
    _direct_channel_id,
    _parse_channel_page,
    _parse_video_feed,
)

SAMPLE_FEED = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns:yt="http://www.youtube.com/xml/schemas/2015" xmlns:media="http://search.yahoo.com/mrss/" xmlns="http://www.w3.org/2005/Atom">
 <title>Test Channel</title>
 <entry>
  <id>yt:video:abc123</id>
  <yt:videoId>abc123</yt:videoId>
  <yt:channelId>UCxxxxxxxxxxxxxxxxxxxxxx</yt:channelId>
  <title>A short video</title>
  <link rel="alternate" href="https://www.youtube.com/shorts/abc123"/>
  <published>2026-01-01T00:00:00+00:00</published>
  <updated>2026-01-02T00:00:00+00:00</updated>
  <media:group>
   <media:title>A short video</media:title>
   <media:thumbnail url="https://i.ytimg.com/vi/abc123/hqdefault.jpg" width="480" height="360"/>
   <media:description>Description one</media:description>
  </media:group>
 </entry>
 <entry>
  <id>yt:video:def456</id>
  <yt:videoId>def456</yt:videoId>
  <yt:channelId>UCxxxxxxxxxxxxxxxxxxxxxx</yt:channelId>
  <title>A long video</title>
  <link rel="alternate" href="https://www.youtube.com/watch?v=def456"/>
  <published>2026-01-03T00:00:00+00:00</published>
  <updated>2026-01-03T00:00:00+00:00</updated>
  <media:group>
   <media:title>A long video</media:title>
   <media:thumbnail url="https://i.ytimg.com/vi/def456/hqdefault.jpg" width="480" height="360"/>
   <media:description>Description two</media:description>
  </media:group>
 </entry>
</feed>
"""


def test_parse_video_feed_extracts_both_entries_with_format_from_link():
    videos = _parse_video_feed(SAMPLE_FEED, limit=15)
    assert len(videos) == 2
    assert videos[0]["video_id"] == "abc123"
    assert videos[0]["title"] == "A short video"
    assert videos[0]["format"] == "short"
    assert videos[0]["description"] == "Description one"
    assert videos[0]["url"] == "https://www.youtube.com/watch?v=abc123"
    assert videos[1]["format"] == "long"


def test_parse_video_feed_respects_limit():
    videos = _parse_video_feed(SAMPLE_FEED, limit=1)
    assert len(videos) == 1


def test_parse_video_feed_empty_feed_returns_empty_list():
    empty = """<?xml version="1.0" encoding="UTF-8"?>
    <feed xmlns="http://www.w3.org/2005/Atom"><title>Empty</title></feed>"""
    assert _parse_video_feed(empty, limit=15) == []


def test_parse_channel_page_extracts_id_and_title():
    html = '<html><script>var x = {"channelId":"UC1234567890abc"};</script>' \
           '<script>{"channelMetadataRenderer": { "title":"My Channel"}}</script></html>'
    channel_id, name = _parse_channel_page(html)
    assert channel_id == "UC1234567890abc"
    assert name == "My Channel"


def test_parse_channel_page_falls_back_to_html_title_tag():
    html = '<html><head><title>Fallback Name - YouTube</title></head>' \
           '<script>"channelId":"UCabcdefghijklmno"</script></html>'
    channel_id, name = _parse_channel_page(html)
    assert channel_id == "UCabcdefghijklmno"
    assert name == "Fallback Name"


def test_parse_channel_page_raises_when_no_channel_id_present():
    with pytest.raises(YoutubeResolutionError):
        _parse_channel_page("<html>no channel here</html>")


def test_direct_channel_id_from_channel_url():
    assert _direct_channel_id("https://www.youtube.com/channel/UC1234567890ab") == "UC1234567890ab"


def test_direct_channel_id_none_for_handle_url():
    assert _direct_channel_id("https://www.youtube.com/@somehandle") is None
