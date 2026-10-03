"""Repository metadata consistency tests."""

import json
from pathlib import Path

ROOT = Path(__file__).parents[1]


def test_manifest_and_hacs_metadata() -> None:
    manifest = json.loads((ROOT / "custom_components/meteocat_weather/manifest.json").read_text())
    hacs = json.loads((ROOT / "hacs.json").read_text())
    assert manifest["domain"] == "meteocat_weather"
    assert manifest["config_flow"] is True
    assert manifest["version"] == "0.1.3"
    assert manifest["documentation"] == "https://github.com/sabatesduran/meteocat-ha"
    assert manifest["issue_tracker"] == "https://github.com/sabatesduran/meteocat-ha/issues"
    assert hacs["homeassistant"] == "2025.12.0"


def test_translation_files_have_matching_top_level_sections() -> None:
    translations = ROOT / "custom_components/meteocat_weather/translations"
    strings = json.loads((ROOT / "custom_components/meteocat_weather/strings.json").read_text())
    for language in ("ca", "es", "en"):
        translated = json.loads((translations / f"{language}.json").read_text())
        assert translated.keys() == strings.keys()
