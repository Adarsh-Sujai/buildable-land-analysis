import type { LayerInfo } from "../types";

interface Props {
  layers: LayerInfo[];
  values: Record<string, number>;
  onChange: (key: string, value: number) => void;
}

// Reasonable slider range for land-use setbacks (feet).
const MAX_FT = 500;

export default function SetbackControls({ layers, values, onChange }: Props) {
  return (
    <div>
      {layers.map((l) => {
        const v = values[l.key] ?? l.setback_ft;
        return (
          <div className="setback" key={l.key}>
            <label>
              <span>
                <span className="swatch" style={{ background: l.color }} />
                {l.label}
              </span>
              <span className="val">{v} ft</span>
            </label>
            <input
              type="range"
              min={0}
              max={MAX_FT}
              step={5}
              value={v}
              onChange={(e) => onChange(l.key, Number(e.target.value))}
            />
            <div className="src" title={l.rationale}>
              Source: {l.source}
            </div>
          </div>
        );
      })}
    </div>
  );
}
