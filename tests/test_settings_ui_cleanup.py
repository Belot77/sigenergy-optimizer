from __future__ import annotations

import re
import unittest
from pathlib import Path

from app.config import Settings


ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_PATH = ROOT / "templates" / "index.html"
ENV_EXAMPLE_PATH = ROOT / ".env.example"


def _config_section_source() -> str:
    template = TEMPLATE_PATH.read_text(encoding="utf-8")
    return template.split("const _CONFIG_SECTIONS = [", 1)[1].split(
        "function cfgFieldId", 1
    )[0]


class SettingsUiCleanupTests(unittest.TestCase):
    def test_rendered_settings_are_real_unique_non_secret_config_keys(self) -> None:
        section_source = _config_section_source()
        keys = re.findall(r"\['([a-z0-9_]+)'\s*,", section_source)

        self.assertEqual(len(keys), len(set(keys)))
        self.assertTrue(set(keys).issubset(Settings.model_fields))
        self.assertNotIn("ha_token", keys)
        self.assertNotIn("ui_api_key", keys)

    def test_dead_legacy_settings_are_not_advertised_in_the_ui(self) -> None:
        section_source = _config_section_source()
        dead_keys = {
            "automated_export_flag",
            "slow_charge_holdoff",
            "slow_charge_limit_kw",
            "export_hysteresis_percent",
            "sun_elevation_evening_threshold",
            "export_limit_value",
            "import_limit_value",
        }

        for key in dead_keys:
            with self.subTest(key=key):
                self.assertNotIn(f"['{key}'", section_source)
                self.assertIn(key, Settings.model_fields)

    def test_env_example_does_not_advertise_dead_legacy_settings(self) -> None:
        env_example = ENV_EXAMPLE_PATH.read_text(encoding="utf-8")

        for env_key in (
            "AUTOMATED_EXPORT_FLAG",
            "SLOW_CHARGE_HOLDOFF",
            "SLOW_CHARGE_LIMIT_KW",
            "EXPORT_HYSTERESIS_PERCENT",
            "SUN_ELEVATION_EVENING_THRESHOLD",
        ):
            with self.subTest(env_key=env_key):
                self.assertNotRegex(env_example, rf"(?m)^{env_key}=")

    def test_price_spike_soc_copy_describes_actual_import_effect(self) -> None:
        section_source = _config_section_source()
        template = TEMPLATE_PATH.read_text(encoding="utf-8")

        self.assertIn("Price Spike Import Block SoC", section_source)
        self.assertIn("cheap-import eligibility while a price spike is active", template)
        self.assertIn("does not set an export floor", template)


if __name__ == "__main__":
    unittest.main()
