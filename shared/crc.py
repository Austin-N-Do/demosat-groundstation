"""CRC-16/CCITT-FALSE — the checksum CCSDS recommends for packet trailers
(polynomial 0x1021, init 0xFFFF, no reflection, no final XOR)."""

_POLY = 0x1021


def crc16_ccitt(data: bytes, crc: int = 0xFFFF) -> int:
    for byte in data:
        crc ^= byte << 8
        for _ in range(8):
            if crc & 0x8000:
                crc = ((crc << 1) ^ _POLY) & 0xFFFF
            else:
                crc = (crc << 1) & 0xFFFF
    return crc
