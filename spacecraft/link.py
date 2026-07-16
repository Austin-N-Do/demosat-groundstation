"""Lossy UDP downlink — wraps a socket send with configurable packet drop
and single-byte corruption probabilities, simulating a noisy space link."""

from __future__ import annotations

import logging
import os
import random
import socket

logger = logging.getLogger("spacecraft.link")

DROP_PROB = float(os.environ.get("DROP_PROB", "0.02"))
CORRUPT_PROB = float(os.environ.get("CORRUPT_PROB", "0.01"))


class LossyLink:
    def __init__(self, host: str, port: int) -> None:
        self.addr = (host, port)
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    def send(self, data: bytes) -> bool:
        """Returns True if a (possibly corrupted) packet was actually sent."""
        if random.random() < DROP_PROB:
            return False
        if random.random() < CORRUPT_PROB:
            data = bytearray(data)
            idx = random.randrange(len(data))
            data[idx] ^= 0xFF
            data = bytes(data)
        try:
            self._sock.sendto(data, self.addr)
        except OSError as e:
            # No ground station listening yet (DNS/unreachable) — same
            # externally-visible effect as a dropped packet.
            logger.debug("send failed (ground station unreachable): %s", e)
            return False
        return True

    def close(self) -> None:
        self._sock.close()
