# Buildable Land Analysis

Given a land parcel and a set of constraint layers (wetlands, FEMA floodplain,
transmission-line easements - each with a configurable **setback**), this app
computes how much of the parcel is actually **buildable**, shows buildable vs.
excluded on an interactive map, and lets you **carve out** and **add back** areas
by hand with the totals updating live.

Demo county: **Aransas County, TX** (Aransas Bay / barrier islands - wetland- and
floodplain-rich, ~26,000 parcels).

A parcel on the satellite map renders as **green (buildable)** vs. **red (excluded)**, with
a live sidebar showing the buildable acreage, a reconciling breakdown of what each layer
removed, configurable setback sliders, and carve-out / add-back drawing tools.

---

## Stack

| Part | Tech |
|------|------|
| Backend | Python 3.12+ / FastAPI, Shapely 2, GeoPandas, pyproj |
| Frontend | React + TypeScript (Vite), MapLibre GL JS (no API key) |
| Geometry | All area/buffer math in **EPSG:3083** (Texas Albers Equal Area, metres) |
| Data | TxGIO/CAD parcels, USFWS NWI wetlands, FEMA NFHL, HIFLD - all public/free |

---

## Quick start (from a clean checkout)

You need **Python 3.10+** and **Node 18+**.

### 1. Backend

```bash
cd backend
python -m pip install -r requirements.txt

# One-time data fetch (needs internet). Downloads the county's parcels +
# constraint layers into backend/data/aransas.gpkg. Takes a couple of minutes.
python -m app.data.fetch_data            # add --insecure if behind a TLS-inspecting proxy

# Run the API
python -m uvicorn app.main:app --reload  # http://localhost:8000  (docs at /docs)
```

### 2. Frontend (separate terminal)

```bash
cd frontend
npm install
npm run dev                              # http://localhost:5173
```

Open **http://localhost:5173** and click any parcel.

> The frontend proxies `/api` to `localhost:8000` (see `vite.config.ts`), so you
> only need both processes running - no CORS setup.

### 3. Tests

```bash
cd backend
python -m pytest            # proves the reconciliation invariants on the geometry engine
```

---

## Data sources

The dataset is **not committed** to the repo: the built GeoPackage is ~145 MB (over
GitHub's 100 MB per-file limit) and is regenerated from public services by the one-time
`fetch_data` step above. No manual download is needed, but here is exactly what the fetch
pulls and from where, all public and key-free:

| Layer | Provider | Live service |
|-------|----------|--------------|
| Parcels | Aransas County Appraisal District (CAD) | [AransasCADWebService](https://services8.arcgis.com/91dtIBbR8eaxrmHR/arcgis/rest/services/AransasCADWebService/FeatureServer/0) |
| Wetlands | USFWS National Wetlands Inventory (hosted by Esri as "USA Wetlands") | [USA_Wetlands](https://services.arcgis.com/P3ePLMYs2RVChkJx/arcgis/rest/services/USA_Wetlands/FeatureServer/0) |
| FEMA flood (SFHA, 1% annual chance) | FEMA National Flood Hazard Layer (hosted by Esri as "USA Flood Hazard Areas") | [USA_Flood_Hazard](https://services.arcgis.com/P3ePLMYs2RVChkJx/arcgis/rest/services/USA_Flood_Hazard_Reduced_Set_gdb/FeatureServer/0) |
| Transmission lines | HIFLD Electric Power Transmission Lines | [Electric_Power_Transmission_Lines](https://services1.arcgis.com/Hp6G80Pky0om7QvQ/arcgis/rest/services/Electric_Power_Transmission_Lines/FeatureServer/0) |

**On the brief's parcel link:** `https://data.tnris.org` is no longer reachable, TNRIS has
become **TxGIO** and its data moved to [data.geographic.texas.gov](https://data.geographic.texas.gov)
(the StratMap parcel layers are also on TxGIO's ArcGIS services). To stay unblocked I used
the Aransas CAD parcel service above; the other layers come from the authoritative hosted
services listed. Full rationale is in [WRITEUP.md](WRITEUP.md).

Provider landing pages, for manual download if ever needed: USFWS NWI
[wetlands data](https://www.fws.gov/program/national-wetlands-inventory/wetlands-data),
FEMA [NFHL](https://www.fema.gov/flood-maps/national-flood-hazard-layer), HIFLD
[Open Data](https://hifld-geoplatform.hub.arcgis.com/).

---

## Using it

1. **Click a parcel** → it computes buildable (green) vs. excluded (red) and a
   breakdown of what was removed and why.
2. **Drag the setback sliders** (wetland buffer, flood, easement) → re-runs live.
   No code edit needed; defaults live in [`config/setbacks.yaml`](config/setbacks.yaml).
3. **Carve out** → draw a polygon to exclude extra area (click points,
   double-click to finish).
4. **Add back** → draw a polygon to restore area (clipped to the parcel, so you
   can't restore land that was never in it).
5. The total and breakdown always reconcile: **buildable + excluded = parcel**, and
   the breakdown sums to the excluded total.

---

## Configuring constraints & setbacks

Everything modelled is declared in [`config/setbacks.yaml`](config/setbacks.yaml):
enable/disable a layer, change its default setback (feet), priority, or colour  - 
no code change. Per-request overrides from the map sliders take precedence.

Pick a different county with `--county` (the cache filename follows it); see the
writeup for what the bundled data source covers.

---

## Layout

```
backend/
  app/
    geo/analysis.py      # the core: buildable area + reconciling breakdown
    geo/crs.py           # projection + area helpers
    data/                # ArcGIS REST client, GeoPackage cache, fetch CLI
    routers/             # /api/parcels, /api/analyze, /api/config
    services.py          # ties config + store + engine together
  tests/test_analysis.py # invariants on synthetic geometries
config/setbacks.yaml     # configurable constraints + setbacks (+ sources)
frontend/src/            # React app: MapView, Sidebar, SetbackControls
WRITEUP.md               # approach, tradeoffs, data/setback sources, limits
```

See [WRITEUP.md](WRITEUP.md) for the reasoning, data sources, and where it strains.
