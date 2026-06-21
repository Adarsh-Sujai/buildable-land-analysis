"""Application services tying config + data store + geometry engine together."""
from __future__ import annotations

from shapely.geometry.base import BaseGeometry

from .config import LayerConfig, get_config
from .data import store
from .geo import geojson
from .geo.analysis import AnalysisResult, LayerInput, analyze
from .schemas import (
    AnalyzeRequest,
    AnalyzeResponse,
    BreakdownItem,
    Totals,
)


class ParcelNotFound(Exception):
    pass


def _layer_inputs(parcel_geom: BaseGeometry, county: str | None, overrides: dict[str, float]):
    """Build LayerInput list: pull each enabled layer's geometry near the parcel,
    applying any per-request setback override."""
    inputs: list[LayerInput] = []
    for layer in get_config().enabled_layers:
        geom = store.constraint_union_near(layer.key, parcel_geom, county)
        setback = overrides.get(layer.key, layer.setback_ft)
        inputs.append(
            LayerInput(
                key=layer.key,
                label=layer.label,
                priority=layer.priority,
                setback_ft=float(setback),
                color=layer.color,
                geometry=geom,
            )
        )
    return inputs


def run_analysis(req: AnalyzeRequest) -> AnalyzeResponse:
    cfg = get_config()
    county = req.county or cfg.county

    prow = store.get_parcel(req.parcel_id, county)
    if prow is None:
        raise ParcelNotFound(req.parcel_id)
    parcel_geom = prow.geometry

    layers = _layer_inputs(parcel_geom, county, req.setbacks)
    carveouts = [g for g in (geojson.to_geometry(c) for c in req.carveouts) if g is not None]
    restores = [g for g in (geojson.to_geometry(r) for r in req.restores) if g is not None]

    result: AnalysisResult = analyze(
        parcel_geom,
        layers,
        carveouts_wgs84=carveouts,
        restores_wgs84=restores,
        analysis_crs=cfg.analysis_crs,
    )

    setbacks_used = {layer.key: layer.setback_ft for layer in layers}
    buildable_pct = (
        100.0 * result.buildable_acres / result.parcel_acres if result.parcel_acres else 0.0
    )

    features = [
        geojson.feature(result.parcel, {"kind": "parcel"}),
        geojson.feature(result.excluded, {"kind": "excluded"}),
        geojson.feature(result.buildable, {"kind": "buildable"}),
    ]

    return AnalyzeResponse(
        parcel_id=req.parcel_id,
        totals=Totals(
            parcel_acres=round(result.parcel_acres, 4),
            buildable_acres=round(result.buildable_acres, 4),
            excluded_acres=round(result.excluded_acres, 4),
            restored_acres=round(result.restored_acres, 4),
            buildable_pct=round(buildable_pct, 1),
        ),
        breakdown=[
            BreakdownItem(
                key=b.key,
                label=b.label,
                color=b.color,
                setback_ft=b.setback_ft,
                net_acres=round(b.net_acres, 4),
                gross_acres=round(b.gross_acres, 4),
            )
            for b in result.breakdown
        ],
        setbacks_used=setbacks_used,
        result=geojson.feature_collection(features),
    )


def layer_info_list() -> list[LayerConfig]:
    return get_config().enabled_layers
