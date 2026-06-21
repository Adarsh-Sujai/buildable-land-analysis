"""Prefetch the county's parcels + constraint layers into a local GeoPackage.

Run ONCE (needs network). After this the API serves everything offline from
``<data_dir>/<county>.gpkg``.

    python -m app.data.fetch_data                  # defaults to Aransas
    python -m app.data.fetch_data --max-parcels 4000   # quick/smaller demo set

Flow (see ``sources.py`` for the source-selection rationale):
  1. Pull all parcels from the county appraisal district service.
  2. Derive the constraint bounding box from the parcel extent.
  3. Pull wetlands / FEMA SFHA / transmission lines within that bbox.
  4. Write everything to one GeoPackage.
"""
from __future__ import annotations

import argparse
import sys

import geopandas as gpd

from ..config import get_config
from . import sources as S
from .store import PARCEL_ID_COL, gpkg_path

WGS84 = "EPSG:4326"


def _features_to_gdf(features: list[dict]) -> gpd.GeoDataFrame:
    if not features:
        return gpd.GeoDataFrame(geometry=[], crs=WGS84)
    gdf = gpd.GeoDataFrame.from_features(features, crs=WGS84)
    return gdf[~gdf.geometry.is_empty & gdf.geometry.notna()].reset_index(drop=True)


def fetch_parcels(*, verify: bool, max_parcels: int | None) -> gpd.GeoDataFrame:
    feats = list(
        S.query_features(
            S.PARCELS,
            out_fields=S.PARCEL_FIELDS,
            verify=verify,
            max_features=max_parcels,
        )
    )
    gdf = _features_to_gdf(feats)
    if gdf.empty:
        return gdf
    # Stable id: prefer the appraisal-district prop_id, fall back to row index.
    if "prop_id" in gdf.columns and gdf["prop_id"].is_unique:
        gdf[PARCEL_ID_COL] = gdf["prop_id"].astype(str)
    else:
        gdf[PARCEL_ID_COL] = [str(i) for i in range(len(gdf))]
    return gdf


def fetch_constraint(layer, bbox, *, where="1=1", out_fields="*", verify: bool) -> gpd.GeoDataFrame:
    feats = list(
        S.query_features(
            layer, where=where, geometry=S.envelope(bbox), out_fields=out_fields, verify=verify
        )
    )
    return _features_to_gdf(feats)


def write_layer(gdf: gpd.GeoDataFrame, path, layer: str) -> int:
    if gdf is None or gdf.empty:
        print(f"  [{layer}] 0 features (skipped)")
        return 0
    gdf.to_file(path, layer=layer, driver="GPKG")
    print(f"  [{layer}] {len(gdf)} features")
    return len(gdf)


def run(county: str, *, verify: bool, max_parcels: int | None) -> bool:
    print(f"County: {county}, TX")
    parcels = fetch_parcels(verify=verify, max_parcels=max_parcels)
    if parcels.empty:
        print("  No parcels returned.")
        return False
    bbox = tuple(parcels.total_bounds)  # (minx, miny, maxx, maxy)
    print(f"  parcels: {len(parcels)}   bbox: {tuple(round(b, 4) for b in bbox)}")

    path = gpkg_path(county)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        path.unlink()

    n_parcels = write_layer(parcels, path, "parcels")
    write_layer(
        fetch_constraint(S.WETLANDS, bbox, out_fields="WETLAND_TYPE", verify=verify),
        path,
        "wetlands",
    )
    write_layer(
        fetch_constraint(
            S.FEMA_FLOOD, bbox, where=S.FEMA_SFHA_WHERE, out_fields="FLD_ZONE", verify=verify
        ),
        path,
        "flood",
    )
    write_layer(
        fetch_constraint(S.TRANSMISSION, bbox, out_fields="VOLTAGE,OWNER", verify=verify),
        path,
        "transmission",
    )

    print(f"Wrote {path}  ({n_parcels} parcels)")
    return True


def main(argv: list[str] | None = None) -> int:
    cfg = get_config()
    ap = argparse.ArgumentParser(description="Fetch county GIS data into a GeoPackage.")
    ap.add_argument("--county", default=cfg.county, help="County name (used for the cache filename).")
    ap.add_argument(
        "--max-parcels",
        type=int,
        default=None,
        help="Cap parcel count (useful for a quick/manageable demo set).",
    )
    ap.add_argument(
        "--insecure",
        action="store_true",
        help="Skip TLS verification (some endpoints have cert quirks).",
    )
    args = ap.parse_args(argv)

    try:
        ok = run(args.county, verify=not args.insecure, max_parcels=args.max_parcels)
        return 0 if ok else 1
    except Exception as exc:  # noqa: BLE001 - surface the failure clearly
        print(f"  error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
