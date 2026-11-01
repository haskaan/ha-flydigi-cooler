"""Offline checks for the Flydigi protocol layer.

Run with:  python tests/test_protocol.py
Expected byte sequences come from real captures of a BS3 Pro
(firmware 0.0.2.4).
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "custom_components", "flydigi_cooler"))

import protocol as p  # noqa: E402


def h(s: str) -> bytes:
    return bytes.fromhex(s.replace(" ", ""))


def test_known_frames() -> None:
    assert p.build_frame(0x25) == h("5a a5 25 02 27"), "query work mode"
    assert p.build_frame(0x22) == h("5a a5 22 02 24"), "query rpm"
    assert p.build_frame(0x27) == h("5a a5 27 02 29"), "query gear table"
    assert p.build_frame(0x23) == h("5a a5 23 02 25"), "enter realtime"
    assert p.cmd_set_rpm(2200) == h("5a a5 21 04 98 08 c5"), "set 2200 rpm"
    assert p.cmd_set_rpm(1700) == h("5a a5 21 04 a4 06 cf"), "set 1700 rpm"
    assert p.cmd_set_gear(3) == h("5a a5 08 03 03 0e"), "fixed gear 3"
    assert p.cmd_power_on() == h("5a a5 05 02 07"), "power on"
    assert p.cmd_power_off() == h("5a a5 06 02 08"), "power off"
    assert p.cmd_set_smart_start_stop(1) == h("5a a5 0d 03 01 11"), "smart stop"
    assert p.cmd_set_smart_start_stop(0) == h("5a a5 0d 03 00 10"), "smart stop off"
    assert p.cmd_set_smart_start_stop(2) == h("5a a5 0d 03 02 12"), "smart stop delayed"
    assert p.cmd_set_gear_light(True) == h("5a a5 48 03 01 4c"), "gear light on"
    assert p.cmd_set_gear_light(False) == h("5a a5 48 03 00 4b"), "gear light off"


def test_invalid_settings_rejected() -> None:
    """Only the three known modes exist; never write a stray flash value."""
    for bad in (-1, 3, 4, 8):
        try:
            p.cmd_set_smart_start_stop(bad)
        except ValueError:
            continue
        raise AssertionError(f"smart stop mode {bad} should be rejected")


def test_rgb_light_frames() -> None:
    """0x46 is the LED output switch; 0x44 only selects an animation preset."""
    assert p.cmd_rgb_enable(False) == h("5a a5 46 03 00 49"), "light off"
    assert p.cmd_rgb_enable(True) == h("5a a5 46 03 01 4a"), "light on"
    assert p.cmd_rgb_preset(0) == h("5a a5 44 03 00 47"), "stop animation"
    assert p.cmd_rgb_preset(1) == h("5a a5 44 03 01 48"), "preset 1"


def test_rgb_program_frames() -> None:
    """0x41 init, 0x47 frame writes, 0x43 commit."""
    assert p.cmd_rgb_upload_init() == h("5a a5 41 02 43"), "upload init"
    assert p.cmd_rgb_commit() == h("5a a5 43 03 01 47"), "commit"
    assert (
        p.cmd_rgb_frame_write(0, bytes(10))
        == h("5a a5 47 0d 00 00 00 00 00 00 00 00 00 00 00 54")
    ), "frame 0"
    frame = p.cmd_rgb_frame_write(18, b"\x01" * 10)
    assert frame[:5] == h("5a a5 47 0d 12")
    assert frame[-1] == (0x47 + 0x0D + 18 + 10) & 0xFF


def test_frame_stream_concatenated_and_split() -> None:
    stream = p.FrameStream()

    # one notification carrying several frames (real capture)
    blob = h(
        "5a a5 01 06 00 00 02 04 0d"
        "5a a5 09 03 00 0c"
        "5a a5 27 0a 14 05 8c 0a b8 0b 74 0e 25"
    )
    frames = stream.feed(blob)
    assert [f.cmd for f in frames] == [0x01, 0x09, 0x27]

    # a frame split over two notifications
    assert stream.feed(h("5a a5 21")) == []
    frames = stream.feed(h("03 01 25"))
    assert len(frames) == 1 and frames[0].cmd == 0x21 and frames[0].payload == b"\x01"

    # leading noise + magic split across packets
    stream = p.FrameStream()
    assert stream.feed(h("00 5a")) == []
    frames = stream.feed(h("a5 25 03 03 2b"))
    assert len(frames) == 1 and frames[0].cmd == 0x25


def test_status_and_replies() -> None:
    stream = p.FrameStream()
    state = p.DeviceState()
    frames = stream.feed(h("5a a5 ef 0d 6c 03 05 54 0b b8 0b 01 01 a9 df 1c"))
    assert len(frames) == 1
    assert p.parse_status(frames[0], state)
    assert state.current_rpm == 2900
    assert state.target_rpm == 3000
    assert state.realtime is True
    assert state.gear == 3
    assert state.smart_stop == p.SMART_STOP_OFF

    p.apply_reply(p.Frame(0x27, h("14 05 8c 0a b8 0b 74 0e")), state)
    assert state.gear_rpm == {1: 1300, 2: 2700, 3: 3000, 4: 3700}
    assert state.max_rpm == 3700

    p.apply_reply(p.Frame(0x22, h("a4 06 b8 0b")), state)
    assert (state.current_rpm, state.target_rpm) == (1700, 3000)

    p.apply_reply(p.Frame(0x01, h("00 00 02 04")), state)
    assert state.firmware == "0.0.2.4"


def test_status_reports_smart_stop() -> None:
    """0xEF byte 1 bits 0x0E carry the smart start/stop mode."""
    cases = (
        (0x03, p.SMART_STOP_OFF),
        (0x05, p.SMART_STOP_IMMEDIATE),
        (0x09, p.SMART_STOP_DELAYED),
    )
    for second_byte, expected in cases:
        state = p.DeviceState()
        payload = h("6c") + bytes([second_byte]) + h("05 54 0b b8 0b 01 01 a9")
        assert p.parse_status(p.Frame(0xEF, payload), state)
        assert state.smart_stop == expected, f"second byte 0x{second_byte:02x}"

    # Unknown bits: keep the previous value instead of guessing a mode.
    state = p.DeviceState()
    state.smart_stop = p.SMART_STOP_DELAYED
    payload = h("6c 01 05 54 0b b8 0b 01 01 a9")
    assert p.parse_status(p.Frame(0xEF, payload), state)
    assert state.smart_stop == p.SMART_STOP_DELAYED


def test_stopped_state_reports_zero_rpm() -> None:
    """target 0 = stopped; stale measured rpm must not keep the fan "on"."""
    state = p.DeviceState()
    payload = h("6c 03 05 54 0b 00 00 0b 01 01 a9")
    assert p.parse_status(p.Frame(0xEF, payload), state)
    assert (state.current_rpm, state.target_rpm) == (0, 0)

    state = p.DeviceState()
    p.apply_reply(p.Frame(0x22, h("54 0b 00 00")), state)
    assert (state.current_rpm, state.target_rpm) == (0, 0)


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"ok  {name}")
    print("all protocol checks passed")
