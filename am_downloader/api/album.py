"""Album API"""

from typing import Optional

import httpx

from am_downloader.api.client import AppleMusicClient
from am_downloader.models.api_models import AlbumResp, TrackResp


def get_album_resp(
    client: AppleMusicClient,
    storefront: str,
    album_id: str,
) -> AlbumResp:
    """获取专辑完整响应（含所有分页音轨）"""
    resp = client.get(
        f"/v1/catalog/{storefront}/albums/{album_id}",
        params={
            "omit[resource]": "autos",
            "include": "tracks,artists,record-labels",
            "include[songs]": "artists",
            "extend": "editorialVideo,extendedAssetUrls",
            "l": client.language,
        },
    )
    obj = AlbumResp(**resp.json())

    # 分页获取更多音轨
    if obj.data and obj.data[0].relationships.tracks.next:
        next_path = obj.data[0].relationships.tracks.next
        while next_path:
            resp2 = client.get(
                next_path,
                params={
                    "omit[resource]": "autos",
                    "include": "artists",
                    "extend": "editorialVideo,extendedAssetUrls",
                },
            )
            obj2 = TrackResp(**resp2.json())
            obj.data[0].relationships.tracks.data.extend(obj2.data)
            next_path = obj2.next

    return obj


def get_album_resp_by_href(
    client: AppleMusicClient,
    href: str,
) -> AlbumResp:
    """通过 href 获取专辑响应"""
    # 去掉查询参数
    href = href.split("?")[0]
    resp = client.get(f"{href}/albums")
    return AlbumResp(**resp.json())
