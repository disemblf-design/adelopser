"""测试配置加载"""

import os
import tempfile

import pytest

from am_downloader.models.config import ConfigSet, load_config, limit_string


def test_config_defaults():
    config = ConfigSet()
    assert config.storefront == "us"
    assert config.alac_max == 192000
    assert config.song_file_format == "{SongNumer}. {SongName}"


def test_limit_string():
    assert limit_string("Hello", 10) == "Hello"
    assert len(limit_string("Hello World", 5)) == 5


def test_load_config_from_yaml():
    yaml_content = """
storefront: jp
alac-max: 96000
media-user-token: test-token-12345678901234567890123456789012345678901234567890
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write(yaml_content)
        f.flush()

        try:
            config = load_config(f.name)
            assert config.storefront == "jp"
            assert config.alac_max == 96000
        finally:
            os.unlink(f.name)


def test_load_config_not_found():
    with pytest.raises(FileNotFoundError):
        load_config("/nonexistent/config.yaml")
