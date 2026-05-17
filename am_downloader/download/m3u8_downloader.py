"""M3U8/HLS 流下载引擎 — 对应原 Go runv2/runv2.go

通过外部 wrapper 服务进行 FairPlay 解密，边下载边解密。
"""

import socket
import struct
import time
from typing import Optional
from urllib.parse import urljoin, urlparse

import httpx
import m3u8

from am_downloader.models.config import ConfigSet

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
)


def _connect_decryptor(host: str, port: int, adam_id: str, total_len: int) -> socket.socket:
    """连接 wrapper 解密服务并发送初始化数据"""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(60)
    sock.connect((host, port))

    # 发送 adam_id 长度 + adam_id 字符串
    id_bytes = adam_id.encode()
    sock.sendall(struct.pack(">I", len(id_bytes)) + id_bytes)

    # 发送总文件大小
    sock.sendall(struct.pack(">q", total_len))

    return sock


def _parse_media_playlist(data: str) -> list:
    """解析 HLS media playlist，提取 segment URI 和 byte range"""
    playlist = m3u8.loads(data)
    segments = []

    if playlist.is_variant:
        # 选择最高码率流
        best = max(playlist.playlists, key=lambda p: p.stream_info.bandwidth if p.stream_info else 0)
        return [{"uri": best.uri}]

    for seg in playlist.segments:
        seg_info = {
            "uri": seg.uri,
            "limit": 0,
            "offset": 0,
        }
        if seg.byterange:
            parts = seg.byterange.split("@")
            seg_info["limit"] = int(parts[0])
            seg_info["offset"] = int(parts[1]) if len(parts) > 1 else 0
        segments.append(seg_info)

    return segments


def _extract_media_from_m3u8(m3u8_url: str, extract_quality: bool = False) -> tuple[str, str]:
    """从 M3U8 URL 解析出最佳媒体 URL 和音质信息"""
    with httpx.Client(timeout=30) as client:
        resp = client.get(m3u8_url, headers={"User-Agent": USER_AGENT})
        resp.raise_for_status()
        body = resp.text

    playlist = m3u8.loads(body)

    if playlist.is_variant:
        # 选择最高音质（最大 bandwidth）
        best = max(playlist.playlists, key=lambda p: p.stream_info.bandwidth if p.stream_info else 0)
        quality = f"{best.stream_info.bandwidth // 1000}Kbps" if best.stream_info else ""
        # 构造绝对 URL
        media_url = urljoin(m3u8_url, best.uri) if best.uri else m3u8_url
        return media_url, quality
    else:
        # 单层 playlist
        if playlist.segments and playlist.segments[0].uri:
            media_url = urljoin(m3u8_url, playlist.segments[0].uri)
            return media_url, ""

    return m3u8_url, ""


def run(
    adam_id: str,
    playlist_url: str,
    outfile: str,
    config: ConfigSet,
) -> None:
    """下载并解密 HLS 流（ALAC/Atmos 等格式）

    Args:
        adam_id: Apple Music 内容 ID
        playlist_url: M3U8 播放列表 URL
        outfile: 输出文件路径
        config: 配置
    """
    parsed = urlparse(playlist_url)

    # Step 1: 请求 media playlist
    with httpx.Client(timeout=30) as client:
        resp = client.get(playlist_url, headers={"User-Agent": USER_AGENT})
        resp.raise_for_status()
        segments = _parse_media_playlist(resp.text)

    if not segments:
        raise RuntimeError("No segments extracted from playlist")

    segment = segments[0]
    if segment.get("limit", 0) <= 0 and isinstance(segment.get("uri", ""), str):
        # 非 byte-range playlist，递归解析
        media_url = urljoin(playlist_url, segment["uri"])
        return run(adam_id, media_url, outfile, config)

    # Step 2: 构造实际文件 URL
    file_url = urljoin(playlist_url, segment["uri"])

    # Step 3: 请求 mp4 文件
    with httpx.Client(timeout=120) as client:
        resp = client.get(file_url, headers={"User-Agent": USER_AGENT})
        resp.raise_for_status()
        total_len = int(resp.headers.get("Content-Length", 0))
        body_data = resp.content

    if total_len == 0:
        total_len = len(body_data)

    # Step 4: 连接解密服务
    host, port_str = config.decrypt_m3u8_port.rsplit(":", 1)
    port = int(port_str)

    try:
        sock = _connect_decryptor(host, port, adam_id, total_len)

        # Step 5: 发送数据到解密服务
        chunk_size = 65536  # 64KB
        offset = 0
        with open(outfile, "wb") as f:
            while offset < len(body_data):
                chunk = body_data[offset:offset + chunk_size]
                sock.sendall(struct.pack(">I", len(chunk)) + chunk)
                # 读取解密后的数据
                resp_len = struct.unpack(">I", _recv_exact(sock, 4))[0]
                decrypted = _recv_exact(sock, resp_len)
                f.write(decrypted)
                offset += len(chunk)

        sock.close()
    except Exception as e:
        raise RuntimeError(f"Decryption failed: {e}")


def _recv_exact(sock: socket.socket, n: int) -> bytes:
    """精确接收 n 字节"""
    data = b""
    while len(data) < n:
        chunk = sock.recv(n - len(data))
        if not chunk:
            raise ConnectionError("Connection closed")
        data += chunk
    return data
