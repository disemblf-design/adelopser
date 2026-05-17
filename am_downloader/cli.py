#!/usr/bin/env python3
"""Apple Music Downloader — 主 CLI 入口

用法:
    am-dl [options] <url1 url2 ...>
    am-dl --search [album|song|artist] <query>

选项:
    --atmos              下载 Dolby Atmos
    --aac                下载 AAC
    --select             选择性下载（交互式选择音轨）
    --song               单曲下载模式
    --all-album          下载艺术家全部专辑
    --debug              调试模式（显示音质信息）
    --json               输出 JSON 摘要
    --save-m3u8-playlist 保存 M3U8 播放列表
    --alac-max N         ALAC 最高采样率
    --atmos-max N        Atmos 最高码率
    --aac-type TYPE      AAC 类型
    --mv-audio-type TYPE MV 音频类型
    --mv-max N           MV 最高分辨率
    --search TYPE        搜索模式 [album|song|artist]
"""

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

import click
from rich.console import Console
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeElapsedColumn,
)
from rich.table import Table

from am_downloader.api.album import get_album_resp, get_album_resp_by_href
from am_downloader.api.artist import get_artist_name, get_artist_relationships
from am_downloader.api.client import AppleMusicClient, get_token
from am_downloader.api.music_video import get_music_video_resp
from am_downloader.api.playlist import get_playlist_resp
from am_downloader.api.search import search
from am_downloader.api.song import get_song_resp
from am_downloader.api.station import get_station_assets_url_and_server_url
from am_downloader.alacfix.alacfix import run as alacfix_run
from am_downloader.download.aac_downloader import (
    download_aac_lc,
    download_radio_stream,
    ext_mv_data,
)
from am_downloader.download.m3u8_downloader import run as m3u8_run
from am_downloader.download.m3u8_downloader import _extract_media_from_m3u8
from am_downloader.download.mv_downloader import download_mv
from am_downloader.lyrics.lyrics import get_lyrics
from am_downloader.models.api_models import AddedTrack, Counter
from am_downloader.models.config import ConfigSet, limit_string, load_config
from am_downloader.models.track import Track
from am_downloader.utils.file_utils import contains, file_exists, is_in_array
from am_downloader.utils.mp4_utils import (
    ffmpeg_artwork_to_gif,
    ffmpeg_convert,
    ffmpeg_download_animated_artwork,
    find_executable,
    mp4box_add_tags,
)
from am_downloader.utils.url_utils import (
    check_url,
    check_url_artist,
    check_url_mv,
    check_url_playlist,
    check_url_song,
    check_url_station,
    parse_url,
    sanitize_filename,
)

console = Console()

# ─── 全局状态 ──────────────────────────────────────────────────

config: ConfigSet = ConfigSet()
counter = Counter()
ok_dict: dict[str, list[int]] = {}
added_tracks: list[AddedTrack] = []
_forbidden_re = re.compile(r'[/\\<>:"|?*]')

# CLI 运行时标志（由 main() 函数设置）
_flags: dict[str, bool] = {
    "dl_atmos": False,
    "dl_aac": False,
    "dl_select": False,
    "dl_song": False,
    "artist_select": False,
    "debug_mode": False,
    "print_json": False,
    "save_m3u8_playlist": False,
}


def _sanitize_filename_aggressive(name: str) -> str:
    return _forbidden_re.sub("_", name)


# ─── MP4 标签写入 ─────────────────────────────────────────────

def write_mp4_tags(track: Track, lrc: str = "") -> None:
    """写入 MP4 标签（使用 MP4Box + mutagen）"""
    try:
        from mutagen.mp4 import MP4, MP4Cover
    except ImportError:
        console.print("[red]mutagen not installed, cannot write tags[/red]")
        return

    if not track.save_path or not os.path.exists(track.save_path):
        return

    mp4 = MP4(track.save_path)

    # 基本标签
    mp4["\xa9nam"] = track.resp.attributes.name if track.resp else track.name
    mp4["\xa9ART"] = track.resp.attributes.artist_name if track.resp else ""
    mp4["aART"] = track.resp.attributes.artist_name if track.resp else ""
    mp4["\xa9alb"] = track.resp.attributes.album_name if track.resp else ""

    if track.resp:
        disc_num = track.resp.attributes.disc_number or 1
        track_num = track.resp.attributes.track_number or track.task_num
        mp4["disk"] = [(disc_num, track.disc_total or 1)]
        mp4["trkn"] = [(track_num, track.task_total)]

    if lrc:
        mp4["\xa9lyr"] = lrc

    mp4.save()


# ─── 封面下载 ─────────────────────────────────────────────────

def write_cover(save_dir: str, name: str, cover_url: str) -> Optional[str]:
    """下载封面图片"""
    import httpx

    if not cover_url:
        return None

    fmt = config.cover_format
    if fmt == "original":
        ext = os.path.splitext(cover_url.split("/")[-1])[1].split("?")[0] or ".jpg"
        cov_path = os.path.join(save_dir, f"{name}{ext}")
    else:
        cov_path = os.path.join(save_dir, f"{name}.{fmt}")

    # 替换尺寸
    url = cover_url.replace("{w}x{h}", config.cover_size)

    # PNG 格式特处
    if fmt == "png":
        url = re.sub(r"(\{w\}x\{h\}).*\.jpg", f"\\1.png", url)

    # original 格式
    if fmt == "original":
        url = url.replace("is1-ssl.mzstatic.com/image/thumb", "a5.mzstatic.com/us/r1000/0")
        url = url[: url.rfind("/")]

    try:
        with httpx.Client(timeout=60) as client:
            resp = client.get(url, headers={"User-Agent": "Mozilla/5.0"})
            if resp.status_code != 200 and fmt == "original":
                # 回退
                fallback = cover_url.replace("{w}x{h}", config.cover_size)
                resp = client.get(fallback, headers={"User-Agent": "Mozilla/5.0"})
            resp.raise_for_status()
            with open(cov_path, "wb") as f:
                f.write(resp.content)
        return cov_path
    except Exception as e:
        console.print(f"[yellow]Failed to download cover: {e}[/yellow]")
        return None


# ─── 音轨下载 ─────────────────────────────────────────────────

def rip_track(track: Track, client: AppleMusicClient) -> None:
    """下载单个音轨（核心逻辑）"""
    global counter, ok_dict, added_tracks

    counter.total += 1
    console.print(f"Track {track.task_num} of {track.task_total}: {track.type}")

    # MV 处理
    if track.type == "music-videos":
        if len(config.media_user_token) <= 50:
            console.print("[yellow]media-user-token not set, skip MV[/yellow]")
            counter.success += 1
            return
        if not find_executable("mp4decrypt"):
            console.print("[yellow]mp4decrypt not found, skip MV[/yellow]")
            counter.success += 1
            return
        try:
            download_mv(track.id, track.save_dir, client, track.storefront, config.media_user_token, track, config)
            counter.success += 1
        except Exception as e:
            console.print(f"[red]Failed to download MV: {e}[/red]")
            counter.error += 1
        return

    # 判断是否需要 AAC-LC
    need_aac_lc = False
    if config.aac_type == "aac-lc" and _flag("dl_aac"):
        need_aac_lc = True
    if not track.web_m3u8 and not need_aac_lc:
        if _flag("dl_atmos"):
            console.print("[yellow]Unavailable[/yellow]")
            counter.unavailable += 1
            return
        console.print("[yellow]Unavailable, trying aac-lc[/yellow]")
        need_aac_lc = True

    # M3U8 音质检查
    if not need_aac_lc:
        need_check = False
        if config.get_m3u8_mode == "all":
            need_check = True
        elif config.get_m3u8_mode == "hires" and track.resp and contains(
            track.resp.attributes.audio_traits, "hi-res-lossless"
        ):
            need_check = True

        if need_check:
            # 从设备端口获取更优 M3U8
            try:
                import httpx
                device_url = f"http://{config.get_m3u8_port.replace(':20020', ':20020')}/get_m3u8"
                resp = httpx.get(device_url, params={"adamId": track.id, "type": "song"}, timeout=10)
                if resp.status_code == 200:
                    m3u8_data = resp.json()
                    enhanced = m3u8_data.get("enhancedHls", "")
                    if enhanced.endswith(".m3u8"):
                        track.m3u8 = enhanced
                        track.device_m3u8 = enhanced
            except Exception:
                pass

    # 提取音质
    quality = ""
    if "{Quality}" in config.song_file_format:
        if _flag("dl_atmos"):
            quality = f"{config.atmos_max - 2000}Kbps"
        elif need_aac_lc:
            quality = "256Kbps"
        elif track.m3u8:
            try:
                _, quality = _extract_media_from_m3u8(track.m3u8, True)
            except Exception:
                pass
    track.quality = quality

    # 生成文件名
    tags_parts = []
    if track.resp:
        if track.resp.attributes.is_apple_digital_master and config.apple_master_choice:
            tags_parts.append(config.apple_master_choice)
        if track.resp.attributes.content_rating == "explicit" and config.explicit_choice:
            tags_parts.append(config.explicit_choice)
        if track.resp.attributes.content_rating == "clean" and config.clean_choice:
            tags_parts.append(config.clean_choice)
    tag_str = " ".join(tags_parts)

    replacements = {
        "{SongId}": track.id,
        "{SongNumer}": f"{track.task_num:02d}",
        "{SongName}": limit_string(track.resp.attributes.name if track.resp else track.name, config.limit_max),
        "{DiscNumber}": str(track.resp.attributes.disc_number if track.resp else 1),
        "{TrackNumber}": str(track.resp.attributes.track_number if track.resp else 1),
        "{Quality}": quality,
        "{Tag}": tag_str,
        "{Codec}": track.codec,
    }
    song_name = config.song_file_format
    for k, v in replacements.items():
        song_name = song_name.replace(k, v)

    filename = f"{_sanitize_filename_aggressive(song_name)}.m4a"
    track.save_name = filename
    track_path = os.path.join(track.save_dir, track.save_name)

    # 检查是否已下载
    if file_exists(track_path):
        console.print("[green]Track already exists locally.[/green]")
        counter.success += 1
        ok_dict.setdefault(track.pre_id, []).append(track.task_num)
        _add_to_tracklist(track_path, track)
        return

    # 获取歌词
    lrc = ""
    if config.embed_lrc or config.save_lrc_file:
        try:
            lrc = get_lyrics(
                track.storefront, track.id, config.lrc_type,
                config.language, config.lrc_format,
                client.token, config.media_user_token,
            )
        except Exception as e:
            console.print(f"[yellow]Lyrics: {e}[/yellow]")

    # 下载
    try:
        if need_aac_lc:
            download_aac_lc(track.id, track_path, client.token, config.media_user_token)
        else:
            track_m3u8_url, _ = _extract_media_from_m3u8(track.m3u8, False)
            m3u8_run(track.id, track_m3u8_url, track_path, config)
    except Exception as e:
        console.print(f"[red]Download failed: {e}[/red]")
        counter.error += 1
        return

    # MP4Box 标签
    tags = ["tool=", "artist=AppleMusic"]
    if config.embed_cover and track.cover_path:
        tags.append(f"cover={track.cover_path}")
    mp4box_add_tags(tags, track_path)

    track.save_path = track_path

    # ALAC 修复
    if config.alac_fix:
        try:
            alacfix_run(track.save_path, True)
        except Exception as e:
            console.print(f"[yellow]ALAC fix failed: {e}[/yellow]")

    # 写入 MP4 标签
    write_mp4_tags(track, lrc)

    # 格式转换
    if config.convert_after_download:
        _convert_track(track)

    counter.success += 1
    ok_dict.setdefault(track.pre_id, []).append(track.task_num)
    _add_to_tracklist(track.save_path, track)


def _add_to_tracklist(path: str, track: Track) -> None:
    artist_id = ""
    if track.resp and track.resp.relationships.artists.data:
        artist_id = track.resp.relationships.artists.data[0].id
    added_tracks.append(AddedTrack(
        path=path,
        artist=track.resp.attributes.artist_name if track.resp else "",
        artistID=artist_id,
        album=track.resp.attributes.album_name if track.resp else "",
        song=track.resp.attributes.name if track.resp else track.name,
    ))


def _convert_track(track: Track) -> None:
    """下载后格式转换"""
    if not config.convert_format or config.convert_format == "copy":
        return

    src_path = track.save_path
    ext = os.path.splitext(src_path)[1].lower()
    target_fmt = config.convert_format.lower()

    if config.convert_skip_if_source_matches and ext == f".{target_fmt}":
        return

    out_path = src_path[: -len(ext)] + f".{target_fmt}"

    if not find_executable("ffmpeg", config):
        console.print("[yellow]ffmpeg not found, skip conversion[/yellow]")
        return

    console.print(f"Converting -> {target_fmt} ...")
    success = ffmpeg_convert(src_path, out_path, target_fmt)
    if success:
        if not config.convert_keep_original:
            os.remove(src_path)
        track.save_path = out_path
        track.save_name = os.path.basename(out_path)


# ─── 专辑/播放列表/电台下载 ───────────────────────────────────

def _flag(name: str) -> bool:
    """获取运行时标志"""
    return _flags.get(name, False)


def _set_flags(**kwargs):
    """批量设置运行时标志"""
    _flags.update(kwargs)


def rip_album(album_id: str, client: AppleMusicClient, storefront: str) -> None:
    """下载专辑"""
    global config, counter, ok_dict

    album_resp = get_album_resp(client, storefront, album_id)
    if not album_resp.data:
        raise RuntimeError("Empty album response")

    meta = album_resp.data[0]
    codec = "ATMOS" if _flag("dl_atmos") else ("AAC" if _flag("dl_aac") else "ALAC")

    # 艺术家目录
    artist_name = meta.attributes.artist_name
    artist_id = meta.relationships.artists.data[0].id if meta.relationships.artists.data else ""
    singer_folder = _build_singer_folder(artist_name, artist_id, codec)
    album_folder_name = _build_album_folder_name(meta, album_id, codec, client, storefront)
    album_folder = os.path.join(singer_folder, _sanitize_filename_aggressive(album_folder_name))
    os.makedirs(album_folder, exist_ok=True)

    # 封面
    cov_path = write_cover(album_folder, "cover", meta.attributes.artwork.url)

    # 音轨
    tracks_data = meta.relationships.tracks.data
    for i, td in enumerate(tracks_data):
        track = Track(
            id=td.id,
            type=td.type,
            name=td.attributes.name,
            storefront=storefront,
            language=config.language,
            save_dir=album_folder,
            codec=codec,
            task_num=i + 1,
            task_total=len(tracks_data),
            m3u8=td.attributes.extended_asset_urls.enhanced_hls,
            web_m3u8=td.attributes.extended_asset_urls.enhanced_hls,
            cover_path=cov_path or "",
            resp=td,
            pre_type="albums",
            pre_id=album_id,
            disc_total=tracks_data[-1].attributes.disc_number if tracks_data else 1,
        )
        rip_track(track, client)


def rip_playlist(playlist_id: str, client: AppleMusicClient, storefront: str) -> None:
    """下载播放列表"""
    global config

    playlist_resp = get_playlist_resp(client, storefront, playlist_id)
    if not playlist_resp.data:
        raise RuntimeError("Empty playlist response")

    meta = playlist_resp.data[0]
    codec = "ATMOS" if _flag("dl_atmos") else ("AAC" if _flag("dl_aac") else "ALAC")

    singer_folder = _build_singer_folder("Apple Music", "", codec)
    playlist_folder_name = _build_playlist_folder_name(meta, playlist_id, codec, client, storefront)
    playlist_folder = os.path.join(singer_folder, _sanitize_filename_aggressive(playlist_folder_name))
    os.makedirs(playlist_folder, exist_ok=True)

    cov_path = write_cover(playlist_folder, "cover", meta.attributes.artwork.url)

    tracks_data = meta.relationships.tracks.data
    for i, td in enumerate(tracks_data):
        track = Track(
            id=td.id,
            type=td.type,
            name=td.attributes.name,
            storefront=storefront,
            language=config.language,
            save_dir=playlist_folder,
            codec=codec,
            task_num=i + 1,
            task_total=len(tracks_data),
            m3u8=td.attributes.extended_asset_urls.enhanced_hls,
            web_m3u8=td.attributes.extended_asset_urls.enhanced_hls,
            cover_path=cov_path or "",
            resp=td,
            pre_type="playlists",
            pre_id=playlist_id,
            playlist_data=meta,
        )
        rip_track(track, client)


def rip_station(station_id: str, client: AppleMusicClient, storefront: str) -> None:
    """下载电台"""
    global config, counter, ok_dict

    from am_downloader.api.station import get_station_assets_url_and_server_url

    assets_url, server_url = get_station_assets_url_and_server_url(client, station_id, config.media_user_token)
    if not assets_url:
        raise RuntimeError("Failed to get station assets")

    track_m3u8 = assets_url.replace("index.m3u8", "256/prog_index.m3u8")
    hex_key, enc_path = download_radio_stream(
        station_id, track_m3u8, client.token, config.media_user_token, server_url
    )

    singer_folder = _build_singer_folder("Apple Music Station", "", "AAC")
    station_folder_name = limit_string("Radio Station", config.limit_max)
    station_folder = os.path.join(singer_folder, _sanitize_filename_aggressive(station_folder_name))
    os.makedirs(station_folder, exist_ok=True)

    out_path = os.path.join(station_folder, f"{station_id}.m4a")
    ext_mv_data(hex_key, enc_path, out_path)

    counter.success += 1
    ok_dict.setdefault(station_id, []).append(1)


# ─── 路径构建辅助 ─────────────────────────────────────────────

def _build_singer_folder(artist_name: str, artist_id: str, codec: str) -> str:
    fmt = config.artist_folder_format or ""
    if not fmt:
        base = config.alac_save_folder
        if _flag("dl_atmos"):
            base = config.atmos_save_folder
        elif _flag("dl_aac"):
            base = config.aac_save_folder
        return base

    fmt = fmt.replace("{ArtistName}", limit_string(artist_name, config.limit_max))
    fmt = fmt.replace("{ArtistId}", artist_id)
    fmt = fmt.replace("{UrlArtistName}", limit_string(artist_name, config.limit_max))
    fmt = fmt.rstrip(".")

    base = config.alac_save_folder
    if _flag("dl_atmos"):
        base = config.atmos_save_folder
    elif _flag("dl_aac"):
        base = config.aac_save_folder

    return os.path.join(base, sanitize_filename(fmt.strip()))


def _build_album_folder_name(meta, album_id: str, codec: str, client, storefront: str) -> str:
    quality = _get_quality(meta, codec, client, storefront, album_id)
    tags = _get_content_tags(meta)
    replacements = {
        "{ReleaseDate}": meta.attributes.release_date,
        "{ReleaseYear}": meta.attributes.release_date[:4] if meta.attributes.release_date else "",
        "{ArtistName}": limit_string(meta.attributes.artist_name, config.limit_max),
        "{AlbumName}": limit_string(meta.attributes.name, config.limit_max),
        "{UPC}": meta.attributes.upc,
        "{RecordLabel}": meta.attributes.record_label,
        "{Copyright}": meta.attributes.copyright,
        "{AlbumId}": album_id,
        "{Quality}": quality,
        "{Codec}": codec,
        "{Tag}": tags,
    }
    result = config.album_folder_format
    for k, v in replacements.items():
        result = result.replace(k, v)
    return result.rstrip(".").strip()


def _build_playlist_folder_name(meta, playlist_id: str, codec: str, client, storefront: str) -> str:
    quality = _get_quality(meta, codec, client, storefront, playlist_id)
    tags = _get_content_tags(meta)
    replacements = {
        "{ArtistName}": "Apple Music",
        "{PlaylistName}": limit_string(meta.attributes.name, config.limit_max),
        "{PlaylistId}": playlist_id,
        "{Quality}": quality,
        "{Codec}": codec,
        "{Tag}": tags,
    }
    result = config.playlist_folder_format
    for k, v in replacements.items():
        result = result.replace(k, v)
    return result.rstrip(".").strip()


def _get_quality(meta, codec: str, client, storefront: str, item_id: str) -> str:
    if "{Quality}" not in config.album_folder_format and "{Quality}" not in config.playlist_folder_format:
        return ""
    if codec == "ATMOS":
        return f"{config.atmos_max - 2000}Kbps"
    if codec == "AAC" and config.aac_type == "aac-lc":
        return "256Kbps"
    # 尝试从第一个音轨的 M3U8 提取
    tracks = meta.relationships.tracks.data
    if tracks:
        m3u8_url = tracks[0].attributes.extended_asset_urls.enhanced_hls
        if m3u8_url:
            try:
                _, q = _extract_media_from_m3u8(m3u8_url, True)
                return q
            except Exception:
                pass
    return ""


def _get_content_tags(meta) -> str:
    parts = []
    if (getattr(meta.attributes, 'is_apple_digital_master', False) or
            getattr(meta.attributes, 'is_mastered_for_itunes', False)):
        if config.apple_master_choice:
            parts.append(config.apple_master_choice)
    cr = getattr(meta.attributes, 'content_rating', '')
    if cr == "explicit" and config.explicit_choice:
        parts.append(config.explicit_choice)
    if cr == "clean" and config.clean_choice:
        parts.append(config.clean_choice)
    return " ".join(parts)


# ─── CLI 入口 ──────────────────────────────────────────────────

@click.command()
@click.option("--atmos", is_flag=True, help="Download Dolby Atmos")
@click.option("--aac", is_flag=True, help="Download AAC")
@click.option("--select", is_flag=True, help="Interactive track selection")
@click.option("--song", is_flag=True, help="Single song download mode")
@click.option("--all-album", is_flag=True, help="Download all artist albums")
@click.option("--debug", is_flag=True, help="Debug mode (show quality info)")
@click.option("--json", "json_output", is_flag=True, help="Output JSON summary")
@click.option("--save-m3u8-playlist", is_flag=True, help="Save M3U8 playlist file")
@click.option("--alac-max", type=int, help="ALAC max sample rate")
@click.option("--atmos-max", type=int, help="Atmos max bitrate")
@click.option("--aac-type", type=str, help="AAC type")
@click.option("--mv-audio-type", type=str, help="MV audio type")
@click.option("--mv-max", type=int, help="MV max resolution")
@click.option(
    "--search", "search_type",
    type=click.Choice(["album", "song", "artist"]),
    help="Interactive search mode",
)
@click.argument("urls", nargs=-1)
def main(
    atmos: bool,
    aac: bool,
    select: bool,
    song: bool,
    all_album: bool,
    debug: bool,
    json_output: bool,
    save_m3u8_playlist: bool,
    alac_max: Optional[int],
    atmos_max: Optional[int],
    aac_type: Optional[str],
    mv_audio_type: Optional[str],
    mv_max: Optional[int],
    search_type: Optional[str],
    urls: tuple[str, ...],
):
    """Apple Music ALAC / Dolby Atmos / AAC Downloader"""
    global config, counter, ok_dict, added_tracks

    # 设置运行时标志
    _set_flags(
        dl_atmos=atmos,
        dl_aac=aac,
        dl_select=select,
        dl_song=song,
        artist_select=all_album,
        debug_mode=debug,
        print_json=json_output,
        save_m3u8_playlist=save_m3u8_playlist,
    )

    # 加载配置
    try:
        config = load_config()
    except FileNotFoundError as e:
        console.print(f"[red]{e}[/red]")
        sys.exit(1)

    # 覆盖配置
    if alac_max is not None:
        config.alac_max = alac_max
    if atmos_max is not None:
        config.atmos_max = atmos_max
    if aac_type is not None:
        config.aac_type = aac_type
    if mv_audio_type is not None:
        config.mv_audio_type = mv_audio_type
    if mv_max is not None:
        config.mv_max = mv_max

    # 获取 token
    client = AppleMusicClient(
        config.authorization_token or config.authorization_token.replace("Bearer ", ""),
        config.language,
    )
    try:
        token = get_token()
        client.token = token
    except Exception:
        if config.authorization_token and config.authorization_token != "your-authorization-token":
            client.token = config.authorization_token.replace("Bearer ", "")
        else:
            console.print("[red]Failed to get token[/red]")
            sys.exit(1)

    # 搜索模式
    if search_type:
        if not urls:
            console.print("[red]--search requires a query argument[/red]")
            return
        query = " ".join(urls)
        _interactive_search(search_type, query, client)
        return

    # URL 模式
    if not urls:
        console.print("[yellow]No URLs provided[/yellow]")
        return

    urls_list = list(urls)

    # 艺术家模式
    for i, url in enumerate(urls_list):
        if "/artist/" in url:
            try:
                artist_name, artist_id = get_artist_name(client, *check_url_artist(url), config.language)
                config.artist_folder_format = config.artist_folder_format.replace(
                    "{UrlArtistName}", limit_string(artist_name, config.limit_max)
                ).replace("{ArtistId}", artist_id)

                album_urls = _get_artist_items(client, url, "albums")
                mv_urls = _get_artist_items(client, url, "music-videos")
                urls_list[i:i + 1] = album_urls + mv_urls
            except Exception as e:
                console.print(f"[red]Failed to get artist data: {e}[/red]")
                return

    # 主下载循环
    total = len(urls_list)
    while True:
        for i, url in enumerate(urls_list):
            console.print(f"Queue {i + 1} of {total}: ", end="")

            parsed = parse_url(url)
            if not parsed:
                console.print(f"[red]Invalid URL: {url}[/red]")
                continue

            if parsed.url_type == "music-video":
                console.print("Music Video")
                if debug:
                    continue
                counter.total += 1
                if len(config.media_user_token) <= 50:
                    console.print("[yellow]media-user-token not set, skip MV[/yellow]")
                    counter.success += 1
                    continue
                if not find_executable("mp4decrypt"):
                    console.print("[yellow]mp4decrypt not found, skip MV[/yellow]")
                    counter.success += 1
                    continue
                try:
                    storefront, mv_id = check_url_mv(url)
                    download_mv(mv_id, config.mv_save_folder, client, storefront, config.media_user_token, config=config)
                    counter.success += 1
                except Exception as e:
                    console.print(f"[red]MV download failed: {e}[/red]")
                    counter.error += 1
                continue

            if parsed.url_type == "song":
                console.print("Song")
                storefront, song_id = check_url_song(url)
                try:
                    _rip_single_song(song_id, client, storefront)
                except Exception as e:
                    console.print(f"[red]Song download failed: {e}[/red]")
                continue

            if parsed.url_type == "album":
                console.print("Album")
                storefront, album_id = check_url(url)
                if storefront and album_id:
                    try:
                        rip_album(album_id, client, storefront)
                    except Exception as e:
                        console.print(f"[red]Album download failed: {e}[/red]")

            elif parsed.url_type == "playlist":
                console.print("Playlist")
                storefront, playlist_id = check_url_playlist(url)
                if storefront and playlist_id:
                    try:
                        rip_playlist(playlist_id, client, storefront)
                    except Exception as e:
                        console.print(f"[red]Playlist download failed: {e}[/red]")

            elif parsed.url_type == "station":
                console.print("Station")
                if len(config.media_user_token) <= 50:
                    console.print("[yellow]media-user-token not set, skip station[/yellow]")
                    continue
                storefront, station_id = check_url_station(url)
                if storefront and station_id:
                    try:
                        rip_station(station_id, client, storefront)
                    except Exception as e:
                        console.print(f"[red]Station download failed: {e}[/red]")

        # 统计
        console.print(
            f"=======  [green]✓[/green] Completed: {counter.success}/{counter.total}  |  "
            f"[yellow]⚠[/yellow] Warnings: {counter.unavailable + counter.not_song}  |  "
            f"[red]✗[/red] Errors: {counter.error}  ======="
        )

        if counter.error == 0:
            break

        input("Error detected, press Enter to retry...")
        console.print("Retrying...")
        counter = Counter()

    # JSON 输出
    if json_output:
        console.print_json(data=[t.model_dump(by_alias=True) for t in added_tracks])


def _rip_single_song(song_id: str, client: AppleMusicClient, storefront: str) -> None:
    """下载单曲（--song 模式）"""
    song_resp = get_song_resp(client, storefront, song_id)
    if not song_resp.data:
        raise RuntimeError("No song data")

    sd = song_resp.data[0]
    album_id = sd.relationships.albums.data[0].id if sd.relationships.albums.data else ""

    codec = "ATMOS" if _flag("dl_atmos") else ("AAC" if _flag("dl_aac") else "ALAC")
    save_dir = os.path.join(config.alac_save_folder, "Singles")
    os.makedirs(save_dir, exist_ok=True)

    track = Track(
        id=sd.id,
        type="songs",
        name=sd.attributes.name,
        storefront=storefront,
        language=config.language,
        save_dir=save_dir,
        codec=codec,
        task_num=1,
        task_total=1,
        m3u8=sd.attributes.extended_asset_urls.enhanced_hls,
        web_m3u8=sd.attributes.extended_asset_urls.enhanced_hls,
        resp=sd,
        pre_type="albums",
        pre_id=album_id,
    )
    rip_track(track, client)


def _get_artist_items(client: AppleMusicClient, artist_url: str, rel_type: str) -> list[str]:
    """获取艺术家的专辑/MV URL 列表"""
    storefront, artist_id = check_url_artist(artist_url)
    items = get_artist_relationships(client, storefront, artist_id, rel_type, config.language)
    return [item.get("attributes", {}).get("url", "") for item in items if item.get("attributes", {}).get("url")]


def _interactive_search(search_type: str, query: str, client: AppleMusicClient) -> None:
    """交互式搜索"""
    import questionary

    console.print(f"Searching {search_type}s for: [bold]{query}[/bold]")

    offset = 0
    limit = 15

    while True:
        try:
            resp = search(client, config.storefront, query, f"{search_type}s", limit, offset)
        except Exception as e:
            console.print(f"[red]Search failed: {e}[/red]")
            return

        items: list[tuple[str, str, str, str]] = []  # (display, type, url, id)

        if search_type == "album" and resp.results.albums:
            for item in resp.results.albums.data:
                year = item.attributes.release_date[:4] if item.attributes.release_date else ""
                detail = f"{item.attributes.artist_name} ({year}, {item.attributes.track_count} tracks)"
                items.append((f"{item.attributes.name} - {detail}", "Album", item.attributes.url, item.id))
            has_next = bool(resp.results.albums.next)
        elif search_type == "song" and resp.results.songs:
            for item in resp.results.songs.data:
                detail = f"{item.attributes.artist_name} ({item.attributes.album_name})"
                items.append((f"{item.attributes.name} - {detail}", "Song", item.attributes.url, item.id))
            has_next = bool(resp.results.songs.next)
        elif search_type == "artist" and resp.results.artists:
            for item in resp.results.artists.data:
                genres = ", ".join(item.attributes.get("genreNames", []))
                items.append((f"{item.attributes.get('name', '')} ({genres})", "Artist", item.attributes.get("url", ""), item.id))
            has_next = bool(resp.results.artists.next)
        else:
            console.print("[yellow]No results found[/yellow]")
            return

        if not items:
            console.print("[yellow]No results found[/yellow]")
            return

        options = []
        if offset > 0:
            options.append("⬅️  Previous Page")
        options.extend([item[0] for item in items])
        if has_next:
            options.append("➡️  Next Page")

        choice = questionary.select(
            "Use arrow keys to navigate, Enter to select:",
            choices=options,
        ).ask()

        if choice is None:
            return

        if choice == "➡️  Next Page":
            offset += limit
            continue
        if choice == "⬅️  Previous Page":
            offset -= limit
            continue

        idx = options.index(choice)
        if offset > 0:
            idx -= 1

        selected = items[idx]
        console.print(f"Selected: {selected[2]}")

        # 音质选择
        quality = questionary.select(
            "Select quality:",
            choices=["Lossless (ALAC)", "High-Quality (AAC)", "Dolby Atmos"],
        ).ask()

        if quality is None:
            return

        # 设置标志并下载
        # 这里简化：直接用 URL 下载
        import sys
        # 模拟 URL 下载流程
        _process_url(selected[2], client)


def _process_url(url: str, client: AppleMusicClient) -> None:
    """处理单个 URL（搜索后使用）"""
    parsed = parse_url(url)
    if not parsed:
        console.print(f"[red]Invalid URL: {url}[/red]")
        return

    if parsed.url_type == "album":
        console.print(f"Album: {parsed.item_id}")
        rip_album(parsed.item_id, client, parsed.storefront)
    elif parsed.url_type == "playlist":
        console.print(f"Playlist: {parsed.item_id}")
        rip_playlist(parsed.item_id, client, parsed.storefront)
    elif parsed.url_type == "song":
        console.print(f"Song: {parsed.item_id}")
        _rip_single_song(parsed.item_id, client, parsed.storefront)


if __name__ == "__main__":
    main()
