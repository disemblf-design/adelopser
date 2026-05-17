"""PSSH 生成工具"""

import base64


def get_pssh(content_id: str, kid_base64: str) -> str:
    """构建 Widevine PSSH 数据（对应 Go runv3.getPSSH）"""
    kid_bytes = base64.b64decode(kid_base64)
    content_id_encoded = base64.b64encode(content_id.encode()).decode()

    # 构建 WidevineCencHeader (简化版 protobuf 手动编码)
    # field 1: algorithm (enum, AESCTR=1)
    # field 2: key_id (repeated bytes)
    # field 4: provider (string, default "")
    # field 5: content_id (bytes)
    # field 6: policy (string, default "")
    from am_downloader.cdm.cdm import _encode_varint, _encode_uint32, _encode_length_delimited

    header = b""
    header += _encode_uint32(1, 1)  # algorithm = AESCTR
    header += _encode_length_delimited(2, kid_bytes)  # key_id
    header += _encode_length_delimited(4, b"")  # provider
    header += _encode_length_delimited(5, content_id_encoded.encode())  # content_id
    header += _encode_length_delimited(6, b"")  # policy

    # 前面添加 32 字节自定义头（与 Go 版一致）
    pssh_data = b"0123456789abcdef0123456789abcdef" + header
    return base64.b64encode(pssh_data).decode()
