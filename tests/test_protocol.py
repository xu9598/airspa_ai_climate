"""Regression tests using the user's captured status frames."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest

PROTOCOL_PATH = (
    Path(__file__).resolve().parents[1]
    / "custom_components"
    / "airspa_ai_climate"
    / "protocol.py"
)
SPEC = importlib.util.spec_from_file_location("airspa_protocol", PROTOCOL_PATH)
protocol = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(protocol)

FRAME_20 = "0FFFFFFF050F0015000103000000000000002B1E07450190001400240000000000000037020100000000"
FRAME_21 = "0FFFFFFF050F0015000103000000000000002B1E07450190001500240000000000000037020100000000"
FRAME_22 = "0FFFFFFF050F0015000103000000000000002B1E07450190001600240000000000000037020100000000"
POWER_OFF_FRAME = "0FFFFFFF050F0015000103000000000000002C1B0651019000110024000000000000003C020100000000"
POWER_ON_FRAME = "0FFFFFFF050F0015010103000000000000002C1B0651019000100024000000000000003C020100000000"
MODE_SMART_FRAME = "0FFFFFFF050F0015010003000000000000002D1A0651019000100024000000000000003C020100000000"
MODE_FRESH_AIR_FRAME = "0FFFFFFF050F0015010103000000000000002D1A0651019000100024000000000000003C020100000000"
MODE_INTERNAL_FRAME = "0FFFFFFF050F0015010203000000000000002D1A0651019000100024000000000000003C020100000000"
MODE_MIXED_FRAME = "0FFFFFFF050F0015010303000000000000002D1A0651019000100024000000000000003C020100000000"
FAN_AUTO_FRAME = "0FFFFFFF050F0015010100000000000000002D1A06510190000F0024000000000000003C020100000000"
FAN_1_FRAME = "0FFFFFFF050F0015010101000000000000002D1A0651019000100024000000000000003C020100000000"
FAN_2_FRAME = "0FFFFFFF050F0015010102000000000000002D1A0651019000100024000000000000003C020100000000"
FAN_3_FRAME = "0FFFFFFF050F0015010103000000000000002D1A06510190000F0024000000000000003C020100000000"
FAN_5_FRAME = "0FFFFFFF050F0015010105000000000000002D1A0651019000100024000000000000003C020100000000"
SLEEP_ON_FRAME = "0FFFFFFF050F0015010105010000000000002D1A0651019000100024000000000000003C020100000000"
SLEEP_OFF_FRAME = "0FFFFFFF050F0015010105000000000000002D1A0651019000100024000000000000003C020100000000"
NEGATIVE_ION_ON_FRAME = "0FFFFFFF050F0015010105000100000000002D1A0651019000100024000000000000003C020100000000"
NEGATIVE_ION_OFF_FRAME = "0FFFFFFF050F0015010105000000000000002D1A0651019000100024000000000000003C020100000000"
SWING_ON_FRAME = "0FFFFFFF050F0015010105000000000000012D1A0651019000100024000000000000003C020100000000"
SWING_OFF_FRAME = "0FFFFFFF050F0015010105000000000000002D1A0651019000100024000000000000003C020100000000"


class RawFrameParserTests(unittest.TestCase):
    def test_captured_values(self):
        status = protocol.parse_status_frame(FRAME_20)
        self.assertEqual(status["indoor_pm25"], 20)
        self.assertEqual(status["indoor_humidity"], 30)
        self.assertEqual(status["outdoor_temperature"], 7)
        self.assertEqual(status["outdoor_humidity"], 69)
        self.assertEqual(status["co2"], 400)
        self.assertEqual(status["indoor_temperature"], 23)
        self.assertEqual(status["outdoor_pm25"], 36)
        self.assertEqual(status["air_quality_level"], 2)
        self.assertEqual(status["filter_life"], 1)

    def test_indoor_pm25_changes(self):
        self.assertEqual(protocol.parse_status_frame(FRAME_21)["indoor_pm25"], 21)
        self.assertEqual(protocol.parse_status_frame(FRAME_22)["indoor_pm25"], 22)

    def test_indoor_temperature_transport_bias(self):
        raw = bytearray.fromhex(FRAME_20)
        raw[18] = 45
        self.assertEqual(protocol.parse_status_frame(raw)["indoor_temperature"], 25)
        raw[18] = 46
        self.assertEqual(protocol.parse_status_frame(raw)["indoor_temperature"], 26)

    def test_indoor_temperature_evaluation(self):
        self.assertEqual(protocol.temperature_evaluation(17), "寒冷")
        self.assertEqual(protocol.temperature_evaluation(18), "温和")
        self.assertEqual(protocol.temperature_evaluation(25), "温和")
        self.assertEqual(protocol.temperature_evaluation(26), "温和")
        self.assertEqual(protocol.temperature_evaluation(27), "炎热")
        raw = bytearray.fromhex(FRAME_20)
        raw[18] = 45
        self.assertEqual(
            protocol.parse_status_frame(raw)["indoor_temperature_evaluation"],
            "温和",
        )

    def test_indoor_humidity_evaluation(self):
        self.assertEqual(protocol.humidity_evaluation(27), "干燥")
        self.assertEqual(protocol.humidity_evaluation(39), "干燥")
        self.assertEqual(protocol.humidity_evaluation(40), "舒适")
        self.assertEqual(protocol.humidity_evaluation(60), "舒适")
        self.assertEqual(protocol.humidity_evaluation(61), "潮湿")
        raw = bytearray.fromhex(FRAME_20)
        raw[19] = 27
        self.assertEqual(
            protocol.parse_status_frame(raw)["indoor_humidity_evaluation"],
            "干燥",
        )

    def test_byte_array_input(self):
        raw = list(bytes.fromhex(FRAME_20))
        self.assertEqual(protocol.parse_status_frame(raw)["co2"], 400)

    def test_signed_outdoor_temperature(self):
        raw = bytearray.fromhex(FRAME_20)
        raw[20] = 0xF9
        self.assertEqual(protocol.parse_status_frame(raw)["outdoor_temperature"], -7)

    def test_invalid_length_is_rejected(self):
        with self.assertRaises(protocol.RawFrameError):
            protocol.parse_status_frame("001122")

    def test_air_quality_label(self):
        self.assertEqual(protocol.air_quality_text(2), "良好")
        self.assertEqual(protocol.air_quality_text(99), "等级 99")

    def test_power_state_and_commands(self):
        self.assertEqual(protocol.parse_status_frame(POWER_OFF_FRAME)["power"], 0)
        self.assertEqual(protocol.parse_status_frame(POWER_ON_FRAME)["power"], 1)
        self.assertEqual(protocol.power_raw(True), "0000000401")
        self.assertEqual(protocol.power_raw(False), "0000000400")

    def test_mode_state_and_commands(self):
        self.assertEqual(protocol.parse_status_frame(MODE_SMART_FRAME)["mode"], 0)
        self.assertEqual(protocol.parse_status_frame(MODE_FRESH_AIR_FRAME)["mode"], 1)
        self.assertEqual(protocol.parse_status_frame(MODE_INTERNAL_FRAME)["mode"], 2)
        self.assertEqual(protocol.parse_status_frame(MODE_MIXED_FRAME)["mode"], 3)
        self.assertEqual(protocol.mode_raw(0), "0000000800")
        self.assertEqual(protocol.mode_raw(1), "0000000801")
        self.assertEqual(protocol.mode_raw(2), "0000000802")
        self.assertEqual(protocol.mode_raw(3), "0000000803")
        self.assertEqual(protocol.mode_from_label("智能"), 0)
        self.assertEqual(protocol.mode_from_label("新风"), 1)
        self.assertEqual(protocol.mode_from_label("内循环"), 2)
        self.assertEqual(protocol.mode_from_label("混风"), 3)
        with self.assertRaises(ValueError):
            protocol.mode_raw(4)
        with self.assertRaises(ValueError):
            protocol.mode_from_label("送风")

    def test_fan_speed_state_and_commands(self):
        self.assertEqual(protocol.parse_status_frame(FAN_AUTO_FRAME)["fan_speed"], 0)
        self.assertEqual(protocol.parse_status_frame(FAN_1_FRAME)["fan_speed"], 1)
        self.assertEqual(protocol.parse_status_frame(FAN_2_FRAME)["fan_speed"], 2)
        self.assertEqual(protocol.parse_status_frame(FAN_3_FRAME)["fan_speed"], 3)
        self.assertEqual(protocol.parse_status_frame(FAN_5_FRAME)["fan_speed"], 5)
        self.assertEqual(protocol.fan_speed_raw(0), "0000001000")
        self.assertEqual(protocol.fan_speed_raw(1), "0000001001")
        self.assertEqual(protocol.fan_speed_raw(2), "0000001002")
        self.assertEqual(protocol.fan_speed_raw(3), "0000001003")
        self.assertEqual(protocol.fan_speed_raw(4), "0000001004")
        self.assertEqual(protocol.fan_speed_raw(5), "0000001005")
        self.assertEqual(protocol.fan_speed_from_label("自动"), 0)
        self.assertEqual(protocol.fan_speed_from_label("1档"), 1)
        self.assertEqual(protocol.fan_speed_from_label("5档"), 5)
        with self.assertRaises(ValueError):
            protocol.fan_speed_raw(6)
        with self.assertRaises(ValueError):
            protocol.fan_speed_from_label("6档")

    def test_auxiliary_switch_states_and_commands(self):
        self.assertEqual(
            protocol.parse_status_frame(NEGATIVE_ION_ON_FRAME)["negative_ion"], 1
        )
        self.assertEqual(
            protocol.parse_status_frame(NEGATIVE_ION_OFF_FRAME)["negative_ion"], 0
        )
        self.assertEqual(protocol.parse_status_frame(SWING_ON_FRAME)["swing"], 1)
        self.assertEqual(protocol.parse_status_frame(SWING_OFF_FRAME)["swing"], 0)
        self.assertEqual(protocol.parse_status_frame(SLEEP_ON_FRAME)["sleep"], 1)
        self.assertEqual(protocol.parse_status_frame(SLEEP_OFF_FRAME)["sleep"], 0)
        self.assertEqual(protocol.NEGATIVE_ION_ON_RAW, "0000004001")
        self.assertEqual(protocol.NEGATIVE_ION_OFF_RAW, "0000004000")
        self.assertEqual(protocol.SWING_ON_RAW, "0000080001")
        self.assertEqual(protocol.SWING_OFF_RAW, "0000080000")
        self.assertEqual(protocol.SLEEP_ON_RAW, "0000002001")
        self.assertEqual(protocol.SLEEP_OFF_RAW, "0000002000")


if __name__ == "__main__":
    unittest.main()
