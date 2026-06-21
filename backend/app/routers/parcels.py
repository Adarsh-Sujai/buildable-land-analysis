"""Parcel browsing endpoints."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from ..config import get_config
from ..data import store
from ..geo import geojson

router = APIRouter(prefix="/api", tags=["parcels"])


@router.get("/config")
def get_app_config():
    """Layer metadata + map view hints, so the frontend builds controls dynamically."""
    cfg = get_config()
    parcels = store.parcels(cfg.county)
    bbox = None
    center = None
    if parcels is not None and not parcels.empty:
        minx, miny, maxx, maxy = (float(v) for v in parcels.total_bounds)
        bbox = [minx, miny, maxx, maxy]
        center = [(minx + maxx) / 2, (miny + maxy) / 2]
    return {
        "county": cfg.county,
        "analysis_crs": cfg.analysis_crs,
        "data_available": parcels is not None and not parcels.empty,
        "parcel_count": 0 if parcels is None else int(len(parcels)),
        "center": center,
        "bbox": bbox,
        "layers": [
            {
                "key": l.key,
                "label": l.label,
                "setback_ft": l.setback_ft,
                "priority": l.priority,
                "color": l.color,
                "source": l.source,
                "rationale": l.rationale,
            }
            for l in cfg.enabled_layers
        ],
    }


@router.get("/parcels")
def list_parcels(
    bbox: str = Query(..., description="minx,miny,maxx,maxy in WGS84"),
    limit: int = Query(400, ge=1, le=2000),
    county: str | None = None,
):
    """Parcels intersecting a bbox (for the map's clickable parcel layer)."""
    try:
        minx, miny, maxx, maxy = (float(v) for v in bbox.split(","))
    except ValueError:
        raise HTTPException(status_code=400, detail="bbox must be 'minx,miny,maxx,maxy'")

    gdf = store.parcels_in_bbox((minx, miny, maxx, maxy), county, limit=limit)
    features = []
    for _, row in gdf.iterrows():
        features.append(
            geojson.feature(
                row.geometry,
                {
                    "parcel_id": str(row[store.PARCEL_ID_COL]),
                    "owner": _safe(row.get("file_as_name")),
                    "legal_acreage": _safe(row.get("legal_acreage")),
                },
            )
        )
    return geojson.feature_collection(features)


@router.get("/parcels/{parcel_id}")
def get_parcel(parcel_id: str, county: str | None = None):
    row = store.get_parcel(parcel_id, county)
    if row is None:
        raise HTTPException(status_code=404, detail=f"parcel '{parcel_id}' not found")
    return geojson.feature(
        row.geometry,
        {
            "parcel_id": parcel_id,
            "owner": _safe(row.get("file_as_name")),
            "legal_acreage": _safe(row.get("legal_acreage")),
            "city": _safe(row.get("city")),
            "legal_desc": _safe(row.get("legal_desc")),
        },
    )


def _safe(value):
    """Coerce pandas NaN/NA to None so JSON stays valid."""
    try:
        import pandas as pd

        if value is None or (not isinstance(value, str) and pd.isna(value)):
            return None
    except Exception:
        pass
    return value
