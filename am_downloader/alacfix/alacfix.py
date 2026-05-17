"""ALAC 修复模块 — 对应原 Go alacfix/alacfix.go

补丁修复损坏的 ALAC 包（TYPE_END 终止符缺失问题）
"""

import os
import struct
from pathlib import Path


class BitReader:
    """ALAC 位流读取器"""

    def __init__(self, buf: bytes):
        self.buf = buf
        self.pos = 0
        self.nbits = len(buf) * 8

    def left(self) -> int:
        return self.nbits - self.pos

    def read(self, n: int) -> int:
        if n == 0:
            return 0
        if self.pos + n > self.nbits:
            raise EOFError("bit reader EOF")
        v = 0
        p = self.pos
        for _ in range(n):
            v = (v << 1) | ((self.buf[p >> 3] >> (7 - (p & 7))) & 1)
            p += 1
        self.pos = p
        return v

    def show(self, n: int) -> int:
        save = self.pos
        v = self.read(n)
        self.pos = save
        return v

    def skip(self, n: int) -> None:
        if self.pos + n > self.nbits:
            raise EOFError("bit reader EOF")
        self.pos += n

    def read_signed(self, n: int) -> int:
        v = self.read(n)
        if v & (1 << (n - 1)):
            return v - (1 << n)
        return v

    def unary_09(self) -> int:
        cnt = 0
        while cnt < 9:
            v = self.read(1)
            if v == 0:
                return cnt
            cnt += 1
        return 9


def run(file_path: str, in_place: bool = True) -> None:
    """修复 ALAC 文件的损坏包

    Args:
        file_path: M4A/MP4 文件路径
        in_place: 是否就地修改（默认 True）
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")

    with open(file_path, "rb") as f:
        data = bytearray(f.read())

    _patch_alac_packets(data)

    if in_place:
        with open(file_path, "wb") as f:
            f.write(data)


def _patch_alac_packets(data: bytearray) -> None:
    """遍历 ISO BMFF 容器，找到 ALAC 音频轨道并修复"""
    offset = 0
    while offset < len(data) - 8:
        # 读取 box size 和 type
        if offset + 8 > len(data):
            break
        size = struct.unpack(">I", data[offset:offset + 4])[0]
        box_type = data[offset + 4:offset + 8].decode("ascii", errors="ignore")

        if size < 8 or offset + size > len(data):
            break

        if box_type == "moov":
            _process_moov(data, offset + 8, offset + size)
            break  # 只处理第一个 moov
        elif box_type in ("ftyp", "free", "mdat", "wide"):
            offset += size
        else:
            offset += 1


def _process_moov(data: bytearray, start: int, end: int) -> None:
    """处理 moov box，查找 stsd 中的 ALAC 编解码器"""
    pos = start
    while pos < end - 8:
        size = struct.unpack(">I", data[pos:pos + 4])[0]
        box_type = data[pos + 4:pos + 8].decode("ascii", errors="ignore")

        if size < 8:
            break

        if box_type == "stsd":
            _process_stsd(data, pos + 8, pos + size)
        elif box_type in ("trak", "mdia", "minf", "stbl"):
            _process_moov(data, pos + 8, pos + size)

        pos += size


def _process_stsd(data: bytearray, start: int, end: int) -> None:
    """处理 stsd box，检查 sample entry 中的编解码器"""
    if end - start < 16:
        return

    # 跳过 version + flags + entry count
    pos = start + 8
    while pos < end - 8:
        size = struct.unpack(">I", data[pos:pos + 4])[0]
        if size < 8 or pos + size > end:
            break

        # sample entry format (4 bytes at offset 4..8)
        if pos + 12 <= len(data):
            fmt = data[pos + 4:pos + 8].decode("ascii", errors="ignore")
            if fmt == "alac":
                _patch_alac_samples(data)

        pos += size


def _patch_alac_samples(data: bytearray) -> None:
    """查找并修复 mdat 中的 ALAC 采样"""
    # 在 mdat box 中搜索 ALAC 包并进行修复
    # 简化实现：遍历 mdat 区域
    offset = 0
    while offset < len(data) - 12:
        # 查找 mdat
        if offset + 8 > len(data):
            break
        size = struct.unpack(">I", data[offset:offset + 4])[0]
        box_type = data[offset + 4:offset + 8].decode("ascii", errors="ignore")

        if box_type == "mdat" and size >= 8:
            mdat_start = offset + 8
            mdat_end = min(offset + size, len(data))
            _patch_in_range(data, mdat_start, mdat_end)
            break

        offset += max(size, 1)


def _patch_in_range(data: bytearray, start: int, end: int) -> None:
    """在指定范围内搜索并修复 ALAC 包"""
    pos = start
    packet_size = 0

    while pos < end:
        # 尝试读取 ALAC 包
        if pos + 4 > end:
            break

        # 简单的 ALAC 帧头检测（改进版）
        header = struct.unpack(">I", data[pos:pos + 4])[0]
        # 检测可能的 ALAC 帧魔数
        if (header & 0xFFFF0000) == 0xFFF00000:
            # 读取完整的 ALAC 帧头
            try:
                _fix_alac_packet(data, pos, end)
            except (EOFError, IndexError):
                pass

        pos += 1


def _fix_alac_packet(data: bytearray, frame_start: int, max_end: int) -> None:
    """修复单个 ALAC 包（添加 TYPE_END 终止符）"""
    buf = bytes(data[frame_start:min(frame_start + 4096, max_end)])

    try:
        br = BitReader(buf)

        # 跳过 ALAC 魔数头
        for _ in range(32):
            br.read(1)

        # 解析 ALAC 元素，直到 TYPE_END 或流结束
        while br.left() > 3:
            tag = br.read(3)
            if tag == 7:  # TYPE_END
                return  # 已有正确终止符，无需修复

            if tag == 0:  # SCE
                _parse_sce(br)
            elif tag == 1:  # CPE
                _parse_sce(br)
                _parse_sce(br)
            elif tag == 2:  # CCE
                _parse_sce(br)
                if br.left() > 3:
                    br.skip(4)  # independent
                if br.left() > 2:
                    br.skip(2)  # coupling channel count
            elif tag == 3:  # LFE
                _parse_sce(br)
            elif tag == 4:  # DSE
                _parse_dse(br)
            elif tag == 5:  # PCE
                return  # 遇到 PCE 说明包结束
            elif tag == 6:  # FIL
                _parse_fil(br)
            else:
                # 无效标签 → 在此处插入 TYPE_END
                bit_pos = br.pos - 3  # 回退 3 位
                byte_pos = bit_pos // 8
                bit_off = bit_pos % 8

                # 写入 TYPE_END (111)
                if byte_pos < len(data):
                    # 设置3位为111
                    mask = 0xE0 >> bit_off
                    data[byte_pos] = (data[byte_pos] & ~mask) | ((0x07 << (5 - bit_off)) & mask)
                return

    except EOFError:
        # 流结束 → 在最后一个完整字节位置添加 TYPE_END
        bit_pos = br.pos
        while br.left() > 0:
            try:
                br.read(1)
                bit_pos += 1
            except EOFError:
                break
        byte_pos = min(bit_pos // 8, len(data) - 1)
        data[byte_pos] |= 0xE0  # 在最高3位写入111


def _parse_sce(br: BitReader) -> None:
    """解析单通道元素"""
    if br.left() <= 0:
        return
    # 简化：跳过 SCE 的详细解析
    # 实际 ALAC 需要完整解析，这里跳过元素体
    _skip_element(br)


def _parse_dse(br: BitReader) -> None:
    """解析数据流元素"""
    if br.left() < 8:
        return
    # 读取 element_instance_tag (4 bits)
    br.read(4)
    # 读取 data_byte_align_flag (1 bit)
    align = br.read(1)
    # 读取 count (8 bits)
    count = br.read(8)
    # 读取 esc_count (8 bits if needed)
    if count == 255:
        count += br.read(8)
    if align:
        br.skip((8 - br.pos % 8) % 8)
    # 跳过数据
    for _ in range(count):
        if br.left() >= 8:
            br.skip(8)


def _parse_fil(br: BitReader) -> None:
    """解析填充元素"""
    if br.left() < 4:
        return
    count = br.read(4)
    if count == 15:
        while br.left() >= 8:
            v = br.read(8)
            if v != 255:
                break
            count += v
    if count > 0:
        br.skip(count * 8)


def _skip_element(br: BitReader) -> None:
    """跳过音频元素体"""
    # 简化跳过策略：按对齐读取
    if br.left() >= 16:
        # 尝试跳过到下一个元素
        br.skip(min(br.left(), 16))
