"""Offline checks for the RGB program builder.

Run with:  python tests/test_light_program.py
Layout: 6-byte header, then 6 LEDs x 10 keyframes x RGB (186 bytes, uploaded
as 19 frames of 10 bytes).
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
    program = lp.build_program(lp.EFFECT_STATIC, 100, [(255, 0, 0)])
    assert len(program) == lp.PROGRAM_SIZE
    # header: flags, flags, firstKeyframe, lastKeyframe, speed, brightness
    assert program[0:6] == bytes([0x00, 0x02, 0x00, 0x00, lp.STATIC_TICKS, 100])
    assert program[6:9] == bytes((255, 0, 0)), "LED0 keyframe0"
    assert program[6 + 5 * 30 : 6 + 5 * 30 + 3] == bytes((255, 0, 0)), "LED5 keyframe0"


BLUE = (0, 0, 255)


def colour(program: bytes, led: int, keyframe: int) -> tuple[int, ...]:
    start = lp.HEADER_SIZE + led * lp.KEYFRAMES * 3 + keyframe * 3
    return tuple(program[start : start + 3])


def lit(program: bytes) -> set[tuple[int, int]]:
    return {
        (led, kf)
        for led in range(lp.LED_COUNT)
        for kf in range(lp.KEYFRAMES)
        if any(colour(program, led, kf))
    }


def test_static_fills_every_keyframe() -> None:
    program = lp.build_program(lp.EFFECT_STATIC, 50, [BLUE])
    assert program[3] == 0, "single keyframe"
    assert program[4] == lp.STATIC_TICKS, "static effects ignore the speed"
    assert all(
        colour(program, led, kf) == BLUE
        for led in range(lp.LED_COUNT)
        for kf in range(lp.KEYFRAMES)
    )


def test_rotation_moves_one_dot() -> None:
    program = lp.build_program(lp.EFFECT_ROTATION, 50, [BLUE])
    assert program[3] == lp.LED_COUNT - 1
    assert lit(program) == {((-kf) % lp.LED_COUNT, kf) for kf in range(lp.LED_COUNT)}


def test_flowing_shifts_palette_per_led() -> None:
    program = lp.build_program(lp.EFFECT_FLOWING, 50)
    size = len(lp.FLOW_PALETTE)
    assert program[3] == size - 1
    for led in range(lp.LED_COUNT):
        for kf in range(lp.KEYFRAMES):
            expected = lp.FLOW_PALETTE[(led + kf) % size] if kf < size else (0, 0, 0)
            assert colour(program, led, kf) == expected


def test_breathing_fades_from_dark() -> None:
    program = lp.build_program(lp.EFFECT_BREATHING, 50, [BLUE])
    assert program[3] == 1
    assert lit(program) == {(led, 1) for led in range(lp.LED_COUNT)}
    assert colour(program, 0, 1) == BLUE


RED = (255, 0, 0)
GREEN = (0, 255, 0)
WHITE = (255, 255, 255)


def test_default_colors_are_blue_red_green() -> None:
    assert lp.DEFAULT_COLORS == (BLUE, RED, GREEN)


def test_multi_color_repeats_three_slots() -> None:
    program = lp.build_program(lp.EFFECT_MULTI, 50, [WHITE, RED, GREEN])
    for led in range(lp.LED_COUNT):
        assert colour(program, led, 0) == (WHITE, RED, GREEN)[led % 3]
    assert lit(program) == {(led, 0) for led in range(lp.LED_COUNT)}


def test_multi_color_pads_with_defaults() -> None:
    program = lp.build_program(lp.EFFECT_MULTI, 50, [WHITE])
    assert [colour(program, led, 0) for led in range(3)] == [WHITE, RED, GREEN]


def test_rotation_with_three_colours() -> None:
    colours = [BLUE, RED, GREEN]
    program = lp.build_program(lp.EFFECT_ROTATION, 50, colours)
    for kf in range(lp.LED_COUNT):
        for slot, expected in enumerate(colours):
            assert colour(program, (slot - kf) % lp.LED_COUNT, kf) == expected
    assert len(lit(program)) == 3 * lp.LED_COUNT


def test_breathing_through_three_colours() -> None:
    colours = [BLUE, RED, GREEN]
    program = lp.build_program(lp.EFFECT_BREATHING, 50, colours)
    assert program[3] == 5, "dark + lit keyframe per colour"
    for led in range(lp.LED_COUNT):
        assert [colour(program, led, kf) for kf in range(6)] == [
            (0, 0, 0), BLUE, (0, 0, 0), RED, (0, 0, 0), GREEN,
        ]


def test_colour_limits_per_effect() -> None:
    six = [(i, i, i) for i in range(1, 8)]
    assert len(lp.effect_colors(lp.EFFECT_STATIC, six)) == 1
    assert len(lp.effect_colors(lp.EFFECT_MULTI, six)) == 3
    assert len(lp.effect_colors(lp.EFFECT_ROTATION, six)) == 6
    assert len(lp.effect_colors(lp.EFFECT_BREATHING, six)) == 5
    assert lp.effect_colors(lp.EFFECT_FLOWING, six) == []
    assert lp.effect_colors(lp.EFFECT_ROTATION, []) == [BLUE]


def test_brightness_is_clamped() -> None:
    assert lp.build_program(lp.EFFECT_STATIC, 250, [(1, 2, 3)])[5] == 100
    assert lp.build_program(lp.EFFECT_STATIC, -5, [(1, 2, 3)])[5] == 0


def test_frames_cover_program() -> None:
    program = lp.build_program(lp.EFFECT_FLOWING, 60)
    frames = lp.split_frames(program)
    assert len(frames) == lp.FRAME_COUNT == 19
    assert all(len(frame) == lp.FRAME_SIZE for frame in frames)
    assert b"".join(frames)[: len(program)] == program


def test_all_effects_build() -> None:
    for effect in lp.EFFECTS:
        program = lp.build_program(effect, 80, [(10, 20, 30)])
        assert len(program) == lp.PROGRAM_SIZE
        assert any(program), f"{effect} produced an empty program"


def test_speed_mapping() -> None:
    """0..100 slider maps to the firmware transitionTicks byte 5..15."""
    assert lp.speed_ticks(100) == lp.SPEED_FAST
    assert lp.speed_ticks(lp.DEFAULT_SPEED) == lp.SPEED_MEDIUM == 0x0A
    assert lp.speed_ticks(30) == 12 and lp.speed_ticks(80) == 8
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
