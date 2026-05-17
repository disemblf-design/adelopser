"""测试 URL 解析"""

import pytest

from am_downloader.utils.url_utils import (
    check_url,
    check_url_song,
    check_url_mv,
    check_url_playlist,
    check_url_station,
    check_url_artist,
    parse_url,
    sanitize_filename,
)


def test_parse_album_url():
    url = "https://music.apple.com/us/album/whenever-you-need-somebody/1624945511"
    result = parse_url(url)
    assert result is not None
    assert result.storefront == "us"
    assert result.item_id == "1624945511"
    assert result.url_type == "album"


def test_parse_song_url():
    url = "https://music.apple.com/us/song/never-gonna-give-you-up/1624945511?i=1624945512"
    result = parse_url(url)
    assert result is not None
    assert result.url_type == "song"


def test_parse_playlist_url():
    url = "https://music.apple.com/us/playlist/taylor-swift-essentials/pl.3950454ced8c45a3b0cc693c2a7db97b"
    result = parse_url(url)
    assert result is not None
    assert result.url_type == "playlist"
    assert result.item_id.startswith("pl.")


def test_parse_station_url():
    url = "https://music.apple.com/us/station/apple-music-1/ra.123456789"
    result = parse_url(url)
    assert result is not None
    assert result.url_type == "station"
    assert result.item_id.startswith("ra.")


def test_parse_artist_url():
    url = "https://music.apple.com/us/artist/taylor-swift/159260351"
    result = parse_url(url)
    assert result is not None
    assert result.url_type == "artist"


def test_parse_mv_url():
    url = "https://music.apple.com/us/music-video/bad-blood/159260351"
    result = parse_url(url)
    assert result is not None
    assert result.url_type == "music-video"


def test_parse_invalid_url():
    result = parse_url("https://example.com")
    assert result is None


def test_sanitize_filename():
    assert sanitize_filename("Hello: World?") == "Hello_ World_"
    assert sanitize_filename("file/name\\test") == "file_name_test"
    assert sanitize_filename("normal_name") == "normal_name"
