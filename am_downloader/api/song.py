"""Song API"""

from am_downloader.api.client import AppleMusicClient
from am_downloader.models.api_models import SongResp


def get_song_resp(
    client: AppleMusicClient,
    storefront: str,
    song_id: str,
) -> SongResp:
    """获取歌曲响应"""
    resp = client.get(
        f"/v1/catalog/{storefront}/songs/{song_id}",
        params={
            "include": "albums,artists",
            "extend": "extendedAssetUrls",
            "l": client.language,
        },
    )
    return SongResp(**resp.json())
