"""Pydantic request/response models for the API."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class LayerInfo(BaseModel):
    key: str
    label: str
    setback_ft: float
    priority: int
    color: str
    source: str
    rationale: str


class ConfigResponse(BaseModel):
    county: str
    analysis_crs: str
    layers: list[LayerInfo]
    center: list[float] | None = None     # [lon, lat]
    bbox: list[float] | None = None        # [minx, miny, maxx, maxy]


class AnalyzeRequest(BaseModel):
    parcel_id: str
    county: str | None = None
    # Per-request setback overrides in FEET, keyed by layer key. Missing keys use
    # the config default; this is how the UI re-runs without touching code.
    setbacks: dict[str, float] = Field(default_factory=dict)
    # User edits as GeoJSON geometries (Polygon/MultiPolygon) in WGS84.
    carveouts: list[dict[str, Any]] = Field(default_factory=list)
    restores: list[dict[str, Any]] = Field(default_factory=list)


class BreakdownItem(BaseModel):
    key: str
    label: str
    color: str
    setback_ft: float
    net_acres: float
    gross_acres: float


class Totals(BaseModel):
    parcel_acres: float
    buildable_acres: float
    excluded_acres: float
    restored_acres: float
    buildable_pct: float


class AnalyzeResponse(BaseModel):
    parcel_id: str
    totals: Totals
    breakdown: list[BreakdownItem]
    setbacks_used: dict[str, float]
    # FeatureCollection with the parcel, buildable and excluded polygons.
    result: dict[str, Any]
