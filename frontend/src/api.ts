import type { AppConfig, AnalyzeResponse, Edits } from "./types";

async function json<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const detail = await res.text();
    throw new Error(`${res.status}: ${detail}`);
  }
  return res.json() as Promise<T>;
}

export function getConfig(): Promise<AppConfig> {
  return fetch("/api/config").then((r) => json<AppConfig>(r));
}

export function getParcels(
  bbox: [number, number, number, number],
  limit = 500,
): Promise<GeoJSON.FeatureCollection> {
  const q = `${bbox.join(",")}`;
  return fetch(`/api/parcels?bbox=${q}&limit=${limit}`).then((r) =>
    json<GeoJSON.FeatureCollection>(r),
  );
}

export interface AnalyzeArgs {
  parcelId: string;
  setbacks: Record<string, number>;
  edits: Edits;
}

export function analyze({ parcelId, setbacks, edits }: AnalyzeArgs): Promise<AnalyzeResponse> {
  return fetch("/api/analyze", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      parcel_id: parcelId,
      setbacks,
      carveouts: edits.carveouts,
      restores: edits.restores,
    }),
  }).then((r) => json<AnalyzeResponse>(r));
}
