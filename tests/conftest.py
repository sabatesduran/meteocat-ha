"""Make pure integration modules importable without installing Home Assistant."""

import sys
import types
from pathlib import Path

ROOT = Path(__file__).parents[1]
COMPONENTS = ROOT / "custom_components"
PACKAGE = COMPONENTS / "meteocat_weather"

custom_components = types.ModuleType("custom_components")
custom_components.__path__ = [str(COMPONENTS)]
sys.modules.setdefault("custom_components", custom_components)

meteocat_weather = types.ModuleType("custom_components.meteocat_weather")
meteocat_weather.__path__ = [str(PACKAGE)]
sys.modules.setdefault("custom_components.meteocat_weather", meteocat_weather)
