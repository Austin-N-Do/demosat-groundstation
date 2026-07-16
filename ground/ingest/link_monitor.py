"""Per-APID link quality tracking: CRC failures and sequence-count gaps,
including the 14-bit sequence counter's wraparound at 16384. A "gap" is one
detected discontinuity (an event); the number of packets actually missed in
that gap is returned to the caller for logging, not accumulated here."""

from __future__ import annotations

SEQ_MODULUS = 16384


class LinkMonitor:
    def __init__(self) -> None:
        self._expected: dict = {}   # apid -> next expected sequence count
        self.crc_failures = 0
        self.gaps = 0
        self.packets_received = 0

    def record_crc_failure(self) -> None:
        self.crc_failures += 1

    def record_receipt(self, apid: int, seq: int) -> int:
        """Returns the number of packets missed before this one (0 = no gap)."""
        self.packets_received += 1
        missed = 0
        expected = self._expected.get(apid)
        if expected is not None and seq != expected:
            missed = (seq - expected) % SEQ_MODULUS
            self.gaps += 1
        self._expected[apid] = (seq + 1) % SEQ_MODULUS
        return missed

    def snapshot(self) -> dict:
        return {
            "crc_failures": self.crc_failures,
            "gaps": self.gaps,
            "packets_received": self.packets_received,
        }
