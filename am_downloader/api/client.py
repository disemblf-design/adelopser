"""Apple Music API 通用 HTTP 客户端"""

import re
from typing import Optional

import httpx

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
)

AMP_API_BASE = "https://amp-api.music.apple.com"


def get_token() -> str:
    """自动从 music.apple.com 首页获取 Bearer token"""
    client = httpx.Client(timeout=30, follow_redirects=True)
    try:
        # 1. 请求首页
        resp = client.get("https://music.apple.com", headers={"User-Agent": USER_AGENT})
        resp.raise_for_status()
        body = resp.text

        # 2. 找到 index JS 文件路径
        match = re.search(r"/assets/index~[^/]+\.js", body)
        if not match:
            raise RuntimeError("Cannot find index JS URI on Apple Music page")
        index_js_uri = match.group(0)

        # 3. 请求 index JS 文件
        resp2 = client.get(
            f"https://music.apple.com{index_js_uri}",
            headers={"User-Agent": USER_AGENT},
        )
        resp2.raise_for_status()
        js_body = resp2.text

        # 4. 提取 token（以 eyJh 开头的 JWT）
        match = re.search(r"eyJh([^\"]*)", js_body)
        if not match:
            raise RuntimeError("Cannot find token in JS bundle")
        return match.group(0)
    finally:
        client.close()


class AppleMusicClient:
    """Apple Music API HTTP 客户端"""

    def __init__(self, token: str = "", language: str = "en-US"):
        self._token = token
        self.language = language
        self._client = httpx.Client(
            timeout=60,
            follow_redirects=True,
            headers={
                "User-Agent": USER_AGENT,
                "Origin": "https://music.apple.com",
            },
        )

    @property
    def token(self) -> str:
        if not self._token:
            self._token = get_token()
        return self._token

    @token.setter
    def token(self, value: str):
        self._token = value

    def _build_headers(self, extra: Optional[dict] = None) -> dict:
        headers = {"Authorization": f"Bearer {self.token}"}
        if extra:
            headers.update(extra)
        return headers

    def get(self, path: str, params: Optional[dict] = None, headers: Optional[dict] = None) -> httpx.Response:
        """GET 请求 AMP API"""
        url = f"{AMP_API_BASE}{path}"
        resp = self._client.get(url, params=params, headers=self._build_headers(headers))
        resp.raise_for_status()
        return resp

    def post(self, path: str, json_data: Optional[dict] = None, headers: Optional[dict] = None) -> httpx.Response:
        """POST 请求"""
        url = f"{AMP_API_BASE}{path}" if path.startswith("/") else path
        resp = self._client.post(url, json=json_data, headers=self._build_headers(headers))
        resp.raise_for_status()
        return resp

    def raw_get(self, url: str, headers: Optional[dict] = None) -> httpx.Response:
        """原始 HTTP GET"""
        resp = self._client.get(url, headers=self._build_headers(headers))
        resp.raise_for_status()
        return resp

    def close(self):
        self._client.close()
