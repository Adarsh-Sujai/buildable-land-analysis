"""Coordinate-reference-system helpers.

The map and all I/O use WGS84 lon/lat (EPSG:4326). Buffering and area, however,
MUST happen in a projected, equal-area CRS measured in metres - doing them in
degrees would give meaningless distances and badly distorted areas. We project
to EPSG:3083 (NAD83 / Texas Centric Albers Equal Area) for the math and convert
results back to 4326 for output.
"""
from __future__ import annotations

from functools import lru_cache

import shapely
from pyproj import Transformer
from shapely.geometry.base import BaseGeometry
from shapely.ops import transform as shp_transform

WGS84 = "EPSG:4326"
DEFAULT_ANALYSIS_CRS = "EPSG:3083"

# Unit conversions.
FEET_TO_METERS = 0.3048
SQ_METERS_PER_ACRE = 4046.8564224


@lru_cache(maxsize=8)
def _transformer(src: str, dst: str) -> Transformer:
    # always_xy keeps coordinates in (lon, lat) / (x, y) order, matching GeoJSON.
    return Transformer.from_crs(src, dst, always_xy=True)


def to_analysis(geom: BaseGeometry, analysis_crs: str = DEFAULT_ANALYSIS_CRS) -> BaseGeometry:
    """Reproject a WGS84 geometry into the equal-area analysis CRS (metres)."""
    return shp_transform(_transformer(WGS84, analysis_crs).transform, geom)


def to_wgs84(geom: BaseGeometry, analysis_crs: str = DEFAULT_ANALYSIS_CRS) -> BaseGeometry:
    """Reproject an analysis-CRS geometry back to WGS84 lon/lat."""
    return shp_transform(_transformer(analysis_crs, WGS84).transform, geom)


def feet_to_meters(feet: float) -> float:
    return feet * FEET_TO_METERS


def area_acres(geom: BaseGeometry | None) -> float:
    """Area in acres. Input must already be in the (metre-based) analysis CRS."""
    if geom is None or geom.is_empty:
        return 0.0
    return geom.area / SQ_METERS_PER_ACRE


def make_valid(geom: BaseGeometry | None) -> BaseGeometry | None:
    """Repair self-intersections / invalid rings that real-world data is full of."""
    if geom is None or geom.is_empty:
        return geom
    if geom.is_valid:
        return geom
    return shapely.make_valid(geom)
