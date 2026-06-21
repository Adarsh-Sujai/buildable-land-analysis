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
