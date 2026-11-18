"""AIRSPA AI climate monitoring and power control integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import (
    CONF_APPID,
    CONF_DEVICE_ID,
    CONF_SERVER_URL,
    CONF_WS_URL,
    DEFAULT_WS_URL,
    DOMAIN,
    LEGACY_DEFAULT_WS_URLS,
    build_ws_url,
    server_base_from_ws_url,
)
from .websocket_client import AirspaWebsocketClient

PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
]


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Migrate endpoints and remove credentials this protocol never uses."""
    if entry.version > 5:
        return False

    original_version = entry.version
    data = dict(entry.data)
    options = dict(entry.options)

    if original_version < 3:
        if data.get(CONF_WS_URL) in LEGACY_DEFAULT_WS_URLS:
            data[CONF_WS_URL] = DEFAULT_WS_URL
        if options.get(CONF_WS_URL) in LEGACY_DEFAULT_WS_URLS:
            options[CONF_WS_URL] = DEFAULT_WS_URL

    if original_version < 4:
        current = {**data, **options}
        did = current.get(CONF_DEVICE_ID, "")
        ws_url = current.get(CONF_WS_URL, DEFAULT_WS_URL)
        server_base = server_base_from_ws_url(ws_url, did)
        data.setdefault(CONF_SERVER_URL, server_base)
        options.setdefault(CONF_SERVER_URL, server_base)
        if did:
            resolved = build_ws_url(server_base, did)
            data.setdefault(CONF_WS_URL, resolved)
            options.setdefault(CONF_WS_URL, resolved)

    # The custom/raw protocol never sent these credentials. Remove stale
    # values left by earlier versions instead of keeping unused secrets.
    data.pop("uid", None)
    data.pop("token", None)
    options.pop("uid", None)
    options.pop("token", None)

    hass.config_entries.async_update_entry(
        entry,
        data=data,
        options=options,
        version=5,
    )
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up the cloud client from a config entry."""
    config = {**entry.data, **entry.options}
    device_id = config[CONF_DEVICE_ID]
    ws_url = config.get(CONF_WS_URL) or build_ws_url(
        config.get(CONF_SERVER_URL, ""),
        device_id,
    )
    client = AirspaWebsocketClient(
        appid=config[CONF_APPID],
        device_id=device_id,
        ws_url=ws_url,
    )

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = client
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    await client.async_start()
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload entities and stop reconnect/heartbeat tasks."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        client = hass.data[DOMAIN].pop(entry.entry_id)
        await client.async_stop()
        if not hass.data[DOMAIN]:
            hass.data.pop(DOMAIN)
    return unload_ok
