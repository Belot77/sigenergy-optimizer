from __future__ import annotations

import unittest

from app.routers.api import _sanitize_preset_payload, _validate_config_value


class _DummyCfg:
    daily_summary_time = "23:55"


class ApiValidationTests(unittest.TestCase):
    def test_validate_config_value_time(self) -> None:
        cfg = _DummyCfg()
        err = _validate_config_value(cfg, "daily_summary_time", "25:99")
        self.assertIsNotNone(err)

    def test_validate_config_value_limit_range(self) -> None:
        cfg = _DummyCfg()
        err = _validate_config_value(cfg, "export_limit_low", 9999)
        self.assertIsNotNone(err)

    def test_sanitize_preset_payload_rejects_empty(self) -> None:
        with self.assertRaises(ValueError):
            _sanitize_preset_payload({})

    def test_sanitize_preset_payload_allows_known_keys(self) -> None:
        payload = _sanitize_preset_payload(
            {
                "export_limit_low": 3,
                "import_limit_low": 5,
                "unknown_key": 999,
            }
        )
        self.assertIn("export_limit_low", payload)
        self.assertIn("import_limit_low", payload)
        self.assertNotIn("unknown_key", payload)


if __name__ == "__main__":
    unittest.main()
