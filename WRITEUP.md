# Buildable Land Analysis - Writeup

## What it does

Given a parcel and a set of constraint layers, it works out the **buildable area**  - 
the land left after you remove what you legally or physically can't build on (wetlands,
the FEMA 100-year floodplain, transmission-line easements), each with a configurable
setback. It shows buildable vs. excluded on a map, breaks down what each layer removed,
and lets you adjust the result by hand (carve out / add back) with totals updating live.

It runs on real Aransas County, TX data: ~26,300 parcels, ~20,000 wetland polygons,
441 floodplain polygons, 13 transmission lines.

---

## Approach

### The geometry, and the one thing that has to be right

All distance and area math happens in an **equal-area projected CRS - EPSG:3083**
(Texas Centric Albers, metres). Doing buffers or areas in raw lon/lat degrees would be
meaningless; this is the single most important modelling decision. Lon/lat (EPSG:4326)
is used only for storage, the API, and the map.

The pipeline per parcel `P`:

1. For each enabled layer: take its features near the parcel, **buffer** by the setback,
   **clip** to `P` (only intra-parcel area can count).
2. `excluded = union(buffered, clipped constraints)`, `buildable = P − excluded`.
3. Apply user edits: `excluded = (excluded ∪ carve-outs) − restores`; restores are
   clipped to `P`, so you can't add back land that was never in the parcel.

### A breakdown that actually adds up

Constraints overlap (a wetland inside the floodplain, an easement crossing both), so a
naive per-layer area double-counts. The breakdown uses **greedy attribution by priority**:
layers are processed in priority order and each is credited only with the area it removes
that a higher-priority layer hasn't already claimed. The result is two guarantees the UI
relies on and the tests enforce:

```
buildable_acres + excluded_acres == parcel_acres
sum(per-layer net acres)         == excluded_acres
```

The response also reports each layer's **gross** (overlap-inclusive) area for transparency.
`backend/tests/test_analysis.py` proves both invariants, plus carve-out and
restore-within-parcel behaviour, on synthetic geometries.

### Architecture

- **Backend is stateless.** `POST /analyze` takes the parcel id, the setbacks to use, and
  the user's edits, and returns the geometry + breakdown + totals. No session state, so the
  same call always yields the same answer and it scales horizontally.
- **Frontend holds the scenario** (selected parcel, setback overrides, edit list) and
  re-posts, debounced, whenever any of it changes. Setbacks come from the server config but
  are overridable per request - which is how the sliders re-run without touching code.

---

## Data and setback choices (with sources)

### A note on the data source (attention-to-detail item)

The brief points at `data.tnris.org`. That URL is **dead** - it fails a TLS certificate
check, because **TNRIS was renamed to TxGIO** (Texas Geographic Information Office) and the
program migrated to texas.gov. The current home is `data.geographic.texas.gov`, with the
StratMap layers also on TxGIO's ArcGIS services. (I flagged this to the recruiter as a
heads-up rather than treat it as a blocker.)

In addition, from the network I built this on, the *direct* agency hosts
(`hazards.fema.gov`, USFWS, `feature.tnris.org`) weren't reliably reachable, so I sourced
each dataset from its **authoritative ArcGIS Online hosted equivalent**, which is stable and
key-free. The source registry is in `backend/app/data/sources.py`.

### Layers, sources, and setbacks

| Layer | Source used | Default setback | Why this number |
|------|-------------|-----------------|-----------------|
| **Parcels** | Aransas County Appraisal District (authoritative, current) | - | the parcel itself |
| **Wetlands** | USFWS National Wetlands Inventory (Esri "USA Wetlands") | **50 ft** | local wetland-buffer ordinances commonly require 25-100 ft vegetated buffers; 50 ft is a defensible mid-range default |
| **FEMA floodplain** | FEMA NFHL, SFHA only (Esri "USA Flood Hazard Areas") | **0 ft** | the Special Flood Hazard Area (1%-annual-chance) is treated as non-buildable - exclude the zone itself; raise it to model freeboard/build-line |
| **Transmission** | HIFLD Electric Power Transmission Lines | **75 ft / side** | ROW half-widths vary by voltage (~50-150 ft); 75 ft is reasonable for mixed-voltage lines |

The brief says it cares more about *reasoning and sources* than an exact figure - agreed.
Every value lives in `config/setbacks.yaml` with a source note, and every value is a slider
in the UI. The wetland buffer or easement width can be changed and re-run in seconds.

### Calls I made

- **County: Aransas**, deliberately not the obvious large coastal county. It's small enough
  to be "manageable" yet constraint-rich (bay + barrier islands), so the demo shows real
  exclusions without a giant download.
- **Parcels from the county CAD** rather than the statewide StratMap mirror: current,
  authoritative, and already county-scoped. Trade-off: it's Aransas-specific, so another
  county needs a different parcel source (the code keeps the source in one small registry).
- **FEMA SFHA as a hard exclusion (0 ft)** rather than a buffer - that's how a floodplain is
  usually treated; freeboard is then just a non-zero setback.
- **Building footprints layer is wired but disabled** by default (coverage is uneven and it
  inflates compute); flip `enabled: true` in the config to add it.

---

## Performance - how it behaves as data grows

The county data is fetched once into a GeoPackage, loaded **once** into memory, and indexed
(GeoPandas spatial index / Shapely STRtree). A single analysis then only touches the
constraint features **near the parcel** (a bbox query against the index), so the
buffer/union/difference runs on a handful of geometries and completes in well under a second.

Crucially, **changing a setback or drawing an edit re-runs the analysis but reuses the cached
layers - no re-fetch.** The cost of an analysis is roughly proportional to the number of
constraint features touching that one parcel, *not* to the size of the county.

Where it would start to strain, and what I'd do:

- **Loading a metro county** (hundreds of thousands to millions of parcels) fully into
  process memory is the real ceiling. Next step: push geometry into **PostGIS** and query
  per-parcel, so memory and indexing live in the database, not the web process.
- **Very large adjacent wetland/flood polygons** make the union/buffer costlier. Mitigation:
  pre-simplify for display, and pre-clip constraints to parcel neighbourhoods.
- **Rendering many parcels** in the browser: the parcel layer is capped to the viewport
  (≤600 features) today; **vector tiles** would scale this to whole-county pan/zoom.
- **Concurrency**: the API is stateless and scales out horizontally; the per-process
  in-memory cache should become a shared spatial DB so instances don't each hold a copy.

---

## Where it breaks / what I'd do next

- **Overlapping CAD polygons.** The appraisal layer contains overlapping tract/abstract
  polygons, so a click can select the topmost of several; I'd de-duplicate or filter to a
  single parcel class on ingest.
- **Uniform setbacks per layer.** Real rules vary by transmission voltage, wetland class, and
  jurisdiction. The data carries those attributes (`VOLTAGE`, wetland `CLASS`) - I'd drive
  setbacks from them instead of one number per layer.
- **No saved scenarios.** Edits and setback tweaks are in-memory on the client; I'd add
  save/share of a scenario (parcel + setbacks + edits) for collaboration.
- **More constraints.** Protected areas (PAD-US), pipelines, and steep slopes/DEM-derived
  constraints are natural additions; the layer registry is built to take them.
- **Precompute.** For a fixed setback profile, the whole county's buildable area could be
  precomputed and tiled, making the map instant and the per-parcel call a lookup.

---

## Verifying it yourself

```bash
cd backend && python -m pytest          # reconciliation invariants
```

Then run both servers (see README), click a constraint-heavy waterfront parcel, drag the
wetland setback up and watch buildable shrink, draw a carve-out (buildable drops) and a
restore (it comes back) - the totals reconcile at every step.
