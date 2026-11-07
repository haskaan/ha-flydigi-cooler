"""RGB light platform for the Flydigi cooler.

The cooler has a 6-LED strip. The firmware exposes built-in animations through
command ``0x44`` and custom programs through ``0x41``/``0x47``/``0x43``.

On/off uses ``0x46`` -- that is the actual LED output switch (``0x44`` only
selects an animation). Effects are uploaded as a program (see
``light_program.py``), which the firmware interpolates on the device.
"""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.components.light import (
    ColorMode,
    LightEntity,
    LightEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv, entity_platform
from homeassistant.helpers.device_registry import CONNECTION_BLUETOOTH
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_ADDRESS, DOMAIN, MANUFACTURER
from .coordinator import FlydigiCoordinator
from .light_program import EFFECTS, MAX_COLORS

SERVICE_SET_LIGHT_COLORS = "set_light_colors"
ATTR_COLORS = "colors"

_RGB = vol.All(
    vol.ExactSequence((cv.byte, cv.byte, cv.byte)),
    vol.Coerce(tuple),
)
SET_LIGHT_COLORS_SCHEMA = {
    vol.Required(ATTR_COLORS): vol.All(
        cv.ensure_list, [_RGB], vol.Length(min=1, max=MAX_COLORS)
    ),
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: FlydigiCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([FlydigiLight(coordinator, entry)])

    platform = entity_platform.async_get_current_platform()
    platform.async_register_entity_service(
        SERVICE_SET_LIGHT_COLORS,
        SET_LIGHT_COLORS_SCHEMA,
        "async_set_colors",
    )


class FlydigiLight(CoordinatorEntity[FlydigiCoordinator], LightEntity):
    """RGB lighting of the cooler with effects, brightness and colour."""

    _attr_has_entity_name = True
    _attr_translation_key = "light"
    _attr_color_mode = ColorMode.RGB
    _attr_supported_color_modes = {ColorMode.RGB}
    _attr_supported_features = LightEntityFeature.EFFECT
    _attr_effect_list = list(EFFECTS)
    _attr_icon = "mdi:led-strip-variant"

    def __init__(self, coordinator: FlydigiCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.data[CONF_ADDRESS]}_light"
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
        return "light"

    @property
    def available(self) -> bool:
        return self.coordinator.last_update_success and self.coordinator.data is not None

    @property
    def is_on(self) -> bool:
        return self.coordinator.light_on

    @property
    def brightness(self) -> int | None:
        if not self.is_on:
            return None
        return max(1, round(self.coordinator.light_brightness * 255 / 100))

    @property
    def rgb_color(self) -> tuple[int, int, int]:
        return self.coordinator.light_color

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """The full colour list (the colour picker edits the first one)."""
        return {ATTR_COLORS: [list(color) for color in self.coordinator.light_colors]}

    @property
    def effect(self) -> str | None:
        return self.coordinator.light_effect if self.is_on else None

    async def async_turn_on(
        self,
        brightness: int | None = None,
        rgb_color: tuple[int, int, int] | None = None,
        effect: str | None = None,
        **kwargs,
    ) -> None:
        await self.coordinator.async_set_light(
            True,
            brightness=(
                None if brightness is None else max(1, round(brightness * 100 / 255))
            ),
            rgb=tuple(int(channel) for channel in rgb_color) if rgb_color else None,
            effect=effect,
        )

    async def async_turn_off(self, **kwargs) -> None:
        await self.coordinator.async_set_light(False)

    async def async_set_colors(self, colors: list[tuple[int, int, int]]) -> None:
        """Handle ``flydigi_cooler.set_light_colors``."""
        await self.coordinator.async_set_light_colors(
            [tuple(int(c) for c in color) for color in colors]
        )
