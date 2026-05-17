"""测试歌词转换"""

import pytest

from am_downloader.lyrics.lyrics import ttml_to_lrc, _ttml_time_to_lrc, contains_cjk


def test_ttml_time_to_lrc():
    assert _ttml_time_to_lrc("00:01:23.456") == "[01:23.45]"
    assert _ttml_time_to_lrc("01:23.456") == "[01:23.45]"
    assert _ttml_time_to_lrc("00:00:00.000") == "[00:00.00]"
    assert _ttml_time_to_lrc("") == ""


def test_contains_cjk():
    assert contains_cjk("你好世界") is True
    assert contains_cjk("Hello World") is False
    assert contains_cjk("こんにちは") is True
    assert contains_cjk("한국어") is True


def test_ttml_to_lrc_simple():
    ttml = """<?xml version="1.0" encoding="UTF-8"?>
<tt xmlns="http://www.w3.org/ns/ttml">
  <body>
    <div>
      <p begin="00:00:10.500">Hello world</p>
      <p begin="00:00:15.000">This is a test</p>
    </div>
  </body>
</tt>"""
    lrc = ttml_to_lrc(ttml)
    assert "[00:10.50]Hello world" in lrc
    assert "[00:15.00]This is a test" in lrc


def test_ttml_to_lrc_empty():
    assert ttml_to_lrc("") == ""
    assert ttml_to_lrc("<invalid>xml") == ""
