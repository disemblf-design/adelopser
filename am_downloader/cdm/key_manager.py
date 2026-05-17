"""Key 管理模块 — 简化版（对应原 Go utils/runv3/key/key.go）"""

import base64
import hashlib

import httpx

from am_downloader.cdm.cdm import new_default_cdm


def get_key(
    license_server_url: str,
    pssh: str,
    adam_id: str,
    uri_prefix: str,
    auth_token: str,
    media_user_token: str,
) -> tuple[str, bytes]:
    """获取 Widevine 解密密钥 → (hex_key, key_bytes)"""
    # 解码 PSSH
    init_data = base64.b64decode(pssh)

    # 创建 CDM 实例
    cdm = new_default_cdm(init_data)

    # 构建 License Request
    license_request = cdm.get_license_request()

    # 构建请求体（对应 Go runv3.BeforeRequest）
    challenge = base64.b64encode(license_request).decode()
    body = {
        "challenge": challenge,
        "key-system": "com.widevine.alpha",
        "uri": f"{uri_prefix},{pssh}",
        "adamId": adam_id,
        "isLibrary": False,
        "user-initiated": True,
    }

    # 发送 License 请求
    with httpx.Client(timeout=30) as client:
        resp = client.post(
            license_server_url,
            json=body,
            headers={
                "Content-Type": "application/json",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Authorization": f"Bearer {auth_token}",
                "x-apple-music-user-token": media_user_token,
                "Origin": "https://music.apple.com",
            },
        )
        resp.raise_for_status()
        resp_data = resp.json()

    if resp_data.get("errorCode", 0) != 0 or resp_data.get("status", 0) != 0:
        raise RuntimeError(
            f"License error: code={resp_data.get('errorCode')}, status={resp_data.get('status')}"
        )

    license_b64 = resp_data.get("license", "")
    license_bytes = base64.b64decode(license_b64)

    # 提取密钥
    keys = cdm.get_license_keys(license_request, license_bytes)

    command = ""
    key_bytes = b""
    for key in keys:
        if key.type == 1:  # CONTENT
            command += key.value.hex()
            key_bytes = key.value

    return command, key_bytes
