"""Light speed slider for the Flydigi cooler.

The firmware stores the animation speed in the program header as
``transitionTicks`` (0x05 fastest .. 0x0F slowest). It is not part of the
``light`` entity, so it is exposed as a separate number entity; changing it
re-uploads the current effect with the new speed.
"""

from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode
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
    async_add_entities([FlydigiLightSpeed(coordinator, entry)])


class FlydigiLightSpeed(CoordinatorEntity[FlydigiCoordinator], NumberEntity):
    """Animation speed of the RGB light (0 = slow, 100 = fast)."""

    _attr_has_entity_name = True
    _attr_translation_key = "light_speed"
    _attr_native_min_value = 0
    _attr_native_max_value = 100
    _attr_native_step = 10
    _attr_mode = NumberMode.SLIDER
    _attr_icon = "mdi:speedometer"

    def __init__(self, coordinator: FlydigiCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.data[CONF_ADDRESS]}_light_speed"
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
        return "light_speed"

    @property
    def available(self) -> bool:
        return self.coordinator.last_update_success and self.coordinator.data is not None

    @property
    def native_value(self) -> float:
        return float(self.coordinator.light_speed)

    async def async_set_native_value(self, value: float) -> None:
        await self.coordinator.async_set_light_speed(int(value))
