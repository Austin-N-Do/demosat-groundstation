import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ground.ingest.link_monitor import LinkMonitor


def test_no_gap_on_first_packet_per_apid():
    mon = LinkMonitor()
    missed = mon.record_receipt(apid=100, seq=57)
    assert missed == 0
    assert mon.gaps == 0
    assert mon.packets_received == 1


def test_no_gap_on_consecutive_sequence():
    mon = LinkMonitor()
    mon.record_receipt(apid=100, seq=5)
    missed = mon.record_receipt(apid=100, seq=6)
    assert missed == 0
    assert mon.gaps == 0


def test_gap_detected_normal_case():
    mon = LinkMonitor()
    mon.record_receipt(apid=100, seq=5)
    missed = mon.record_receipt(apid=100, seq=8)   # skipped 6, 7
    assert missed == 2
    assert mon.gaps == 1


def test_gap_wraparound_16382_to_1_is_2_missed():
    mon = LinkMonitor()
    mon.record_receipt(apid=100, seq=16382)         # expected becomes 16383
    missed = mon.record_receipt(apid=100, seq=1)    # skipped 16383, 0
    assert missed == 2
    assert mon.gaps == 1


def test_wraparound_consecutive_is_not_a_gap():
    mon = LinkMonitor()
    mon.record_receipt(apid=100, seq=16383)         # expected becomes 0
    missed = mon.record_receipt(apid=100, seq=0)    # exactly the wrapped next value
    assert missed == 0
    assert mon.gaps == 0


def test_apids_tracked_independently():
    mon = LinkMonitor()
    mon.record_receipt(apid=100, seq=10)
    mon.record_receipt(apid=101, seq=999)
    # A gap on apid 101 must not affect apid 100's expectation.
    missed_101 = mon.record_receipt(apid=101, seq=1001)
    missed_100 = mon.record_receipt(apid=100, seq=11)
    assert missed_101 == 1
    assert missed_100 == 0
    assert mon.gaps == 1


def test_crc_failures_counted_independently_of_gaps():
    mon = LinkMonitor()
    mon.record_crc_failure()
    mon.record_crc_failure()
    mon.record_receipt(apid=100, seq=0)
    snap = mon.snapshot()
    assert snap == {"crc_failures": 2, "gaps": 0, "packets_received": 1}
