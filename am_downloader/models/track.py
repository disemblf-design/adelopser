"""下载任务数据模型 — 对应原 Go task 包"""

from dataclasses import dataclass, field
from typing import Optional

from am_downloader.models.api_models import AlbumRespData, PlaylistRespData, TrackRespData


@dataclass
class Track:
    """下载音轨任务"""
    id: str = ""
    type: str = ""
    name: str = ""
    storefront: str = ""
    language: str = ""

    save_dir: str = ""
    save_name: str = ""
    save_path: str = ""
    codec: str = ""
    task_num: int = 0
    task_total: int = 0
    m3u8: str = ""
    web_m3u8: str = ""
    device_m3u8: str = ""
    quality: str = ""
    cover_path: str = ""

    resp: Optional[TrackRespData] = None
    pre_type: str = ""       # "albums" | "playlists" | "stations"
    pre_id: str = ""
    disc_total: int = 0
    album_data: Optional[AlbumRespData] = None
    playlist_data: Optional[PlaylistRespData] = None

    def get_album_data(self, client, token: str):
        """获取音轨所属专辑数据（播放列表模式下按需获取）"""
        from am_downloader.api.album import get_album_resp_by_href
        if self.resp is None:
            return
        resp = get_album_resp_by_href(client, self.resp.href)
        if resp.data:
            self.album_data = resp.data[0]
            tracks = resp.data[0].relationships.tracks.data
            if tracks:
                self.disc_total = tracks[-1].attributes.disc_number
