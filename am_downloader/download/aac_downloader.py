"""AAC-LC 下载引擎 — 对应原 Go runv3/runv3.go

通过 WebPlayback API + Widevine CDM 下载 AAC-LC 音频。
"""

import base64
import os
import re
import struct
from typing import Optional
from urllib.parse import urljoin

import httpx
import m3u8

from am_downloader.cdm.key_manager import get_key
from am_downloader.cdm.pssh import get_pssh
from am_downloader.utils.mp4_utils import mp4decrypt_decrypt

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
)


def _extract_kid_base64(m3u8_url: str) -> tuple[str, str, str]:
    """从 M3U8 URL 提取 kid base64、文件 URL 和 URI 前缀 → (kid_b64, file_url, uri_prefix)"""
    with httpx.Client(timeout=30) as client:
        resp = client.get(m3u8_url, headers={"User-Agent": USER_AGENT})
        resp.raise_for_status()
        body = resp.text

    playlist = m3u8.loads(body)

    if playlist.is_variant:
        # 选择最高码率
        best = max(playlist.playlists, key=lambda p: p.stream_info.bandwidth if p.stream_info else 0)
        if best.uri:
            return _extract_kid_base64(urljoin(m3u8_url, best.uri))

    # 解析 media playlist
    kid_b64 = ""
    uri_prefix = ""
    if playlist.keys and playlist.keys[0]:
        key = playlist.keys[0]
        if key.uri:
            parts = key.uri.split(",")
            uri_prefix = parts[0]
            kid_b64 = parts[1] if len(parts) > 1 else ""

    # 获取 segment URL
    file_url = ""
    if playlist.segments:
        seg = playlist.segments[0]
        if seg.uri:
            file_url = urljoin(m3u8_url, seg.uri)

    return kid_b64, file_url, uri_prefix


def _get_web_playback(
    adam_id: str,
    auth_token: str,
    media_user_token: str,
    mv_mode: bool = False,
) -> tuple[str, str, str]:
    """调用 WebPlayback API 获取 HLS URL"""
    with httpx.Client(timeout=30) as client:
        resp = client.post(
            "https://play.music.apple.com/WebObjects/MZPlay.woa/wa/webPlayback",
            json={"salableAdamId": adam_id},
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {auth_token}",
                "User-Agent": USER_AGENT,
                "Origin": "https://music.apple.com",
                "Referer": "https://music.apple.com/",
                "x-apple-music-user-token": media_user_token,
            },
        )
        resp.raise_for_status()
        data = resp.json()

    song_list = data.get("songList", [])
    if not song_list:
        raise RuntimeError("Unavailable")

    item = song_list[0]

    if mv_mode:
        return item.get("hls-playlist-url", ""), "", ""

    # 查找 flavor "28:ctrp256" (AAC-LC)
    for asset in item.get("assets", []):
        if asset.get("flavor") == "28:ctrp256":
            try:
                kid_b64, file_url, uri_prefix = _extract_kid_base64(asset["URL"])
                return file_url, kid_b64, uri_prefix
            except Exception:
                continue

    raise RuntimeError("Unavailable")


def download_aac_lc(
    adam_id: str,
    output_path: str,
    auth_token: str,
    media_user_token: str,
) -> None:
    """下载 AAC-LC 音频文件

    Args:
        adam_id: Apple Music 内容 ID
        output_path: 输出路径 (.m4a)
        auth_token: Bearer token
        media_user_token: 媒体用户 token
    """
    # Step 1: 获取 WebPlayback URL
    file_url, kid_b64, uri_prefix = _get_web_playback(adam_id, auth_token, media_user_token)

    if not file_url:
        raise RuntimeError("No AAC-LC URL available")

    # Step 2: 获取 PSSH
    pssh = get_pssh(adam_id, kid_b64)

    # Step 3: 获取解密密钥
    license_url = "https://play.music.apple.com/WebObjects/MZPlay.woa/wa/widevineLicense"
    hex_key, key_bytes = get_key(license_url, pssh, adam_id, uri_prefix, auth_token, media_user_token)

    # Step 4: 下载加密的音频文件
    enc_path = output_path + ".enc"
    with httpx.Client(timeout=120) as client:
        resp = client.get(file_url, headers={"User-Agent": USER_AGENT})
        resp.raise_for_status()
        with open(enc_path, "wb") as f:
            f.write(resp.content)

    # Step 5: mp4decrypt 解密
    success = mp4decrypt_decrypt(enc_path, output_path, hex_key)

    # 清理加密文件
    if os.path.exists(enc_path):
        os.remove(enc_path)

    if not success:
        raise RuntimeError("mp4decrypt failed")


def download_radio_stream(
    adam_id: str,
    m3u8_url: str,
    auth_token: str,
    media_user_token: str,
    server_url: str,
) -> tuple[str, str]:
    """下载电台流 → (key_hex, encrypted_file_path)

    电台模式不需要 mp4decrypt，而是返回密钥供外部合并。
    """
    # 获取 m3u8 信息
    with httpx.Client(timeout=30) as client:
        resp = client.get(m3u8_url, headers={"User-Agent": USER_AGENT})
        resp.raise_for_status()
        body = resp.text

    playlist = m3u8.loads(body)
    kid_b64 = ""
    uri_prefix = ""
    file_url = ""

    if playlist.keys and playlist.keys[0] and playlist.keys[0].uri:
        parts = playlist.keys[0].uri.split(",")
        uri_prefix = parts[0]
        kid_b64 = parts[1] if len(parts) > 1 else ""

    if playlist.segments:
        seg = playlist.segments[0]
        if seg.uri:
            file_url = urljoin(m3u8_url, seg.uri)

    # 获取 PSSH 和密钥
    pssh = get_pssh(adam_id, kid_b64)
    hex_key, key_bytes = get_key(server_url, pssh, adam_id, uri_prefix, auth_token, media_user_token)

    # 下载加密数据
    enc_path = file_url.split("/")[-1] + ".enc"
    if not file_url:
        return hex_key, ""

    with httpx.Client(timeout=120) as client:
        resp = client.get(file_url, headers={"User-Agent": USER_AGENT})
        resp.raise_for_status()
        with open(enc_path, "wb") as f:
            f.write(resp.content)

    return hex_key, enc_path


def ext_mv_data(key_hex: str, enc_path: str, output_path: str) -> None:
    """用 mp4decrypt 解密电台流数据并输出"""
    success = mp4decrypt_decrypt(enc_path, output_path, key_hex)
    if os.path.exists(enc_path):
        os.remove(enc_path)
    if not success:
        raise RuntimeError("mp4decrypt failed for radio stream")
