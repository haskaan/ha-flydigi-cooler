<p align="center">
  <img src="https://raw.githubusercontent.com/haskaan/ha-flydigi-cooler/main/custom_components/flydigi_cooler/brand/icon@2x.png" alt="Flydigi Cooler" width="200">
</p>

<h1 align="center">Flydigi Cooler for Home Assistant</h1>

<p align="center">
  <a href="https://hacs.xyz"><img alt="HACS" src="https://img.shields.io/badge/HACS-Custom-41BDF5.svg"></a>
  <img alt="Home Assistant" src="https://img.shields.io/badge/Home%20Assistant-2024.6%2B-41BDF5.svg">
  <a href="https://github.com/haskaan/ha-flydigi-cooler/releases"><img alt="Release" src="https://img.shields.io/github/v/release/haskaan/ha-flydigi-cooler?label=release&sort=semver"></a>
</p>

<p align="center">
  <a href="https://analytics.home-assistant.io/"><img alt="HA installs" src="https://img.shields.io/badge/dynamic/json?url=https%3A%2F%2Fanalytics.home-assistant.io%2Fcustom_integrations.json&amp;query=%24.flydigi_cooler.total&amp;label=HA%20installs&amp;color=41BDF5&amp;logo=home-assistant&amp;logoColor=white"></a>
  <a href="https://github.com/haskaan/ha-flydigi-cooler/stargazers"><img alt="Stars" src="https://img.shields.io/github/stars/haskaan/ha-flydigi-cooler.svg?logo=github"></a>
  <a href="https://github.com/haskaan/ha-flydigi-cooler/issues"><img alt="Issues" src="https://img.shields.io/github/issues/haskaan/ha-flydigi-cooler.svg"></a>
  <a href="https://github.com/haskaan/ha-flydigi-cooler/actions/workflows/validate.yml"><img alt="Validate" src="https://img.shields.io/github/actions/workflow/status/haskaan/ha-flydigi-cooler/validate.yml?label=validate"></a>
</p>

<p align="center">
  Integration for <b>Flydigi BS2 / BS2 Pro / BS3 / BS3 Pro</b> laptop cooling pads.<br>
  Control the fan, modes and levels, the RGB light and the device settings over Bluetooth LE.
</p>

<p align="center">
  <sub><b>Unofficial community project.</b> Not affiliated with, endorsed by, or supported by Flydigi.
  "Flydigi" is a trademark of its respective owner and is used here only to describe the hardware
  this integration works with. Built on a community reverse-engineered protocol — use at your own risk.</sub>
</p>

<p align="center">
  If you find this integration useful, please give it a ⭐ on GitHub.
  <br>
  <sub><i>Türkçe dokümantasyon: <a href="README.tr.md">README.tr.md</a></i></sub>
</p>

---

## Installation

### Option 1. Using HACS (recommended)

1. Install [HACS](https://hacs.xyz) if you have not already.
2. Open HACS → Integrations.
3. Search for **Flydigi Cooler** and install it.
4. Restart Home Assistant.

### Option 2. Using HACS as a custom repository

Use this if **Flydigi Cooler** does not show up in the HACS search.

1. Install [HACS](https://hacs.xyz) if you have not already.
2. Open HACS → Integrations → ⋮ → **Custom repositories**.
3. Add `https://github.com/haskaan/ha-flydigi-cooler` with category **Integration**.
4. Search for **Flydigi Cooler** on the HACS integration page and install it.
5. Restart Home Assistant.

### Option 3. Manually

1. Open the directory for your HA configuration (where `configuration.yaml` lives).
2. If there is no `custom_components` directory, create it.
3. Inside `custom_components`, create a new folder called `flydigi_cooler`.
4. Download all files from the `custom_components/flydigi_cooler/` directory in this repository.
5. Place the downloaded files in the folder you created.
6. Restart Home Assistant.

## Configuration

### Adding the device

**Settings → Devices & Services → Add Integration → Flydigi Cooler.**

If the device is advertising in pairing mode it shows up as **Discovered** —
just confirm. Otherwise pick it from the discovered list, or enter the
Bluetooth address manually.

## Requirements

- Home Assistant 2024.6 or newer, with the Bluetooth integration working
- The device in range and powered on
- The device must **not** be connected to another host (e.g. a laptop running
  Flydigi Space Station)

> BLE peripherals usually accept a single connection. Home Assistant and the
> Windows app cannot be connected at the same time. Turn off Flydigi Space
> Station (or that laptop's Bluetooth) while using Home Assistant.

## Features

| Platform | Entity | Description |
| --- | --- | --- |
| `fan` | Main fan | On/off, percentage speed (real-time RPM), preset modes (Silent / Standard / Strong / Overclock) |
| `select` | Level | One of 3 speed levels of the active mode (`1` / `2` / `3`) |
| `select` | Smart stop | Fan behaviour when the PC powers off (`Off` / `Immediate` / `Delayed`; `0x0D`) |
| `switch` | Gear light | The 4 gear LEDs on the device (`0x48`) |
| `switch` | Power-on start | Start the fan automatically when power is applied (`0x0C`) |
| `light` | RGB light | On/off, effect, brightness and colour |
| `number` | Light speed | Animation speed (0 slow – 100 fast) |
| `sensor` | Current RPM | RPM measured by the device |
| `sensor` | Target RPM | RPM the device is aiming for |
| `sensor` | Control mode | `Fixed gear` / `Real-time` |
| `sensor` | Selected gear | Active mode name; raw gear index in the `gear` attribute |
| `sensor` | Firmware | e.g. `0.0.2.4` |

Entity display names are translated (`en` / `tr`). Entity IDs always stay in
English (`current_rpm`, `control_mode`, …), so changing the UI language does not
break your automations.

## Supported devices

| Model | Status |
| --- | --- |
| BS3 Pro | Tested |
| BS3 | Expected to work |
| BS2 Pro | Expected to work |
| BS2 | Expected to work |

Multiple coolers can be added at the same time (e.g. a BS3 Pro and a BS2 Pro).
Each device gets its own config entry and entities. The model name is read from
the Bluetooth advertisement (`FlyDigi BS2PRO`, `FlyDigi BS3PRO`, …) and falls
back to the model number in the Device Information service.

## Modes and levels

The fan card exposes 4 modes; `select.<device>_level` picks one of 3 levels per
mode:

| Mode | Level 1 | Level 2 | Level 3 |
| --- | ---: | ---: | ---: |
| Silent | 1300 | 1700 | 1900 |
| Standard | 2100 | 2400 | 2700 |
| Strong | 2900 | 3000 | 3300 |
| Overclock | 3400 | 3700 | 4000 |

Levels are **not** written into the device's fixed gear table; they are applied
as **real-time RPM** (no flash write). The gears selected with the device's own
button map to the same mode names: Gear 1 = Silent, Gear 2 = Standard,
Gear 3 = Strong, Gear 4 = Overclock. Selecting a gear with the button moves the
level to the one matching that gear's RPM (e.g. Gear 2 → Standard 3).

> **Every mode remembers its own level.** If you pick Silent 2 and then switch
> to Strong, coming back to Silent keeps **2**. Selections are stored in
> `.storage` and survive a restart. In automations therefore call
> **`fan.set_preset_mode` (mode) first, then `select.select_option` (level)** —
> the level is saved into the mode that is active at that moment.

The fixed gears are read from the device (observed on one unit:
1300 / 2700 / 3000 / **4000** RPM; percentage calculations use the highest gear
as the upper bound).

The device pushes a status notification (`0xEF`) once per second; the
integration forwards these to entities at most every 3 seconds (the 30 s poll
stays as a fallback). When the fan is turned off the **target RPM becomes 0** and
the fan counts as off, even if the device keeps reporting the last measured RPM
for a few seconds (this prevents the toggle from flipping back on).

Turning the fan back on restores the **last mode**: if a mode/level was selected
before switching off, the same mode and level come back (e.g. Standard 2 →
2400 RPM); in percentage mode the same target RPM returns (e.g. 60% → 2720 RPM).
The selection is stored in `.storage` and survives restarts. Gear changes made
with the device's own button are tracked too. While the fan is off the card still
shows the last mode and level as **selected**; in percentage mode no preset/level
is shown as selected (the percentage comes back when you turn it on).

## Light (RGB)

`light.<device>_light` — on/off, brightness, colour and effect selection.

On/off uses `0x46` (the only command that enables/disables the LED output;
`0x44` merely selects an animation). Effects are uploaded to the device as a
**program** (`0x41` init → 19 × `0x47` frames → `0x43` commit); the firmware
interpolates between frames.

| Effect | Behaviour |
| --- | --- |
| Static | Single colour, steady |
| Multi color | Red / green / blue, steady |
| Rotation | Single dot rotating in the selected colour |
| Flowing | Six-colour rainbow flow |
| Breathing | Breathing in the selected colour |

Brightness is applied by the firmware (0–100). The `0x43` commit erases one
flash page on every effect change. Effect, colour and brightness are stored in
`.storage`. The uploaded program lives in RAM and is lost when the device loses
power with the PC; turning the light on again re-uploads the remembered effect.
If the light is already on and nothing changed, no command is sent. The light is
independent of the fan: turning the fan on or off does not change it.

Animation speed is set with `number.<device>_light_speed` (0–100; 100 = fast,
0 = slow, the same scale as "Speed" in the official app). Changing the speed
re-uploads the effect at the new speed.

## Device settings (flash)

These three settings are written to the device's own flash and stay active even
when Home Assistant is off. Each write erases a flash page, so the integration
sends the command **only when the value actually changes** and **only when you
change it yourself**.

| Entity | Command | Behaviour |
| --- | --- | --- |
| `select.<device>_smart_stop` | `0x0D` | **Off:** feature disabled. **Immediate:** fan stops as soon as the PC powers off. **Delayed:** keeps running for a while to push the hot air out (the cooler must stay powered). |
| `switch.<device>_gear_light` | `0x48` | Turns the 4 gear LEDs above the RGB strip on/off. |
| `switch.<device>_power_on_start` | `0x0C` | Starts with the last mode as soon as the device receives power (smart plug, dock) without pressing the button. |

- **None of these commands are sent while Home Assistant starts or reconnects.**
  At startup only `0x23` / `0x21` / `0x08` (real-time RPM and gear) are used, and
  they do not write to flash.
- The smart-stop mode is read from the device via `0xEF` (byte 2, bits `0x0E`),
  so the select always shows the hardware's real value without writing.
- Gear light and power-on start are not reported by the device; their last value
  is stored in `.storage` and marked optimistic.
- `0x48` is not compared by the firmware: even re-sending the same value erases
  a flash page. The integration therefore caches the value and never re-sends it.
  `0x0C` / `0x0D` are compared by the firmware.

## Pairing and address changes

The device has no separate pairing button. The only method from the manual:

> Hold the power button for **10 seconds** — the gear indicator blinks and the
> Bluetooth pairing information is erased. The device then accepts a new
> connection.

This makes the device forget the host it was paired with (e.g. a Windows
laptop). While paired to one host it ignores connection requests from others at
the link layer; in an HCI log this shows up as
`0x3E Connection Failed to be Established` after `LE Connection Complete`.

The device also generates a **random static BLE address** on some boots
(observed: `DD:7F:64:2D:BA:83` → `DE:7F:64:2D:BA:83`). The integration
therefore does not rely on a fixed address: it first looks for the advertised
name (`FlyDigi BS3PRO`) or the `FFF0` service, and only then falls back to the
stored address. No extra steps are needed when the address changes.

On every successful connection the address is written to
`.storage/flydigi_cooler.<entry_id>` and tried **first** after a restart. This
matters because the device does not advertise its name/`FFF0` during normal
operation (`advertised=[]` in the logs); the name only appears in pairing mode.
If the address changes anyway, hold the power button for 10 s to enter pairing
mode; HA finds the device by name and stores the new address itself.

## Protocol (for tinkerers)

```
5A A5 <CMD> <LEN> <PAYLOAD...> <CHECKSUM>
LEN      = 2 + payload length
CHECKSUM = (CMD + LEN + payload bytes) & 0xFF
```

Transport runs over the device's custom GATT service — no HID layer needed:

| | UUID |
| --- | --- |
| Service | `0000fff0-0000-1000-8000-00805f9b34fb` |
| Write | `0000fff2-0000-1000-8000-00805f9b34fb` |
| Notify | `0000fff1-0000-1000-8000-00805f9b34fb` |

Commands used:

| CMD | Meaning |
| --- | --- |
| `0x21` | Real-time target RPM (`rpm_lo rpm_hi`) |
| `0x22` | RPM query |
| `0x23` / `0x24` | Enter / leave real-time mode |
| `0x25` | Operating mode query |
| `0x27` | Gear RPM table |
| `0x08` | Select fixed gear (no flash write) |
| `0x0C` | Power-on start (flash) |
| `0x0D` | Smart stop: 0 off / 1 immediate / 2 delayed (flash) |
| `0x48` | Gear light LEDs (flash, value not compared) |
| `0xEF` | Status notification from the device (once per second) |

Notifications may contain multiple frames, and a frame may be split across two
notifications; `protocol.FrameStream` reassembles them.

Every frame sent is logged as `tx 5a a5 …` when debug logging is enabled for the
integration, so you can verify which command went out:

```yaml
logger:
  logs:
    custom_components.flydigi_cooler: debug
```

### Commands that write to flash

`0x26` (gear RPM write), `0x46` (RGB on/off), `0x48` (gear light), `0x43` (RGB
commit), `0x0C` (power-on start) and `0x0D` (smart stop) write to the device's
flash on every call. `0x26` is never used; gears are applied with `0x08` only
(no flash write).

All other setters are skipped when the value has not changed: the known state is
stored in `.storage` and every setter first checks "is it already this value?".
None of them are sent on startup, on reconnect or during polling; a single frame
goes out only when the user changes an entity. The guard is mandatory for `0x48`
because the firmware does not compare values; for `0x0C` / `0x0D` the firmware
itself skips an unchanged write.

### Device timeout

The BS3 Pro returns to the selected fixed gear about 2 minutes after entering
real-time mode (including 0 RPM). The integration refreshes both the 0 RPM while
off and the target RPM while a mode/level or percentage is active every 60
seconds (runtime command, no flash write), so Silent / Standard / Strong /
Overclock and percentage speed do not drift.

## Troubleshooting

| Symptom | Cause / fix |
| --- | --- |
| Device not discovered | Hold the power button 10 s to enter pairing mode; make sure no other host is connected |
| `Connection Failed to be Established` | The device is still paired to another host — erase pairing (10 s hold) |
| Fan turns itself back on | Update to the latest version; off state now forces target RPM 0 |
| Mode/level drifts back after ~2 min | Keep the integration running — it refreshes the target RPM every 60 s |

## Credits

Protocol information:

- [chenqianhe/Flydigi-BS](https://github.com/chenqianhe/Flydigi-BS) — macOS BS3 controller, command set
- [TIANLI0/THRM](https://github.com/TIANLI0/THRM) — open-source control centre for the BS series, detailed protocol documentation

## License

[MIT](LICENSE)

## Disclaimer

Not affiliated with Flydigi. Use at your own risk. Commands that write to the
device's flash are only sent for settings you change manually, and only when the
value actually changes; nothing is written when Home Assistant restarts.
