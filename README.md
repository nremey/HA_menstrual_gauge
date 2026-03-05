# HA_menstrual_gauge

<img width="30%" height="30%" alt="normal card view" src="https://github.com/user-attachments/assets/6fb8fb40-e42b-4243-bd52-3cb5f3d7bf8d" /> <img width="30%" height="30%" alt="click a day to set/delete a cycle start date" src="https://github.com/user-attachments/assets/cadb8113-fabb-4eb6-9611-a1901db311d4" />







Monorepo for a Home Assistant menstruation tracker:
- `ha-menstruation-gauge` (backend integration)
- `lovelace-menstruation-gauge-card` (interactive Lovelace card)

Repository target: `https://github.com/nremey/HA_menstrual_gauge`

## What is included

### 1) Home Assistant integration (`ha-menstruation-gauge`)
- Stores cycle-start history persistently (local HA storage).
- Publishes `sensor.menstruation_gauge`.
- Provides forecast-related attributes (e.g. `days_until_next_start`, predicted start, fertile window).
- Exposes services:
  - `menstruation_gauge.add_cycle_start`
  - `menstruation_gauge.remove_cycle_start`
  - `menstruation_gauge.set_history`
  - `menstruation_gauge.set_period_duration`

### 2) Lovelace card (`lovelace-menstruation-gauge-card`)
- Circular monthly gauge view.
- Forecast marker (+/-1 day).
- Fertile-window ring segment.
- Click-to-edit mini calendar (add/remove cycle start days).
- Uses the integration sensor and services.

## Installation via HACS (Recommended)

The integration automatically installs the Lovelace card when you install the integration - no separate installation needed!

### Install Integration (Card Included)

1. Open HACS in Home Assistant
2. Go to `...` (three dots menu) → `Custom repositories`
3. Add repository:
   - Repository: `https://github.com/nremey/HA_menstrual_gauge`
   - Category: **Integration**
4. Click `Install` on "Menstruation Gauge"
5. Restart Home Assistant
6. The integration can be added via UI (Settings > Devices & Services > Add Integration) or add to `configuration.yaml`:

```yaml
menstruation_gauge:
```

7. Restart Home Assistant again (if using YAML)

**Note:** The Lovelace card is automatically copied to `/config/www/community/menstruation_gauge/menstruation-gauge-card.js` during integration setup. You just need to add it as a Lovelace resource (see below).

## Manual Installation (without HACS)

1. Copy integration folder:
- From: `custom_components/menstruation_gauge`
- To: `/config/custom_components/menstruation_gauge`

2. Add to `configuration.yaml`:

```yaml
menstruation_gauge:
```

3. Restart Home Assistant.

**Note:** The card file is automatically copied to `/config/www/community/menstruation_gauge/menstruation-gauge-card.js` when the integration loads. If you need to copy it manually, it's located at `custom_components/menstruation_gauge/frontend/menstruation-gauge-card.js`.

4. Add Lovelace resource:

## How to add Lovelace resource (UI steps)

1. Open Home Assistant.
2. Go to `Settings` -> `Dashboards`.
3. Open your target dashboard.
4. Click `⋮` (top right) -> `Resources`.
5. Click `+ Add Resource`.
6. Enter:
   - URL: `/local/community/menstruation_gauge/menstruation-gauge-card.js`
   - Type: `JavaScript Module`
7. Save and reload browser (hard refresh recommended).



## Add a custom gauge card this way:

```yaml
type: custom:menstruation-gauge-card
entity: sensor.menstruation_gauge
period_duration_days: 5
show_editor: true
```


## Disclaimer

This project is for orientation and personal tracking support only.
It is not medical advice and not suitable as a reliable method for contraception or conception planning.

The sensor.menstruation_gauge may be used for automation as you see fit. An Automation template (adding item to a shopping list) for an example is found in the ReadMe.md of the lovelace-mentruation-gauge-card folder.


## AI note

A significant part of this project was created with AI assistance (OpenAI Codex), then reviewed and adjusted manually.  
It is tested in practical use, but edge cases may still exist.
