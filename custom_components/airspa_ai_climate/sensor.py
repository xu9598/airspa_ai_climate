"""Sensor entities for the AI climate raw status frame."""

from __future__ import annotations

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    CONCENTRATION_PARTS_PER_MILLION,
    PERCENTAGE,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .entity import device_info
from .protocol import air_quality_text
from .websocket_client import AirspaWebsocketClient

SENSOR_DESCRIPTIONS = (
    SensorEntityDescription(
        key="indoor_temperature",
        name="室内温度",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
    ),
    SensorEntityDescription(
        key="indoor_temperature_evaluation",
        name="室内温度评价",
        icon="mdi:thermometer-check",
    ),
    SensorEntityDescription(
        key="indoor_humidity",
        name="室内湿度",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="indoor_humidity_evaluation",
        name="室内湿度评价",
        icon="mdi:water-check",
    ),
    SensorEntityDescription(
        key="indoor_pm25",
        name="室内 PM2.5",
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        device_class=SensorDeviceClass.PM25,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="co2",
        name="室内 CO₂",
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_MILLION,
        device_class=SensorDeviceClass.CO2,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="outdoor_temperature",
        name="室外温度",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="outdoor_humidity",
        name="室外湿度",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="outdoor_pm25",
        name="室外 PM2.5",
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        device_class=SensorDeviceClass.PM25,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="air_quality_level",
        name="室外空气质量",
        icon="mdi:leaf",
    ),
    SensorEntityDescription(
        key="filter_life",
        name="滤网寿命",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:air-filter",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    client: AirspaWebsocketClient = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        AirspaSensor(client, entry, description)
        for description in SENSOR_DESCRIPTIONS
    )


class AirspaSensor(SensorEntity):
    """A push sensor backed by one parsed raw-frame field."""

    _attr_should_poll = False
    _attr_has_entity_name = True

    def __init__(
        self,
        client: AirspaWebsocketClient,
        entry: ConfigEntry,
        description: SensorEntityDescription,
    ) -> None:
        self.client = client
        self.entity_description = description
        self._attr_unique_id = f"{entry.unique_id}_{description.key}"
        self._attr_device_info = device_info(entry)

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(self.client.register_callback(self._handle_update))

    def _handle_update(self) -> None:
        self.async_write_ha_state()

    @property
    def available(self) -> bool:
        return self.client.is_connected and self.entity_description.key in self.client.status

    @property
    def native_value(self):
        value = self.client.status.get(self.entity_description.key)
        if self.entity_description.key == "air_quality_level" and value is not None:
            return air_quality_text(value)
        return value
