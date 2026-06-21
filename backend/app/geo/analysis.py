"""Buildable-area computation.

Given a parcel and a set of constraint layers (each with a setback distance), plus
optional user edits (carve-outs and restores), compute:

  * the buildable polygon,
  * the excluded polygon,
  * a per-layer breakdown of *what was removed and why* that reconciles exactly
    (sum of the breakdown == total excluded; buildable + excluded == parcel).

All geometry math runs in an equal-area, metre-based CRS (see ``crs.py``); inputs
and outputs are WGS84 lon/lat.

The two reconciliation invariants this module guarantees:

    buildable_acres + excluded_acres  ==  parcel_acres
    sum(line.net_acres for line in breakdown)  ==  excluded_acres

"Net" attribution is *greedy by priority*: when buffered layers overlap, each is
credited only with the area it removes that a higher-priority layer hasn't already
claimed. That keeps the breakdown honest (no double counting) and additive.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import shapely
from shapely.geometry import MultiPolygon, Polygon
from shapely.geometry.base import BaseGeometry

from . import crs as _crs

# Synthetic breakdown keys for user edits.
CARVEOUT_KEY = "manual_carveout"
RESTORE_KEY = "manual_restore"

EPS = 1e-9  # area in m^2 below which a sliver is treated as empty


@dataclass
class LayerInput:
    """One constraint layer's *raw* (un-buffered) geometry + how to treat it.

    ``geometry`` is the union of that layer's features in WGS84, or ``None`` if the
    layer has no features intersecting the parcel.
    """

    key: str
    label: str
    priority: int
    setback_ft: float
    color: str = "#888888"
    geometry: BaseGeometry | None = None


@dataclass
class BreakdownLine:
    key: str
    label: str
    color: str
    setback_ft: float
    net_acres: float       # additive, sums to excluded_acres (greedy attribution)
    gross_acres: float     # this layer alone, overlap-inclusive (for transparency)


@dataclass
class AnalysisResult:
    parcel: BaseGeometry           # WGS84
    buildable: BaseGeometry        # WGS84
    excluded: BaseGeometry         # WGS84
    parcel_acres: float
    buildable_acres: float
    excluded_acres: float
    restored_acres: float          # area added back by user "restore" edits (informational)
    breakdown: list[BreakdownLine] = field(default_factory=list)


def _clean(geom: BaseGeometry | None) -> BaseGeometry | None:
    geom = _crs.make_valid(geom)
    if geom is None or geom.is_empty:
        return None
    return geom


def _union(geoms: list[BaseGeometry]) -> BaseGeometry | None:
    real = [g for g in geoms if g is not None and not g.is_empty]
    if not real:
        return None
    return _clean(shapely.union_all(real))


def _as_polygonal(geom: BaseGeometry | None) -> BaseGeometry | None:
    """Drop stray lines/points that ``difference`` can leave behind; keep only area."""
    if geom is None or geom.is_empty:
        return None
    if isinstance(geom, (Polygon, MultiPolygon)):
        return geom
    polys = [g for g in getattr(geom, "geoms", []) if isinstance(g, (Polygon, MultiPolygon))]
    return _union(polys) if polys else None


def analyze(
    parcel_wgs84: BaseGeometry,
    layers: list[LayerInput],
    carveouts_wgs84: list[BaseGeometry] | None = None,
    restores_wgs84: list[BaseGeometry] | None = None,
    analysis_crs: str = _crs.DEFAULT_ANALYSIS_CRS,
) -> AnalysisResult:
    """Run the full buildable-area analysis. See module docstring for invariants."""
    carveouts_wgs84 = carveouts_wgs84 or []
    restores_wgs84 = restores_wgs84 or []

    parcel = _clean(_crs.to_analysis(parcel_wgs84, analysis_crs))
    if parcel is None:
        raise ValueError("parcel geometry is empty or invalid")
    parcel_acres = _crs.area_acres(parcel)

    # ------------------------------------------------------------------ #
    # 1. Per-layer excluded geometry: buffer by setback, clip to parcel.
    #    "Sources" is the ordered list used for greedy attribution.
    # ------------------------------------------------------------------ #
    @dataclass
    class _Source:
        key: str
        label: str
        color: str
        setback_ft: float
        clipped: BaseGeometry  # buffered-and-clipped-to-parcel excluded area

    sources: list[_Source] = []

    for layer in sorted(layers, key=lambda l: l.priority):
        if layer.geometry is None or layer.geometry.is_empty:
            continue
        geom = _clean(_crs.to_analysis(layer.geometry, analysis_crs))
        if geom is None:
            continue
        buffered = geom.buffer(_crs.feet_to_meters(layer.setback_ft)) if layer.setback_ft else geom
        clipped = _as_polygonal(_clean(buffered).intersection(parcel)) if buffered else None
        if clipped is None or clipped.area <= EPS:
            continue
        sources.append(
            _Source(layer.key, layer.label, layer.color, layer.setback_ft, clipped)
        )

    # Manual carve-outs behave like a lowest-priority constraint source.
    carveout_clipped = _as_polygonal(
        _intersect_all_with_parcel(carveouts_wgs84, parcel, analysis_crs)
    )
    if carveout_clipped is not None and carveout_clipped.area > EPS:
        sources.append(
            _Source(CARVEOUT_KEY, "Manual carve-out", "#7a0177", 0.0, carveout_clipped)
        )

    constraint_union = _union([s.clipped for s in sources])

    # ------------------------------------------------------------------ #
    # 2. Apply restores: excluded = (constraints u carveouts) - restores.
    # ------------------------------------------------------------------ #
    restore_clipped = _as_polygonal(
        _intersect_all_with_parcel(restores_wgs84, parcel, analysis_crs)
    )

    excluded = constraint_union
    restored_acres = 0.0
    if excluded is not None and restore_clipped is not None:
        before = excluded.area
        excluded = _as_polygonal(_clean(excluded).difference(restore_clipped))
        after = excluded.area if excluded is not None else 0.0
        restored_acres = max(0.0, (before - after)) / _crs.SQ_METERS_PER_ACRE

    buildable = _as_polygonal(parcel.difference(excluded)) if excluded is not None else parcel
    if buildable is None:
        buildable = Polygon()  # whole parcel excluded

    excluded_acres = _crs.area_acres(excluded)
    buildable_acres = _crs.area_acres(buildable)

    # ------------------------------------------------------------------ #
    # 3. Greedy breakdown over the FINAL excluded geometry. Intersecting each
    #    source with `excluded` accounts for area a restore may have removed,
    #    so the net column always sums back to excluded_acres.
    # ------------------------------------------------------------------ #
    breakdown: list[BreakdownLine] = []
    running: BaseGeometry | None = None
    final_excluded = excluded

    for src in sources:
        gross_acres = _crs.area_acres(src.clipped)
        net_geom = src.clipped
        if final_excluded is not None:
            net_geom = _as_polygonal(_clean(src.clipped).intersection(final_excluded))
        else:
            net_geom = None
        if net_geom is not None and running is not None:
            net_geom = _as_polygonal(_clean(net_geom).difference(running))
        net_acres = _crs.area_acres(net_geom)
        if net_geom is not None:
            running = _union([running, net_geom]) if running is not None else net_geom
        breakdown.append(
            BreakdownLine(
                key=src.key,
                label=src.label,
                color=src.color,
                setback_ft=src.setback_ft,
                net_acres=net_acres,
                gross_acres=gross_acres,
            )
        )

    return AnalysisResult(
        parcel=_crs.to_wgs84(parcel, analysis_crs),
        buildable=_crs.to_wgs84(buildable, analysis_crs) if not buildable.is_empty else buildable,
        excluded=_crs.to_wgs84(excluded, analysis_crs) if excluded is not None else Polygon(),
        parcel_acres=parcel_acres,
        buildable_acres=buildable_acres,
        excluded_acres=excluded_acres,
        restored_acres=restored_acres,
        breakdown=breakdown,
    )


def _intersect_all_with_parcel(
    geoms_wgs84: list[BaseGeometry],
    parcel_proj: BaseGeometry,
    analysis_crs: str,
) -> BaseGeometry | None:
    """Project user-drawn geoms, union them, and clip to the parcel.

    Clipping to the parcel is what makes a *restore* unable to add back land that
    was never part of the parcel, and a *carve-out* unable to exclude area outside
    it - both are bounded by the parcel by construction.
    """
    projected = []
    for g in geoms_wgs84:
        if g is None or g.is_empty:
            continue
        pg = _clean(_crs.to_analysis(g, analysis_crs))
        if pg is not None:
            projected.append(pg)
    union = _union(projected)
    if union is None:
        return None
    return _clean(union.intersection(parcel_proj))
