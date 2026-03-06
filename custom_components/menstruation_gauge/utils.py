"""Utility functions for menstruation gauge integration."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from aiohttp.web import Application
    from homeassistant.core import HomeAssistant


def register_static_path(app: Application, url_path: str, local_path: Path) -> None:
    """Register a static file path with the HTTP app."""
    # Extract the directory path from URL
    url_dir = "/".join(url_path.split("/")[:-1])
    local_dir = local_path.parent
    
    # Register static route - serve files from local_dir at url_dir
    app.router.add_static(url_dir, str(local_dir))


async def init_resource(hass: HomeAssistant, url_path: str, version: str) -> None:
    """Initialize Lovelace resource for the card."""
    # Note: Automatic resource registration may not be available in all HA versions.
    # The static file is served and can be added manually via:
    # Settings > Dashboards > Resources > + Add Resource
    # URL: /local/menstruation_gauge/www/menstruation-gauge-card.js
    # Type: JavaScript Module
    pass
