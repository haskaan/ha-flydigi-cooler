"""Fan platform for the Flydigi cooler."""

from __future__ import annotations

import logging

from homeassistant.components.fan import FanEntity, FanEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import CONNECTION_BLUETOOTH
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_ADDRESS, DOMAIN, MANUFACTURER
from .coordinator import FlydigiCoordinator
from .modes import MODE_NAMES, MODES, find_mode, mode_for_gear
from .protocol import MIN_RPM, DeviceState

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: FlydigiCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([FlydigiFan(coordinator, entry)])


class FlydigiFan(CoordinatorEntity[FlydigiCoordinator], FanEntity):
    """Fan of a Flydigi cooling pad."""

    _attr_has_entity_name = True
    _attr_name = None
    _attr_supported_features = (
        FanEntityFeature.SET_SPEED
        | FanEntityFeature.PRESET_MODE
        | FanEntityFeature.TURN_ON
        | FanEntityFeature.TURN_OFF
    )

    def __init__(self, coordinator: FlydigiCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._attr_unique_id = f"{entry.data[CONF_ADDRESS]}_fan"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.data[CONF_ADDRESS])},
            "connections": {(CONNECTION_BLUETOOTH, coordinator.client.address)},
            "manufacturer": MANUFACTURER,
            "name": entry.title,
            "model": entry.data.get("model", "Cooling pad"),
            "sw_version": coordinator.data.firmware if coordinator.data else None,
        }

    @property
    def _state(self):
        return self.coordinator.data or DeviceState()

    @property
    def available(self) -> bool:
        return self.coordinator.last_update_success and self.coordinator.data is not None

    @property
    def preset_modes(self) -> list[str]:
        return list(MODE_NAMES)

    @property
    def preset_mode(self) -> str | None:
        state = self._state
        if state.target_rpm <= 0:
            # While off the device is in realtime mode, but the card should
            # keep showing the mode that turn_on will restore.
            last = self.coordinator.last_on
            if last.get("mode") == "mode":
                return str(last.get("name"))
            if last.get("mode") == "gear":
                return mode_for_gear(int(last.get("gear") or 1))
            return None
        if state.realtime:
            found = find_mode(state.target_rpm)
            return found[0] if found is not None else None
        return mode_for_gear(state.gear)

    @property
    def percentage(self) -> int | None:
        state = self._state
        if state.target_rpm <= 0:
            return 0
        span = max(state.max_rpm - MIN_RPM, 1)
        return max(1, min(100, round((state.target_rpm - MIN_RPM) / span * 100)))

    @property
    def is_on(self) -> bool:
        state = self._state
        # The target RPM is what we (or the device) asked for; the measured
        # RPM can lag behind by a few seconds while the fan spins down, which
        # used to make the toggle flip back to "on" right after turning off.
        return state.target_rpm > 0

    async def async_set_percentage(self, percentage: int) -> None:
        await self.coordinator.async_set_percentage(percentage)

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        if preset_mode in MODES:
            await self.coordinator.async_set_mode(preset_mode)
            return
        # Keep the old "Gear N" calls working (existing automations).
        if preset_mode.startswith("Gear "):
            await self.coordinator.async_set_gear(int(preset_mode.split()[-1]))
            return
        raise ValueError(f"unknown preset mode: {preset_mode}")

    async def async_turn_on(
        self, percentage: int | None = None, preset_mode: str | None = None, **kwargs
    ) -> None:
        if preset_mode is not None:
            await self.async_set_preset_mode(preset_mode)
            return
        if percentage is not None:
            await self.async_set_percentage(percentage)
            return
        await self.coordinator.async_turn_on()

    async def async_turn_off(self, **kwargs) -> None:
        await self.coordinator.async_turn_off()

