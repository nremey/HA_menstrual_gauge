"""Menstruation Gauge integration.

Lightweight service-based integration that stores cycle start dates and
publishes a sensor state with derived forecast attributes.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
import logging
import os
import shutil
from pathlib import Path
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers.storage import Store

from .const import (
    ATTR_AVG_CYCLE_DAYS,
    ATTR_DAYS_UNTIL_NEXT_START,
    ATTR_FERTILE_WINDOW_END,
    ATTR_FERTILE_WINDOW_START,
    ATTR_GROUPED_CYCLE_STARTS,
    ATTR_HISTORY,
    ATTR_LAST_UPDATED,
    ATTR_NEXT_PREDICTED_START,
    ATTR_PERIOD_DURATION_DAYS,
    DATA_KEY,
    DEFAULT_ENTITY_ID,
    DEFAULT_PERIOD_DURATION_DAYS,
    DOMAIN,
    SERVICE_ADD_CYCLE_START,
    SERVICE_REMOVE_CYCLE_START,
    SERVICE_SET_HISTORY,
    SERVICE_SET_PERIOD_DURATION,
    STORE_KEY,
    STORE_VERSION,
)

_LOGGER = logging.getLogger(__name__)

DATE_RE = r"^\d{4}-\d{2}-\d{2}$"

SERVICE_SCHEMA_DATE = vol.Schema({vol.Required("date"): vol.All(str, vol.Match(DATE_RE))})
SERVICE_SCHEMA_SET_HISTORY = vol.Schema({vol.Required("dates"): [vol.All(str, vol.Match(DATE_RE))]})
SERVICE_SCHEMA_SET_DURATION = vol.Schema({vol.Required("days"): vol.All(vol.Coerce(int), vol.Range(min=1, max=14))})


def _norm_iso(value: str) -> str | None:
    try:
        return date.fromisoformat(str(value)).isoformat()
    except ValueError:
        return None


def _dedupe_sort(items: list[str]) -> list[str]:
    return sorted({x for x in (_norm_iso(v) for v in items) if x})


def _grouped_cycle_starts(history: list[str]) -> list[str]:
    grouped: list[str] = []
    sorted_days = _dedupe_sort(history)
    for idx, day in enumerate(sorted_days):
        if idx == 0:
            grouped.append(day)
            continue
        prev = date.fromisoformat(sorted_days[idx - 1])
        cur = date.fromisoformat(day)
        if (cur - prev).days > 2:
            grouped.append(day)
    return grouped


def _predict_next_start(grouped_starts: list[str]) -> tuple[str | None, int | None]:
    if not grouped_starts:
        return None, None

    if len(grouped_starts) == 1:
        base = date.fromisoformat(grouped_starts[0])
        avg = 28
        return (base + timedelta(days=avg)).isoformat(), avg

    intervals: list[int] = []
    start_index = max(1, len(grouped_starts) - 4)
    for idx in range(start_index, len(grouped_starts)):
        prev = date.fromisoformat(grouped_starts[idx - 1])
        cur = date.fromisoformat(grouped_starts[idx])
        diff = (cur - prev).days
        if 10 < diff < 80:
            intervals.append(diff)

    avg = round(sum(intervals) / len(intervals)) if intervals else 28
    last = date.fromisoformat(grouped_starts[-1])
    return (last + timedelta(days=avg)).isoformat(), avg


def _build_state_payload(data: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    history = _dedupe_sort(list(data.get("history") or []))
    period_duration_days = int(data.get("period_duration_days") or DEFAULT_PERIOD_DURATION_DAYS)
    grouped = _grouped_cycle_starts(history)
    next_pred, avg_cycle = _predict_next_start(grouped)

    today = date.today()
    days_until = None
    fertile_start = None
    fertile_end = None

    if next_pred:
        next_dt = date.fromisoformat(next_pred)
        days_until = (next_dt - today).days
        ovulation = next_dt - timedelta(days=14)
        fertile_start = (ovulation - timedelta(days=5)).isoformat()
        fertile_end = (ovulation + timedelta(days=1)).isoformat()

    is_period_today = False
    for start_iso in grouped:
        start_dt = date.fromisoformat(start_iso)
        if 0 <= (today - start_dt).days < period_duration_days:
            is_period_today = True
            break

    is_fertile_today = False
    if fertile_start and fertile_end:
        is_fertile_today = date.fromisoformat(fertile_start) <= today <= date.fromisoformat(fertile_end)

    is_pms_today = isinstance(days_until, int) and 0 <= days_until <= 3

    state = "neutral"
    if is_period_today:
        state = "period"
    elif is_fertile_today:
        state = "fertile"
    elif is_pms_today:
        state = "pms"

    attrs = {
        ATTR_HISTORY: history,
        ATTR_GROUPED_CYCLE_STARTS: grouped,
        ATTR_NEXT_PREDICTED_START: next_pred,
        ATTR_DAYS_UNTIL_NEXT_START: days_until,
        ATTR_AVG_CYCLE_DAYS: avg_cycle,
        ATTR_PERIOD_DURATION_DAYS: period_duration_days,
        ATTR_FERTILE_WINDOW_START: fertile_start,
        ATTR_FERTILE_WINDOW_END: fertile_end,
        ATTR_LAST_UPDATED: datetime.now().isoformat(timespec="seconds"),
        "friendly_name": "Menstruation Gauge",
    }
    return state, attrs


async def _push_state(hass: HomeAssistant) -> None:
    data = hass.data[DATA_KEY]
    state, attrs = _build_state_payload(data)
    hass.states.async_set(DEFAULT_ENTITY_ID, state, attrs)


async def _save_store(hass: HomeAssistant) -> None:
    data = hass.data[DATA_KEY]
    payload = {
        "history": _dedupe_sort(list(data.get("history") or [])),
        "period_duration_days": int(data.get("period_duration_days") or DEFAULT_PERIOD_DURATION_DAYS),
    }
    await data["store"].async_save(payload)


async def _copy_card_file(hass: HomeAssistant) -> None:
    """Copy the Lovelace card file to the www directory."""
    try:
        # Get the integration directory
        integration_dir = Path(__file__).parent
        card_source = integration_dir / "frontend" / "menstruation-gauge-card.js"
        
        if not card_source.exists():
            _LOGGER.warning("Card file not found at %s", card_source)
            return
        
        # Get Home Assistant config directory
        config_dir = Path(hass.config.config_dir)
        www_dir = config_dir / "www" / "community" / DOMAIN
        www_dir.mkdir(parents=True, exist_ok=True)
        
        # Destination file
        card_dest = www_dir / "menstruation-gauge-card.js"
        
        # Copy file (use sync copy since we're in async context but file ops are fast)
        # We'll use run_in_executor to avoid blocking
        def _copy():
            shutil.copy2(card_source, card_dest)
            _LOGGER.info("Card file copied to %s", card_dest)
        
        await hass.async_add_executor_job(_copy)
        
    except Exception as e:
        _LOGGER.warning("Failed to copy card file: %s", e)


async def _setup_integration(hass: HomeAssistant) -> None:
    """Set up the integration services and state."""
    async def _handle_add_cycle_start(call: ServiceCall) -> None:
        iso = _norm_iso(call.data["date"])
        if not iso:
            _LOGGER.warning("Invalid date for add_cycle_start: %s", call.data.get("date"))
            return
        items = list(hass.data[DATA_KEY]["history"])
        items.append(iso)
        hass.data[DATA_KEY]["history"] = _dedupe_sort(items)
        await _save_store(hass)
        await _push_state(hass)

    async def _handle_remove_cycle_start(call: ServiceCall) -> None:
        iso = _norm_iso(call.data["date"])
        if not iso:
            _LOGGER.warning("Invalid date for remove_cycle_start: %s", call.data.get("date"))
            return
        items = [d for d in hass.data[DATA_KEY]["history"] if d != iso]
        hass.data[DATA_KEY]["history"] = _dedupe_sort(items)
        await _save_store(hass)
        await _push_state(hass)

    async def _handle_set_history(call: ServiceCall) -> None:
        hass.data[DATA_KEY]["history"] = _dedupe_sort(call.data["dates"])
        await _save_store(hass)
        await _push_state(hass)

    async def _handle_set_period_duration(call: ServiceCall) -> None:
        hass.data[DATA_KEY]["period_duration_days"] = int(call.data["days"])
        await _save_store(hass)
        await _push_state(hass)

    hass.services.async_register(DOMAIN, SERVICE_ADD_CYCLE_START, _handle_add_cycle_start, schema=SERVICE_SCHEMA_DATE)
    hass.services.async_register(
        DOMAIN,
        SERVICE_REMOVE_CYCLE_START,
        _handle_remove_cycle_start,
        schema=SERVICE_SCHEMA_DATE,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_HISTORY,
        _handle_set_history,
        schema=SERVICE_SCHEMA_SET_HISTORY,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_PERIOD_DURATION,
        _handle_set_period_duration,
        schema=SERVICE_SCHEMA_SET_DURATION,
    )

    await _push_state(hass)


async def async_setup(hass: HomeAssistant, config: dict[str, Any]) -> bool:
    """Set up integration from configuration.yaml with `menstruation_gauge:`."""
    if DOMAIN not in config:
        return True

    store: Store = Store(hass, STORE_VERSION, STORE_KEY)
    stored = await store.async_load() or {}
    history = _dedupe_sort(list(stored.get("history") or []))
    duration = int(stored.get("period_duration_days") or DEFAULT_PERIOD_DURATION_DAYS)

    hass.data[DATA_KEY] = {
        "store": store,
        "history": history,
        "period_duration_days": max(1, min(14, duration)),
    }

    await _copy_card_file(hass)
    await _setup_integration(hass)
    _LOGGER.info("Menstruation Gauge initialized with %s history points", len(history))
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Menstruation Gauge from a config entry."""
    store: Store = Store(hass, STORE_VERSION, STORE_KEY)
    stored = await store.async_load() or {}
    history = _dedupe_sort(list(stored.get("history") or []))
    duration = int(stored.get("period_duration_days") or DEFAULT_PERIOD_DURATION_DAYS)

    hass.data[DATA_KEY] = {
        "store": store,
        "history": history,
        "period_duration_days": max(1, min(14, duration)),
    }

    await _copy_card_file(hass)
    await _setup_integration(hass)
    _LOGGER.info("Menstruation Gauge initialized with %s history points", len(history))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    # Unregister services
    hass.services.async_remove(DOMAIN, SERVICE_ADD_CYCLE_START)
    hass.services.async_remove(DOMAIN, SERVICE_REMOVE_CYCLE_START)
    hass.services.async_remove(DOMAIN, SERVICE_SET_HISTORY)
    hass.services.async_remove(DOMAIN, SERVICE_SET_PERIOD_DURATION)
    
    # Remove state
    hass.states.async_remove(DEFAULT_ENTITY_ID)
    
    # Remove data
    hass.data.pop(DATA_KEY, None)
    
    return True
