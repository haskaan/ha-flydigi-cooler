"""Offline checks for the flash-backed device settings.

Verifies the promise that Home Assistant restarts and no-op changes never
write to the cooler's flash: 0x0C (power-on start), 0x0D (smart stop) and
0x48 (gear light) may only be sent when the user changes a value.

Run with:  python tests/test_settings.py
"""

from __future__ import annotations

import asyncio
import importlib
import os
import sys
import types

CUSTOM_COMPONENTS = os.path.join(
    os.path.dirname(__file__), "..", "custom_components"
)
PACKAGE = os.path.join(CUSTOM_COMPONENTS, "flydigi_cooler")

FLASH_COMMANDS = (0x0C, 0x0D, 0x48)


def _module(name: str, **attrs) -> types.ModuleType:
    mod = types.ModuleType(name)
    for key, value in attrs.items():
        setattr(mod, key, value)
    sys.modules[name] = mod
    return mod


def _install_stubs() -> None:
    """Stub the Home Assistant surface the coordinator touches."""
    if "homeassistant" in sys.modules:
        return

    class _Base:
        def __init__(self, hass=None, *args, **kwargs):
            self.hass = hass
            self.data = None
            self.last_update_success = True

        def async_set_updated_data(self, data):
            self.data = data

        async def async_shutdown(self):
            return None

    class _Coordinator(_Base):
        def __class_getitem__(cls, item):
            return cls

    class HomeAssistantError(Exception):
        pass

    class _Store:
        def __init__(self, hass, version, key):
            self.hass = hass
            self.key = key

        async def async_load(self):
            return self.hass.storage.get(self.key)

        async def async_save(self, data):
            self.hass.storage[self.key] = data

        def __class_getitem__(cls, item):
            return cls

    _module("homeassistant")
    _module("homeassistant.const", Platform=types.SimpleNamespace())
    _module("homeassistant.config_entries", ConfigEntry=object)
    _module("homeassistant.core", HomeAssistant=object, callback=lambda fn: fn)
    _module("homeassistant.exceptions", HomeAssistantError=HomeAssistantError)
    _module("homeassistant.helpers")
    _module(
        "homeassistant.helpers.event",
        async_track_time_interval=lambda *args, **kwargs: (lambda: None),
    )
    _module("homeassistant.helpers.storage", Store=_Store)
    _module(
        "homeassistant.helpers.update_coordinator",
        DataUpdateCoordinator=_Coordinator,
        UpdateFailed=Exception,
    )

    pkg = types.ModuleType("flydigi_cooler")
    pkg.__path__ = [PACKAGE]
    sys.modules["flydigi_cooler"] = pkg

    _module("flydigi_cooler.flydigi_client", FlydigiClient=None, FlydigiConnectionError=Exception)


def _load():
    _install_stubs()
    if PACKAGE not in sys.path:
        sys.path.insert(0, PACKAGE)
    protocol = importlib.import_module("flydigi_cooler.protocol")
    coordinator_mod = importlib.import_module("flydigi_cooler.coordinator")

    class FakeClient:
        def __init__(self, hass, address):
            self.hass = hass
            self.address = address
            self.state = protocol.DeviceState()
            self.sent: list[bytes] = []
            self.state_callback = None

        def set_state_callback(self, callback):
            self.state_callback = callback

        def set_connect_callback(self, callback):
            self.connect_callback = callback

        def set_known_address(self, address):
            self.known_address = address

        async def async_send(self, frame, expect=()):
            self.sent.append(bytes(frame))

        async def async_send_sequence(self, frames):
            self.sent.extend(bytes(frame) for frame, _expect in frames)

        async def async_update(self):
            return self.state

        async def async_disconnect(self):
            return None

    coordinator_mod.FlydigiClient = FakeClient
    return protocol, coordinator_mod


protocol, coordinator_mod = _load()
FlydigiCoordinator = coordinator_mod.FlydigiCoordinator


class FakeHass:
    def __init__(self) -> None:
        self.storage: dict[str, dict] = {}
        self.tasks: list[asyncio.Task] = []

    def async_create_task(self, coro):
        task = asyncio.ensure_future(coro)
        self.tasks.append(task)
        return task

    async def settle(self) -> None:
        """Let queued store writes run."""
        while self.tasks:
            pending, self.tasks = self.tasks, []
            await asyncio.gather(*pending)


class FakeEntry:
    entry_id = "test"
    title = "Flydigi BS3 Pro"
    data = {"address": "AA:BB:CC:DD:EE:FF"}
    options: dict = {}


STORE_KEY = "flydigi_cooler.test"


def _flash_frames(frames: list[bytes]) -> list[bytes]:
    return [frame for frame in frames if len(frame) > 2 and frame[2] in FLASH_COMMANDS]


async def _restart(hass: FakeHass, stored: dict | None = None):
    """Simulate an HA start: load the store and run the startup restore."""
    if stored is not None:
        hass.storage[STORE_KEY] = stored
    coordinator = FlydigiCoordinator(hass, FakeEntry())
    await coordinator.async_load_known_address()
    coordinator.client.state.gear_rpm = {1: 1300, 2: 2700, 3: 3000, 4: 4000}
    await coordinator.async_restore_last_state()
    await hass.settle()
    return coordinator


async def test_restart_never_writes_flash() -> None:
    """A restart restores the fan with 0x08/0x21/0x23 only, never flash."""
    hass = FakeHass()
    stored = {
        "last_on": {"mode": "mode", "name": "Standart", "level": 2},
        "levels": {"Silent": 1, "Standart": 2, "Strong": 1, "Overclock": 1},
        "gear_light": False,
        "power_on_start": True,
        "smart_stop": 2,
    }
    coordinator = await _restart(hass, stored)

    sent = coordinator.client.sent
    assert not _flash_frames(sent), f"flash written on startup: {_flash_frames(sent)}"
    assert any(frame[2] == 0x21 for frame in sent), "realtime restore still happens"

    # The persisted values are exposed without touching the device.
    assert coordinator.gear_light is False
    assert coordinator.power_on_start is True
    assert coordinator.smart_stop == 2


async def test_noop_settings_do_not_write() -> None:
    """Setting a value that is already known must not erase a flash page."""
    hass = FakeHass()
    coordinator = await _restart(
        hass,
        {
            "last_on": {"mode": "gear", "gear": 1},
            "gear_light": False,
            "power_on_start": True,
            "smart_stop": 2,
        },
    )
    coordinator.client.sent.clear()

    await coordinator.async_set_gear_light(False)
    await coordinator.async_set_power_on_start(True)
    await coordinator.async_set_smart_start_stop(2)
    await hass.settle()

    assert coordinator.client.sent == [], "no-op change must not reach the device"


async def test_manual_changes_write_once() -> None:
    """A real change sends exactly one frame; repeating it is a no-op."""
    hass = FakeHass()
    coordinator = await _restart(
        hass,
        {
            "last_on": {"mode": "gear", "gear": 1},
            "gear_light": False,
            "power_on_start": True,
            "smart_stop": 2,
        },
    )
    client = coordinator.client
    client.sent.clear()

    await coordinator.async_set_gear_light(True)
    await coordinator.async_set_gear_light(True)
    await coordinator.async_set_power_on_start(False)
    await coordinator.async_set_power_on_start(False)
    await coordinator.async_set_smart_start_stop(0)
    await coordinator.async_set_smart_start_stop(0)
    await hass.settle()

    commands = [frame[2] for frame in client.sent]
    assert commands == [0x48, 0x0C, 0x0D], commands
    assert client.sent[0][4] == 0x01, "gear light on"
    assert client.sent[1][4] == 0x02, "power-on start off"
    assert client.sent[2][4] == 0x00, "smart stop off"

    # And the new values are what a restart will see.
    stored = hass.storage[STORE_KEY]
    assert stored["gear_light"] is True
    assert stored["power_on_start"] is False
    assert stored["smart_stop"] == 0


async def test_smart_stop_follows_device_without_writing() -> None:
    """0xEF reports the mode; adopting it must not write to the device."""
    hass = FakeHass()
    coordinator = await _restart(
        hass, {"last_on": {"mode": "gear", "gear": 1}, "smart_stop": 2}
    )
    client = coordinator.client
    client.sent.clear()

    client.state.smart_stop = protocol.SMART_STOP_IMMEDIATE
    coordinator._on_client_state()
    await hass.settle()
    assert coordinator.smart_stop == protocol.SMART_STOP_IMMEDIATE
    assert client.sent == []

    # Right after a write, stale status frames must not undo the user's choice.
    await coordinator.async_set_smart_start_stop(protocol.SMART_STOP_OFF)
    client.sent.clear()
    client.state.smart_stop = protocol.SMART_STOP_IMMEDIATE
    coordinator._on_client_state()
    assert coordinator.smart_stop == protocol.SMART_STOP_OFF

    # Once the settle window is over the device wins again.
    coordinator._smart_stop_written_at = 0.0
    coordinator._on_client_state()
    assert coordinator.smart_stop == protocol.SMART_STOP_IMMEDIATE
    assert client.sent == []


async def test_unknown_settings_are_optimistic() -> None:
    """Without a store the switches are assumed and still do not write."""
    hass = FakeHass()
    coordinator = await _restart(hass)
    assert coordinator.gear_light_known is False
    assert coordinator.power_on_start_known is False
    assert coordinator.smart_stop is None
    assert coordinator.client.sent == [] or not _flash_frames(coordinator.client.sent)

async def test_old_single_colour_store_is_migrated() -> None:
    """A store from before colour lists keeps its colour as colour 1."""
    hass = FakeHass()
    coordinator = await _restart(
        hass, {"last_on": {"mode": "gear", "gear": 1}, "light_color": [255, 255, 255]}
    )
    assert coordinator.light_colors == [(255, 255, 255), (255, 0, 0), (0, 255, 0)]
    assert coordinator.light_color == (255, 255, 255)


async def test_set_light_colors_while_off_only_stores() -> None:
    hass = FakeHass()
    coordinator = await _restart(
        hass, {"last_on": {"mode": "gear", "gear": 1}, "light_on": False}
    )
    coordinator.client.sent.clear()
    await coordinator.async_set_light_colors([(1, 2, 3), (4, 5, 6)])
    await hass.settle()
    assert coordinator.client.sent == [], "an off light must not be uploaded"
    assert coordinator.light_colors == [(1, 2, 3), (4, 5, 6)]
    assert hass.storage[STORE_KEY]["light_colors"] == [[1, 2, 3], [4, 5, 6]]


async def test_set_light_colors_while_on_uploads_once() -> None:
    hass = FakeHass()
    coordinator = await _restart(
        hass,
        {
            "last_on": {"mode": "gear", "gear": 1},
            "light_on": True,
            "light_effect": "Rotation",
        },
    )
    coordinator.client.sent.clear()
    await coordinator.async_set_light_colors([(1, 2, 3)])
    await hass.settle()
    commits = [frame for frame in coordinator.client.sent if frame[2] == 0x43]
    assert len(commits) == 1
    coordinator.client.sent.clear()
    await coordinator.async_set_light_colors([(1, 2, 3)])
    assert coordinator.client.sent == [], "same colours must not re-upload"


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            asyncio.run(fn())
            print(f"ok  {name}")
    print("all settings checks passed")
