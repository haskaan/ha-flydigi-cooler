"""Switches for cooler settings that are stored in the device flash.

``0x0C`` (power-on auto start) and ``0x48`` (gear light) erase a flash page
when they are written, and ``0x48`` is not even compared by the firmware.
The coordinator therefore only sends a command when the user flips a switch;
nothing is written on startup, reconnect or poll.
"""

from __future__ import annotations

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import CONNECTION_BLUETOOTH
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_ADDRESS, DOMAIN, MANUFACTURER
from .coordinator import FlydigiCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: FlydigiCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            FlydigiGearLightSwitch(coordinator, entry),
            FlydigiPowerOnStartSwitch(coordinator, entry),
        ]
    )


class _FlydigiFlashSwitch(CoordinatorEntity[FlydigiCoordinator], SwitchEntity):
    """Base class for the optimistic switches backed by device flash."""

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

    @property
    def assumed_state(self) -> bool:
        """The device does not report this flag, so the state is optimistic."""
        return not self.known

    @property
    def is_on(self) -> bool:
        return self.value

    @property
    def known(self) -> bool:
        raise NotImplementedError

    @property
    def value(self) -> bool:
        raise NotImplementedError


class FlydigiGearLightSwitch(_FlydigiFlashSwitch):
    """The 4 gear indicator LEDs next to the RGB strip (0x48)."""

    _setting = "gear_light"
    _attr_translation_key = "gear_light"
    _attr_icon = "mdi:lightbulb-group"

    @property
    def known(self) -> bool:
        return self.coordinator.gear_light_known

    @property
    def value(self) -> bool:
        return self.coordinator.gear_light

    async def async_turn_on(self, **kwargs) -> None:
        await self.coordinator.async_set_gear_light(True)

    async def async_turn_off(self, **kwargs) -> None:
        await self.coordinator.async_set_gear_light(False)


class FlydigiPowerOnStartSwitch(_FlydigiFlashSwitch):
    """Start the fan as soon as the cooler receives power (0x0C)."""

    _setting = "power_on_start"
    _attr_translation_key = "power_on_start"
    _attr_icon = "mdi:power-plug"

    @property
    def known(self) -> bool:
        return self.coordinator.power_on_start_known

    @property
    def value(self) -> bool:
        return self.coordinator.power_on_start

    async def async_turn_on(self, **kwargs) -> None:
        await self.coordinator.async_set_power_on_start(True)

    async def async_turn_off(self, **kwargs) -> None:
        await self.coordinator.async_set_power_on_start(False)
