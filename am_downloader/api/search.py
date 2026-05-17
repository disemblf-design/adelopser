"""Search API"""

from am_downloader.api.client import AppleMusicClient
from am_downloader.models.api_models import SearchResp


def search(
    client: AppleMusicClient,
    storefront: str,
    term: str,
    types: str,  # e.g. "songs,albums,artists"
    limit: int = 15,
    offset: int = 0,
) -> SearchResp:
    """搜索 Apple Music 目录"""
    resp = client.get(
        f"/v1/catalog/{storefront}/search",
        params={
            "term": term,
            "types": types,
            "limit": str(limit),
            "offset": str(offset),
            "l": client.language,
        },
    )
    return SearchResp(**resp.json())
