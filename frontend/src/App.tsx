import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import MapView from "./components/MapView";
import Sidebar from "./components/Sidebar";
import * as api from "./api";
import type { AnalyzeResponse, AppConfig, DrawMode, Edits } from "./types";

const EMPTY_EDITS: Edits = { carveouts: [], restores: [] };

export default function App() {
  const [config, setConfig] = useState<AppConfig | null>(null);
  const [parcels, setParcels] = useState<GeoJSON.FeatureCollection | null>(null);
  const [selectedParcel, setSelectedParcel] = useState<string | null>(null);
  const [setbacks, setSetbacks] = useState<Record<string, number>>({});
  const [edits, setEdits] = useState<Edits>(EMPTY_EDITS);
  const [drawMode, setDrawMode] = useState<DrawMode>(null);
  const [result, setResult] = useState<AnalyzeResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // ---- load config once ----
  useEffect(() => {
    api
      .getConfig()
      .then((cfg) => {
        setConfig(cfg);
        const defaults: Record<string, number> = {};
        cfg.layers.forEach((l) => (defaults[l.key] = l.setback_ft));
        setSetbacks(defaults);
        if (!cfg.data_available) {
          setError("No data cached. Run: python -m app.data.fetch_data");
        }
      })
      .catch((e) => setError(String(e.message ?? e)));
  }, []);

  // ---- fetch parcels for the current viewport (debounced) ----
  const parcelTimer = useRef<number | undefined>(undefined);
  const onMapMove = useCallback((bbox: [number, number, number, number]) => {
    window.clearTimeout(parcelTimer.current);
    parcelTimer.current = window.setTimeout(() => {
      api
        .getParcels(bbox, 600)
        .then(setParcels)
        .catch(() => {});
    }, 250);
  }, []);

  // ---- run analysis when the selection / setbacks / edits change (debounced) ----
  const setbacksKey = JSON.stringify(setbacks);
  const editsKey = JSON.stringify(edits);
  const analyzeTimer = useRef<number | undefined>(undefined);
  const reqSeq = useRef(0);

  useEffect(() => {
    if (!selectedParcel) {
      setResult(null);
      return;
    }
    window.clearTimeout(analyzeTimer.current);
    setLoading(true);
    const seq = ++reqSeq.current;
    analyzeTimer.current = window.setTimeout(() => {
      api
        .analyze({ parcelId: selectedParcel, setbacks, edits })
        .then((res) => {
          if (seq === reqSeq.current) {
            setResult(res);
            setError(null);
          }
        })
        .catch((e) => {
          if (seq === reqSeq.current) setError(String(e.message ?? e));
        })
        .finally(() => {
          if (seq === reqSeq.current) setLoading(false);
        });
    }, 200);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedParcel, setbacksKey, editsKey]);

  // ---- handlers ----
  const onParcelClick = useCallback((id: string) => {
    setSelectedParcel(id);
    setEdits(EMPTY_EDITS); // edits are parcel-specific
    setDrawMode(null);
  }, []);

  const onSetbackChange = useCallback((key: string, value: number) => {
    setSetbacks((s) => ({ ...s, [key]: value }));
  }, []);

  const onDrawCreate = useCallback(
    (geom: GeoJSON.Geometry) => {
      setEdits((e) =>
        drawMode === "restore"
          ? { ...e, restores: [...e.restores, geom] }
          : { ...e, carveouts: [...e.carveouts, geom] },
      );
    },
    [drawMode],
  );

  const onClearEdits = useCallback(() => setEdits(EMPTY_EDITS), []);

  const resultFC = useMemo(() => result?.result ?? null, [result]);
  const editCount = edits.carveouts.length + edits.restores.length;

  if (!config) {
    return (
      <div style={{ padding: 24 }}>
        {error ? <p className="err">⚠ {error}</p> : <p>Loading…</p>}
      </div>
    );
  }

  return (
    <div className="app">
      <Sidebar
        config={config}
        selectedParcel={selectedParcel}
        result={result}
        loading={loading}
        error={error}
        setbacks={setbacks}
        onSetbackChange={onSetbackChange}
        drawMode={drawMode}
        onDrawMode={setDrawMode}
        editCount={editCount}
        onClearEdits={onClearEdits}
      />
      <div className="map-wrap">
        <MapView
          config={config}
          parcels={parcels}
          result={resultFC}
          edits={edits}
          drawMode={drawMode}
          onParcelClick={onParcelClick}
          onMapMove={onMapMove}
          onDrawCreate={onDrawCreate}
        />
        {drawMode && (
          <div className="statuschip drawing">
            Drawing {drawMode === "carve" ? "carve-out (exclude)" : "restore (add back)"}  - 
            double-click to finish
          </div>
        )}
        <div className="legend">
          <div className="row">
            <span className="swatch" style={{ background: "#2ecc71" }} /> Buildable
          </div>
          <div className="row">
            <span className="swatch" style={{ background: "#e74c3c" }} /> Excluded
          </div>
          <div className="row">
            <span className="swatch" style={{ background: "#e67e22" }} /> Carve-out
          </div>
          <div className="row">
            <span className="swatch" style={{ background: "#4aa3ff" }} /> Restore
          </div>
        </div>
      </div>
    </div>
  );
}
