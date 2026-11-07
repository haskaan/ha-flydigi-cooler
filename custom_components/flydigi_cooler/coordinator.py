"""Coordinator for the Flydigi cooler integration."""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from datetime import datetime, timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import CONF_ADDRESS, DEFAULT_SCAN_INTERVAL, DOMAIN
from .flydigi_client import FlydigiClient, FlydigiConnectionError
from .light_program import (
    DEFAULT_COLORS,
    DEFAULT_SPEED,
    EFFECT_STATIC,
    MAX_COLORS,
    EFFECTS,
    build_program,
    speed_ticks,
    split_frames,
)
from .modes import MODE_NAMES, MODES, find_mode, mode_for_gear, rpm_for
from .protocol import (
    CMD_GEAR_LIGHT,
    CMD_SET_FIXED_GEAR,
    CMD_SET_POWER_ON_START,
    CMD_SET_REALTIME_RPM,
    CMD_SET_SMART_START_STOP,
    CMD_ENTER_REALTIME_RPM,
    CMD_RGB_COMMIT,
    CMD_RGB_ENABLE,
    CMD_RGB_FRAME_WRITE,
    CMD_RGB_UPLOAD_INIT,
    DeviceState,
    SMART_STOP_MODES,
    cmd_enter_realtime,
    cmd_rgb_commit,
    cmd_rgb_enable,
    cmd_rgb_frame_write,
    cmd_rgb_upload_init,
    cmd_set_gear,
    cmd_set_gear_light,
    cmd_set_rpm,
    cmd_set_smart_start_stop,
    cmd_set_power_on_start,
    DEFAULT_MAX_RPM,
    MIN_RPM,
)

_LOGGER = logging.getLogger(__name__)


def _rpm_limit(state) -> int:
    """Upper bound for realtime targets.

    The fixed gear table can top out below the mode table (e.g. gear 4 at
    3700 RPM while Overclock 3 is 4000). Clamping to the gear table would
    silently turn Overclock 3 into Overclock 2, so realtime targets may go up
    to the hardware maximum as well.
    """
    return max(state.max_rpm, DEFAULT_MAX_RPM)


def _parse_colors(value: object) -> list[tuple[int, int, int]]:
    """Validate a stored colour list; return [] when it is unusable."""
    if not isinstance(value, (list, tuple)):
        return []
    colors: list[tuple[int, int, int]] = []
    for color in value[:MAX_COLORS]:
        if not isinstance(color, (list, tuple)) or len(color) != 3:
            return []
        try:
            colors.append(tuple(max(0, min(255, int(c))) for c in color))
        except (TypeError, ValueError):
            return []
    return colors

# The device pushes a 0xEF status frame about once per second. Forward those
# to the entities, but not more often than this (seconds) to keep recorder and
# state machine writes cheap.
STATE_PUSH_MIN_INTERVAL = 3.0

# The firmware drops out of realtime mode after roughly two minutes and falls
# back to the selected fixed gear. While the fan should be off we re-assert
# 0 RPM before that timeout expires; while a mode/level is active we do the
# same with its target RPM.
OFF_REFRESH_INTERVAL = 60.0
ON_REFRESH_INTERVAL = 60.0

# After writing a flash-backed setting, ignore the status frames that still
# carry the previous value for a moment (the device applies it asynchronously).
SETTINGS_SETTLE = 5.0


class FlydigiCoordinator(DataUpdateCoordinator[DeviceState]):
    """Polls the cooler and owns command sending."""

    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        address = entry.options.get(CONF_ADDRESS) or entry.data[CONF_ADDRESS]
        self.address = address
        self.client = FlydigiClient(hass, address)
        self._store: Store[dict] = Store(hass, 1, f"{DOMAIN}.{entry.entry_id}")
        self._last_push = 0.0
        self._known_address: str | None = None
        # True while the fan is supposed to stay off (the device would leave
        # realtime mode after ~2 minutes otherwise).
        self._off_requested = False
        self._last_off_at = 0.0
        # What to restore when the fan is switched back on: the mode that was
        # active before it was turned off.
        self._last_on: dict[str, int | str] = {"mode": "gear", "gear": 1}
        # Remembered 1-based level for every cooling mode (1..3 each). Each
        # mode keeps its own selection, so switching away and back restores it.
        self._levels: dict[str, int] = {name: 1 for name in MODE_NAMES}
        # RGB light state. The device only reports it via a query we do not
        # parse, so this is optimistic and persisted; the factory default is on.
        self._light_on = True
        self._light_known = False
        self._light_effect = EFFECT_STATIC
        self._light_brightness = 50
        # Colour list shared by the effects (1..6 colours, the first one is
        # the light's colour picker).
        self._light_colors: list[tuple[int, int, int]] = list(DEFAULT_COLORS)
        # Animation speed 0..100 (100 = fastest).
        self._light_speed = DEFAULT_SPEED
        # Settings the cooler keeps in its own flash (0x0D smart start/stop,
        # 0x0C power-on start, 0x48 gear light). A write erases a flash page,
        # so commands are only sent when the user changes a value -- never on
        # startup, reconnect or poll.
        self._smart_stop: int | None = None
        self._smart_stop_written_at = 0.0
        self._gear_light = True
        self._gear_light_known = False
        self._power_on_start = False
        self._power_on_start_known = False
        # Realtime targets are also dropped by the firmware after ~2 minutes;
        # keep re-asserting the active target (0 uses the off path above).
        self._keepalive_rpm = 0
        self._keepalive_gear: int | None = None
        self._last_keepalive_at = 0.0
        self._keepalive_unsub: Callable[[], None] | None = None
        # Snapshot of the persisted state, used once after startup to put the
        # fan back into the mode it had before Home Assistant restarted.
        self._startup_last_on: dict[str, int | str] = {}
        self._startup_restore_done = False
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN} {address}",
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
        )
        self.client.set_state_callback(self._on_client_state)
        self.client.set_connect_callback(self._remember_address)

    async def async_load_known_address(self) -> None:
        """Restore the last address and last mode from the previous run."""
        data = await self._store.async_load()
        if not isinstance(data, dict):
            return
        known = data.get("last_good_address")
        if known:
            self._known_address = known
            self.client.set_known_address(known)
        last_on = data.get("last_on")
        if isinstance(last_on, dict) and last_on.get("mode") in (
            "gear",
            "realtime",
            "mode",
        ):
            self._last_on = last_on
        levels = data.get("levels")
        if isinstance(levels, dict):
            for name in MODE_NAMES:
                value = levels.get(name)
                if isinstance(value, int) and 1 <= value <= 3:
                    self._levels[name] = value
        else:
            # Older store kept a single level shared by all modes.
            level = data.get("level")
            if isinstance(level, int) and 1 <= level <= 3:
                self._levels = {name: level for name in MODE_NAMES}
        if self._last_on.get("mode") == "mode":
            name = str(self._last_on.get("name") or "")
            saved_level = self._last_on.get("level")
            if (
                name in MODE_NAMES
                and isinstance(saved_level, int)
                and 1 <= saved_level <= 3
            ):
                self._levels[name] = saved_level
        self._startup_last_on = dict(self._last_on)
        off = data.get("off")
        if isinstance(off, bool):
            self._off_requested = off
        light_on = data.get("light_on")
        if isinstance(light_on, bool):
            self._light_on = light_on
            self._light_known = True
        effect = data.get("light_effect")
        if isinstance(effect, str) and effect in EFFECTS:
            self._light_effect = effect
        brightness = data.get("light_brightness")
        if isinstance(brightness, int) and 0 <= brightness <= 100:
            self._light_brightness = brightness
        colors = _parse_colors(data.get("light_colors"))
        if colors:
            self._light_colors = colors
        else:
            # Older versions stored a single colour: keep it as the first one.
            single = _parse_colors([data.get("light_color")])
            if single:
                self._light_colors = single + list(DEFAULT_COLORS[1:])
        speed = data.get("light_speed")
        if isinstance(speed, int) and 0 <= speed <= 100:
            self._light_speed = speed
        smart_stop = data.get("smart_stop")
        if smart_stop in SMART_STOP_MODES:
            self._smart_stop = smart_stop
        gear_light = data.get("gear_light")
        if isinstance(gear_light, bool):
            self._gear_light = gear_light
            self._gear_light_known = True
        power_on_start = data.get("power_on_start")
        if isinstance(power_on_start, bool):
            self._power_on_start = power_on_start
            self._power_on_start_known = True

    def _save_store(self) -> None:
        self.hass.async_create_task(
            self._store.async_save(
                {
                    "last_good_address": self._known_address,
                    "last_on": self._last_on,
                    "levels": self._levels,
                    "off": self._off_requested,
                    "light_on": self._light_on,
                    "light_effect": self._light_effect,
                    "light_brightness": self._light_brightness,
                    "light_colors": [list(color) for color in self._light_colors],
                    "light_speed": self._light_speed,
                    "smart_stop": self._smart_stop,
                    "gear_light": self._gear_light,
                    "power_on_start": self._power_on_start,
                }
            )
        )

    def _remember_address(self, address: str) -> None:
        """Persist a working address; the device rotates it on some boots."""
        self._known_address = address
        self._save_store()

    def _remember_mode(self) -> None:
        """Track the mode that is currently driving the fan (for turn_on)."""
        if self._off_requested:
            # Ignore transient frames while the fan is being switched off;
            # _last_on must keep the mode to restore on the next turn_on.
            return
        state = self.client.state
        if state.target_rpm <= 0:
            return
        if state.realtime:
            if self._keepalive_rpm <= 0:
                # A realtime target set outside HA (e.g. after a restart) is
                # still kept alive so it does not fall back to the fixed gear.
                # Force the next timer tick to re-assert it promptly.
                self._set_keepalive(state.target_rpm)
                self._last_keepalive_at = 0.0
            found = find_mode(state.target_rpm)
            if found is None:
                self._last_on = {"mode": "realtime", "rpm": state.target_rpm}
                return
            mode, level = found
            self._last_on = {"mode": "mode", "name": mode, "level": level}
            # Do not overwrite self._levels here: status frames can briefly
            # report the previous target while a new command is being
            # applied, and the user's level selection must stay authoritative.
            return

        # Fixed-gear mode. If HA was driving a realtime target, the firmware
        # may have timed out (~2 min). A changed gear means the physical
        # button was used, so the user's choice wins; the same gear means a
        # firmware fallback, so keep the desired target and re-assert it.
        if self._keepalive_rpm > 0:
            if self._keepalive_gear is not None and state.gear != self._keepalive_gear:
                self._keepalive_rpm = 0
                self._keepalive_gear = None
                _LOGGER.debug("physical gear change detected; keepalive cancelled")
            else:
                _LOGGER.debug(
                    "device left realtime; will re-assert %s rpm", self._keepalive_rpm
                )
                return
        self._last_on = {"mode": "gear", "gear": state.gear}
        native = state.gear_rpm.get(state.gear)
        if native is None:
            return
        found = find_mode(native)
        if found is not None and self._levels.get(found[0]) != found[1]:
            self._levels[found[0]] = found[1]
            self._save_store()

    def _set_keepalive(self, rpm: int) -> None:
        """Remember the realtime target that must be re-asserted."""
        if rpm > 0:
            self._keepalive_rpm = rpm
            self._keepalive_gear = self.client.state.gear
            self._last_keepalive_at = time.monotonic()
        else:
            self._keepalive_rpm = 0
            self._keepalive_gear = None

    @property
    def last_on(self) -> dict[str, int | str]:
        """Mode that turn_on will restore (used by the fan entity while off)."""
        return self._last_on

    @property
    def level(self) -> int:
        """Remembered level of the active (or last used) mode."""
        mode = self.active_mode
        if mode is None:
            return 1
        return self._levels.get(mode, 1)

    @property
    def levels(self) -> dict[str, int]:
        """Remembered level per mode (a copy, for diagnostics/tests)."""
        return dict(self._levels)

    @property
    def light_on(self) -> bool:
        """Whether the RGB light is on (optimistic, device does not report it)."""
        return self._light_on

    @property
    def light_effect(self) -> str:
        """Effect currently applied to the light."""
        return self._light_effect

    @property
    def light_brightness(self) -> int:
        """Light brightness in percent (0..100)."""
        return self._light_brightness

    @property
    def light_colors(self) -> list[tuple[int, int, int]]:
        """Colour list used by the effects (1..6 colours)."""
        return list(self._light_colors)

    @property
    def light_color(self) -> tuple[int, int, int]:
        """First colour of the list (the light entity's colour picker)."""
        return self._light_colors[0]

    @property
    def light_speed(self) -> int:
        """Animation speed, 0 (slow) .. 100 (fast)."""
        return self._light_speed

    @property
    def smart_stop(self) -> int | None:
        """Smart start/stop mode: 0 off, 1 immediate, 2 delayed."""
        return self._smart_stop

    @property
    def gear_light(self) -> bool:
        """Gear indicator LEDs (optimistic, the device does not report it)."""
        return self._gear_light

    @property
    def gear_light_known(self) -> bool:
        """Whether the gear light state is known (persisted or set once)."""
        return self._gear_light_known

    @property
    def power_on_start(self) -> bool:
        """Start the fan as soon as the cooler receives power (optimistic)."""
        return self._power_on_start

    @property
    def power_on_start_known(self) -> bool:
        """Whether the power-on start state is known (persisted or set once)."""
        return self._power_on_start_known

    @property
    def active_mode(self) -> str | None:
        """Mode currently driving the fan, if it can be determined."""
        state = self.client.state
        if state.target_rpm > 0:
            if state.realtime:
                found = find_mode(state.target_rpm)
                if found is not None:
                    return found[0]
            else:
                mode = mode_for_gear(state.gear)
                if mode is not None:
                    return mode
        last = self._last_on
        if last.get("mode") == "mode":
            return str(last.get("name"))
        if last.get("mode") == "gear":
            return mode_for_gear(int(last.get("gear") or 1))
        return None

    @property
    def active_level(self) -> int | None:
        """Level matching the current speed; None for arbitrary RPM."""
        state = self.client.state
        if state.target_rpm <= 0:
            last = self._last_on
            if last.get("mode") == "mode":
                level = last.get("level")
                if isinstance(level, int) and 1 <= level <= 3:
                    return level
                return self.level
            if last.get("mode") == "gear":
                gear = int(last.get("gear") or 1)
                native = state.gear_rpm.get(gear)
                if native is not None:
                    found = find_mode(native)
                    if found is not None:
                        return found[1]
                return self.level
            # A saved arbitrary percentage has no level.
            return None
        if state.realtime:
            found = find_mode(state.target_rpm)
            return found[1] if found is not None else None
        native = state.gear_rpm.get(state.gear)
        if native is not None:
            found = find_mode(native)
            if found is not None:
                return found[1]
        return self.level

    async def _async_update_data(self) -> DeviceState:
        try:
            state = await self.client.async_update()
        except FlydigiConnectionError as err:
            raise UpdateFailed(str(err)) from err
        await self.async_restore_last_state()
        return state

    async def async_restore_last_state(self) -> None:
        """Put the fan back into its pre-restart state after the first poll.

        The firmware reverts from realtime RPM to its stored fixed gear after
        roughly two minutes without a command -- exactly what happens while
        Home Assistant is restarting. Without this the fan would come back as
        "Standart" (Gear 2) instead of the mode that was selected before.
        """
        if self._startup_restore_done:
            return
        self._startup_restore_done = True
        state = self.client.state

        if self._off_requested:
            # The fan was off; make sure the firmware did not spin it up.
            if state.target_rpm > 0:
                try:
                    await self._refresh_off()
                except FlydigiConnectionError as err:
                    _LOGGER.debug("restore off failed: %s", err)
            return

        last = self._startup_last_on
        if last.get("mode") == "mode":
            name = str(last.get("name") or "")
            if name not in MODES:
                return
            target = rpm_for(name, self._levels.get(name, 1))
            if state.realtime and state.target_rpm == target:
                return
            await self.async_set_mode(name)
        elif last.get("mode") == "realtime":
            rpm = int(last.get("rpm") or 0)
            if rpm <= 0 or (state.realtime and state.target_rpm == rpm):
                return
            self._set_keepalive(rpm)
            await self._apply_rpm(rpm)
            self._save_store()

    @callback
    def async_start_keepalive(self) -> None:
        """Start the periodic keepalive, independent of the poll timer."""
        if self._keepalive_unsub is not None:
            return
        self._keepalive_unsub = async_track_time_interval(
            self.hass, self._async_keepalive, timedelta(seconds=30)
        )

    async def _async_keepalive(self, now: datetime) -> None:
        """Re-assert the desired speed before the firmware times out."""
        if self._off_requested:
            if time.monotonic() - self._last_off_at < OFF_REFRESH_INTERVAL:
                return
            try:
                await self._refresh_off()
            except FlydigiConnectionError as err:
                _LOGGER.debug("off refresh failed: %s", err)
            return
        if (
            self._keepalive_rpm > 0
            and time.monotonic() - self._last_keepalive_at >= ON_REFRESH_INTERVAL
        ):
            try:
                await self._refresh_on()
            except FlydigiConnectionError as err:
                _LOGGER.debug("mode refresh failed: %s", err)

    async def _refresh_off(self) -> None:
        """Re-assert 0 RPM before the firmware falls back to a fixed gear."""
        state = self.client.state
        self._set_keepalive(0)
        await self.client.async_send(cmd_enter_realtime(), {CMD_ENTER_REALTIME_RPM})
        await self.client.async_send(cmd_set_rpm(0, state.max_rpm), {CMD_SET_REALTIME_RPM})
        state.realtime = True
        state.target_rpm = 0
        state.current_rpm = 0
        self._last_off_at = time.monotonic()
        _LOGGER.debug("off state refreshed")

    async def _refresh_on(self) -> None:
        """Re-assert the active realtime target before the firmware falls back."""
        state = self.client.state
        rpm = self._keepalive_rpm
        if rpm <= 0:
            return
        await self.client.async_send(cmd_enter_realtime(), {CMD_ENTER_REALTIME_RPM})
        await self.client.async_send(cmd_set_rpm(rpm, _rpm_limit(state)), {CMD_SET_REALTIME_RPM})
        state.realtime = True
        state.target_rpm = rpm
        self._last_keepalive_at = time.monotonic()
        self.async_set_updated_data(state)
        _LOGGER.debug("mode state refreshed at %s rpm", rpm)

    def _sync_device_settings(self) -> None:
        """Adopt the settings the device reports about itself (read only)."""
        reported = self.client.state.smart_stop
        if reported is None or reported == self._smart_stop:
            return
        if time.monotonic() - self._smart_stop_written_at < SETTINGS_SETTLE:
            # Status frames may still carry the previous mode right after a
            # write; do not let them undo the user's choice.
            return
        self._smart_stop = reported
        self._save_store()

    def _on_client_state(self) -> None:
        """Forward a device notification to the entities (throttled)."""
        self._sync_device_settings()
        self._remember_mode()
        now = time.monotonic()
        if now - self._last_push < STATE_PUSH_MIN_INTERVAL:
            return
        self._last_push = now
        self.async_set_updated_data(self.client.state)

    async def async_shutdown(self) -> None:
        if self._keepalive_unsub is not None:
            self._keepalive_unsub()
            self._keepalive_unsub = None
        await self.client.async_disconnect()
        await super().async_shutdown()

    # -- commands ---------------------------------------------------------
    async def _apply_rpm(self, rpm: int) -> None:
        """Switch to realtime mode and set an exact target RPM."""
        state = self.client.state
        await self.client.async_send(cmd_enter_realtime(), {CMD_ENTER_REALTIME_RPM})
        await self.client.async_send(cmd_set_rpm(rpm, _rpm_limit(state)), {CMD_SET_REALTIME_RPM})
        state.realtime = True
        state.target_rpm = rpm
        if rpm <= 0:
            # Do not show the last measured RPM while the fan spins down.
            state.current_rpm = 0
        self.async_set_updated_data(state)

    async def async_set_percentage(self, percentage: int) -> None:
        state = self.client.state
        if percentage <= 0:
            rpm = 0
        else:
            rpm = round(MIN_RPM + (percentage / 100) * (state.max_rpm - MIN_RPM))
        if rpm > 0:
            self._off_requested = False
            self._set_keepalive(rpm)
        else:
            self._off_requested = True
            self._set_keepalive(0)
        await self._apply_rpm(rpm)
        if rpm > 0:
            self._last_on = {"mode": "realtime", "rpm": rpm}
        else:
            self._last_off_at = time.monotonic()
        self._save_store()

    async def async_set_gear(self, gear: int) -> None:
        await self.client.async_send(cmd_set_gear(gear), {CMD_SET_FIXED_GEAR})
        self.client.state.realtime = False
        self.client.state.gear = gear
        self.client.state.target_rpm = self.client.state.gear_rpm.get(gear, 0)
        self._off_requested = False
        self._set_keepalive(0)
        self._last_on = {"mode": "gear", "gear": gear}
        native = self.client.state.gear_rpm.get(gear)
        found = find_mode(native) if native is not None else None
        if found is not None:
            self._levels[found[0]] = found[1]
        self._save_store()
        self.async_set_updated_data(self.client.state)

    async def async_set_mode(self, mode: str) -> None:
        """Apply a named mode at the level remembered for that mode."""
        level = self._levels.get(mode, 1)
        rpm = rpm_for(mode, level)
        self._off_requested = False
        self._set_keepalive(rpm)
        await self._apply_rpm(rpm)
        self._last_on = {"mode": "mode", "name": mode, "level": level}
        self._save_store()

    async def async_set_level(self, level: int) -> None:
        """Select a level; each mode keeps its own last selection."""
        if not 1 <= level <= 3:
            raise ValueError("level must be 1..3")
        state = self.client.state
        mode = self.active_mode or "Silent"
        self._levels[mode] = level
        if state.target_rpm <= 0:
            # Keep the fan off; only remember what turn_on should restore.
            self._set_keepalive(0)
            last = self._last_on
            self._last_on = {
                "mode": "mode",
                "name": last.get("name") if last.get("mode") == "mode" else mode,
                "level": level,
            }
            self._save_store()
            self.async_set_updated_data(state)
            return
        rpm = rpm_for(mode, level)
        self._off_requested = False
        self._set_keepalive(rpm)
        await self._apply_rpm(rpm)
        self._last_on = {"mode": "mode", "name": mode, "level": level}
        self._save_store()

    async def async_turn_off(self) -> None:
        await self.async_set_percentage(0)

    async def async_turn_on(self) -> None:
        """Turn on with the mode that was active before the fan was stopped."""
        self._off_requested = False
        if self._last_on.get("mode") == "mode":
            mode = str(self._last_on.get("name") or "")
            if mode in MODES:
                await self.async_set_mode(mode)
                return
        if self._last_on.get("mode") == "gear":
            gear = int(self._last_on.get("gear") or 1)
            await self.async_set_gear(max(1, min(4, gear)))
            return
        rpm = int(self._last_on.get("rpm") or 0)
        if rpm > 0:
            self._set_keepalive(rpm)
            await self._apply_rpm(rpm)
            self._save_store()
            return
        await self.async_set_percentage(50)

    async def async_set_light(
        self,
        on: bool,
        *,
        brightness: int | None = None,
        rgb: tuple[int, int, int] | None = None,
        effect: str | None = None,
        colors: list[tuple[int, int, int]] | None = None,
    ) -> None:
        """Turn the LED output on/off and optionally change its effect.

        ``rgb`` replaces the first colour of the list, ``colors`` the whole
        list (1..6 colours).

        ``0x46`` is the actual switch (``0x44`` only selects an animation).
        Custom effects are uploaded as a program: ``0x41`` init, 19 x ``0x47``
        frames, then ``0x43`` commit. Every ``0x46`` and ``0x43`` erases a
        flash page, so commands are skipped when nothing changes.
        """
        if not on:
            if self._light_known and not self._light_on:
                return
            await self.client.async_send(cmd_rgb_enable(False), {CMD_RGB_ENABLE})
            self._light_on = False
            self._light_known = True
            self._save_store()
            self.async_set_updated_data(self.client.state)
            return

        brightness = (
            self._light_brightness
            if brightness is None
            else max(1, min(100, brightness))
        )
        new_colors = (
            _parse_colors(colors) if colors is not None else list(self._light_colors)
        )
        if not new_colors:
            raise ValueError("colors must be a list of 1..6 [r, g, b] values")
        if rgb is not None:
            new_colors[0] = tuple(max(0, min(255, int(c))) for c in rgb)
        effect = effect or self._light_effect
        if effect not in EFFECTS:
            raise ValueError(f"unknown light effect: {effect}")

        same = (effect, brightness, new_colors) == (
            self._light_effect,
            self._light_brightness,
            self._light_colors,
        )
        if same and self._light_known and self._light_on:
            return
        # Even when the parameters are unchanged the program is uploaded again:
        # the cooler loses its RAM program when it powers off with the PC, so
        # enabling the output alone would show the factory animation instead of
        # the remembered effect.

        await self._async_apply_light(effect, brightness, new_colors)
        self._light_on = True
        self._light_known = True
        self._light_effect = effect
        self._light_brightness = brightness
        self._light_colors = new_colors
        self._save_store()
        self.async_set_updated_data(self.client.state)

    async def _async_apply_light(
        self, effect: str, brightness: int, colors: list[tuple[int, int, int]]
    ) -> None:
        """Upload and commit one complete light program."""
        frames: list[tuple[bytes, tuple[int, ...]]] = []
        if not (self._light_known and self._light_on):
            frames.append((cmd_rgb_enable(True), (CMD_RGB_ENABLE,)))
        frames.append((cmd_rgb_upload_init(), (CMD_RGB_UPLOAD_INIT,)))
        for index, chunk in enumerate(
            split_frames(
                build_program(
                    effect, brightness, colors, speed_ticks(self._light_speed)
                )
            )
        ):
            # The 19 frame writes are paced by the GATT write-with-response
            # handshake; waiting for a firmware ack each would add ~1s per
            # upload for no benefit.
            frames.append((cmd_rgb_frame_write(index, chunk), ()))
        frames.append((cmd_rgb_commit(), (CMD_RGB_COMMIT,)))
        await self.client.async_send_sequence(frames)

    async def async_set_light_colors(self, colors: list[tuple[int, int, int]]) -> None:
        """Replace the colour list; re-uploads the effect only while the light is on."""
        new_colors = _parse_colors(colors)
        if not new_colors:
            raise ValueError("colors must be a list of 1..6 [r, g, b] values")
        if self._light_known and self._light_on:
            await self.async_set_light(True, colors=new_colors)
            return
        if new_colors == self._light_colors:
            return
        self._light_colors = new_colors
        self._save_store()
        self.async_set_updated_data(self.client.state)

    async def async_set_light_speed(self, speed: int) -> None:
        """Change the animation speed; re-uploads the current program."""
        speed = max(0, min(100, int(speed)))
        if speed == self._light_speed:
            return
        self._light_speed = speed
        self._save_store()
        if self._light_known and self._light_on:
            await self._async_apply_light(
                self._light_effect, self._light_brightness, self._light_colors
            )
        self.async_set_updated_data(self.client.state)

    async def async_set_smart_start_stop(self, mode: int) -> None:
        """Write the smart start/stop mode (flash: only when it changes)."""
        if mode not in SMART_STOP_MODES:
            raise ValueError("smart start/stop mode must be 0, 1 or 2")
        if mode == self._smart_stop:
            _LOGGER.debug("smart start/stop already %s; skipping flash write", mode)
            return
        await self.client.async_send(
            cmd_set_smart_start_stop(mode), {CMD_SET_SMART_START_STOP}
        )
        self._smart_stop = mode
        self._smart_stop_written_at = time.monotonic()
        self._save_store()
        self.async_set_updated_data(self.client.state)

    async def async_set_power_on_start(self, enabled: bool) -> None:
        """Write the power-on start flag (flash: only when it changes)."""
        if self._power_on_start_known and enabled == self._power_on_start:
            _LOGGER.debug("power-on start already %s; skipping flash write", enabled)
            return
        await self.client.async_send(
            cmd_set_power_on_start(enabled), {CMD_SET_POWER_ON_START}
        )
        self._power_on_start = enabled
        self._power_on_start_known = True
        self._save_store()
        self.async_set_updated_data(self.client.state)

    async def async_set_gear_light(self, enabled: bool) -> None:
        """Write the gear light flag (flash: only when it changes).

        ``0x48`` erases a flash page on every call and the firmware does not
        compare values, so the no-op guard here is what protects the flash.
        """
        if self._gear_light_known and enabled == self._gear_light:
            _LOGGER.debug("gear light already %s; skipping flash write", enabled)
            return
        await self.client.async_send(cmd_set_gear_light(enabled), {CMD_GEAR_LIGHT})
        self._gear_light = enabled
        self._gear_light_known = True
        self._save_store()
        self.async_set_updated_data(self.client.state)
