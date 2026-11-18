"""Operating-mode and fan-speed selectors for the AI climate system."""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .entity import device_info
from .protocol import FAN_SPEED_LABELS, MODE_LABELS
from .websocket_client import AirspaWebsocketClient


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    client: AirspaWebsocketClient = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            AirspaModeSelect(client, entry),
            AirspaFanSpeedSelect(client, entry),
        ]
    )


class AirspaModeSelect(SelectEntity):
    """Show and select one of the four captured operating modes."""

    _attr_should_poll = False
    _attr_has_entity_name = True
    _attr_name = "运行模式"
    _attr_icon = "mdi:air-filter"
    _attr_options = list(MODE_LABELS.values())

    def __init__(self, client: AirspaWebsocketClient, entry: ConfigEntry) -> None:
        self.client = client
        self._attr_unique_id = f"{entry.unique_id}_mode"
        self._attr_device_info = device_info(entry)

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(self.client.register_callback(self._handle_update))

    def _handle_update(self) -> None:
        self.async_write_ha_state()

    @property
    def available(self) -> bool:
        return self.client.is_connected and "mode" in self.client.status

    @property
    def current_option(self) -> str | None:
        return MODE_LABELS.get(self.client.status.get("mode"))

    async def async_select_option(self, option: str, **kwargs) -> None:
        for mode, label in MODE_LABELS.items():
            if label == option:
                await self.client.async_set_mode(mode)
                return
        raise ValueError(f"Unsupported mode: {option}")


class AirspaFanSpeedSelect(SelectEntity):
    """Select automatic or one of five captured fan speeds."""

    _attr_should_poll = False
    _attr_has_entity_name = True
    _attr_name = "风速"
    _attr_icon = "mdi:fan"
    _attr_options = list(FAN_SPEED_LABELS.values())

    def __init__(self, client: AirspaWebsocketClient, entry: ConfigEntry) -> None:
        self.client = client
        self._attr_unique_id = f"{entry.unique_id}_fan_speed"
        self._attr_device_info = device_info(entry)

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(self.client.register_callback(self._handle_update))

    def _handle_update(self) -> None:
        self.async_write_ha_state()

    @property
    def available(self) -> bool:
        return self.client.is_connected and "fan_speed" in self.client.status

    @property
    def current_option(self) -> str | None:
        return FAN_SPEED_LABELS.get(self.client.status.get("fan_speed"))

    async def async_select_option(self, option: str, **kwargs) -> None:
        for speed, label in FAN_SPEED_LABELS.items():
            if label == option:
                await self.client.async_set_fan_speed(speed)
                return
        raise ValueError(f"Unsupported fan speed: {option}")
