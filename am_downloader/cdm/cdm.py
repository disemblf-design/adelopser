"""Widevine CDM — 纯 Python 实现（对应原 Go cdm/*.go）

基于 cryptography 库实现 RSA、AES-CBC、CMAC 签名和 Widevine License 协议。
"""

import base64
import os
import struct
import time
from dataclasses import dataclass, field
from typing import Optional

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend


# ─── Protobuf Wire Types ─────────────────────────────────────────

# 简化版 protobuf 编解码（避免依赖 .proto 编译产物，直接手写 wire 格式）

def _encode_varint(value: int) -> bytes:
    """编码 varint"""
    result = bytearray()
    while value > 0x7F:
        result.append((value & 0x7F) | 0x80)
        value >>= 7
    result.append(value & 0x7F)
    return bytes(result)


def _decode_varint(data: bytes, offset: int) -> tuple[int, int]:
    """解码 varint → (value, new_offset)"""
    result = 0
    shift = 0
    while offset < len(data):
        byte = data[offset]
        result |= (byte & 0x7F) << shift
        offset += 1
        if not (byte & 0x80):
            return result, offset
        shift += 7
    return result, offset


def _encode_length_delimited(field_number: int, data: bytes) -> bytes:
    """编码 protobuf length-delimited 字段"""
    tag = (field_number << 3) | 2  # wire type 2
    return _encode_varint(tag) + _encode_varint(len(data)) + data


def _encode_uint32(field_number: int, value: int) -> bytes:
    """编码 protobuf varint 字段"""
    tag = (field_number << 3) | 0  # wire type 0
    return _encode_varint(tag) + _encode_varint(value)


def _get_field(data: bytes, field_number: int) -> tuple[Optional[bytes], int]:
    """从 protobuf 二进制中提取指定字段的 bytes 值 → (value, new_offset)"""
    offset = 0
    while offset < len(data):
        tag, offset = _decode_varint(data, offset)
        fn = tag >> 3
        wire_type = tag & 0x07
        if wire_type == 0:  # varint
            _, offset = _decode_varint(data, offset)
        elif wire_type == 2:  # length-delimited
            length, offset = _decode_varint(data, offset)
            value = data[offset:offset + length]
            offset += length
            if fn == field_number:
                return value, offset
        else:
            break
    return None, offset


# ─── CMAC (AES-CMAC) ────────────────────────────────────────────

def aes_cmac(key: bytes, message: bytes) -> bytes:
    """AES-128-CMAC 签名"""
    # RFC 4493 实现
    block_size = 16

    # 生成子密钥
    def _shift_left(data: bytes) -> bytes:
        result = bytearray(len(data))
        carry = 0
        for i in range(len(data) - 1, -1, -1):
            tmp = data[i] << 1 | carry
            result[i] = tmp & 0xFF
            carry = (tmp >> 8) & 1
        return bytes(result)

    cipher = Cipher(algorithms.AES(key), modes.ECB(), backend=default_backend())
    encryptor = cipher.encryptor()

    # 生成 K1, K2
    zero_block = b"\x00" * block_size
    L = encryptor.update(zero_block)

    Rb = 0x87
    if L[0] & 0x80:
        K1 = _shift_left(L)
        K1 = bytes([K1[-1] ^ Rb]) if len(K1) > 0 else K1
        K1 = K1[:-1] + bytes([K1[-1] ^ Rb])
    else:
        K1 = _shift_left(L)

    if K1[0] & 0x80:
        K2 = _shift_left(K1)
        K2 = K2[:-1] + bytes([K2[-1] ^ Rb])
    else:
        K2 = _shift_left(K1)

    # 处理消息
    n = (len(message) + block_size - 1) // block_size
    if n == 0:
        n = 1

    last_complete = (len(message) % block_size) == 0 and len(message) > 0

    encryptor = cipher.encryptor()
    X = b"\x00" * block_size

    for i in range(n - 1):
        block = message[i * block_size:(i + 1) * block_size]
        Y = bytes(a ^ b for a, b in zip(X, block))
        X = encryptor.update(Y)

    last_block = message[(n - 1) * block_size:]
    if last_complete:
        Y = bytes(a ^ b for a, b in zip(X, K1))
    else:
        padding_len = block_size - len(last_block)
        last_block = last_block + b"\x80" + b"\x00" * (padding_len - 1)
        Y = bytes(a ^ b for a, b in zip(X, K2))

    Y = bytes(a ^ b for a, b in zip(Y, last_block))
    return encryptor.update(Y)


def sha1(data: bytes) -> bytes:
    """SHA-1 哈希"""
    digest = hashes.Hash(hashes.SHA1(), backend=default_backend())
    digest.update(data)
    return digest.finalize()


# ─── 设备常量 ────────────────────────────────────────────────────

DEFAULT_PRIVATE_KEY = """-----BEGIN RSA PRIVATE KEY-----
MIIEpAIBAAKCAQEA2bO3yvFwNnIHsbDl3MTjKdDsiBWsuZWOGVxInFWAVMp+nffG
YlquTKpJurEry95yprcRB3hYhvA5ghsACidcWPDEPVqqRZ7YXLevyUA+Sn2Jxpvt
OcwyFHbSwruNxprWOkHCT774O4L/wJUt5x2C4iFCrJByjw0omN8u+EHdavvH7ZPn
b3/EZp/cpZa9/+HOkutvBHBvaPp18F8JQhzUQ9MwLuDFTr+QLDB5+Y57Je2tNYDK
xD1K+Ed5Ja0A4OKhPKIwPwPre0nt5scjLba3LSAKtKxiGqFtWO4U7Tf1YrdjJv2o
9o8Sf8qcnbpzvQ4KwFqehuJnB7+W7mdJJw12PQIDAQABAoIBACE32wOMc6LbI3Fp
nKljIYZv6qeZJxHqUBRukGXKZhqKC2fvNsYrMA1irn1eK2CgQL5PkLmjE18DqMLB
e/AQsXagxlDWVMTqx/jdzmTW+KpFHZDAmiIHllypBN/R3oA/gBDDl/KzIQ1zn7Kz
EJ4DUsVObe4G3HQXfepVo8Udx7tbB7X6wHe2kEgFyY3lPdvubik0C4t4ipSD79y7
SfW7XVA5XUQmqN4U2kWM0uSwzd4BA7hqyScJsygf6KgpMWPS2xFZEZQRUpYcBH48
E7YqNrrlYP3yaQ+9Jx56kKS0mvv3vUXS7AfUbU8CiHwD9I3BGwswEUueOGGVeXbx
tFF8s8ECgYEA97BDcL/bt+r3qJF0dxtMB5ZngJbFx9RdsblYepVpblr2UfxnFttO
PoNSKa4W36HuDsun49dkaoABJWdtZs2Hy6q+xvEgozvhMaBVE3spnWnzCT1yTMYL
G02uDEl0dPiTg116bVElaswtqMXvnnpbOTMTe7Ig9sWiUW/GH9RM+N8CgYEA4QHb
+OA0BfczbVQP9B+plt4mAuu4BDm4GPwq1yXOWo3Ct8Ik+HeY1hqOObpfyQMAza+E
e/kP6W8vXpiElGrmiUbTXK4Rzmf+yYeOrvl3D80bFq4GtDNAIQD3jpj6zjlT+Gzw
I501gRx5iPl4fSccRSdpoeri7F9ANtc6EEGFyGMCgYEAjMznWYXHGkL47BtbkIW0
769BQSj0X4dKh8gsEusylugglDSeSbD7RrASGd175T7A/CorU2rTC3OesyubVlBJ
/K4gaykRe5mDh1l0Y3GlE3XyEXObsSb3k1rSMOvkxsWz3X5bJR923MIaxpFWiMlX
aCmvzqZQ9NceUZrvjpJ5+xMCgYAJa8KCESEcftUwZqykVA8Nug9tX+E8jA4hPa2t
hG+3augUOZTCsn87t7Dsydjo2a9W7Vpmtm7sHzOkik5CyJcOeGCxKLimI8SPO5XF
zbwmdTgFIxQ0x1CQETJMTityJwRVCnqjgxmSZlbQXWGmG9UbMCNEHEmUDAjsQuaz
d4racQKBgQDR1Y2kalvleYGrhwcA8LTnIh0rYEfAt9YxNmTi5qDKf5QPvUP2v+WO
fSB5coUqR8LBweHE5V8JgFt74fdLBqZV/k2z/dI0r+EQWmpZ2uPEC0Khk/Sb9iRD
fH7at3PMusrkwZCGZ8beFEAr6icXclV08nPCNGB6WckacfzpAj8Azg==
-----END RSA PRIVATE KEY-----"""

DEFAULT_CLIENT_ID_B64 = (
    "CAESmgsK3QMIAhIQeeRrycR5oAnVvSCrdzFrTxivgsKlBiKOAjCCAQoCggEBANmzt8rxcDZyB7Gw5dzE4ynQ7IgVrLmVjhlcSJxVgFTKfp33xmJarkyqSbqxK8vecqa3EQd4WIbwOYIbAAonXFjwxD1aqkWe2Fy3r8lAPkp9icab7TnMMhR20sK7jcaa1jpBwk+++DuC/8CVLecdguIhQqyQco8NKJjfLvhB3Wr7x+2T529/xGaf3KWWvf/hzpLrbwRwb2j6dfBfCUIc1EPTMC7gxU6/kCwwefmOeyXtrTWAysQ9SvhHeSWtAODioTyiMD8D63tJ7ebHIy22ty0gCrSsYhqhbVjuFO039WK3Yyb9qPaPEn/KnJ26c70OCsBanobiZwe/lu5nSScNdj0CAwEAASjwIkgBUqoBCAEQABqBAQQZhh0LPs5wmuuobaJofVK1k0DjvnNhqvOMfGw0Zlzum4aTAvasMiyWfhjo/+xmHtsRvK3ek9EOdIB1e2c5azFuScAMS2n7ZGzqA8XBb+UPM46FUeGt7o1jDm/AysaZt4U6Ji8wXl41dWA9kF/iIK7uThSmb+mhspLLYo3AUiu2hiIgFm8idU4+UvSfVB4JveJ+hqeNbpYuNWkrxlbj9DDjWgYSgAIemDQcy+RKUwwGq59NhaxYSH3hxSHGCkhcXnjNC0OeV5gBdJQl7uqN90lkF3JxnlvYF3mhux7pZR5jii4KaNG6+vZXEq21irNMnoSxwIlzvpMov7xOvQWVm00K+xDkO20ncTC1ClXpmAAHyDXmMeTrzvCLo7tc3USbaImlIWAX92saZojzJ3n9gc+cjBKGqz2AgcsFCigSZ5vpLtz/wEk5PxIGKJ6OWjEy4D5HZG0p2MYyhM84fUh3TOfuexK1ceWrOfPxCbxSPRi9w0BEaDmixt/K4mIalUFTBJsWxtE6ww38UmFLktWoMM8+QLnhxe6jmuVpuchdLtnMPnkAs6XjGrQFCq4CCAESEGnj6Ji7LD+4o7MoHYT4jBQYjtW+kQUijgIwggEKAoIBAQDY9um1ifBRIOmkPtDZTqH+CZUBbb0eK0Cn3NHFf8MFUDzPEz+emK/OTub/hNxCJCao//pP5L8tRNUPFDrrvCBMo7Rn+iUb+mA/2yXiJ6ivqcN9Cu9i5qOU1ygon9SWZRsujFFB8nxVreY5Lzeq0283zn1Cg1stcX4tOHT7utPzFG/ReDFQt0O/GLlzVwB0d1sn3SKMO4XLjhZdncrtF9jljpg7xjMIlnWJUqxDo7TQkTytJmUl0kcM7bndBLerAdJFGaXc6oSY4eNy/IGDluLCQR3KZEQsy/mLeV1ggQ44MFr7XOM+rd+4/314q/deQbjHqjWFuVr8iIaKbq+R63ShAgMBAAEo8CISgAMii2Mw6z+Qs1bvvxGStie9tpcgoO2uAt5Zvv0CDXvrFlwnSbo+qR71Ru2IlZWVSbN5XYSIDwcwBzHjY8rNr3fgsXtSJty425djNQtF5+J2jrAhf3Q2m7EI5aohZGpD2E0cr+dVj9o8x0uJR2NWR8FVoVQSXZpad3M/4QzBLNto/tz+UKyZwa7Sc/eTQc2+ZcDS3ZEO3lGRsH864Kf/cEGvJRBBqcpJXKfG+ItqEW1AAPptjuggzmZEzRq5xTGf6or+bXrKjCpBS9G1SOyvCNF1k5z6lG8KsXhgQxL6ADHMoulxvUIihyPY5MpimdXfUdEQ5HA2EqNiNVNIO4qP007jW51yAeThOry4J22xs8RdkIClOGAauLIl0lLA4flMzW+VfQl5xYxP0E5tuhn0h+844DslU8ZF7U1dU2QprIApffXD9wgAACk26Rggy8e96z8i86/+YYyZQkc9hIdCAERrgEYCEbByzONrdRDs1MrS/ch1moV5pJv63BIKvQHGvLkaFgoMY29tcGFueV9uYW1lEgZHb29nbGUaIQoKbW9kZWxfbmFtZRITQU9TUCBvbiBJQSBFbXVsYXRvchoYChFhcmNoaXRlY3R1cmVfbmFtZRIDeDg2Gh4KC2RldmljZV9uYW1lEg9nZW5lcmljX3g4Nl9hcm0aIgoMcHJvZHVjdF9uYW1lEhJzZGtfZ3Bob25lX3g4Nl9hcm0aZAoKYnVpbGRfaW5mbxJWZ29vZ2xlL3Nka19ncGhvbmVfeDg2X2FybS9nZW5lcmljX3g4Nl9hcm06OS9QU1IxLjE4MDcyMC4xMjIvNjczNjc0Mjp1c2VyZGVidWcvZGV2LWtleXMaHgoUd2lkZXZpbmVfY2RtX3ZlcnNpb24SBjE0LjAuMBokCh9vZW1fY3J5cHRvX3NlY3VyaXR5X3BhdGNoX2xldmVsEgEwMg4QASAAKA0wQEAASABQAA=="
)


def init_constants():
    """初始化设备常量（与 Go 版一致）"""
    return {
        "private_key": DEFAULT_PRIVATE_KEY,
        "client_id": base64.b64decode(DEFAULT_CLIENT_ID_B64),
    }


# ─── CDM 核心 ────────────────────────────────────────────────────

@dataclass
class Key:
    """解密密钥"""
    id: bytes = b""
    type: int = 0  # License_KeyContainer_KeyType (CONTENT = 1)
    value: bytes = b""


@dataclass
class CDM:
    """Widevine CDM 实例"""
    private_key: rsa.RSAPrivateKey
    client_id: bytes
    session_id: bytes = field(default_factory=lambda: os.urandom(16) + b"01" + b"0" * 14)
    init_data: bytes = b""
    privacy_mode: bool = False

    def __init__(self, private_key_pem: str, client_id: bytes, init_data: bytes):
        # 解析 RSA 私钥
        self.private_key = serialization.load_pem_private_key(
            private_key_pem.encode(), password=None, backend=default_backend()
        )
        self.client_id = client_id

        # init_data 前 32 字节是自定义头，后面是 WidevineCencHeader protobuf
        if len(init_data) < 32:
            raise ValueError("init_data too short (need at least 32 bytes)")
        self.init_data = init_data

        # 生成 session ID（与 Go 版一致：16字节随机 + "01" + 14个'0'）
        import random
        chars = b"ABCDEF0123456789"
        sid = bytearray(32)
        for i in range(16):
            sid[i] = chars[random.randint(0, len(chars) - 1)]
        sid[16] = ord("0")
        sid[17] = ord("1")
        for i in range(18, 32):
            sid[i] = ord("0")
        self.session_id = bytes(sid)

    def get_license_request(self) -> bytes:
        """构建 Widevine License Request protobuf"""
        # SignedLicenseRequest
        #   .type = LICENSE_REQUEST (1)
        #   .msg = LicenseRequest
        #     .type = NEW (1)
        #     .request_time = unix_timestamp
        #     .protocol_version = CURRENT (21)
        #     .key_control_nonce = random uint32
        #     .content_id.cenc_id.pssh = init_data[32:]
        #     .content_id.cenc_id.license_type = DEFAULT (1)
        #     .content_id.cenc_id.request_id = session_id

        pssh_data = self.init_data[32:]
        import random as _random

        nonce = _random.randint(0, 0xFFFFFFFF)
        req_time = int(time.time())

        # 构建 LicenseRequest.ContentIdentification.CENC
        # field 1: pssh (bytes)
        # field 2: license_type (varint, DEFAULT=1)
        # field 3: request_id (bytes)
        cenc_id = b""
        cenc_id += _encode_length_delimited(1, pssh_data)
        cenc_id += _encode_uint32(2, 1)  # license_type = DEFAULT
        cenc_id += _encode_length_delimited(3, self.session_id)

        # ContentIdentification
        # field 1: cenc_id
        content_id = _encode_length_delimited(1, cenc_id)

        # LicenseRequest
        # field 1: type = NEW (1)
        # field 2: request_time
        # field 3: protocol_version = CURRENT (21)
        # field 4: key_control_nonce
        # field 5: content_id
        license_req = b""
        license_req += _encode_uint32(1, 1)  # type = NEW
        license_req += _encode_uint32(2, req_time)
        license_req += _encode_uint32(3, 21)  # protocol_version = CURRENT
        license_req += _encode_uint32(4, nonce)
        license_req += content_id

        # SignedLicenseRequest
        # field 1: type = LICENSE_REQUEST (1)
        # field 2: msg
        signed = b""
        signed += _encode_uint32(1, 1)  # type = LICENSE_REQUEST
        signed += _encode_length_delimited(2, license_req)

        return signed

    def get_license_keys(self, license_request: bytes, license_response: bytes) -> list[Key]:
        """解析 License 响应，提取 CONTENT 密钥"""
        # Step 1: 解析 SignedLicense
        # field 2 = msg (License)
        license_msg, _ = _get_field(license_response, 2)
        if license_msg is None:
            raise ValueError("Cannot find license msg in response")

        # Step 2: 从 License 中提取 key 容器
        # field 1 = id (LicenseIdentification)
        # field 2 = key (repeated License.KeyContainer)
        # 遍历提取 key 字段

        keys: list[Key] = []
        offset = 0
        while offset < len(license_msg):
            tag, offset = _decode_varint(license_msg, offset)
            fn = tag >> 3
            wire_type = tag & 0x07
            if wire_type == 0:
                _, offset = _decode_varint(license_msg, offset)
            elif wire_type == 2:
                length, offset = _decode_varint(license_msg, offset)
                value = license_msg[offset:offset + length]
                offset += length
                if fn == 2:  # key container
                    key = self._parse_key_container(value)
                    if key:
                        keys.append(key)
            else:
                break

        return keys

    def _parse_key_container(self, data: bytes) -> Optional[Key]:
        """解析 License.KeyContainer"""
        key = Key()
        offset = 0
        while offset < len(data):
            tag, offset = _decode_varint(data, offset)
            fn = tag >> 3
            wire_type = tag & 0x07
            if wire_type == 0:
                val, offset = _decode_varint(data, offset)
                if fn == 2:  # type
                    key.type = val
            elif wire_type == 2:
                length, offset = _decode_varint(data, offset)
                value = data[offset:offset + length]
                offset += length
                if fn == 1:  # id
                    key.id = value
                elif fn == 3:  # key (encrypted)
                    # 解密密钥
                    decrypted = self.private_key.decrypt(
                        value,
                        padding.OAEP(
                            mgf=padding.MGF1(algorithm=hashes.SHA1()),
                            algorithm=hashes.SHA1(),
                            label=None,
                        ),
                    )
                    key.value = decrypted
            else:
                break
        return key if key.value else None


def new_default_cdm(init_data: bytes) -> CDM:
    """使用默认设备创建 CDM 实例"""
    constants = init_constants()
    return CDM(constants["private_key"], constants["client_id"], init_data)
