# Menstruation Gauge Card (Lovelace)

Lovelace custom card for menstruation cycle visualization and interaction.

## Features
- Circular monthly gauge
- Forecast marker (+/-1 day)
- Fertile window ring segment
- Clickable mini-editor to add/remove cycle starts
- Calls Home Assistant services from `menstruation_gauge` integration

## Requirements
- Home Assistant integration `menstruation_gauge` installed
- Entity available: `sensor.menstruation_gauge`

## Install (HACS custom repository)
1. HACS -> `...` -> Custom repositories
2. Add `https://github.com/nremey/HA_menstrual_gauge` as category `Dashboard` (only if you publish the card as standalone plugin entry)
3. Install **Menstruation Gauge Card**
4. Reload browser (or HA frontend)

## Manual installation (without HACS)
1. Copy `dist/menstruation-gauge-card.js` to:
   - `/config/www/community/remeys_menstrual_gauge/menstruation-gauge-card.js`
2. In Home Assistant, add Lovelace resource:
   - URL: `/local/community/remeys_menstrual_gauge/menstruation-gauge-card.js`
   - Type: `JavaScript Module`
3. Reload browser (hard refresh recommended).
4. Add the card in dashboard YAML:

```yaml
type: custom:menstruation-gauge-card
entity: sensor.menstruation_gauge
period_duration_days: 5
show_editor: true
```

## Monorepo source path
If you use a single repo (`nremey/HA_mentrual_gauge`) with both folders, take this file from:
- `lovelace-menstruation-gauge-card/dist/menstruation-gauge-card.js`

## Card config
```yaml
type: custom:menstruation-gauge-card
entity: sensor.menstruation_gauge
period_duration_days: 5
show_editor: true
```

## Automation template (shopping list)
Basic rule example using `days_until_next_start` from `sensor.menstruation_gauge`:

```yaml
alias: Menstruation shopping reminder
mode: single
trigger:
  - platform: time
    at: "08:00:00"
variables:
  days: "{{ state_attr('sensor.menstruation_gauge', 'days_until_next_start') | int(999) }}"
  xy1: 5
  xy2: 2
action:
  - choose:
      - conditions:
          - condition: template
            value_template: "{{ days >= 0 and days < xy2 }}"
        sequence:
          - service: todo.add_item
            target:
              entity_id: todo.shoppinglist
            data:
              item: "XXX3"
          - service: todo.add_item
            target:
              entity_id: todo.shoppinglist
            data:
              item: "XXX4"
      - conditions:
          - condition: template
            value_template: "{{ days >= 0 and days < xy1 }}"
        sequence:
          - service: todo.add_item
            target:
              entity_id: todo.shoppinglist
            data:
              item: "XXX1"
          - service: todo.add_item
            target:
              entity_id: todo.shoppinglist
            data:
              item: "XXX2"
```

Notes:
- `xy1` and `xy2` are your thresholds (days).
- Replace `XXX1 ... XXX4` with your product names.
- Optional: add extra checks if you want to prevent duplicate shopping-list entries.

## Disclaimer
This card is for orientation and tracking support only.
Not intended for medical diagnostics, reliable contraception, or reliable conception planning.
