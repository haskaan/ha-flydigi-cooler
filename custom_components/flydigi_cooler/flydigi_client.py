"""BLE transport for Flydigi BS2/BS3 coolers (vendor FFF0 service)."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable, Iterable

from bleak import BleakClient
from bleak.exc import BleakError
from homeassistant.components.bluetooth import (
    async_ble_device_from_address,
    async_discovered_service_info,
)
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .protocol import (
    CMD_QUERY_FIRMWARE,
    CMD_QUERY_GEAR_TABLE,
    CMD_QUERY_RPM_STATE,
    CMD_QUERY_WORK_MODE,
    CMD_STATUS_NOTIFY,
    DeviceState,
    Frame,
    FrameStream,
    apply_reply,
    cmd_query_firmware,
    cmd_query_gear_table,
    cmd_query_rpm,
    cmd_query_work_mode,
    parse_status,
)

_LOGGER = logging.getLogger(__name__)

CHAR_WRITE = "0000fff2-0000-1000-8000-00805f9b34fb"
CHAR_NOTIFY = "0000fff1-0000-1000-8000-00805f9b34fb"
SERVICE_UUID = "0000fff0-0000-1000-8000-00805f9b34fb"
DEVICE_NAME = "flydigi"
DEVICE_INFO_NAME_CHAR = "00002a00-0000-1000-8000-00805f9b34fb"
DEVICE_INFO_MODEL_CHAR = "00002a24-0000-1000-8000-00805f9b34fb"

CONNECT_TIMEOUT = 15
REPLY_TIMEOUT = 3.0
IDLE_DISCONNECT = 90.0


class FlydigiError(Exception):
    """Base error."""


class FlydigiConnectionError(FlydigiError):
    """Raised when the device cannot be reached."""


class FlydigiClient:
    """Owns one BLE link and keeps the latest :class:`DeviceState`."""

    def __init__(self, hass: HomeAssistant, address: str) -> None:
        self.hass = hass
        self.address = address.upper()
        self.state = DeviceState()
        self._client: BleakClient | None = None
        self._stream = FrameStream()
        self._frames: asyncio.Queue[Frame] = asyncio.Queue()
        self._lock = asyncio.Lock()
        self._idle: asyncio.TimerHandle | None = None
        self._last_good: str | None = None
        self._state_callback: Callable[[], None] | None = None
        self._connect_callback: Callable[[str], None] | None = None
        self._known: str | None = None

    # -- public API -------------------------------------------------------
    def set_state_callback(self, callback: Callable[[], None] | None) -> None:
        """Register a callback fired when a status notification updates state."""
        self._state_callback = callback

    def set_connect_callback(self, callback: Callable[[str], None] | None) -> None:
        """Register a callback fired with the address of a successful link."""
        self._connect_callback = callback

    def set_known_address(self, address: str | None) -> None:
        """Seed the last address that worked (persisted across restarts)."""
        self._known = address.upper() if address else None

    @property
    def known_addresses(self) -> set[str]:
        """Return addresses this cooler may currently use."""
        return {
            address.upper()
            for address in (self.address, self._last_good, self._known)
            if address
        }

    async def async_update(self) -> DeviceState:
        """Query the device and return fresh state."""
        async with self._lock:
            await self._ensure_connected()
            self._arm_idle_timer()
            for cmd in (
                cmd_query_rpm(),
                cmd_query_work_mode(),
                cmd_query_gear_table(),
                cmd_query_firmware(),
            ):
                await self._write(cmd)
            await self._collect(
                {CMD_QUERY_RPM_STATE, CMD_QUERY_WORK_MODE, CMD_QUERY_GEAR_TABLE, CMD_QUERY_FIRMWARE},
                REPLY_TIMEOUT,
            )
            return self.state

    async def async_read_model_name(self) -> str | None:
        """Read the Device Information model string, if the device exposes it."""
        return await self._async_read_text_char(DEVICE_INFO_MODEL_CHAR)

    async def async_read_device_name(self) -> str | None:
        """Read the Device Information name string, if the device exposes it."""
        return await self._async_read_text_char(DEVICE_INFO_NAME_CHAR)

    async def _async_read_text_char(self, char: str) -> str | None:
        """Read one UTF-8 text characteristic from the Device Information service."""
        async with self._lock:
            await self._ensure_connected()
            assert self._client is not None
            try:
                raw = await self._client.read_gatt_char(char)
            except (BleakError, TimeoutError, OSError) as err:
                _LOGGER.debug("device info read failed for %s: %s", char, err)
                return None
            finally:
                self._arm_idle_timer()
            text = bytes(raw).decode("utf-8", errors="ignore").strip("\x00 ")
            return text or None

    async def async_send(self, frame: bytes, expect: Iterable[int] = ()) -> None:
        """Write one command frame, optionally waiting for the ack."""
        async with self._lock:
            await self._ensure_connected()
            await self._write(frame)
            expected = set(expect)
            if expected:
                await self._collect(expected, REPLY_TIMEOUT)
            self._arm_idle_timer()

    async def async_send_sequence(
        self, frames: Iterable[tuple[bytes, Iterable[int]]]
    ) -> None:
        """Write several frames while holding the link lock (one transaction).

        Used for the multi-command RGB upload so the periodic fan keepalive
        cannot slip a frame in between the ``0x41``/``0x47``/``0x43`` writes.
        """
        async with self._lock:
            await self._ensure_connected()
            for frame, expect in frames:
                await self._write(frame)
                expected = set(expect)
                if expected:
                    await self._collect(expected, REPLY_TIMEOUT)
            self._arm_idle_timer()

    async def async_disconnect(self) -> None:
        async with self._lock:
            await self._close()

    # -- internals --------------------------------------------------------
    def _candidates(self) -> list:
        """Return plausible devices to connect to, best first.

        The cooler generates a new static random address on some power cycles,
        so the address stored in the config entry can go stale. Advertisements
        that carry the advertised name or the vendor FFF0 service are trusted
        more than a bare address match.
        """
        found: dict[str, object] = {}
        order: list[str] = []

        def add(device) -> None:
            if device is None:
                return
            address = device.address.upper()
            if address in found:
                return
            found[address] = device
            order.append(address)

        if self._last_good:
            add(
                async_ble_device_from_address(
                    self.hass, self._last_good, connectable=True
                )
            )

        if self._known and self._known != self._last_good:
            add(
                async_ble_device_from_address(self.hass, self._known, connectable=True)
            )

        advertised = []
        discovered = async_discovered_service_info(self.hass, connectable=True)
        for info in discovered:
            name = (info.name or "").strip().lower()
            uuids = {uuid.lower() for uuid in (info.service_uuids or ())}
            if DEVICE_NAME in name or SERVICE_UUID in uuids:
                advertised.append(info)
        advertised.sort(
            key=lambda info: (
                0
                if DEVICE_NAME in ((info.name or "")).strip().lower()
                else 1,
                -(info.rssi if info.rssi is not None else -999),
            )
        )
        for info in advertised:
            add(info.device)

        add(
            async_ble_device_from_address(self.hass, self.address, connectable=True)
        )

        _LOGGER.debug(
            "discovered=%d advertised=%s stored=%s known=%s",
            len(discovered),
            [(i.address, i.name, i.rssi) for i in advertised],
            self.address,
            self._known,
        )
        candidates = [found[address] for address in order]
        _LOGGER.debug("candidates=%s", [device.address for device in candidates])
        return candidates

    async def _ensure_connected(self) -> None:
        if self._client is not None and self._client.is_connected:
            return

        candidates = self._candidates()
        if not candidates:
            raise FlydigiConnectionError(
                f"{self.address} not visible to the Bluetooth adapter"
            )

        last_error = "connection failed"
        for ble_device in candidates:
            client = BleakClient(
                ble_device,
                timeout=CONNECT_TIMEOUT,
                disconnected_callback=self._on_disconnect,
            )
            try:
                await client.connect()
                await client.start_notify(CHAR_NOTIFY, self._on_notify)
            except (BleakError, TimeoutError, OSError) as err:
                last_error = str(err) or err.__class__.__name__
                _LOGGER.debug("connect to %s failed: %s", ble_device.address, last_error)
                try:
                    await client.disconnect()
                except Exception:  # noqa: BLE001 - best effort
                    pass
                continue

            self._last_good = ble_device.address.upper()
            self.address = self._last_good
            if self._known != self._last_good:
                self._known = self._last_good
                if self._connect_callback is not None:
                    self._connect_callback(self._last_good)
            _LOGGER.debug("%s connected (%s)", DOMAIN, self.address)
            self._client = client
            self._stream = FrameStream()
            self._frames = asyncio.Queue()
            return

        raise FlydigiConnectionError(last_error)

    def _on_notify(self, _sender: object, data: bytearray) -> None:
        for frame in self._stream.feed(bytes(data)):
            if frame.cmd == CMD_STATUS_NOTIFY:
                if parse_status(frame, self.state) and self._state_callback:
                    self._state_callback()
            else:
                self._frames.put_nowait(frame)

    def _on_disconnect(self, _client: BleakClient) -> None:
        _LOGGER.debug("disconnected from %s", self.address)
        self._client = None

    async def _write(self, frame: bytes) -> None:
        assert self._client is not None
        _LOGGER.debug("tx %s", frame.hex(" "))
        try:
            await self._client.write_gatt_char(CHAR_WRITE, frame, response=True)
        except (BleakError, TimeoutError, OSError) as err:
            raise FlydigiConnectionError(f"write failed: {err}") from err

    async def _collect(self, expected: set[int], timeout: float) -> None:
        """Drain replies until all expected command ids were seen or timeout."""
        pending = set(expected)
        loop = asyncio.get_running_loop()
        deadline = loop.time() + timeout
        while pending:
            remaining = deadline - loop.time()
            if remaining <= 0:
                _LOGGER.debug("no reply for %s", [hex(c) for c in pending])
                return
            try:
                frame = await asyncio.wait_for(self._frames.get(), remaining)
            except asyncio.TimeoutError:
                return
            apply_reply(frame, self.state)
            pending.discard(frame.cmd)

    def _arm_idle_timer(self) -> None:
        if self._idle is not None:
            self._idle.cancel()
        loop = asyncio.get_running_loop()
        self._idle = loop.call_later(
            IDLE_DISCONNECT, lambda: asyncio.ensure_future(self.async_disconnect())
        )

    async def _close(self) -> None:
        if self._idle is not None:
            self._idle.cancel()
            self._idle = None
        client, self._client = self._client, None
        if client is None:
            return
        try:
            await client.stop_notify(CHAR_NOTIFY)
        except Exception:  # noqa: BLE001 - link may already be gone
            pass
        try:
            await client.disconnect()
        except Exception:  # noqa: BLE001
            pass


