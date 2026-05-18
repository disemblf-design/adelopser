"""Artist API functions"""
from typing import List, Dict, Any
from am_downloader.api.client import AppleMusicClient

BASE_URL = "https://amp-api.music.apple.com"

def get_artist_name(client: AppleMusicClient, storefront: str, artist_id: str, language: str) -> tuple[str, str]:
    """Get artist name and ID"""
    url = f"{BASE_URL}/v1/catalog/{storefront}/artists/{artist_id}"
    params = {"l": language}
    resp = client.get(url, params=params)
    data = resp.json()
    if "data" in data and len(data["data"]) > 0:
        artist = data["data"][0]
        return artist["attributes"]["name"], artist["id"]
    raise ValueError(f"Artist {artist_id} not found")

def get_artist_relationships(client: AppleMusicClient, storefront: str, artist_id: str, relationship: str, language: str) -> List[Dict[str, Any]]:
    """Get artist relationships (albums, music-videos, etc.) without pagination"""
    url = f"{BASE_URL}/v1/catalog/{storefront}/artists/{artist_id}/{relationship}"
    params = {
        "limit": 100,
        "offset": 0,
        "l": language,
    }
    try:
        resp = client.get(url, params=params)
        data = resp.json()
        if "data" in data:
            return data["data"]
        return []
    except Exception as e:
        # Если 404 или другая ошибка, возвращаем пустой список
        print(f"DEBUG: get_artist_relationships failed for {relationship}: {e}", flush=True)
        return []
