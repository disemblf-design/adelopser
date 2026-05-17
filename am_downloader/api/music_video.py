"""Music Video API"""

from am_downloader.api.client import AppleMusicClient
from am_downloader.models.api_models import MVResp


def get_music_video_resp(
    client: AppleMusicClient,
    storefront: str,
    mv_id: str,
) -> MVResp:
    """获取 MV 响应"""
    resp = client.get(
        f"/v1/catalog/{storefront}/music-videos/{mv_id}",
        params={"l": client.language},
    )
    return MVResp(**resp.json())
