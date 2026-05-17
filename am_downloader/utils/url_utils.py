"""URL 解析工具 — 从 Apple Music URL 提取 storefront 和 ID"""

import re
from dataclasses import dataclass
from typing import Optional


@dataclass
class ParsedUrl:
    storefront: str
    item_id: str
    url_type: str  # album, song, playlist, station, artist, music-video


# URL 正则模式（与 Go 版完全对应）
_ALBUM_PAT = re.compile(
    r"^(?:https://(?:beta\.music|music|classical\.music)\.apple\.com/(\w{2})(?:/album|/album/.+))/(?:id)?(\d[^\D]+)(?:$|\?)"
)
_SONG_PAT = re.compile(
    r"^(?:https://(?:beta\.music|music|classical\.music)\.apple\.com/(\w{2})(?:/song|/song/.+))/(?:id)?(\d[^\D]+)(?:$|\?)"
)
_PLAYLIST_PAT = re.compile(
    r"^(?:https://(?:beta\.music|music|classical\.music)\.apple\.com/(\w{2})(?:/playlist|/playlist/.+))/(?:id)?(pl\.[\w-]+)(?:$|\?)"
)
_STATION_PAT = re.compile(
    r"^(?:https://(?:beta\.music|music)\.apple\.com/(\w{2})(?:/station|/station/.+))/(?:id)?(ra\.[\w-]+)(?:$|\?)"
)
_ARTIST_PAT = re.compile(
    r"^(?:https://(?:beta\.music|music|classical\.music)\.apple\.com/(\w{2})(?:/artist|/artist/.+))/(?:id)?(\d[^\D]+)(?:$|\?)"
)
_MV_PAT = re.compile(
    r"^(?:https://(?:beta\.music|music)\.apple\.com/(\w{2})(?:/music-video|/music-video/.+))/(?:id)?(\d[^\D]+)(?:$|\?)"
)

FORBIDDEN_NAMES = re.compile(r'[/\\<>:"|?*]')


def sanitize_filename(name: str) -> str:
    """替换文件名中的非法字符"""
    return FORBIDDEN_NAMES.sub("_", name)


def parse_url(url: str) -> Optional[ParsedUrl]:
    """解析 Apple Music URL，返回 ParsedUrl 或 None"""
    for pattern, url_type in [
        (_MV_PAT, "music-video"),
        (_SONG_PAT, "song"),
        (_ALBUM_PAT, "album"),
        (_PLAYLIST_PAT, "playlist"),
        (_STATION_PAT, "station"),
        (_ARTIST_PAT, "artist"),
    ]:
        m = pattern.search(url)
        if m:
            return ParsedUrl(storefront=m.group(1), item_id=m.group(2), url_type=url_type)
    return None


def check_url(url: str) -> tuple[str, str]:
    """解析专辑 URL → (storefront, id)"""
    m = _ALBUM_PAT.search(url)
    return (m.group(1), m.group(2)) if m else ("", "")


def check_url_song(url: str) -> tuple[str, str]:
    """解析歌曲 URL → (storefront, id)"""
    m = _SONG_PAT.search(url)
    return (m.group(1), m.group(2)) if m else ("", "")


def check_url_mv(url: str) -> tuple[str, str]:
    """解析 MV URL → (storefront, id)"""
    m = _MV_PAT.search(url)
    return (m.group(1), m.group(2)) if m else ("", "")


def check_url_playlist(url: str) -> tuple[str, str]:
    """解析播放列表 URL → (storefront, id)"""
    m = _PLAYLIST_PAT.search(url)
    return (m.group(1), m.group(2)) if m else ("", "")


def check_url_station(url: str) -> tuple[str, str]:
    """解析电台 URL → (storefront, id)"""
    m = _STATION_PAT.search(url)
    return (m.group(1), m.group(2)) if m else ("", "")


def check_url_artist(url: str) -> tuple[str, str]:
    """解析艺术家 URL → (storefront, id)"""
    m = _ARTIST_PAT.search(url)
    return (m.group(1), m.group(2)) if m else ("", "")
