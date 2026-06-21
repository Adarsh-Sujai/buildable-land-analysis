"""Local GeoPackage cache + read access.

The fetch script writes one GeoPackage per county (``<data_dir>/<county>.gpkg``)
with layers ``parcels``, ``wetlands``, ``flood``, ``transmission``. The API reads
from here, so after a single documented fetch the app runs fully offline.

Layers are loaded once and cached in memory; spatial queries use GeoPandas' built-in
spatial index, which is plenty fast for a county-sized dataset.
"""
from __future__ import annotations

import threading
from functools import lru_cache
from pathlib import Path

import geopandas as gpd
from shapely.geometry.base import BaseGeometry

from ..config import get_config

PARCEL_ID_COL = "parcel_id"
WGS84 = "EPSG:4326"

_lock = threading.Lock()


def gpkg_path(county: str | None = None) -> Path:
    cfg = get_config()
    county = (county or cfg.county).strip()
    return cfg.data_dir / f"{county.lower().replace(' ', '_')}.gpkg"


def county_is_available(county: str | None = None) -> bool:
    path = gpkg_path(county)
    if not path.exists():
        return False
    try:
        import pyogrio

        return "parcels" in set(pyogrio.list_layers(path)[:, 0])
    except Exception:
        return False


@lru_cache(maxsize=16)
def _load_layer(path_str: str, layer: str) -> gpd.GeoDataFrame:
    gdf = gpd.read_file(path_str, layer=layer)
    if gdf.crs is None:
        gdf = gdf.set_crs(WGS84)
    elif gdf.crs.to_epsg() != 4326:
        gdf = gdf.to_crs(WGS84)
    # Ensure the spatial index is built up front.
    _ = gdf.sindex
    return gdf


def load_layer(county: str | None, layer: str) -> gpd.GeoDataFrame | None:
    path = gpkg_path(county)
    if not path.exists():
        return None
    with _lock:
        try:
            return _load_layer(str(path), layer)
        except Exception:
            return None


# --------------------------------------------------------------------------- #
# Parcels
# --------------------------------------------------------------------------- #


def parcels(county: str | None = None) -> gpd.GeoDataFrame | None:
    return load_layer(county, "parcels")


def parcels_in_bbox(
    bbox: tuple[float, float, float, float],
    county: str | None = None,
    limit: int = 500,
) -> gpd.GeoDataFrame:
    gdf = parcels(county)
    if gdf is None or gdf.empty:
        return gpd.GeoDataFrame(geometry=[], crs=WGS84)
    xmin, ymin, xmax, ymax = bbox
    idx = list(gdf.sindex.intersection((xmin, ymin, xmax, ymax)))
    subset = gdf.iloc[idx]
    # sindex uses bounding boxes; tighten with an actual intersects test.
    from shapely.geometry import box as _box

    clip = _box(*bbox)
    subset = subset[subset.intersects(clip)]
    return subset.head(limit)


def get_parcel(parcel_id: str, county: str | None = None):
    gdf = parcels(county)
    if gdf is None or gdf.empty:
        return None
    match = gdf[gdf[PARCEL_ID_COL].astype(str) == str(parcel_id)]
    if match.empty:
        return None
    return match.iloc[0]


# --------------------------------------------------------------------------- #
# Constraint layers near a parcel
# --------------------------------------------------------------------------- #


def constraint_union_near(
    layer_key: str,
    geom_wgs84: BaseGeometry,
    county: str | None = None,
) -> BaseGeometry | None:
    """Union of a constraint layer's features intersecting ``geom``'s bounds.

    We only need constraint features that touch the parcel, so we filter by the
    parcel's bounding box (spatial index) before unioning - cheap and keeps the
    buffer/clip in the analysis step small.
    """
    gdf = load_layer(county, layer_key)
    if gdf is None or gdf.empty:
        return None
    bounds = geom_wgs84.bounds
    idx = list(gdf.sindex.intersection(bounds))
    if not idx:
        return None
    subset = gdf.iloc[idx]
    subset = subset[subset.intersects(geom_wgs84)]
    if subset.empty:
        return None
    return subset.geometry.union_all()
