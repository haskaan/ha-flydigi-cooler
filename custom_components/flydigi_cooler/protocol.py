"""Protocol layer for Flydigi BS-series laptop coolers (BS1/BS2/BS3 + Pro).

Frame layout (both directions)::

    5A A5 <CMD> <LEN> <PAYLOAD...> <CHECKSUM>

* ``LEN``      = 2 + len(payload)  (counts CMD and LEN themselves)
* ``CHECKSUM`` = (CMD + LEN + payload bytes) & 0xFF

Transport on the BS2/BS3 family is a vendor GATT service::

    service 0000fff0-...  -> write 0000fff2-..., notify 0000fff1-...

Frames are written to FFF2 as-is (no report id, no padding). Notifications on
FFF1 may contain several concatenated frames and may be split across
notifications, so use :class:`FrameStream` to reassemble them.

Everything here is pure python so it can be unit tested without Bluetooth.
"""

from __future__ import annotations

from dataclasses import dataclass, field

MAGIC = b"\x5a\xa5"

# --- command ids ---------------------------------------------------------
CMD_QUERY_FIRMWARE = 0x01
CMD_QUERY_CONFIG_STATE = 0x02
CMD_INITIALIZE = 0x03
CMD_QUERY_DEVICE_ID = 0x04
CMD_POWER_ON = 0x05
CMD_POWER_OFF = 0x06
CMD_QUERY_CAPABILITY = 0x07
CMD_SET_FIXED_GEAR = 0x08
CMD_QUERY_IDENTITY = 0x0B
CMD_SET_POWER_ON_START = 0x0C
CMD_SET_SMART_START_STOP = 0x0D
CMD_SET_REALTIME_RPM = 0x21
CMD_QUERY_RPM_STATE = 0x22
CMD_ENTER_REALTIME_RPM = 0x23
CMD_EXIT_REALTIME_RPM = 0x24
CMD_QUERY_WORK_MODE = 0x25
CMD_SET_GEAR_RPM = 0x26
CMD_QUERY_GEAR_TABLE = 0x27
CMD_RGB_UPLOAD_INIT = 0x41
CMD_RGB_COMMIT = 0x43
CMD_RGB_DYNAMIC_PARAM = 0x44
CMD_RGB_STATUS = 0x45
CMD_RGB_ENABLE = 0x46
CMD_RGB_FRAME_WRITE = 0x47
CMD_GEAR_LIGHT = 0x48
CMD_STATUS_NOTIFY = 0xEF

ACK_OK = 0x01

# Smart start/stop modes (payload values for 0x0D). The 0xEF status frame
# reports the active mode in bits 0x0E of its second byte.
SMART_STOP_OFF = 0
SMART_STOP_IMMEDIATE = 1
SMART_STOP_DELAYED = 2
SMART_STOP_MODES = (SMART_STOP_OFF, SMART_STOP_IMMEDIATE, SMART_STOP_DELAYED)

_STATUS_SMART_STOP = {
    0x02: SMART_STOP_OFF,
    0x04: SMART_STOP_IMMEDIATE,
    0x08: SMART_STOP_DELAYED,
}

MIN_RPM = 800
DEFAULT_MAX_RPM = 4000
STOPPED_RPM = 0


def checksum(cmd: int, payload: bytes) -> int:
    return (cmd + 2 + len(payload) + sum(payload)) & 0xFF


def build_frame(cmd: int, payload: bytes = b"") -> bytes:
    """Build one wire frame (no report id, no padding)."""
    return (
        bytes([0x5A, 0xA5, cmd, 2 + len(payload)])
        + payload
        + bytes([checksum(cmd, payload)])
    )


@dataclass
class Frame:
    cmd: int
    payload: bytes


@dataclass
class DeviceState:
    """State assembled from device replies/notifications."""

    current_rpm: int = 0
    target_rpm: int = 0
    gear: int = 1  # 1..4 selected fixed gear
    max_gear: int = 4
    realtime: bool = False
    gear_rpm: dict[int, int] = field(default_factory=dict)
    firmware: str | None = None
    # 0 = off, 1 = immediate, 2 = delayed; None until the device reports it.
    smart_stop: int | None = None

    @property
    def max_rpm(self) -> int:
        return max(self.gear_rpm.values()) if self.gear_rpm else DEFAULT_MAX_RPM


class FrameStream:
    """Reassembles concatenated/split frames from a notification stream."""

    MAX_BUFFER = 4096

    def __init__(self) -> None:
        self._buf = bytearray()

    def feed(self, data: bytes) -> list[Frame]:
        self._buf.extend(data)
        frames: list[Frame] = []

        while True:
            idx = self._buf.find(MAGIC)
            if idx < 0:
                # keep a trailing 0x5a in case the magic is split
                self._buf = self._buf[-1:] if self._buf[-1:] == b"\x5a" else bytearray()
                break
            if idx:
                del self._buf[:idx]
            if len(self._buf) < 5:
                break

            length = self._buf[3]
            if length < 2 or length > 64:
                del self._buf[:2]
                continue

            total = 2 + length + 1
            if len(self._buf) < total:
                break

            cmd = self._buf[2]
            payload = bytes(self._buf[4 : 2 + length])
            frames.append(Frame(cmd=cmd, payload=payload))
            del self._buf[:total]

        if len(self._buf) > self.MAX_BUFFER:
            self._buf.clear()
        return frames


def parse_status(frame: Frame, state: DeviceState) -> bool:
    """Apply a 0xEF status notification to ``state``. Returns True if applied."""
    if frame.cmd != CMD_STATUS_NOTIFY or len(frame.payload) < 7:
        return False
    p = frame.payload
    state.current_rpm = p[3] | (p[4] << 8)
    state.target_rpm = p[5] | (p[6] << 8)
    if state.target_rpm <= 0:
        # Device can keep reporting the last measured RPM for a while after
        # the fan was stopped; treat "no target" as stopped so the fan entity
        # does not flip back to on while spinning down.
        state.current_rpm = 0
    state.realtime = bool(p[1] & 0x01)
    smart_stop = _STATUS_SMART_STOP.get(p[1] & 0x0E)
    if smart_stop is not None:
        state.smart_stop = smart_stop

    gear_code = p[0] & 0x0F
    if 0x8 <= gear_code <= 0xE and gear_code % 2 == 0:
        state.gear = (gear_code - 0x8) // 2 + 1
    max_code = (p[0] >> 4) & 0x0F
    if max_code:
        state.max_gear = max(1, max_code // 2)
    return True


def apply_reply(frame: Frame, state: DeviceState) -> None:
    """Apply a synchronous query reply to ``state``."""
    p = frame.payload
    if frame.cmd == CMD_QUERY_RPM_STATE and len(p) >= 4:
        state.current_rpm = p[0] | (p[1] << 8)
        state.target_rpm = p[2] | (p[3] << 8)
        if state.target_rpm <= 0:
            state.current_rpm = 0
    elif frame.cmd == CMD_QUERY_WORK_MODE and len(p) >= 1:
        work = p[0]
        if 1 <= work <= 4:
            state.gear = work
            state.realtime = False
        else:
            state.realtime = True
    elif frame.cmd == CMD_QUERY_GEAR_TABLE and len(p) >= 2:
        gears: dict[int, int] = {}
        for i in range(min(len(p) // 2, 4)):
            gears[i + 1] = p[i * 2] | (p[i * 2 + 1] << 8)
        if gears:
            state.gear_rpm = gears
    elif frame.cmd == CMD_QUERY_FIRMWARE and len(p) >= 4:
        state.firmware = ".".join(str(b) for b in p[:4])


# --- command builders ----------------------------------------------------
def cmd_power_on() -> bytes:
    return build_frame(CMD_POWER_ON)


def cmd_power_off() -> bytes:
    return build_frame(CMD_POWER_OFF)


def cmd_set_gear(gear: int) -> bytes:
    """Select fixed gear 1..4. Does not write flash."""
    if not 1 <= gear <= 4:
        raise ValueError("gear must be 1..4")
    return build_frame(CMD_SET_FIXED_GEAR, bytes([gear]))


def cmd_enter_realtime() -> bytes:
    return build_frame(CMD_ENTER_REALTIME_RPM)


def cmd_exit_realtime() -> bytes:
    return build_frame(CMD_EXIT_REALTIME_RPM)


def cmd_set_rpm(rpm: int, max_rpm: int = DEFAULT_MAX_RPM) -> bytes:
    rpm = max(0, min(rpm, max(max_rpm, MIN_RPM)))
    return build_frame(CMD_SET_REALTIME_RPM, bytes([rpm & 0xFF, (rpm >> 8) & 0xFF]))


def cmd_query_rpm() -> bytes:
    return build_frame(CMD_QUERY_RPM_STATE)


def cmd_query_work_mode() -> bytes:
    return build_frame(CMD_QUERY_WORK_MODE)


def cmd_query_gear_table() -> bytes:
    return build_frame(CMD_QUERY_GEAR_TABLE)


def cmd_query_firmware() -> bytes:
    return build_frame(CMD_QUERY_FIRMWARE)


def cmd_set_smart_start_stop(mode: int) -> bytes:
    """0 = off, 1 = immediate, 2 = delayed. Writes flash on change."""
    if mode not in SMART_STOP_MODES:
        raise ValueError("smart start/stop mode must be 0, 1 or 2")
    return build_frame(CMD_SET_SMART_START_STOP, bytes([mode & 0xFF]))


def cmd_set_power_on_start(enabled: bool) -> bytes:
    """Writes flash on change."""
    return build_frame(CMD_SET_POWER_ON_START, bytes([1 if enabled else 2]))


def cmd_set_gear_light(enabled: bool) -> bytes:
    """Turn the 4 gear indicator LEDs on/off (0x48).

    The firmware erases a flash page on every call and does not compare the
    new value with the stored one, so only send this when the state changes.
    """
    return build_frame(CMD_GEAR_LIGHT, bytes([1 if enabled else 0]))


def cmd_set_gear_rpm(gear: int, rpm: int) -> bytes:
    """Writes flash on every call. Not used by the integration."""
    if not 1 <= gear <= 4:
        raise ValueError("gear must be 1..4")
    return build_frame(
        CMD_SET_GEAR_RPM, bytes([gear - 1, rpm & 0xFF, (rpm >> 8) & 0xFF])
    )


def cmd_rgb_preset(preset: int) -> bytes:
    """0 = stop/reset animation, 1..5 = built-in presets. No flash write."""
    return build_frame(CMD_RGB_DYNAMIC_PARAM, bytes([preset & 0xFF]))


def cmd_rgb_enable(enabled: bool) -> bytes:
    """Turn the LED output on/off (0x46).

    This is the actual light switch: ``0x44`` only selects an animation, it
    does not enable the LED output. The firmware erases a flash page on every
    call (no value comparison), so only send it when the state changes.
    """
    return build_frame(CMD_RGB_ENABLE, bytes([1 if enabled else 0]))


def cmd_rgb_upload_init() -> bytes:
    """Start a frame-buffer upload (0x41). Does not write flash."""
    return build_frame(CMD_RGB_UPLOAD_INIT)


def cmd_rgb_frame_write(index: int, data: bytes) -> bytes:
    """Write 10 bytes of the program at frame ``index`` (0x47)."""
    return build_frame(CMD_RGB_FRAME_WRITE, bytes([index & 0xFF]) + bytes(data))


def cmd_rgb_commit() -> bytes:
    """Apply the uploaded program (0x43). Erases a flash page."""
    return build_frame(CMD_RGB_COMMIT, b"\x01")
