"""Menstruation Gauge integration.

Lightweight service-based integration that stores cycle start dates and
publishes a sensor state with derived forecast attributes.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
import logging
from pathlib import Path
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.storage import Store

from . import utils

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

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


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

    await _setup_integration(hass)
    _LOGGER.info("Menstruation Gauge initialized with %s history points", len(history))

    # Serve lovelace card
    path = Path(__file__).parent / "www"

    try:
        utils.register_static_path(
            hass.http.app,
            "/menstruation_gauge/www/menstruation-gauge-card.js",
            path / "menstruation-gauge-card.js",
        )

        # Add card to resources
        version = getattr(hass.data["integrations"][DOMAIN], "version", "0.1.0")
        await utils.init_resource(
            hass, "/menstruation_gauge/www/menstruation-gauge-card.js", str(version)
        )
    except Exception:
        pass

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

    await _setup_integration(hass)
    _LOGGER.info("Menstruation Gauge initialized with %s history points", len(history))

    # Serve lovelace card
    path = Path(__file__).parent / "www"

    try:
        utils.register_static_path(
            hass.http.app,
            "/menstruation_gauge/www/menstruation-gauge-card.js",
            path / "menstruation-gauge-card.js",
        )

        # Add card to resources
        version = getattr(hass.data["integrations"][DOMAIN], "version", "0.1.0")
        await utils.init_resource(
            hass, "/menstruation_gauge/www/menstruation-gauge-card.js", str(version)
        )
                # 3. Tell the frontend to load this JS file as a module
        # This is what "automatically" adds it as a resource
        if "frontend" in hass.config.components:
            from homeassistant.components.frontend import add_extra_js_url
            add_extra_js_url(hass, "/menstruation_gauge/www/menstruation-gauge-card.js")

    except Exception:
        pass

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
