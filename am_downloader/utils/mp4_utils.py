"""MP4 工具 — MP4Box / mp4decrypt / ffmpeg 封装"""

import os
import shutil
import subprocess
from pathlib import Path
from typing import Optional

from am_downloader.models.config import ConfigSet


def find_executable(name: str, config: Optional[ConfigSet] = None) -> Optional[str]:
    """查找可执行文件路径"""
    # ffmpeg 特殊处理
    if name == "ffmpeg" and config and config.ffmpeg_path:
        name = config.ffmpeg_path
    return shutil.which(name)


def mp4box_add_tags(tags: list[str], track_path: str) -> bool:
    """使用 MP4Box 添加标签（fmp4 → mp4 转换 + 标签嵌入）"""
    tags_str = ":".join(tags)
    try:
        subprocess.run(
            ["MP4Box", "-itags", tags_str, track_path],
            check=True,
            capture_output=True,
            timeout=120,
        )
        return True
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        print(f"MP4Box failed: {e}")
        return False


def mp4decrypt_decrypt(
    input_path: str,
    output_path: str,
    key: str,
) -> bool:
    """使用 mp4decrypt 解密 MP4 文件"""
    try:
        subprocess.run(
            ["mp4decrypt", "--key", f"1:{key}", input_path, output_path],
            check=True,
            capture_output=True,
            timeout=300,
        )
        return True
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        print(f"mp4decrypt failed: {e}")
        return False


def ffmpeg_convert(
    input_path: str,
    output_path: str,
    codec: str = "copy",
    extra_args: Optional[list[str]] = None,
) -> bool:
    """使用 ffmpeg 转换/合并视频"""
    args = ["ffmpeg", "-loglevel", "quiet", "-y", "-i", input_path]
    if codec == "copy":
        args.extend(["-c", "copy"])
    else:
        args.extend(["-c:a", codec])
    if extra_args:
        args.extend(extra_args)
    args.append(output_path)

    try:
        subprocess.run(args, check=True, capture_output=True, timeout=300)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        print(f"ffmpeg failed: {e}")
        return False


def ffmpeg_merge_video_audio(
    video_path: str,
    audio_path: str,
    output_path: str,
    config: ConfigSet,
) -> bool:
    """合并视频和音频轨道"""
    args = [
        "ffmpeg", "-loglevel", "quiet", "-y",
        "-i", video_path,
        "-i", audio_path,
        "-c:v", "copy",
        "-c:a", "copy",
        "-map", "0:v:0",
        "-map", "1:a:0",
        output_path,
    ]
    try:
        subprocess.run(args, check=True, capture_output=True, timeout=300)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        print(f"ffmpeg merge failed: {e}")
        return False


def ffmpeg_download_animated_artwork(url: str, output_path: str) -> bool:
    """下载动画封面"""
    args = ["ffmpeg", "-loglevel", "quiet", "-y", "-i", url, "-c", "copy", output_path]
    try:
        subprocess.run(args, check=True, capture_output=True, timeout=120)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        print(f"ffmpeg animated artwork failed: {e}")
        return False


def ffmpeg_artwork_to_gif(input_path: str, output_path: str) -> bool:
    """动画封面转 GIF（Emby 兼容）"""
    args = [
        "ffmpeg", "-i", input_path,
        "-vf", "scale=440:-1", "-r", "24", "-f", "gif",
        output_path,
    ]
    try:
        subprocess.run(args, check=True, capture_output=True, timeout=60)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        print(f"ffmpeg gif failed: {e}")
        return False
