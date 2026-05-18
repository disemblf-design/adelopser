"""Artist API"""

from typing import Any

from am_downloader.api.client import AppleMusicClient


def get_artist_relationships(
    client: AppleMusicClient,
    storefront: str,
    artist_id: str,
    relationship: str,  # "albums" or "music-videos"
    language: str,
) -> list[dict[str, Any]]:
    """获取艺术家的 albums 或 music-videos 列表（без пагинации）"""
    url = f"https://amp-api.music.apple.com/v1/catalog/{storefront}/artists/{artist_id}/{relationship}"
    params = {"limit": 100, "offset": 0, "l": language}
    
    # Используем client.get, который уже включает заголовки
    resp = client.get(url, params=params)
    body = resp.json()
    data_list = body.get("data", [])
    
    # Сортируем по дате релиза (опционально)
    data_list.sort(key=lambda x: x.get("attributes", {}).get("releaseDate", ""))
    return data_list


def get_artist_name(
    client: AppleMusicClient,
    storefront: str,
    artist_id: str,
    language: str,
) -> tuple[str, str]:
    """获取艺术家名称和 ID → (name, id)"""
    url = f"https://amp-api.music.apple.com/v1/catalog/{storefront}/artists/{artist_id}"
    params = {"l": language}
    resp = client.get(url, params=params)
    obj = resp.json()
    data = obj.get("data", [])
    if data:
        attrs = data[0].get("attributes", {})
        return attrs.get("name", ""), data[0].get("id", "")
    return "", ""
