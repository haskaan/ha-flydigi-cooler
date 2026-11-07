# ha-flydigi-cooler

Public HACS integration for Flydigi coolers: github.com/haskaan/ha-flydigi-cooler.
Everything in this repo is public.

## Facts
- Domain `flydigi_cooler`, BLE (`dependencies: bluetooth`), `iot_class: local_polling`.
- Models: BS1, BS2, BS2 Pro, BS3, BS3 Pro. GATT service `fff0`, write `fff2`, notify `fff1`.
- Platforms: fan, light, number, select, sensor, switch.
  Core logic: `coordinator.py`, `protocol.py`, `flydigi_client.py`.
- Minimum HA: `2024.6.0` (`hacs.json`).

## Rules
- Tests: `pip install -r requirements-dev.txt && pytest -q` (Python 3.12, `asyncio_mode = auto`).
  They must pass locally before pushing.
- CI (`.github/workflows/validate.yml`) runs hassfest, the HACS action and pytest.
- Translations: keep `strings.json` and `translations/en.json` identical; update `translations/tr.json` too.
- Update `README.md` and `README.tr.md` together.
- Release: bump `version` in `manifest.json`, then tag `vX.Y.Z` (current: `v0.1.0`). Use the `/release` skill.
- Commit messages in English.
- **No personal data:** no webhook IDs, IPs, MAC addresses, tokens or personal automations.
  Examples must use placeholders.
- Renaming an entity, unique_id, select option or service breaks users' automations:
  call it out in the commit message and the README.
