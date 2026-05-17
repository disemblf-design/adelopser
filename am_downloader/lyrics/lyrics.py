"""歌词模块 — TTML → LRC 转换（对应原 Go lyrics/lyrics.go）"""

import re
from xml.etree import ElementTree

import httpx

from am_downloader.api.client import USER_AGENT


def contains_cjk(s: str) -> bool:
    """检测字符串是否包含 CJK 字符"""
    for ch in s:
        cp = ord(ch)
        if any([
            0x1100 <= cp <= 0x11FF,   # Hangul Jamo
            0x2E80 <= cp <= 0x2EFF,   # CJK Radicals Supplement
            0x2F00 <= cp <= 0x2FDF,   # Kangxi Radicals
            0x3000 <= cp <= 0x303F,   # CJK Symbols and Punctuation
            0x3040 <= cp <= 0x309F,   # Hiragana
            0x30A0 <= cp <= 0x30FF,   # Katakana
            0x3130 <= cp <= 0x318F,   # Hangul Compatibility Jamo
            0x31C0 <= cp <= 0x31EF,   # CJK Strokes
            0x3200 <= cp <= 0x32FF,   # Enclosed CJK Letters
            0x3300 <= cp <= 0x33FF,   # CJK Compatibility
            0x3400 <= cp <= 0x4DBF,   # CJK Extension A
            0x4E00 <= cp <= 0x9FFF,   # CJK Unified Ideographs
            0xA960 <= cp <= 0xA97F,   # Hangul Jamo Extended-A
            0xAC00 <= cp <= 0xD7AF,   # Hangul Syllables
            0xD7B0 <= cp <= 0xD7FF,   # Hangul Jamo Extended-B
            0xF900 <= cp <= 0xFAFF,   # CJK Compatibility Ideographs
            0xFE30 <= cp <= 0xFE4F,   # CJK Compatibility Forms
            0xFF00 <= cp <= 0xFFEF,   # Halfwidth and Fullwidth Forms
            0x20000 <= cp <= 0x2A6DF,  # CJK Extension B
            0x2A700 <= cp <= 0x2B73F,  # CJK Extension C
            0x2B740 <= cp <= 0x2B81F,  # CJK Extension D
            0x2F800 <= cp <= 0x2FA1F,  # CJK Compatibility Supplement
        ]):
            return True
    return False


def get_lyrics(
    storefront: str,
    song_id: str,
    lrc_type: str,       # "lyrics" or "syllable-lyrics"
    language: str,
    lrc_format: str,     # "lrc" or "ttml"
    token: str,
    media_user_token: str,
) -> str:
    """获取歌词并转换为指定格式"""
    if len(media_user_token) < 50:
        raise ValueError("MediaUserToken not set or too short")

    ttml = _fetch_song_lyrics(song_id, storefront, token, media_user_token, lrc_type, language)

    if lrc_format == "ttml":
        return ttml

    lrc = ttml_to_lrc(ttml)
    return lrc


def _fetch_song_lyrics(
    song_id: str,
    storefront: str,
    token: str,
    media_user_token: str,
    lrc_type: str,
    language: str,
) -> str:
    """从 Apple Music API 获取 TTML 歌词"""
    url = (
        f"https://amp-api.music.apple.com/v1/catalog/{storefront}/songs/"
        f"{song_id}/{lrc_type}"
        f"?l={language}&extend=ttmlLocalizations"
    )

    with httpx.Client(timeout=30) as client:
        resp = client.get(
            url,
            headers={
                "Authorization": f"Bearer {token}",
                "User-Agent": USER_AGENT,
                "Origin": "https://music.apple.com",
                "Referer": "https://music.apple.com/",
            },
            cookies={"media-user-token": media_user_token},
        )
        resp.raise_for_status()
        data = resp.json()

    song_data = data.get("data", [])
    if song_data:
        attrs = song_data[0].get("attributes", {})
        ttml = attrs.get("ttml", "")
        if ttml:
            return ttml
        return attrs.get("ttmlLocalizations", "")

    raise RuntimeError("Failed to get lyrics")


def ttml_to_lrc(ttml: str) -> str:
    """将 TTML 歌词转换为 LRC 格式"""
    if not ttml:
        return ""

    try:
        root = ElementTree.fromstring(ttml)
    except ElementTree.ParseError:
        return ""

    # TTML 命名空间
    ns = {
        "tt": "http://www.w3.org/ns/ttml",
        "itunes": "http://music.apple.com/lyric-ttml-internal",
    }

    lrc_lines = []

    # 查找所有 <p> 元素（歌词段落/行）
    for body in root.findall(".//tt:body", ns):
        for div in body.findall(".//tt:div", ns):
            for p in div.findall(".//tt:p", ns):
                begin = p.get("begin", "")
                text = "".join(p.itertext()).strip()
                if not text:
                    continue

                # 转换时间戳 (HH:MM:SS.sss → [MM:SS.ss])
                lrc_time = _ttml_time_to_lrc(begin)
                if lrc_time:
                    lrc_lines.append(f"{lrc_time}{text}")

    return "\n".join(lrc_lines) if lrc_lines else ""


def _ttml_time_to_lrc(ttml_time: str) -> str:
    """转换 TTML 时间戳到 LRC 格式

    TTML: 00:01:23.456 → LRC: [01:23.45]
    """
    if not ttml_time:
        return ""

    # 匹配多种格式
    # HH:MM:SS.sss
    m = re.match(r"(\d+):(\d+):(\d+(?:\.\d+)?)", ttml_time)
    if m:
        hours = int(m.group(1))
        minutes = int(m.group(2))
        seconds = float(m.group(3))
        total_minutes = hours * 60 + minutes
        whole_sec = int(seconds)
        centisec = int((seconds - whole_sec) * 100)
        return f"[{total_minutes:02d}:{whole_sec:02d}.{centisec:02d}]"

    # MM:SS.sss
    m = re.match(r"(\d+):(\d+(?:\.\d+)?)", ttml_time)
    if m:
        minutes = int(m.group(1))
        seconds = float(m.group(2))
        whole_sec = int(seconds)
        centisec = int((seconds - whole_sec) * 100)
        return f"[{minutes:02d}:{whole_sec:02d}.{centisec:02d}]"

    # SS.sss
    m = re.match(r"(\d+(?:\.\d+)?)s?", ttml_time)
    if m:
        seconds = float(m.group(1))
        minutes = int(seconds // 60)
        whole_sec = int(seconds % 60)
        centisec = int((seconds - int(seconds)) * 100)
        return f"[{minutes:02d}:{whole_sec:02d}.{centisec:02d}]"

    return ""
