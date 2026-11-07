"""Build the RGB program the cooler expects (0x41 / 0x47... / 0x43).

Program layout (186 bytes, uploaded as 19 ``0x47`` frames of 10 bytes)::

    byte 0..5   [0x00, 0x02, 0x00, last_keyframe, transition_ticks, brightness]
    byte 6..    6 LEDs x 10 keyframes x RGB, LED-major:
                colour(led, keyframe) at 6 + led * 30 + keyframe * 3

The firmware loops keyframes 0..last_keyframe and fades between them, waiting
``transition_ticks`` per step. Brightness (0..100) is applied by the firmware,
so colours are stored unscaled. Pure python, testable without Bluetooth.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence

Color = tuple[int, int, int]

LED_COUNT = 6
KEYFRAMES = 10
FRAME_SIZE = 10
HEADER_SIZE = 6
PROGRAM_SIZE = HEADER_SIZE + LED_COUNT * KEYFRAMES * 3
FRAME_COUNT = (PROGRAM_SIZE + FRAME_SIZE - 1) // FRAME_SIZE

SPEED_FAST = 0x05
SPEED_MEDIUM = 0x0A
SPEED_SLOW = 0x0F
# Default slider position (maps to 0x0A).
DEFAULT_SPEED = 60
# Static effects do not animate; they always use this transition byte.
STATIC_TICKS = 0x0B


def speed_ticks(value: int) -> int:
    """Map a 0..100 speed slider to the firmware transition byte (15..5).

    0 = slowest (0x0F), 60 = the app default (0x0A), 100 = fastest (0x05);
    linear on both sides of the default. One step lasts ``ticks * 10``
    firmware substeps, so 0x0A is roughly one second per keyframe.
    """
    value = max(0, min(100, int(value)))
    if value <= DEFAULT_SPEED:
        ticks = SPEED_SLOW - value * (SPEED_SLOW - SPEED_MEDIUM) / DEFAULT_SPEED
    else:
        ticks = SPEED_MEDIUM - (value - DEFAULT_SPEED) * (
            SPEED_MEDIUM - SPEED_FAST
        ) / (100 - DEFAULT_SPEED)
    return round(ticks)


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

BLACK: Color = (0, 0, 0)
# Default colour list: blue, red, green.
DEFAULT_COLORS: tuple[Color, ...] = ((0, 0, 255), (255, 0, 0), (0, 255, 0))
DEFAULT_COLOR: Color = DEFAULT_COLORS[0]

# How many colours each effect uses (min, max).
MAX_COLORS = 6
EFFECT_COLOR_LIMITS: dict[str, tuple[int, int]] = {
    EFFECT_STATIC: (1, 1),
    EFFECT_MULTI: (3, 3),
    EFFECT_ROTATION: (1, 6),
    EFFECT_FLOWING: (0, 0),
    EFFECT_BREATHING: (1, 5),
}

# Flowing: fixed palette, mixed colours at half intensity.
FLOW_PALETTE: tuple[Color, ...] = (
    (0, 0, 255),
    (0, 127, 127),
    (0, 255, 0),
    (127, 127, 0),
    (255, 0, 0),
    (127, 0, 127),
)

# A pattern returns the colour of one LED at one keyframe.
Pattern = Callable[[int, int], Color]


def _encode(last_keyframe: int, ticks: int, brightness: int, pattern: Pattern) -> bytes:
    header = bytes([0x00, 0x02, 0x00, last_keyframe, ticks & 0xFF, brightness])
    body = bytearray()
    for led in range(LED_COUNT):
        for keyframe in range(KEYFRAMES):
            body += bytes(pattern(led, keyframe))
    return header + bytes(body)


def effect_colors(effect: str, colors: Sequence[Sequence[int]]) -> list[Color]:
    """Return the colours ``effect`` uses: trimmed to its limit, padded with defaults."""
    if effect not in EFFECT_COLOR_LIMITS:
        raise ValueError(f"unknown light effect: {effect}")
    low, high = EFFECT_COLOR_LIMITS[effect]
    result: list[Color] = [
        tuple(max(0, min(255, int(c))) for c in color)  # type: ignore[misc]
        for color in list(colors)[:high]
    ]
    while len(result) < low:
        # Missing slots take the default colour of the same position.
        result.append(DEFAULT_COLORS[len(result) % len(DEFAULT_COLORS)])
    return result


def build_program(
    effect: str,
    brightness: int,
    colors: Sequence[Sequence[int]] = DEFAULT_COLORS,
    speed: int = SPEED_MEDIUM,
) -> bytes:
    """Return the 186-byte program for one effect.

    ``colors`` is the user's colour list; each effect takes as many as it
    supports (see ``EFFECT_COLOR_LIMITS``).
    """
    brightness = max(0, min(100, int(brightness)))
    palette = effect_colors(effect, colors)

    if effect == EFFECT_STATIC:
        # One keyframe; the app still fills every keyframe with the colour.
        return _encode(0, STATIC_TICKS, brightness, lambda led, kf: palette[0])

    if effect == EFFECT_MULTI:
        # The three colour slots repeat along the strip.
        return _encode(
            0,
            STATIC_TICKS,
            brightness,
            lambda led, kf: palette[led % 3] if kf == 0 else BLACK,
        )

    if effect == EFFECT_ROTATION:
        # The colours sit on consecutive LEDs and the group steps backwards
        # along the strip, one LED per keyframe.
        def rotation(led: int, kf: int) -> Color:
            if kf >= LED_COUNT:
                return BLACK
            slot = (led + kf) % LED_COUNT
            return palette[slot] if slot < len(palette) else BLACK

        return _encode(LED_COUNT - 1, speed, brightness, rotation)

    if effect == EFFECT_FLOWING:
        size = len(FLOW_PALETTE)
        return _encode(
            size - 1,
            speed,
            brightness,
            lambda led, kf: FLOW_PALETTE[(led + kf) % size] if kf < size else BLACK,
        )

    if effect == EFFECT_BREATHING:
        # Every colour gets a dark keyframe followed by a lit one, so the
        # firmware fade breathes through the colours in order.
        def breathing(led: int, kf: int) -> Color:
            index, lit = divmod(kf, 2)
            return palette[index] if lit and index < len(palette) else BLACK

        return _encode(len(palette) * 2 - 1, speed, brightness, breathing)

    raise ValueError(f"unknown light effect: {effect}")


def split_frames(program: bytes) -> list[bytes]:
    """Split a program into the 10-byte ``0x47`` payloads (zero padded)."""
    padded = program + bytes(FRAME_COUNT * FRAME_SIZE - len(program))
    return [
        padded[index * FRAME_SIZE : (index + 1) * FRAME_SIZE]
        for index in range(FRAME_COUNT)
    ]
