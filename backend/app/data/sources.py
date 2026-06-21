"""ArcGIS REST data sources (all public, no key required).

A thin client for ArcGIS Feature/Map services that handles the one thing that
actually bites you with real data: **paging**. Services cap each response
(``maxRecordCount``, often 1000-2000), so we follow ``resultOffset`` /
``exceededTransferLimit`` until the layer is drained.

Services used:
  * Parcels      - TxGIO/TNRIS StratMap statewide parcels (filter by county)
  * Wetlands     - USFWS National Wetlands Inventory
  * FEMA flood   - National Flood Hazard Layer, Flood Hazard Zones (SFHA)
  * Transmission - HIFLD Electric Power Transmission Lines
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Iterator

import requests

# --------------------------------------------------------------------------- #
# Service registry
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class ArcGISLayer:
    url: str          # ".../MapServer" or ".../FeatureServer"
    layer_id: int
    name: str

    @property
    def query_url(self) -> str:
        return f"{self.url}/{self.layer_id}/query"

    @property
    def layer_url(self) -> str:
        return f"{self.url}/{self.layer_id}"


# --- Source selection note --------------------------------------------------
# The brief's TNRIS endpoint (feature.tnris.org) is unreachable post TNRIS->TxGIO
# migration, and the direct FEMA/USFWS hosts are not reachable from every network.
# We therefore source from the authoritative ArcGIS Online hosted equivalents,
# which are stable and key-free:
#   * Parcels  -> Aransas County Appraisal District (the county's own parcels,
#                 current + authoritative; already scoped to the county).
#   * Wetlands -> Esri "USA Wetlands" (hosted USFWS National Wetlands Inventory).
#   * Flood    -> Esri "USA Flood Hazard Areas" (hosted FEMA NFHL), SFHA only.
#   * Transmission -> HIFLD Electric Power Transmission Lines.
# Each layer's `out_fields` keeps only what we display, to shrink payloads.

# Aransas County Appraisal District - layer 0 is the parcel polygons.
PARCELS = ArcGISLayer(
    url="https://services8.arcgis.com/91dtIBbR8eaxrmHR/arcgis/rest/services/AransasCADWebService/FeatureServer",
    layer_id=0,
    name="parcels",
)
PARCEL_FIELDS = "prop_id,file_as_name,legal_acreage,city,legal_desc,market"

# USFWS National Wetlands Inventory, hosted by Esri as "USA Wetlands".
WETLANDS = ArcGISLayer(
    url="https://services.arcgis.com/P3ePLMYs2RVChkJx/arcgis/rest/services/USA_Wetlands/FeatureServer",
    layer_id=0,
    name="wetlands",
)

# FEMA National Flood Hazard Layer, hosted by Esri as "USA Flood Hazard Areas".
# We keep only the Special Flood Hazard Area (1%-annual-chance) polygons.
FEMA_FLOOD = ArcGISLayer(
    url="https://services.arcgis.com/P3ePLMYs2RVChkJx/arcgis/rest/services/USA_Flood_Hazard_Reduced_Set_gdb/FeatureServer",
    layer_id=0,
    name="flood",
)
FEMA_SFHA_WHERE = "SFHA_TF='T'"

# HIFLD Electric Power Transmission Lines (ArcGIS Online hosted feature service).
TRANSMISSION = ArcGISLayer(
    url="https://services1.arcgis.com/Hp6G80Pky0om7QvQ/arcgis/rest/services/Electric_Power_Transmission_Lines/FeatureServer",
    layer_id=0,
    name="transmission",
)

USER_AGENT = "BuildableLandAnalysis/0.1 (assignment; public data)"


# --------------------------------------------------------------------------- #
# Client
# --------------------------------------------------------------------------- #


class ArcGISError(RuntimeError):
    pass


def get_layer_meta(layer: ArcGISLayer, *, verify: bool = True, timeout: int = 60) -> dict[str, Any]:
    """Fetch a layer's JSON metadata (fields, maxRecordCount, extent)."""
    resp = requests.get(
        layer.layer_url,
        params={"f": "json"},
        headers={"User-Agent": USER_AGENT},
        verify=verify,
        timeout=timeout,
    )
    resp.raise_for_status()
    meta = resp.json()
    if "error" in meta:
        raise ArcGISError(f"{layer.name} meta: {meta['error']}")
    return meta


def query_features(
    layer: ArcGISLayer,
    *,
    where: str = "1=1",
    geometry: dict[str, Any] | None = None,
    out_fields: str = "*",
    page_size: int = 1000,
    out_sr: int = 4326,
    verify: bool = True,
    timeout: int = 120,
    max_features: int | None = None,
) -> Iterator[dict[str, Any]]:
    """Yield GeoJSON Feature dicts from an ArcGIS layer, following paging.

    ``geometry`` is an ArcGIS envelope dict (xmin/ymin/xmax/ymax + spatialReference)
    used as an intersects filter; ``where`` is an attribute SQL filter. Combine or
    use either alone.
    """
    offset = 0
    yielded = 0
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})

    while True:
        params: dict[str, Any] = {
            "where": where,
            "outFields": out_fields,
            "returnGeometry": "true",
            "outSR": out_sr,
            "f": "geojson",
            "resultOffset": offset,
            "resultRecordCount": page_size,
        }
        if geometry is not None:
            params.update(
                {
                    "geometry": _envelope_str(geometry),
                    "geometryType": "esriGeometryEnvelope",
                    "inSR": geometry.get("spatialReference", {}).get("wkid", 4326),
                    "spatialRel": "esriSpatialRelIntersects",
                }
            )

        data = _get_json(session, layer.query_url, params, verify=verify, timeout=timeout)
        features = data.get("features", [])
        if not features:
            break

        for feat in features:
            if feat.get("geometry") is None:
                continue
            yield feat
            yielded += 1
            if max_features is not None and yielded >= max_features:
                return

        # ArcGIS signals more pages via exceededTransferLimit; some services omit
        # it, so we also stop when a short page comes back.
        more = data.get("exceededTransferLimit") or data.get("properties", {}).get(
            "exceededTransferLimit"
        )
        if not more and len(features) < page_size:
            break
        offset += len(features)
        time.sleep(0.1)  # be polite to public endpoints


def _get_json(session, url, params, *, verify, timeout, retries=3) -> dict[str, Any]:
    last_exc: Exception | None = None
    for attempt in range(retries):
        try:
            resp = session.get(url, params=params, verify=verify, timeout=timeout)
            resp.raise_for_status()
            data = resp.json()
            if "error" in data:
                raise ArcGISError(str(data["error"]))
            return data
        except (requests.RequestException, ArcGISError) as exc:  # transient
            last_exc = exc
            time.sleep(1.5 * (attempt + 1))
    raise ArcGISError(f"request failed after {retries} attempts: {last_exc}")


def _envelope_str(env: dict[str, Any]) -> str:
    return f"{env['xmin']},{env['ymin']},{env['xmax']},{env['ymax']}"


def envelope(bbox: tuple[float, float, float, float], wkid: int = 4326) -> dict[str, Any]:
    xmin, ymin, xmax, ymax = bbox
    return {
        "xmin": xmin,
        "ymin": ymin,
        "xmax": xmax,
        "ymax": ymax,
        "spatialReference": {"wkid": wkid},
    }
