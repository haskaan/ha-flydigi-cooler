"""Constants for the Flydigi cooler integration."""

import re

DOMAIN = "flydigi_cooler"
MANUFACTURER = "Flydigi"

CONF_ADDRESS = "address"

SERVICE_UUID = "0000fff0-0000-1000-8000-00805f9b34fb"
CHAR_WRITE = "0000fff2-0000-1000-8000-00805f9b34fb"
CHAR_NOTIFY = "0000fff1-0000-1000-8000-00805f9b34fb"

DEFAULT_SCAN_INTERVAL = 30
MIN_SCAN_INTERVAL = 10
MAX_SCAN_INTERVAL = 300

KNOWN_MODELS = {
    "flydigi bs1": "BS1",
    "flydigi bs2pro": "BS2 Pro",
    "flydigi bs2 pro": "BS2 Pro",
    "flydigi bs2": "BS2",
    "flydigi bs3pro": "BS3 Pro",
    "flydigi bs3 pro": "BS3 Pro",
    "flydigi bs3": "BS3",
}


_ADDRESS_RE = re.compile(r"^(?:[0-9a-f]{2}[:-]){5}[0-9a-f]{2}$", re.IGNORECASE)


def is_address_like(value: str | None) -> bool:
    """Return True if value is just a Bluetooth MAC address."""
    return bool(value) and bool(_ADDRESS_RE.fullmatch(value.strip()))


def known_model(name: str | None) -> str | None:
    """Return the friendly model name for an advertised or GATT name."""
    if not name:
        return None
    lowered = name.lower()
    for key, model in KNOWN_MODELS.items():
        token = key.removeprefix("flydigi ")
        if token in lowered:
            return model
    return None


def friendly_model(name: str | None) -> str:
    """Return a friendly model name, ignoring MAC-address-only names."""
    if not name or is_address_like(name):
        return "Cooling pad"
    return known_model(name) or name
