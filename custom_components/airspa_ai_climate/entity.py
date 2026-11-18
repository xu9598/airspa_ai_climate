"""Shared entity helpers."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry

from .const import CONF_DEVICE_ID, DOMAIN


def device_info(entry: ConfigEntry) -> dict:
    """Return one shared HA device for all integration entities."""
    device_id = entry.options.get(CONF_DEVICE_ID, entry.data[CONF_DEVICE_ID])
    return {
        "identifiers": {(DOMAIN, device_id)},
        "name": entry.title,
        "manufacturer": "艾尔斯派",
        "model": "AI 五恒系统",
    }
