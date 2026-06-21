export interface LayerInfo {
  key: string;
  label: string;
  setback_ft: number;
  priority: number;
  color: string;
  source: string;
  rationale: string;
}

export interface AppConfig {
  county: string;
  analysis_crs: string;
  data_available: boolean;
  parcel_count: number;
  center: [number, number] | null;
  bbox: [number, number, number, number] | null;
  layers: LayerInfo[];
}

export interface Totals {
  parcel_acres: number;
  buildable_acres: number;
  excluded_acres: number;
  restored_acres: number;
  buildable_pct: number;
}

export interface BreakdownItem {
  key: string;
  label: string;
  color: string;
  setback_ft: number;
  net_acres: number;
  gross_acres: number;
}

export interface AnalyzeResponse {
  parcel_id: string;
  totals: Totals;
  breakdown: BreakdownItem[];
  setbacks_used: Record<string, number>;
  result: GeoJSON.FeatureCollection;
}

export type DrawMode = "carve" | "restore" | null;

export interface Edits {
  carveouts: GeoJSON.Geometry[];
  restores: GeoJSON.Geometry[];
}
