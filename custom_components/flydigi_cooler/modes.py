"""Cooling modes and their three speed levels.

The device itself only stores four fixed gears. These modes are applied as
exact realtime RPM targets (no flash writes) and map the four physical gears
to the same names so the card stays consistent when the button is used.
"""

from __future__ import annotations

MODES: dict[str, tuple[int, int, int]] = {
    "Silent": (1300, 1700, 1900),
    "Standart": (2100, 2400, 2700),
    "Strong": (2900, 3000, 3300),
    "Overclock": (3400, 3700, 4000),
}

MODE_NAMES: tuple[str, ...] = tuple(MODES)

GEAR_MODES: dict[int, str] = {
    1: "Silent",
    2: "Standart",
    3: "Strong",
    4: "Overclock",
}


def rpm_for(mode: str, level: int) -> int:
    """Return the RPM for a mode and a 1-based level."""
    try:
        levels = MODES[mode]
    except KeyError as err:
        raise ValueError(f"unknown mode: {mode}") from err
    if not 1 <= level <= 3:
        raise ValueError("level must be 1..3")
    return levels[level - 1]


def find_mode(rpm: int) -> tuple[str, int] | None:
    """Return ``(mode, level)`` for an exact RPM, if it belongs to the table."""
    for mode, levels in MODES.items():
        for index, value in enumerate(levels, start=1):
            if value == rpm:
                return mode, index
    return None


def mode_for_gear(gear: int) -> str | None:
    """Return the mode name for a physical gear (1..4)."""
    return GEAR_MODES.get(gear)
