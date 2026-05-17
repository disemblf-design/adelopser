"""Station API"""

import httpx

from am_downloader.api.client import AppleMusicClient, USER_AGENT


def get_station_assets_url_and_server_url(
    client: AppleMusicClient,
    station_id: str,
    media_user_token: str,
) -> tuple[str, str]:
    """获取电台流 assets URL 和 server URL"""
    resp = client._client.post(
        "https://play.music.apple.com/WebObjects/MZPlay.woa/wa/webPlayback",
        json={"salableAdamId": station_id},
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {client.token}",
            "User-Agent": USER_AGENT,
            "Origin": "https://music.apple.com",
            "Referer": "https://music.apple.com/",
            "x-apple-music-user-token": media_user_token,
        },
    )
    resp.raise_for_status()
    data = resp.json()
    song_list = data.get("songList", [])
    if song_list:
        item = song_list[0]
        return item.get("hls-key-cert-url", ""), item.get("hls-playlist-url", "")
    return "", ""
