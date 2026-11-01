"""Config flow for the Flydigi cooler integration."""

from __future__ import annotations

import logging

import voluptuous as vol
from homeassistant.components.bluetooth import (
    BluetoothServiceInfoBleak,
    async_discovered_service_info,
)
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_ADDRESS
from homeassistant.helpers.selector import (
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .const import (
    CONF_ADDRESS as CONF_COOLER_ADDRESS,
    DOMAIN,
    SERVICE_UUID,
    friendly_model,
    is_address_like,
    known_model,
)
from .flydigi_client import FlydigiClient, FlydigiConnectionError

_LOGGER = logging.getLogger(__name__)


class FlydigiConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for a Flydigi cooling pad."""

    VERSION = 1

    def __init__(self) -> None:
        self._address: str | None = None
        self._model: str = "Cooling pad"

    async def async_step_bluetooth(
        self, discovery_info: BluetoothServiceInfoBleak
    ) -> ConfigFlowResult:
        """Handle a device discovered over Bluetooth."""
        await self.async_set_unique_id(discovery_info.address)
        self._abort_if_unique_id_configured()
        if self._address_in_use(discovery_info.address):
            return self.async_abort(reason="already_configured")

        self._address = discovery_info.address
        self._model = friendly_model(discovery_info.name)
        self.context["title_placeholders"] = {"name": self._model}

        if not await self._async_probe():
            return self.async_abort(reason="cannot_connect")

        # The probe may have read a more precise model from the device.
        self.context["title_placeholders"] = {"name": self._model}
        return await self.async_step_bluetooth_confirm()

    async def async_step_bluetooth_confirm(
        self, user_input: dict | None = None
    ) -> ConfigFlowResult:
        """Confirm a discovered device."""
        if user_input is not None:
            return self._create_entry()

        self._set_confirm_only()
        return self.async_show_form(
            step_id="bluetooth_confirm",
            description_placeholders={"name": self._model},
        )

    async def async_step_user(self, user_input: dict | None = None) -> ConfigFlowResult:
        """Add a cooler by picking a discovered device or entering an address."""
        errors: dict[str, str] = {}
        discovered = self._discovered()
        devices = sorted(
            discovered.items(),
            key=lambda item: (
                not item[1] or is_address_like(item[1]),
                _display_name(item[1]).lower(),
                item[0],
            ),
        )

        if user_input is not None:
            address = str(user_input[CONF_ADDRESS]).strip().upper()
            self._address = address
            self._model = friendly_model(discovered.get(address))
            await self.async_set_unique_id(address, raise_on_progress=False)
            self._abort_if_unique_id_configured()
            if self._address_in_use(address):
                return self.async_abort(reason="already_configured")

            if await self._async_probe():
                return self._create_entry()
            errors["base"] = "cannot_connect"

        if devices:
            options = [
                {"value": address, "label": _device_label(name, address)}
                for address, name in devices
            ]
            schema = vol.Schema(
                {
                    vol.Required(
                        CONF_ADDRESS,
                        default=self._address or options[0]["value"],
                    ): SelectSelector(
                        SelectSelectorConfig(
                            options=options,
                            mode=SelectSelectorMode.DROPDOWN,
                            custom_value=True,
                        )
                    )
                }
            )
        elif self._address:
            schema = vol.Schema(
                {vol.Required(CONF_ADDRESS, default=self._address): str}
            )
        else:
            schema = vol.Schema({vol.Required(CONF_ADDRESS): str})

        return self.async_show_form(
            step_id="user",
            data_schema=schema,
            errors=errors,
            description_placeholders={"found": _found_text(devices)},
        )

    def _create_entry(self) -> ConfigFlowResult:
        assert self._address is not None
        title = self._model
        if not title.lower().startswith("flydigi"):
            title = f"Flydigi {title}"
        return self.async_create_entry(
            title=title,
            data={CONF_COOLER_ADDRESS: self._address, "model": self._model},
        )

    async def _async_probe(self) -> bool:
        assert self._address is not None
        client = FlydigiClient(self.hass, self._address)
        try:
            state = await client.async_update()
            _LOGGER.debug("probe ok: %s", state)
            if known_model(self._model) is None:
                try:
                    device_model = await client.async_read_model_name()
                except FlydigiConnectionError as err:
                    _LOGGER.debug("model read failed for %s: %s", self._address, err)
                    device_model = None
                if device_model:
                    self._model = friendly_model(device_model)
                if known_model(self._model) is None:
                    try:
                        device_name = await client.async_read_device_name()
                    except FlydigiConnectionError as err:
                        _LOGGER.debug("name read failed for %s: %s", self._address, err)
                        device_name = None
                    if device_name:
                        self._model = friendly_model(device_name)
            return True
        except FlydigiConnectionError as err:
            _LOGGER.debug("probe failed for %s: %s", self._address, err)
            return False
        finally:
            await client.async_disconnect()

    def _discovered(self) -> dict[str, str]:
        """Return currently discovered Flydigi devices keyed by address."""
        result: dict[str, str] = {}
        for info in async_discovered_service_info(self.hass, connectable=True):
            name = (info.name or "").strip()
            uuids = {uuid.lower() for uuid in (info.service_uuids or ())}
            if _is_flydigi(name) or SERVICE_UUID in uuids:
                result[info.address.upper()] = name
        return result

    def _address_in_use(self, address: str) -> bool:
        """Return True if an existing cooler already uses this address."""
        address = address.upper()
        for coordinator in self.hass.data.get(DOMAIN, {}).values():
            client = getattr(coordinator, "client", None)
            addresses = getattr(client, "known_addresses", None)
            if addresses and address in addresses:
                return True
        return False


def _is_flydigi(name: str | None) -> bool:
    return bool(name) and "flydigi" in (name or "").lower()


def _display_name(name: str | None) -> str:
    """Return a human-readable label for a discovered device."""
    if not name or is_address_like(name):
        return "Flydigi Cooler"
    model = known_model(name)
    if model is not None:
        return f"Flydigi {model}"
    return name


def _device_label(name: str | None, address: str) -> str:
    """Return the label shown for a discovered device."""
    return f"{_display_name(name)} ({address})"


def _found_text(devices: list[tuple[str, str]]) -> str:
    """Return the discovered devices as one line per device."""
    return "\n".join(
        _device_label(name, address) for address, name in devices
    ) or "-"
