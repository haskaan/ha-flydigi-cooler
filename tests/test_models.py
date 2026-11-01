"""Offline checks for model detection from Bluetooth/GATT names.

Run with:  python tests/test_models.py
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

import const  # noqa: E402


def test_known_model() -> None:
    assert const.known_model("FlyDigi BS1") == "BS1"
    assert const.known_model("FlyDigi BS2PRO") == "BS2 Pro"
    assert const.known_model("FlyDigi BS2 Pro") == "BS2 Pro"
    assert const.known_model("FlyDigi BS3PRO") == "BS3 Pro"
    assert const.known_model("FlyDigi BS3 Pro") == "BS3 Pro"
    assert const.known_model("BS2PRO") == "BS2 Pro"
    assert const.known_model("BS2") == "BS2"
    assert const.known_model("BS3") == "BS3"
    assert const.known_model("Cooling pad") is None
    assert const.known_model(None) is None


def test_friendly_model() -> None:
    assert const.friendly_model("FlyDigi BS2PRO") == "BS2 Pro"
    assert const.friendly_model("FlyDigi BS3PRO") == "BS3 Pro"
    assert const.friendly_model("FlyDigi Mystery") == "FlyDigi Mystery"
    assert const.friendly_model("62:BA:F8:C0:36:2A") == "Cooling pad"
    assert const.friendly_model("DD-7F-64-2D-BA-83") == "Cooling pad"
    assert const.friendly_model("") == "Cooling pad"
    assert const.friendly_model(None) == "Cooling pad"


def test_address_like() -> None:
    assert const.is_address_like("62:BA:F8:C0:36:2A")
    assert const.is_address_like("dd-7f-64-2d-ba-83")
    assert not const.is_address_like("FlyDigi BS2PRO")
    assert not const.is_address_like("Kaan H")
    assert not const.is_address_like(None)
    assert not const.is_address_like("")


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"ok  {name}")
    print("all model checks passed")
