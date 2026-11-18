"""Parser for the 42-byte raw status frames seen in the mini-program capture."""

from __future__ import annotations

from typing import Any

STATUS_FRAME_LENGTH = 42

AIR_QUALITY_LABELS = {
    1: "优",
    2: "良好",
    3: "轻度污染",
    4: "中度污染",
    5: "重度污染",
    6: "严重污染",
}

# The capture changed mode with commands 0000000800 through 0000000803.
# This label order follows the order supplied by the device owner.
MODE_LABELS = {
    0: "智能",
    1: "新风",
    2: "内循环",
    3: "混风",
}

FAN_SPEED_LABELS = {
    0: "自动",
    1: "1档",
    2: "2档",
    3: "3档",
    4: "4档",
    5: "5档",
}

# Qualitative labels shown by the mini-program next to indoor temperature and
# humidity. These are derived locally; the 42-byte frame has no such fields.
COLD_LABEL = "寒冷"
MILD_LABEL = "温和"
HOT_LABEL = "炎热"
DRY_LABEL = "干燥"
COMFORTABLE_LABEL = "舒适"
HUMID_LABEL = "潮湿"

SLEEP_ON_RAW = "0000002001"
SLEEP_OFF_RAW = "0000002000"
NEGATIVE_ION_ON_RAW = "0000004001"
NEGATIVE_ION_OFF_RAW = "0000004000"
SWING_ON_RAW = "0000080001"
SWING_OFF_RAW = "0000080000"


class RawFrameError(ValueError):
    """Raised when a raw message is not a supported status frame."""


def decode_raw(raw: Any) -> bytes:
    """Decode either the captured hexadecimal string or a protocol byte array."""
    if isinstance(raw, str):
        compact = "".join(raw.split()).replace(":", "").replace("-", "")
        try:
            data = bytes.fromhex(compact)
        except ValueError as err:
            raise RawFrameError("Raw status is not valid hexadecimal") from err
    elif isinstance(raw, (bytes, bytearray)):
        data = bytes(raw)
    elif isinstance(raw, (list, tuple)):
        try:
            data = bytes(raw)
        except (TypeError, ValueError) as err:
            raise RawFrameError("Raw status is not a valid byte array") from err
    else:
        raise RawFrameError(f"Unsupported raw status type: {type(raw).__name__}")

    if len(data) != STATUS_FRAME_LENGTH:
        raise RawFrameError(
            f"Expected {STATUS_FRAME_LENGTH} bytes, received {len(data)}"
        )
    return data


def parse_status_frame(raw: Any) -> dict[str, int | float | str]:
    """Map captured byte offsets to HA entities.

    Byte 8 is the confirmed power flag: 0=off, 1=on. Byte 9 is the confirmed
    mode enum, byte 10 fan speed, byte 11 sleep, byte 12 negative ion, and byte
    17 swing. Byte 18 is indoor temperature with a +20 °C transport bias;
    bytes 24-25 are indoor PM2.5 (big-endian unsigned). Sensor mappings were
    checked against the mini-program screenshot and subsequent live HA values.
    Temperature and humidity evaluations mirror the mini-program labels and
    are derived from the decoded indoor values.
    """
    data = decode_raw(raw)
    indoor_temperature = data[18] - 20
    indoor_humidity = data[19]
    return {
        "power": data[8],
        "mode": data[9],
        "fan_speed": data[10],
        "negative_ion": data[12],
        "swing": data[17],
        "sleep": data[11],
        "indoor_pm25": int.from_bytes(data[24:26], byteorder="big"),
        "indoor_humidity": indoor_humidity,
        "indoor_humidity_evaluation": humidity_evaluation(indoor_humidity),
        "outdoor_temperature": int.from_bytes(
            data[20:21], byteorder="big", signed=True
        ),
        "outdoor_humidity": data[21],
        "co2": int.from_bytes(data[22:24], byteorder="big"),
        "indoor_temperature": indoor_temperature,
        "indoor_temperature_evaluation": temperature_evaluation(
            indoor_temperature
        ),
        "outdoor_pm25": int.from_bytes(data[26:28], byteorder="big"),
        "air_quality_level": data[36],
        "filter_life": data[37],
    }


def power_raw(power: bool) -> str:
    """Return the exact five-byte power command seen in the capture."""
    return "0000000401" if power else "0000000400"


def mode_raw(mode: int) -> str:
    """Return the captured five-byte operating-mode command."""
    try:
        if mode not in MODE_LABELS:
            raise ValueError(f"Unsupported mode: {mode}")
    except TypeError as err:
        raise ValueError(f"Unsupported mode: {mode}") from err
    return f"00000008{mode:02X}"


def mode_from_label(label: str) -> int:
    """Resolve the climate preset label to the captured mode code."""
    for mode, mode_label in MODE_LABELS.items():
        if mode_label == label:
            return mode
    raise ValueError(f"Unsupported mode: {label}")


def fan_speed_raw(speed: int) -> str:
    """Return the captured five-byte fan-speed command."""
    try:
        if speed not in FAN_SPEED_LABELS:
            raise ValueError(f"Unsupported fan speed: {speed}")
    except TypeError as err:
        raise ValueError(f"Unsupported fan speed: {speed}") from err
    return f"00000010{speed:02X}"


def fan_speed_from_label(label: str) -> int:
    """Resolve the climate fan-mode label to the captured speed code."""
    for speed, speed_label in FAN_SPEED_LABELS.items():
        if speed_label == label:
            return speed
    raise ValueError(f"Unsupported fan speed: {label}")


def air_quality_text(level: int) -> str:
    """Return a cautious label while preserving unknown enum values."""
    return AIR_QUALITY_LABELS.get(level, f"等级 {level}")


def temperature_evaluation(temperature: int | float) -> str:
    """Return the mini-program's qualitative indoor-temperature label."""
    if temperature < 18:
        return COLD_LABEL
    if temperature <= 26:
        return MILD_LABEL
    return HOT_LABEL


def humidity_evaluation(humidity: int | float) -> str:
    """Return the mini-program's qualitative indoor-humidity label."""
    if humidity < 40:
        return DRY_LABEL
    if humidity <= 60:
        return COMFORTABLE_LABEL
    return HUMID_LABEL
