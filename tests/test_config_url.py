"""Tests for the split server-address / DID configuration helpers."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest

CONST_PATH = (
    Path(__file__).resolve().parents[1]
    / "custom_components"
    / "airspa_ai_climate"
    / "const.py"
)
SPEC = importlib.util.spec_from_file_location("airspa_const", CONST_PATH)
const = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(const)

DID = "productkey_001122334455"


class WebSocketAddressTests(unittest.TestCase):
    def test_base_and_did_are_joined(self):
        self.assertEqual(
            const.build_ws_url("wss://aisp.airspa.cn:81", DID),
            f"wss://aisp.airspa.cn:81/{DID}",
        )

    def test_trailing_slash_is_not_duplicated(self):
        self.assertEqual(
            const.build_ws_url("wss://aisp.airspa.cn:81/", DID),
            f"wss://aisp.airspa.cn:81/{DID}",
        )

    def test_full_endpoint_is_not_joined_twice(self):
        full = f"wss://aisp.airspa.cn:81/{DID}"
        self.assertEqual(const.build_ws_url(full, DID), full)

    def test_legacy_template_is_supported(self):
        self.assertEqual(
            const.build_ws_url(
                "wss://aisp.airspa.cn:81/{device_id}", DID
            ),
            f"wss://aisp.airspa.cn:81/{DID}",
        )

    def test_blank_server_uses_default(self):
        self.assertEqual(
            const.build_ws_url("", DID),
            f"{const.DEFAULT_SERVER_URL}/{DID}",
        )

    def test_ws_url_is_reduced_to_server_base(self):
        full = f"wss://aisp.airspa.cn:81/{DID}"
        self.assertEqual(
            const.server_base_from_ws_url(full, DID),
            "wss://aisp.airspa.cn:81",
        )

    def test_url_validation(self):
        self.assertTrue(const.is_valid_ws_url("wss://aisp.airspa.cn:81"))
        self.assertFalse(const.is_valid_ws_url("https://aisp.airspa.cn:81"))


if __name__ == "__main__":
    unittest.main()
