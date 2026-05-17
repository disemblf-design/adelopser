"""Apple Music Downloader — 配置系统（pydantic 模型 + YAML 加载）"""

from pathlib import Path
from typing import Optional

import yaml
from pydantic import BaseModel, Field


class ConfigSet(BaseModel):
    """完整配置集，对应原 Go 的 structs.ConfigSet"""

    storefront: str = "us"
    media_user_token: str = ""
    authorization_token: str = ""
    language: str = ""

    # 歌词
    lrc_type: str = "lyrics"  # lyrics | syllable-lyrics
    lrc_format: str = "lrc"  # lrc | ttml
    embed_lrc: bool = True
    save_lrc_file: bool = False

    # 封面
    save_artist_cover: bool = False
    save_animated_artwork: bool = False
    emby_animated_artwork: bool = False
    embed_cover: bool = True
    cover_size: str = "5000x5000"
    cover_format: str = "jpg"  # jpg | png | original

    # 标签
    tag_sort_order: bool = True
    tag_itunes_id: bool = True

    # 保存路径
    alac_save_folder: str = "AM-DL downloads"
    atmos_save_folder: str = "AM-DL-Atmos downloads"
    aac_save_folder: str = "AM-DL-AAC downloads"
    mv_save_folder: str = "AM-DL-MV downloads"

    # 文件夹 & 文件命名格式
    album_folder_format: str = "{AlbumName}"
    playlist_folder_format: str = "{PlaylistName}"
    artist_folder_format: str = "{UrlArtistName}"
    song_file_format: str = "{SongNumer}. {SongName}"

    # 内容分级标签
    explicit_choice: str = "[E]"
    clean_choice: str = "[C]"
    apple_master_choice: str = "[M]"

    # 内存限制 (MB)
    max_memory_limit: int = 256

    # Wrapper 解密服务端口
    decrypt_m3u8_port: str = "127.0.0.1:10020"
    get_m3u8_port: str = "127.0.0.1:20020"
    get_m3u8_from_device: bool = True
    get_m3u8_mode: str = "hires"  # all | hires

    # 音质
    aac_type: str = "aac-lc"  # aac-lc | aac | aac-binaural | aac-downmix
    alac_max: int = 192000  # 192000 | 96000 | 48000 | 44100
    atmos_max: int = 2768  # 2768 | 2448
    limit_max: int = 200

    # 播放列表
    use_songinfo_for_playlist: bool = False
    dl_albumcover_for_playlist: bool = False

    # MV
    mv_audio_type: str = "atmos"  # atmos | ac3 | aac
    mv_max: int = 2160

    # 转换
    convert_after_download: bool = False
    convert_format: str = "flac"  # flac | mp3 | opus | wav | copy
    convert_keep_original: bool = False
    convert_skip_if_source_matches: bool = True
    ffmpeg_path: str = "ffmpeg"
    convert_extra_args: str = ""
    convert_with_metadata: bool = True
    convert_warn_lossy_to_lossless: bool = True
    convert_skip_lossy_to_lossless: bool = True
    convert_check_bad_alac: bool = False
    convert_delete_bad_alac: bool = False

    # ALAC 修复
    alac_fix: bool = False

    class Config:
        extra = "allow"


def load_config(config_path: str = "config.yaml") -> ConfigSet:
    """从 YAML 加载配置，返回 ConfigSet 实例"""
    path = Path(config_path)
    if not path.exists():
        raise FileNotFoundError(
            f"Config file not found: {config_path}\n"
            f"Please copy config.yaml.example to config.yaml and fill in your tokens."
        )
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    # 将 YAML 中的连字符 key 转换为下划线 key（pydantic 使用下划线）
    data = {k.replace("-", "_"): v for k, v in data.items()}
    config = ConfigSet(**data)
    if len(config.storefront) != 2:
        config.storefront = "us"
    return config


def limit_string(s: str, max_len: int) -> str:
    """截断 UTF-8 字符串到指定字符数"""
    if len(s) > max_len:
        return s[:max_len]
    return s
