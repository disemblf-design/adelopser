"""Artist API"""

from typing import Any

import httpx

from am_downloader.api.client import AppleMusicClient


def get_artist_relationships(
    client: AppleMusicClient,
    storefront: str,
    artist_id: str,
    relationship: str,  # "albums" or "music-videos"
    language: str,
) -> list[dict[str, Any]]:
    """获取艺术家的 albums 或 music-videos 列表（含分页）"""
    all_data: list[dict[str, Any]] = []
    offset = 0

    while True:
        resp = client._client.get(
            f"https://amp-api.music.apple.com/v1/catalog/{storefront}/artists/{artist_id}/{relationship}",
            params={"limit": 100, "offset": offset, "l": language},
            headers={
                "Authorization": f"Bearer {client.token}",
                "User-Agent": client._client.headers.get("User-Agent", ""),
                "Origin": "https://music.apple.com",
            },
        )
        resp.raise_for_status()
        body = resp.json()
        data_list = body.get("data", [])
        all_data.extend(data_list)

        if not body.get("next"):
            break
        offset += 100

    # 按发布日期排序
    all_data.sort(key=lambda x: x.get("attributes", {}).get("releaseDate", ""))
    return all_data


def get_artist_name(
    client: AppleMusicClient,
    storefront: str,
    artist_id: str,
    language: str,
) -> tuple[str, str]:
    """获取艺术家名称和 ID → (name, id)"""
    resp = client._client.get(
        f"https://amp-api.music.apple.com/v1/catalog/{storefront}/artists/{artist_id}",
        params={"l": language},
        headers={
            "Authorization": f"Bearer {client.token}",
            "User-Agent": client._client.headers.get("User-Agent", ""),
            "Origin": "https://music.apple.com",
        },
    )
    resp.raise_for_status()
    obj = resp.json()
    data = obj.get("data", [])
    if data:
        attrs = data[0].get("attributes", {})
        return attrs.get("name", ""), data[0].get("id", "")
    return "", ""
