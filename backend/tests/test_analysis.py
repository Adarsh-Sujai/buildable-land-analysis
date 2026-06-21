"""Unit tests for the buildable-area engine.

These prove the two invariants the whole app rests on, using synthetic geometries
placed over Aransas County, TX (so the EPSG:3083 projection is well-behaved):

    buildable_acres + excluded_acres == parcel_acres
    sum(net_acres) == excluded_acres

plus the behaviour of greedy attribution, carve-outs and restores.
"""
from __future__ import annotations

import math

from shapely.geometry import box

from app.geo.analysis import (
    CARVEOUT_KEY,
    LayerInput,
    analyze,
)

# Roughly the centre of Aransas County, TX.
LON0, LAT0 = -97.05, 28.02
# ~0.01 deg ≈ 1 km here; small enough to stay local, big enough to buffer in feet.
DEG = 0.02


def sq(cx: float, cy: float, half: float):
    """Axis-aligned square (lon/lat) centred at (cx, cy) with given half-width in deg."""
    return box(cx - half, cy - half, cx + half, cy + half)


def parcel():
    return sq(LON0, LAT0, DEG)


def reconciles(result, tol_acres=1e-4):
    assert math.isclose(
        result.buildable_acres + result.excluded_acres,
        result.parcel_acres,
        abs_tol=tol_acres,
    ), "buildable + excluded must equal parcel"
    net_sum = sum(line.net_acres for line in result.breakdown)
    assert math.isclose(net_sum, result.excluded_acres, abs_tol=tol_acres), (
        f"breakdown net sum {net_sum} must equal excluded {result.excluded_acres}"
    )


def test_no_constraints_means_whole_parcel_buildable():
    result = analyze(parcel(), layers=[])
    assert result.excluded_acres == 0.0
    assert math.isclose(result.buildable_acres, result.parcel_acres, abs_tol=1e-6)
    reconciles(result)


def test_single_layer_reconciles():
    # A constraint covering the left half of the parcel.
    left_half = box(LON0 - DEG, LAT0 - DEG, LON0, LAT0 + DEG)
    layers = [LayerInput("wetlands", "Wetlands", priority=10, setback_ft=0, geometry=left_half)]
    result = analyze(parcel(), layers=layers)
    assert result.excluded_acres > 0
    # Left half of a symmetric square ≈ half the parcel.
    assert math.isclose(result.excluded_acres, result.parcel_acres / 2, rel_tol=1e-3)
    reconciles(result)


def test_setback_increases_excluded_area():
    line_geom = box(LON0 - 1e-5, LAT0 - DEG, LON0 + 1e-5, LAT0 + DEG)  # thin vertical sliver
    base = analyze(
        parcel(),
        [LayerInput("x", "X", priority=10, setback_ft=0, geometry=line_geom)],
    )
    buffered = analyze(
        parcel(),
        [LayerInput("x", "X", priority=10, setback_ft=200, geometry=line_geom)],
    )
    assert buffered.excluded_acres > base.excluded_acres
    reconciles(base)
    reconciles(buffered)


def test_overlapping_layers_no_double_count():
    # Two layers covering the SAME left half. Higher-priority (lower number) wins.
    left_half = box(LON0 - DEG, LAT0 - DEG, LON0, LAT0 + DEG)
    layers = [
        LayerInput("a", "A", priority=10, setback_ft=0, geometry=left_half),
        LayerInput("b", "B", priority=20, setback_ft=0, geometry=left_half),
    ]
    result = analyze(parcel(), layers=layers)
    by_key = {line.key: line for line in result.breakdown}
    # B fully overlaps A -> B nets ~0 but its gross is the full half.
    assert by_key["a"].net_acres > 0
    assert math.isclose(by_key["b"].net_acres, 0.0, abs_tol=1e-4)
    assert by_key["b"].gross_acres > 0.1
    reconciles(result)


def test_carveout_adds_exclusion():
    no_edit = analyze(parcel(), layers=[])
    carve = box(LON0, LAT0, LON0 + DEG, LAT0 + DEG)  # a quadrant
    with_edit = analyze(parcel(), layers=[], carveouts_wgs84=[carve])
    assert with_edit.excluded_acres > no_edit.excluded_acres
    assert any(line.key == CARVEOUT_KEY for line in with_edit.breakdown)
    reconciles(with_edit)


def test_restore_adds_back_only_within_parcel():
    # Exclude the left half via a constraint, then restore a box straddling the
    # parcel's left edge. Only the in-parcel, in-excluded part should come back.
    left_half = box(LON0 - DEG, LAT0 - DEG, LON0, LAT0 + DEG)
    constraint = [LayerInput("w", "W", priority=10, setback_ft=0, geometry=left_half)]
    restore = box(LON0 - 2 * DEG, LAT0 - DEG / 2, LON0 - DEG / 2, LAT0 + DEG / 2)

    base = analyze(parcel(), layers=constraint)
    restored = analyze(parcel(), layers=constraint, restores_wgs84=[restore])

    assert restored.excluded_acres < base.excluded_acres
    assert restored.buildable_acres > base.buildable_acres
    assert restored.restored_acres > 0
    # Restore reaches outside the parcel, but only in-parcel area is credited.
    assert restored.restored_acres <= base.excluded_acres + 1e-6
    reconciles(base)
    reconciles(restored)


def test_full_overlap_of_constraints_and_edits_reconciles():
    left = box(LON0 - DEG, LAT0 - DEG, LON0, LAT0 + DEG)
    bottom = box(LON0 - DEG, LAT0 - DEG, LON0 + DEG, LAT0)
    layers = [
        LayerInput("wetlands", "Wetlands", priority=10, setback_ft=30, geometry=left),
        LayerInput("flood", "Flood", priority=20, setback_ft=0, geometry=bottom),
    ]
    carve = box(LON0 + DEG / 2, LAT0 + DEG / 2, LON0 + DEG, LAT0 + DEG)
    restore = box(LON0 - DEG, LAT0 - DEG, LON0 - DEG / 2, LAT0 - DEG / 2)
    result = analyze(parcel(), layers=layers, carveouts_wgs84=[carve], restores_wgs84=[restore])
    reconciles(result)
    assert 0 < result.buildable_acres < result.parcel_acres
