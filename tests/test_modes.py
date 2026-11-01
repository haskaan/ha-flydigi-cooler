"""Offline checks for the cooling mode/level table.

Run with:  python tests/test_modes.py
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "custom_components", "flydigi_cooler"))

import modes as m  # noqa: E402


def test_mode_table() -> None:
    assert m.MODE_NAMES == ("Silent", "Standart", "Strong", "Overclock")
    assert m.MODES["Silent"] == (1300, 1700, 1900)
    assert m.MODES["Standart"] == (2100, 2400, 2700)
    assert m.MODES["Strong"] == (2900, 3000, 3300)
    assert m.MODES["Overclock"] == (3400, 3700, 4000)


def test_rpm_for() -> None:
    assert m.rpm_for("Silent", 1) == 1300
    assert m.rpm_for("Standart", 2) == 2400
    assert m.rpm_for("Strong", 3) == 3300
    assert m.rpm_for("Overclock", 3) == 4000


def test_find_mode() -> None:
    assert m.find_mode(1300) == ("Silent", 1)
    assert m.find_mode(2700) == ("Standart", 3)
    assert m.find_mode(3000) == ("Strong", 2)
    assert m.find_mode(4000) == ("Overclock", 3)
    assert m.find_mode(2720) is None


def test_gear_mapping() -> None:
    assert [m.mode_for_gear(g) for g in (1, 2, 3, 4)] == [
        "Silent",
        "Standart",
        "Strong",
        "Overclock",
    ]
    assert m.mode_for_gear(5) is None


def test_invalid_inputs() -> None:
    for args in (("Nope", 1), ("Silent", 0), ("Silent", 4)):
        try:
            m.rpm_for(*args)
        except ValueError:
            pass
        else:
            raise AssertionError(f"expected ValueError for {args}")


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"ok  {name}")
    print("all mode checks passed")
