"""Power, mode and auxiliary switches for the AI climate system."""

from __future__ import annotations

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .entity import device_info
from .protocol import (
    MODE_LABELS,
    NEGATIVE_ION_OFF_RAW,
    NEGATIVE_ION_ON_RAW,
    SLEEP_OFF_RAW,
    SLEEP_ON_RAW,
    SWING_OFF_RAW,
    SWING_ON_RAW,
)
from .websocket_client import AirspaWebsocketClient


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    client: AirspaWebsocketClient = hass.data[DOMAIN][entry.entry_id]
    entities: list[SwitchEntity] = [
        AirspaPowerSwitch(client, entry),
        AirspaBooleanSwitch(
            client,
            entry,
            key="sleep",
            display_name="睡眠模式",
            icon="mdi:sleep",
            unique_suffix="sleep",
            on_raw=SLEEP_ON_RAW,
            off_raw=SLEEP_OFF_RAW,
        ),
        AirspaBooleanSwitch(
            client,
            entry,
            key="negative_ion",
            display_name="负离子",
            icon="mdi:atom",
            unique_suffix="negative_ion",
            on_raw=NEGATIVE_ION_ON_RAW,
            off_raw=NEGATIVE_ION_OFF_RAW,
        ),
        AirspaBooleanSwitch(
            client,
            entry,
            key="swing",
            display_name="摆风",
            icon="mdi:weather-windy",
            unique_suffix="swing",
            on_raw=SWING_ON_RAW,
            off_raw=SWING_OFF_RAW,
        ),
    ]

    for mode, label in MODE_LABELS.items():
        entities.append(
            AirspaModeSwitch(
                client,
                entry,
                mode=mode,
                label=label,
            )
        )

    async_add_entities(entities)


class AirspaPowerSwitch(SwitchEntity):
    """Power switch styled like the negative-ion and sleep switches."""

    _attr_should_poll = False
    _attr_has_entity_name = True
    _attr_name = "开关"
    _attr_icon = "mdi:power"

    def __init__(self, client: AirspaWebsocketClient, entry: ConfigEntry) -> None:
        self.client = client
        self._attr_unique_id = f"{entry.unique_id}_power"
        self._attr_device_info = device_info(entry)

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(self.client.register_callback(self._handle_update))

    def _handle_update(self) -> None:
        self.async_write_ha_state()

    @property
    def available(self) -> bool:
        return self.client.is_connected and "power" in self.client.status

    @property
    def is_on(self) -> bool:
        return self.client.status.get("power") == 1

    async def async_turn_on(self, **kwargs) -> None:
        await self.client.async_set_power(True)

    async def async_turn_off(self, **kwargs) -> None:
        await self.client.async_set_power(False)


class AirspaModeSwitch(SwitchEntity):
    """One mutually-exclusive mode switch, styled like the ion switch."""

    _attr_should_poll = False
    _attr_has_entity_name = True
    _attr_icon = "mdi:air-conditioner"

    def __init__(
        self,
        client: AirspaWebsocketClient,
        entry: ConfigEntry,
        *,
        mode: int,
        label: str,
    ) -> None:
        self.client = client
        self._mode = mode
        self._attr_name = label
        self._attr_unique_id = f"{entry.unique_id}_mode_switch_{mode}"
        self._attr_device_info = device_info(entry)

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(self.client.register_callback(self._handle_update))

    def _handle_update(self) -> None:
        self.async_write_ha_state()

    @property
    def available(self) -> bool:
        return (
            self.client.is_connected
            and "power" in self.client.status
            and "mode" in self.client.status
        )

    @property
    def is_on(self) -> bool:
        return (
            self.client.status.get("power") == 1
            and self.client.status.get("mode") == self._mode
        )

    async def async_turn_on(self, **kwargs) -> None:
        await self.client.async_set_controls(
            {"power": True, "mode": self._mode}
        )

    async def async_turn_off(self, **kwargs) -> None:
        if self.is_on:
            await self.client.async_set_controls({"power": False})


class AirspaBooleanSwitch(SwitchEntity):
    """One captured on/off function backed by a single status byte."""

    _attr_should_poll = False
    _attr_has_entity_name = True

    def __init__(
        self,
        client: AirspaWebsocketClient,
        entry: ConfigEntry,
        *,
        key: str,
        display_name: str,
        icon: str,
        unique_suffix: str,
        on_raw: str,
        off_raw: str,
    ) -> None:
        self.client = client
        self._key = key
        self._on_raw = on_raw
        self._off_raw = off_raw
        self._attr_name = display_name
        self._attr_icon = icon
        self._attr_unique_id = f"{entry.unique_id}_{unique_suffix}"
        self._attr_device_info = device_info(entry)

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(self.client.register_callback(self._handle_update))

    def _handle_update(self) -> None:
        self.async_write_ha_state()

    @property
    def available(self) -> bool:
        return self.client.is_connected and self._key in self.client.status

    @property
    def is_on(self) -> bool:
        return self.client.status.get(self._key) == 1

    async def async_turn_on(self, **kwargs) -> None:
        await self.client.async_set_raw_command(self._on_raw, f"开启{self._attr_name}")

    async def async_turn_off(self, **kwargs) -> None:
        await self.client.async_set_raw_command(self._off_raw, f"关闭{self._attr_name}")
