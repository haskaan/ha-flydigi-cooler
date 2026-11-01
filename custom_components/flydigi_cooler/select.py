"""Selectors for the Flydigi cooler: speed level and smart stop."""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import CONNECTION_BLUETOOTH
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_ADDRESS, DOMAIN, MANUFACTURER
from .coordinator import FlydigiCoordinator
from .protocol import (
    SMART_STOP_DELAYED,
    SMART_STOP_IMMEDIATE,
    SMART_STOP_OFF,
)

LEVELS = ["1", "2", "3"]

# Smart start/stop (0x0D). Values are translated in strings.json, so the
# option tokens stay language independent.
SMART_STOP_OPTIONS = ["off", "immediate", "delayed"]
SMART_STOP_BY_OPTION = {
    "off": SMART_STOP_OFF,
    "immediate": SMART_STOP_IMMEDIATE,
    "delayed": SMART_STOP_DELAYED,
}
OPTION_BY_SMART_STOP = {value: key for key, value in SMART_STOP_BY_OPTION.items()}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: FlydigiCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            FlydigiLevelSelect(coordinator, entry),
            FlydigiSmartStopSelect(coordinator, entry),
        ]
    )


class _FlydigiSelect(CoordinatorEntity[FlydigiCoordinator], SelectEntity):
    """Shared device info and availability for the cooler's selects."""

    _attr_has_entity_name = True
    _setting = ""

    def __init__(self, coordinator: FlydigiCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.data[CONF_ADDRESS]}_{self._setting}"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.data[CONF_ADDRESS])},
            "connections": {(CONNECTION_BLUETOOTH, coordinator.client.address)},
            "manufacturer": MANUFACTURER,
            "name": entry.title,
            "model": entry.data.get("model", "Cooling pad"),
        }

    @property
    def suggested_object_id(self) -> str | None:
        """Keep the entity ID English regardless of the UI language."""
        return self._setting

    @property
    def available(self) -> bool:
        return self.coordinator.last_update_success and self.coordinator.data is not None


class FlydigiLevelSelect(_FlydigiSelect):
    """Pick one of the three speed levels inside the active mode."""

    _setting = "level"
    _attr_translation_key = "level"
    _attr_icon = "mdi:layers-triple"
    _attr_options = LEVELS

    @property
    def current_option(self) -> str | None:
        level = self.coordinator.active_level
        return str(level) if level in (1, 2, 3) else None

    async def async_select_option(self, option: str) -> None:
        await self.coordinator.async_set_level(int(option))


class FlydigiSmartStopSelect(_FlydigiSelect):
    """Smart start/stop mode, stored in the cooler's flash.

    The device reports the active mode in every ``0xEF`` status frame, so the
    entity follows the hardware without ever writing to it. A command is only
    sent when the user picks a different option.
    """

    _setting = "smart_stop"
    _attr_translation_key = "smart_stop"
    _attr_icon = "mdi:fan-auto"
    _attr_options = SMART_STOP_OPTIONS

    @property
    def current_option(self) -> str | None:
        return OPTION_BY_SMART_STOP.get(self.coordinator.smart_stop)

    async def async_select_option(self, option: str) -> None:
        await self.coordinator.async_set_smart_start_stop(SMART_STOP_BY_OPTION[option])
