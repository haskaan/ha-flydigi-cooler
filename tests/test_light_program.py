"""Offline checks for the RGB program builder.

Run with:  python tests/test_light_program.py
Layout copied from the firmware/THRM analysis: 6-byte header, then
6 LEDs x 10 keyframes x RGB (186 bytes, uploaded as 19 frames of 10 bytes).
"""

from __future__ import annotations

import os
import sys

sys.path.insert(
    0,
    os.path.join(
        os.path.dirname(__file__), "..", "custom_components", "flydigi_cooler"
    ),
)

import light_program as lp  # noqa: E402


def test_layout() -> None:
    program = lp.build_program(lp.EFFECT_STATIC, 100, (255, 0, 0))
    assert len(program) == lp.PROGRAM_SIZE
    # header: flags, flags, firstKeyframe, lastKeyframe, speed, brightness
    assert program[0:6] == bytes([0x00, 0x02, 0x00, 0x00, lp.SPEED_MEDIUM, 100])
    assert program[6:9] == bytes((255, 0, 0)), "LED0 keyframe0"
    assert program[6 + 5 * 30 : 6 + 5 * 30 + 3] == bytes((255, 0, 0)), "LED5 keyframe0"


def test_brightness_is_clamped() -> None:
    assert lp.build_program(lp.EFFECT_STATIC, 250, (1, 2, 3))[5] == 100
    assert lp.build_program(lp.EFFECT_STATIC, -5, (1, 2, 3))[5] == 0


def test_frames_cover_program() -> None:
    program = lp.build_program(lp.EFFECT_FLOWING, 60)
    frames = lp.split_frames(program)
    assert len(frames) == lp.FRAME_COUNT == 19
    assert all(len(frame) == lp.FRAME_SIZE for frame in frames)
    assert b"".join(frames)[: len(program)] == program


def test_all_effects_build() -> None:
    for effect in lp.EFFECTS:
        program = lp.build_program(effect, 80, (10, 20, 30))
        assert len(program) == lp.PROGRAM_SIZE
        assert any(program), f"{effect} produced an empty program"


def test_speed_mapping() -> None:
    """0..100 slider maps to the firmware transitionTicks byte 5..15."""
    assert lp.speed_ticks(100) == lp.SPEED_FAST
    assert lp.speed_ticks(50) == lp.SPEED_MEDIUM
    assert lp.speed_ticks(0) == lp.SPEED_SLOW
    program = lp.build_program(lp.EFFECT_FLOWING, 50, speed=lp.speed_ticks(100))
    assert program[4] == lp.SPEED_FAST, "transitionTicks lives at header byte 4"


def test_unknown_effect_raises() -> None:
    try:
        lp.build_program("nope", 50)
    except ValueError:
        return
    raise AssertionError("unknown effect should raise")


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"ok  {name}")
    print("all light program checks passed")
