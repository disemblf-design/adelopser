"""文件工具函数"""

import os
from pathlib import Path


def file_exists(path: str) -> bool:
    """检查文件是否存在（不包括目录）"""
    p = Path(path)
    return p.exists() and p.is_file()


def ensure_dir(path: str):
    """确保目录存在"""
    Path(path).mkdir(parents=True, exist_ok=True)


def is_in_array(arr: list[int], target: int) -> bool:
    """检查 target 是否在列表中"""
    return target in arr


def contains(slice_: list[str], item: str) -> bool:
    """检查 item 是否在字符串列表中"""
    return item in slice_
