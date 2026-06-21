"""Tiny GeoJSON <-> Shapely helpers."""
from __future__ import annotations

from typing import Any

from shapely.geometry import mapping, shape
from shapely.geometry.base import BaseGeometry


def to_geometry(geojson: dict[str, Any] | None) -> BaseGeometry | None:
    """Accept a GeoJSON geometry OR a Feature and return a shapely geometry."""
    if not geojson:
        return None
    if geojson.get("type") == "Feature":
        geojson = geojson.get("geometry")
        if not geojson:
            return None
    return shape(geojson)


def feature(geom: BaseGeometry | None, properties: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": "Feature",
        "properties": properties,
        "geometry": mapping(geom) if geom is not None and not geom.is_empty else None,
    }


def feature_collection(features: list[dict[str, Any]]) -> dict[str, Any]:
    return {"type": "FeatureCollection", "features": features}
