"""Sensors for the Flydigi cooler."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import CONNECTION_BLUETOOTH
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_ADDRESS, DOMAIN, MANUFACTURER
from .coordinator import FlydigiCoordinator
from .modes import MODE_NAMES


@dataclass(frozen=True, kw_only=True)
class FlydigiSensorDescription(SensorEntityDescription):
    value_fn: Any = lambda state: None
    # English object id used when generating the entity ID. Kept independent of
    # the translated name so IDs stay stable whatever the UI language is.
    object_id: str | None = None


SENSORS: tuple[FlydigiSensorDescription, ...] = (
    FlydigiSensorDescription(
        key="current_rpm",
        translation_key="current_rpm",
        object_id="current_rpm",
        native_unit_of_measurement="RPM",
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:fan",
        value_fn=lambda state: state.current_rpm,
    ),
    FlydigiSensorDescription(
        key="target_rpm",
        translation_key="target_rpm",
        object_id="target_rpm",
        native_unit_of_measurement="RPM",
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:fan-clock",
        value_fn=lambda state: state.target_rpm,
    ),
    FlydigiSensorDescription(
        key="mode",
        translation_key="mode",
        object_id="control_mode",
        icon="mdi:tune",
        device_class=SensorDeviceClass.ENUM,
        options=["gear", "realtime"],
        value_fn=lambda state: "realtime" if state.realtime else "gear",
    ),
    FlydigiSensorDescription(
        key="gear",
        translation_key="gear",
        object_id="selected_gear",
        icon="mdi:fan-auto",
        device_class=SensorDeviceClass.ENUM,
        options=list(MODE_NAMES),
    ),
    FlydigiSensorDescription(
        key="firmware",
        translation_key="firmware",
        object_id="firmware",
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:chip",
        value_fn=lambda state: state.firmware,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: FlydigiCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        FlydigiSensor(coordinator, entry, description) for description in SENSORS
    )


class FlydigiSensor(CoordinatorEntity[FlydigiCoordinator], SensorEntity):
    """One readable value of the cooler."""

    _attr_has_entity_name = True
    entity_description: FlydigiSensorDescription

    def __init__(
        self,
        coordinator: FlydigiCoordinator,
        entry: ConfigEntry,
        description: FlydigiSensorDescription,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{entry.data[CONF_ADDRESS]}_{description.key}"
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
        return self.entity_description.object_id or self.entity_description.key

    @property
    def native_value(self):
        if self.coordinator.data is None:
            return None
        if self.entity_description.key == "gear":
            return self.coordinator.active_mode
        return self.entity_description.value_fn(self.coordinator.data)

    @property
    def extra_state_attributes(self):
        if self.entity_description.key != "gear" or self.coordinator.data is None:
            return None
        return {"gear": self.coordinator.data.gear}

    @property
    def available(self) -> bool:
        return self.coordinator.last_update_success and self.coordinator.data is not None
