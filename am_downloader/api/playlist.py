"""Playlist API"""

from am_downloader.api.client import AppleMusicClient
from am_downloader.models.api_models import PlaylistResp, TrackResp


def get_playlist_resp(
    client: AppleMusicClient,
    storefront: str,
    playlist_id: str,
) -> PlaylistResp:
    """获取播放列表完整响应（含所有分页音轨）"""
    resp = client.get(
        f"/v1/catalog/{storefront}/playlists/{playlist_id}",
        params={
            "omit[resource]": "autos",
            "include": "tracks,artists,record-labels",
            "include[songs]": "artists",
            "extend": "editorialVideo,extendedAssetUrls",
            "l": client.language,
        },
    )
    obj = PlaylistResp(**resp.json())

    # 分页
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
