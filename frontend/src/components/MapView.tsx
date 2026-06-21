import { useEffect, useRef } from "react";
import maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import type { AppConfig, DrawMode, Edits } from "../types";

interface Props {
  config: AppConfig;
  parcels: GeoJSON.FeatureCollection | null;
  result: GeoJSON.FeatureCollection | null;
  edits: Edits;
  drawMode: DrawMode;
  onParcelClick: (parcelId: string) => void;
  onMapMove: (bbox: [number, number, number, number]) => void;
  onDrawCreate: (geom: GeoJSON.Geometry) => void;
}

const EMPTY: GeoJSON.FeatureCollection = { type: "FeatureCollection", features: [] };

// Esri World Imagery - free satellite raster, no API key. Ideal for land context.
const SATELLITE_STYLE: maplibregl.StyleSpecification = {
  version: 8,
  sources: {
    sat: {
      type: "raster",
      tiles: [
        "https://services.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
      ],
      tileSize: 256,
      attribution: "Imagery © Esri",
    },
  },
  layers: [{ id: "sat", type: "raster", source: "sat" }],
};

function editsToFC(edits: Edits): GeoJSON.FeatureCollection {
  const f = (g: GeoJSON.Geometry, kind: string): GeoJSON.Feature => ({
    type: "Feature",
    geometry: g,
    properties: { kind },
  });
  return {
    type: "FeatureCollection",
    features: [
      ...edits.carveouts.map((g) => f(g, "carve")),
      ...edits.restores.map((g) => f(g, "restore")),
    ],
  };
}

export default function MapView(props: Props) {
  const mapRef = useRef<maplibregl.Map | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const loadedRef = useRef(false);

  // Draw state kept in refs so map event handlers always see the latest values.
  const drawModeRef = useRef<DrawMode>(props.drawMode);
  const vertsRef = useRef<[number, number][]>([]);
  drawModeRef.current = props.drawMode;

  const onParcelClick = useRef(props.onParcelClick);
  const onMapMove = useRef(props.onMapMove);
  const onDrawCreate = useRef(props.onDrawCreate);
  onParcelClick.current = props.onParcelClick;
  onMapMove.current = props.onMapMove;
  onDrawCreate.current = props.onDrawCreate;

  // ---- init once ----
  useEffect(() => {
    if (mapRef.current || !containerRef.current) return;
    const center = props.config.center ?? [-97.05, 28.02];
    const map = new maplibregl.Map({
      container: containerRef.current,
      style: SATELLITE_STYLE,
      center,
      zoom: 12,
    });
    mapRef.current = map;
    if (import.meta.env.DEV) (window as any).__map = map; // dev-only handle for testing
    map.addControl(new maplibregl.NavigationControl(), "top-right");
    map.addControl(new maplibregl.ScaleControl({ unit: "imperial" }), "bottom-right");
    if (props.config.bbox) {
      const [minx, miny, maxx, maxy] = props.config.bbox;
      map.fitBounds([[minx, miny], [maxx, maxy]], { padding: 40, duration: 0 });
    }

    map.on("load", () => {
      // Sources
      map.addSource("parcels", { type: "geojson", data: EMPTY });
      map.addSource("analysis", { type: "geojson", data: EMPTY });
      map.addSource("edits", { type: "geojson", data: EMPTY });
      map.addSource("draw", { type: "geojson", data: EMPTY });

      // Parcels (clickable). Fill is near-transparent; line is the visible part.
      map.addLayer({
        id: "parcels-fill",
        type: "fill",
        source: "parcels",
        paint: { "fill-color": "#ffffff", "fill-opacity": 0.04 },
      });
      map.addLayer({
        id: "parcels-line",
        type: "line",
        source: "parcels",
        paint: { "line-color": "#cfd8e3", "line-width": 0.7, "line-opacity": 0.55 },
      });

      // Analysis result
      map.addLayer({
        id: "excluded-fill",
        type: "fill",
        source: "analysis",
        filter: ["==", ["get", "kind"], "excluded"],
        paint: { "fill-color": "#e74c3c", "fill-opacity": 0.5 },
      });
      map.addLayer({
        id: "buildable-fill",
        type: "fill",
        source: "analysis",
        filter: ["==", ["get", "kind"], "buildable"],
        paint: { "fill-color": "#2ecc71", "fill-opacity": 0.55 },
      });
      map.addLayer({
        id: "parcel-outline",
        type: "line",
        source: "analysis",
        filter: ["==", ["get", "kind"], "parcel"],
        paint: { "line-color": "#ffffff", "line-width": 2.2 },
      });

      // User edits
      map.addLayer({
        id: "carve-line",
        type: "line",
        source: "edits",
        filter: ["==", ["get", "kind"], "carve"],
        paint: { "line-color": "#e67e22", "line-width": 2, "line-dasharray": [2, 1] },
      });
      map.addLayer({
        id: "restore-line",
        type: "line",
        source: "edits",
        filter: ["==", ["get", "kind"], "restore"],
        paint: { "line-color": "#4aa3ff", "line-width": 2, "line-dasharray": [2, 1] },
      });

      // In-progress drawing
      map.addLayer({
        id: "draw-fill",
        type: "fill",
        source: "draw",
        filter: ["==", ["geometry-type"], "Polygon"],
        paint: { "fill-color": "#f1c40f", "fill-opacity": 0.2 },
      });
      map.addLayer({
        id: "draw-line",
        type: "line",
        source: "draw",
        paint: { "line-color": "#f1c40f", "line-width": 2 },
      });
      map.addLayer({
        id: "draw-points",
        type: "circle",
        source: "draw",
        filter: ["==", ["geometry-type"], "Point"],
        paint: { "circle-radius": 4, "circle-color": "#f1c40f", "circle-stroke-color": "#000", "circle-stroke-width": 1 },
      });

      loadedRef.current = true;
      setData(map, "parcels", props.parcels);
      setData(map, "analysis", props.result);
      setData(map, "edits", editsToFC(props.edits));
      emitMove(map);
      map.getCanvas().style.cursor = "";
    });

    const emitMove = (m: maplibregl.Map) => {
      const b = m.getBounds();
      onMapMove.current([b.getWest(), b.getSouth(), b.getEast(), b.getNorth()]);
    };

    // ---- interactions ----
    map.on("moveend", () => emitMove(map));

    map.on("click", (e) => {
      if (drawModeRef.current) {
        addVertex(map, [e.lngLat.lng, e.lngLat.lat]);
        return;
      }
      const hits = map.queryRenderedFeatures(e.point, { layers: ["parcels-fill"] });
      const pid = hits[0]?.properties?.parcel_id;
      if (pid != null) onParcelClick.current(String(pid));
    });

    map.on("mousemove", (e) => {
      if (!drawModeRef.current || vertsRef.current.length === 0) return;
      renderDraw(map, [e.lngLat.lng, e.lngLat.lat]);
    });

    map.on("dblclick", (e) => {
      if (!drawModeRef.current) return;
      e.preventDefault();
      finishDraw(map);
    });

    const onKey = (ev: KeyboardEvent) => {
      if (ev.key === "Enter") finishDraw(map);
      if (ev.key === "Escape") cancelDraw(map);
    };
    window.addEventListener("keydown", onKey);

    return () => {
      window.removeEventListener("keydown", onKey);
      map.remove();
      mapRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // ---- prop -> source updates ----
  useEffect(() => {
    const map = mapRef.current;
    if (map && loadedRef.current) setData(map, "parcels", props.parcels);
  }, [props.parcels]);

  useEffect(() => {
    const map = mapRef.current;
    if (map && loadedRef.current) setData(map, "analysis", props.result);
  }, [props.result]);

  useEffect(() => {
    const map = mapRef.current;
    if (map && loadedRef.current) setData(map, "edits", editsToFC(props.edits));
  }, [props.edits]);

  // Cursor + reset partial drawing when the tool toggles.
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    map.doubleClickZoom[props.drawMode ? "disable" : "enable"]();
    map.getCanvas().style.cursor = props.drawMode ? "crosshair" : "";
    if (!props.drawMode) cancelDraw(map);
  }, [props.drawMode]);

  // ---- draw helpers ----
  function addVertex(map: maplibregl.Map, pt: [number, number]) {
    vertsRef.current = [...vertsRef.current, pt];
    renderDraw(map, pt);
  }

  function renderDraw(map: maplibregl.Map, cursor: [number, number]) {
    const verts = vertsRef.current;
    if (verts.length === 0) {
      setData(map, "draw", EMPTY);
      return;
    }
    const ring = [...verts, cursor];
    const features: GeoJSON.Feature[] = verts.map((v) => ({
      type: "Feature",
      geometry: { type: "Point", coordinates: v },
      properties: {},
    }));
    if (ring.length >= 3) {
      features.push({
        type: "Feature",
        geometry: { type: "Polygon", coordinates: [[...ring, ring[0]]] },
        properties: {},
      });
    } else {
      features.push({
        type: "Feature",
        geometry: { type: "LineString", coordinates: ring },
        properties: {},
      });
    }
    setData(map, "draw", { type: "FeatureCollection", features });
  }

  function finishDraw(map: maplibregl.Map) {
    const verts = vertsRef.current;
    if (verts.length < 3) return;
    const geom: GeoJSON.Geometry = {
      type: "Polygon",
      coordinates: [[...verts, verts[0]]],
    };
    vertsRef.current = [];
    setData(map, "draw", EMPTY);
    onDrawCreate.current(geom);
  }

  function cancelDraw(map: maplibregl.Map) {
    vertsRef.current = [];
    setData(map, "draw", EMPTY);
  }

  return <div id="map" ref={containerRef} />;
}

function setData(map: maplibregl.Map, id: string, data: GeoJSON.FeatureCollection | null) {
  const src = map.getSource(id) as maplibregl.GeoJSONSource | undefined;
  if (src) src.setData(data ?? EMPTY);
}
