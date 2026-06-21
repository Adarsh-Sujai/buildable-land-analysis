import type { AnalyzeResponse, AppConfig, DrawMode, LayerInfo } from "../types";
import SetbackControls from "./SetbackControls";

interface Props {
  config: AppConfig;
  selectedParcel: string | null;
  result: AnalyzeResponse | null;
  loading: boolean;
  error: string | null;
  setbacks: Record<string, number>;
  onSetbackChange: (key: string, value: number) => void;
  drawMode: DrawMode;
  onDrawMode: (m: DrawMode) => void;
  editCount: number;
  onClearEdits: () => void;
}

const fmt = (n: number) => n.toLocaleString(undefined, { maximumFractionDigits: 2 });

export default function Sidebar(props: Props) {
  const { config, result, totals } = { ...props, totals: props.result?.totals };

  return (
    <div className="sidebar">
      <h1>Buildable Land Analysis</h1>
      <p className="sub">
        {config.county} County, TX &middot; {config.parcel_count.toLocaleString()} parcels
      </p>

      {!props.selectedParcel && (
        <div className="card">
          <p className="hint">
            Click any parcel on the map to compute its buildable area. The analysis subtracts
            constraint layers (each with a configurable setback) and reconciles exactly:
            <br />
            <strong>buildable + excluded = parcel</strong>.
          </p>
        </div>
      )}

      {props.error && (
        <div className="card">
          <p className="err">⚠ {props.error}</p>
        </div>
      )}

      {totals && (
        <div className="card">
          <h2>
            Buildable{" "}
            {props.loading && <span className="spinner" />}
          </h2>
          <div className="headline">
            <span className="big">{fmt(totals.buildable_acres)}</span>
            <span className="unit">acres &middot; {totals.buildable_pct}% of parcel</span>
          </div>
          <div className="bar">
            <span style={{ width: `${totals.buildable_pct}%` }} />
          </div>
          <div className="totrow">
            <span className="muted">Parcel</span>
            <span>{fmt(totals.parcel_acres)} ac</span>
          </div>
          <div className="totrow">
            <span className="muted">Excluded</span>
            <span>{fmt(totals.excluded_acres)} ac</span>
          </div>
          {totals.restored_acres > 0 && (
            <div className="totrow">
              <span className="muted">Restored (added back)</span>
              <span>+{fmt(totals.restored_acres)} ac</span>
            </div>
          )}
        </div>
      )}

      {result && result.breakdown.length > 0 && (
        <div className="card">
          <h2>What was removed</h2>
          <table className="breakdown">
            <tbody>
              {result.breakdown.map((b) => (
                <tr key={b.key}>
                  <td>
                    <span className="swatch" style={{ background: b.color }} />
                    {b.label}
                    {b.setback_ft > 0 ? ` · ${b.setback_ft}ft` : ""}
                  </td>
                  <td className="num">{fmt(b.net_acres)} ac</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {props.selectedParcel && (
        <div className="card">
          <h2>Edit by hand</h2>
          <div className="btnrow">
            <button
              className={`tool carve ${props.drawMode === "carve" ? "active" : ""}`}
              onClick={() => props.onDrawMode(props.drawMode === "carve" ? null : "carve")}
            >
              ✂ Carve out
            </button>
            <button
              className={`tool restore ${props.drawMode === "restore" ? "active" : ""}`}
              onClick={() => props.onDrawMode(props.drawMode === "restore" ? null : "restore")}
            >
              ＋ Add back
            </button>
          </div>
          <p className="hint" style={{ marginTop: 10 }}>
            {props.drawMode
              ? "Click to place points, double-click (or Enter) to finish. Esc cancels."
              : "Draw an area to exclude (carve out) or to restore (add back). Totals update live."}
          </p>
          {props.editCount > 0 && (
            <button className="ghost" onClick={props.onClearEdits} style={{ marginTop: 8 }}>
              Clear {props.editCount} edit{props.editCount > 1 ? "s" : ""}
            </button>
          )}
        </div>
      )}

      <div className="card">
        <h2>Setbacks (configurable)</h2>
        <SetbackControls
          layers={config.layers as LayerInfo[]}
          values={props.setbacks}
          onChange={props.onSetbackChange}
        />
      </div>
    </div>
  );
}
