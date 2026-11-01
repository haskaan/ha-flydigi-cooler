"""Build the RGB program the cooler expects (0x41 / 0x47... / 0x43).

Ported from TIANLI0/THRM (``internal/device/rgb.go``). The firmware frame
buffer is a 6-byte header followed by 6 LEDs x 10 keyframes x RGB::

    [flags0, flags1, firstKeyframe, lastKeyframe, transitionTicks, brightness]
    colour(led, keyframe) at 6 + led*30 + keyframe*3

Brightness is applied by the firmware, so colours are stored unscaled.
Everything here is pure python so it can be unit tested without Bluetooth.
"""

from __future__ import annotations

LED_COUNT = 6
KEYFRAMES = 10
FRAME_SIZE = 10
HEADER_SIZE = 6
PROGRAM_SIZE = HEADER_SIZE + LED_COUNT * KEYFRAMES * 3
FRAME_COUNT = (PROGRAM_SIZE + FRAME_SIZE - 1) // FRAME_SIZE

SPEED_FAST = 0x05
SPEED_MEDIUM = 0x0A
SPEED_SLOW = 0x0F


def speed_ticks(value: int) -> int:
    """Map a 0..100 speed slider to the firmware transitionTicks byte (5..15).

    100 = fastest (0x05), 0 = slowest (0x0F), 50 = medium (0x0A) -- the same
    mapping the vendor app uses.
    """
    value = max(0, min(100, int(value)))
    return round(SPEED_SLOW - value * (SPEED_SLOW - SPEED_FAST) / 100)

EFFECT_STATIC = "Static"
EFFECT_MULTI = "Multi color"
EFFECT_ROTATION = "Rotation"
EFFECT_FLOWING = "Flowing"
EFFECT_BREATHING = "Breathing"
EFFECTS: tuple[str, ...] = (
    EFFECT_STATIC,
    EFFECT_MULTI,
    EFFECT_ROTATION,
    EFFECT_FLOWING,
    EFFECT_BREATHING,
)

DEFAULT_COLOR = (255, 255, 255)
MULTI_COLORS = ((255, 0, 0), (0, 255, 0), (0, 0, 255))
FLOW_PALETTE = (
    (255, 0, 0),
    (255, 255, 0),
    (0, 255, 0),
    (0, 255, 255),
    (0, 0, 255),
    (255, 0, 255),
)


def _new(last_keyframe: int, brightness: int, speed: int) -> bytearray:
    buf = bytearray(PROGRAM_SIZE)
    buf[0:HEADER_SIZE] = bytes(
        [0x00, 0x02, 0x00, last_keyframe & 0xFF, speed, brightness]
    )
    return buf


def _set_color(buf: bytearray, led: int, keyframe: int, color) -> None:
    offset = HEADER_SIZE + led * KEYFRAMES * 3 + keyframe * 3
    buf[offset : offset + 3] = bytes(color)


def build_program(
    effect: str,
    brightness: int,
    color=DEFAULT_COLOR,
    speed: int = SPEED_MEDIUM,
) -> bytes:
    """Return the 186-byte program for one effect."""
    brightness = max(0, min(100, int(brightness)))

    if effect == EFFECT_STATIC:
        buf = _new(0, brightness, speed)
        for led in range(LED_COUNT):
            _set_color(buf, led, 0, color)
        return bytes(buf)

    if effect == EFFECT_MULTI:
        buf = _new(0, brightness, speed)
        for led in range(LED_COUNT):
            _set_color(buf, led, 0, MULTI_COLORS[led % len(MULTI_COLORS)])
        return bytes(buf)

    if effect == EFFECT_ROTATION:
        # A single coloured dot travelling along the strip.
        buf = _new(LED_COUNT - 1, brightness, speed)
        for led in range(LED_COUNT):
            for keyframe in range(LED_COUNT):
                if (led + keyframe) % LED_COUNT == 0:
                    _set_color(buf, led, keyframe, color)
        return bytes(buf)

    if effect == EFFECT_FLOWING:
        buf = _new(len(FLOW_PALETTE) - 1, brightness, speed)
        for led in range(LED_COUNT):
            for keyframe in range(len(FLOW_PALETTE)):
                _set_color(
                    buf,
                    led,
                    keyframe,
                    FLOW_PALETTE[(led + keyframe) % len(FLOW_PALETTE)],
                )
        return bytes(buf)

    if effect == EFFECT_BREATHING:
        # Even keyframes carry the colour, odd ones stay black: the firmware
        # interpolates between them, which is the breathing fade.
        buf = _new(1, brightness, speed)
        for led in range(LED_COUNT):
            _set_color(buf, led, 0, color)
        return bytes(buf)

    raise ValueError(f"unknown light effect: {effect}")


def split_frames(program: bytes) -> list[bytes]:
    """Split a program into the 10-byte ``0x47`` payloads (zero padded)."""
    padded = program + bytes(FRAME_COUNT * FRAME_SIZE - len(program))
    return [
        padded[index * FRAME_SIZE : (index + 1) * FRAME_SIZE]
        for index in range(FRAME_COUNT)
    ]
