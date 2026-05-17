"""Token 获取（单独模块，保持与 Go 版 token.go 一致）"""

from am_downloader.api.client import get_token

__all__ = ["get_token"]
