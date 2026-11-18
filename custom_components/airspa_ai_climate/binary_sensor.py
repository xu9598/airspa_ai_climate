"""Cloud connectivity diagnostic entity."""

from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .entity import device_info
from .websocket_client import AirspaWebsocketClient


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    client: AirspaWebsocketClient = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([AirspaConnectivitySensor(client, entry)])


class AirspaConnectivitySensor(BinarySensorEntity):
    """Show whether WebSocket login has succeeded."""

    _attr_should_poll = False
    _attr_has_entity_name = True
    _attr_name = "云端连接"
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY

    def __init__(self, client: AirspaWebsocketClient, entry: ConfigEntry) -> None:
        self.client = client
        self._attr_unique_id = f"{entry.unique_id}_cloud_connection"
        self._attr_device_info = device_info(entry)

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(self.client.register_callback(self._handle_update))

    def _handle_update(self) -> None:
        self.async_write_ha_state()

    @property
    def is_on(self) -> bool:
        return self.client.is_connected

    @property
    def extra_state_attributes(self) -> dict:
        return {
            "received_status": self.client.has_data,
            "last_error": self.client.last_error or "无",
            "last_stage": self.client.last_stage,
            "last_message_cmd": self.client.last_message_cmd or "无",
            "subscription_status": self.client.subscription_status,
            "raw_frames_received": self.client.raw_frames_received,
            "refresh_reads_sent": self.client.refresh_reads_sent,
            "connection_attempts": self.client.connection_attempts,
            "login_responses": self.client.login_responses,
            "last_login_result": self.client.last_login_result,
            "last_raw_length": self.client.last_raw_length,
            "last_raw_error": self.client.last_raw_error or "无",
            "last_close_code": (
                self.client.last_close_code
                if self.client.last_close_code is not None
                else "无"
            ),
            "last_close_reason": self.client.last_close_reason or "无",
        }
