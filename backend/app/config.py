"""Configuration loading.

Reads ``config/setbacks.yaml`` (constraint layers + default setbacks) and a few
environment knobs. Kept deliberately small: the YAML is the single source of
truth for *what* we model and the default *how far*, and it is editable without
touching code.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

import yaml

# Repo layout: <root>/backend/app/config.py  ->  root is parents[2]
ROOT_DIR = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG_PATH = ROOT_DIR / "config" / "setbacks.yaml"
DEFAULT_DATA_DIR = ROOT_DIR / "backend" / "data"


@dataclass(frozen=True)
class LayerConfig:
    """One constraint layer's metadata + default setback."""

    key: str
    label: str
    enabled: bool
    setback_ft: float
    priority: int
    color: str
    source: str
    rationale: str = ""


@dataclass(frozen=True)
class AppConfig:
    analysis_crs: str
    county: str
    county_fallbacks: list[str]
    layers: list[LayerConfig]
    data_dir: Path

    def layer(self, key: str) -> LayerConfig | None:
        return next((layer for layer in self.layers if layer.key == key), None)

    @property
    def enabled_layers(self) -> list[LayerConfig]:
        """Enabled layers, in attribution order (ascending priority)."""
        return sorted(
            (layer for layer in self.layers if layer.enabled),
            key=lambda layer: layer.priority,
        )


def _config_path() -> Path:
    return Path(os.environ.get("BLA_CONFIG", DEFAULT_CONFIG_PATH))


def _data_dir() -> Path:
    return Path(os.environ.get("BLA_DATA_DIR", DEFAULT_DATA_DIR))


@lru_cache(maxsize=1)
def get_config() -> AppConfig:
    raw = yaml.safe_load(_config_path().read_text(encoding="utf-8"))

    layers = [
        LayerConfig(
            key=item["key"],
            label=item["label"],
            enabled=bool(item.get("enabled", True)),
            setback_ft=float(item.get("setback_ft", 0)),
            priority=int(item.get("priority", 100)),
            color=item.get("color", "#888888"),
            source=item.get("source", ""),
            rationale=" ".join((item.get("rationale") or "").split()),
        )
        for item in raw.get("layers", [])
    ]

    # County can be overridden via env (handy for the fetch script / fallbacks).
    county = os.environ.get("BLA_COUNTY", raw.get("county", "Aransas"))

    return AppConfig(
        analysis_crs=raw.get("analysis_crs", "EPSG:3083"),
        county=county,
        county_fallbacks=list(raw.get("county_fallbacks", [])),
        layers=layers,
        data_dir=_data_dir(),
    )
