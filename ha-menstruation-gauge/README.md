# Menstruation Gauge (Home Assistant Integration)

Home Assistant custom integration for cycle tracking and forecast attributes.

## Features
- Persistent storage of cycle start dates
- Forecast attributes on `sensor.menstruation_gauge`
- Services to add/remove/update history
- Automatically installs the Lovelace card during setup

## Install (HACS custom repository)

The integration automatically installs the Lovelace card - no separate installation needed!

1. HACS -> `...` -> Custom repositories
2. Add `https://github.com/nremey/HA_menstrual_gauge` as category `Integration`
3. Install **Menstruation Gauge**
4. Restart Home Assistant
5. Add the integration via UI (Settings > Devices & Services > Add Integration) or add to `configuration.yaml`:

```yaml
menstruation_gauge:
```

6. Restart Home Assistant again (if using YAML)

**Note:** The card file is automatically copied to `/config/www/community/menstruation_gauge/menstruation-gauge-card.js`. You just need to add it as a Lovelace resource in your dashboard settings.

## Monorepo layout
This project lives in one repository (`nremey/HA_menstrual_gauge`) with both components:
- Integration files: `custom_components/menstruation_gauge/` (at repository root)
- Card files: `lovelace-menstruation-gauge-card/`

The integration is structured at the repository root for HACS compatibility.

## Sensor
- Entity: `sensor.menstruation_gauge`
- State values: `neutral`, `period`, `fertile`, `pms`
- Attributes include history and forecast fields

## Services
- `menstruation_gauge.add_cycle_start` `{ date: "YYYY-MM-DD" }`
- `menstruation_gauge.remove_cycle_start` `{ date: "YYYY-MM-DD" }`
- `menstruation_gauge.set_history` `{ dates: ["YYYY-MM-DD", ...] }`
- `menstruation_gauge.set_period_duration` `{ days: 1..14 }`

## Notes
- This integration is for orientation and tracking support only.
- See disclaimer file for reliability limits.

## Development
Before publishing:
- create GitHub release tags (`v0.1.0`, ...)
