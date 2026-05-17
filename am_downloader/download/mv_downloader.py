"""MV 下载引擎 — 对应原 Go mvDownloader

下载 Music Video：视频 + 音频分离下载 → mp4decrypt 解密 → ffmpeg 合并
"""

import os
import tempfile
from typing import Optional

import httpx

from am_downloader.api.music_video import get_music_video_resp
from am_downloader.api.client import AppleMusicClient
from am_downloader.download.aac_downloader import _get_web_playback
from am_downloader.models.config import ConfigSet
from am_downloader.models.track import Track
from am_downloader.utils.mp4_utils import (
    ffmpeg_merge_video_audio,
    mp4decrypt_decrypt,
)

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
)


def download_mv(
    adam_id: str,
    save_dir: str,
    client: AppleMusicClient,
    storefront: str,
    media_user_token: str,
    track: Optional[Track] = None,
    config: Optional[ConfigSet] = None,
) -> None:
    """下载 Music Video

    Args:
        adam_id: MV ID
        save_dir: 保存目录
        client: API 客户端
        storefront: 商店地区
        media_user_token: 媒体用户 token
        track: 可选 Track 对象（用于命名）
        config: 可选配置
    """
    # Step 1: 获取 MV 元数据
    mv_resp = get_music_video_resp(client, storefront, adam_id)
    if not mv_resp.data:
        raise RuntimeError("No MV data")

    mv_data = mv_resp.data[0]
    mv_name = mv_data.attributes.name

    if track:
        mv_name = f"{track.task_num:02d}. {mv_data.attributes.name}"

    vid_path = os.path.join(save_dir, f"{adam_id}_vid.mp4")
    aud_path = os.path.join(save_dir, f"{adam_id}_aud.mp4")
    out_path = os.path.join(save_dir, f"{mv_name} ({adam_id}).mp4")

    # Step 2: 获取 WebPlayback（MV 模式）
    hls_url, _, _ = _get_web_playback(adam_id, client.token, media_user_token, mv_mode=True)

    if not hls_url:
        raise RuntimeError("No MV HLS URL available")

    # Step 3: 解析 M3U8 并下载视频+音频流
    import m3u8

    with httpx.Client(timeout=30) as http_client:
        resp = http_client.get(hls_url, headers={"User-Agent": USER_AGENT})
        resp.raise_for_status()
        playlist = m3u8.loads(resp.text)

    # 查找视频和音频轨道
    video_uri = None
    audio_uri = None

    if playlist.is_variant:
        for p in playlist.playlists:
            if not p.stream_info:
                continue
            # 有视频分辨率即为视频流，否则为纯音频
            if p.stream_info.resolution and p.stream_info.resolution[0] > 0:
                if not video_uri or (
                    p.stream_info.bandwidth
                    and video_uri[1]
                    and p.stream_info.bandwidth > video_uri[1]
                ):
                    video_uri = (p.uri, p.stream_info.bandwidth)
            else:
                if not audio_uri or (
                    p.stream_info.bandwidth
                    and audio_uri[1]
                    and p.stream_info.bandwidth > audio_uri[1]
                ):
                    audio_uri = (p.uri, p.stream_info.bandwidth)

    # Step 4: 下载并解密视频
    if video_uri:
        _download_stream(video_uri[0], vid_path, adam_id, client.token, media_user_token)
    else:
        # 可能单层 m3u8
        _download_single_stream(hls_url, vid_path, adam_id, client.token, media_user_token)

    # Step 5: 下载并解密音频
    if audio_uri:
        _download_stream(audio_uri[0], aud_path, adam_id, client.token, media_user_token)

    # Step 6: 合并
    if audio_uri and os.path.exists(vid_path) and os.path.exists(aud_path):
        ffmpeg_merge_video_audio(vid_path, aud_path, out_path, config or ConfigSet())
        # 清理临时文件
        if os.path.exists(vid_path):
            os.remove(vid_path)
        if os.path.exists(aud_path):
            os.remove(aud_path)
    elif os.path.exists(vid_path):
        os.rename(vid_path, out_path)


def _download_stream(
    stream_uri: str,
    output_path: str,
    adam_id: str,
    token: str,
    media_user_token: str,
) -> None:
    """下载并解密单个流"""
    from urllib.parse import urljoin

    import m3u8

    with httpx.Client(timeout=30) as client:
        resp = client.get(stream_uri, headers={"User-Agent": USER_AGENT})
        resp.raise_for_status()
        playlist = m3u8.loads(resp.text)

    # 提取 KID 和 PSSH
    kid_b64 = ""
    uri_prefix = ""
    if playlist.keys and playlist.keys[0] and playlist.keys[0].uri:
        parts = playlist.keys[0].uri.split(",")
        uri_prefix = parts[0]
        kid_b64 = parts[1] if len(parts) > 1 else ""

    # 获取完整流 URL
    file_url = stream_uri
    if playlist.segments:
        seg = playlist.segments[0]
        if seg.uri:
            file_url = urljoin(stream_uri, seg.uri)

    # 获取解密密钥
    from am_downloader.cdm.key_manager import get_key
    from am_downloader.cdm.pssh import get_pssh

    pssh = get_pssh(adam_id, kid_b64)
    license_url = "https://play.music.apple.com/WebObjects/MZPlay.woa/wa/widevineLicense"
    hex_key, _ = get_key(license_url, pssh, adam_id, uri_prefix, token, media_user_token)

    # 下载
    enc_path = output_path + ".enc"
    with httpx.Client(timeout=300) as client:
        resp = client.get(file_url, headers={"User-Agent": USER_AGENT})
        resp.raise_for_status()
        with open(enc_path, "wb") as f:
            f.write(resp.content)

    # 解密
    mp4decrypt_decrypt(enc_path, output_path, hex_key)
    if os.path.exists(enc_path):
        os.remove(enc_path)


def _download_single_stream(
    stream_uri: str,
    output_path: str,
    adam_id: str,
    token: str,
    media_user_token: str,
) -> None:
    """下载单层 M3U8 流"""
    _download_stream(stream_uri, output_path, adam_id, token, media_user_token)
