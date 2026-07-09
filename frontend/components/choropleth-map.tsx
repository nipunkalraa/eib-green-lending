"use client";

import { useEffect, useRef, useState } from "react";
import maplibregl, { type Map as MapLibreMap, type MapGeoJSONFeature } from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import { Button } from "@/components/ui/button";
import { MapLegend } from "@/components/map-legend";
import { RegionDetailSheet } from "@/components/region-detail-sheet";
import { formatEUR, formatNumber } from "@/lib/format";
import type { RegionProperties } from "@/lib/types";

const BASEMAP_STYLE = "https://basemaps.cartocdn.com/gl/positron-gl-style/style.json";
const SOURCE_ID = "regions";
const FILL_LAYER = "regions-fill";
const LINE_LAYER = "regions-line";

const COLORS = ["#f3f7f2", "#c8e2d3", "#7fb8ab", "#3d8a76", "#0c5a4a"];

// Fixed to mainland Europe (incl. Iceland/Turkey) rather than computed from
// the raw geometry extent - several countries' polygons include overseas
// territories (French Guiana, Réunion, the Azores, etc.) which would
// otherwise blow the bounding box out to a near-world view.
const EUROPE_BOUNDS: maplibregl.LngLatBoundsLike = [
  [-25, 33],
  [45, 72],
];

interface HoverInfo {
  x: number;
  y: number;
  name: string;
  cntr: string;
  total: number;
  count: number;
}

function quantileBreaks(values: number[], classes: number): number[] {
  const sorted = [...values].sort((a, b) => a - b);
  const breaks: number[] = [];
  for (let i = 1; i < classes; i++) {
    const idx = Math.floor((sorted.length - 1) * (i / classes));
    breaks.push(sorted[idx]);
  }
  return breaks;
}

export function ChoroplethMap() {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<MapLibreMap | null>(null);
  const boundsRef = useRef<maplibregl.LngLatBoundsLike | null>(null);

  const [hover, setHover] = useState<HoverInfo | null>(null);
  const [selected, setSelected] = useState<RegionProperties | null>(null);
  const [sheetOpen, setSheetOpen] = useState(false);
  const [range, setRange] = useState<{ min: number; max: number }>({ min: 0, max: 1 });
  // MapLibre converts GeoJSON to vector tiles internally, which flattens
  // feature properties to primitives - nested arrays like top_sectors don't
  // survive on feature.properties. Keep the original parsed GeoJSON's full
  // properties here, keyed by NUTS_ID, and look up from this instead.
  const regionsByIdRef = useRef<Map<string, RegionProperties>>(new Map());

  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;

    let hoveredId: string | number | null = null;

    const map = new maplibregl.Map({
      container: containerRef.current,
      style: BASEMAP_STYLE,
      center: [10, 50],
      zoom: 3,
      attributionControl: { compact: true },
    });
    mapRef.current = map;
    map.addControl(new maplibregl.NavigationControl({ showCompass: false }), "top-right");

    map.on("load", async () => {
      const res = await fetch("/data/nuts_lending.geojson");
      const geojson = await res.json();

      geojson.features.forEach((f: GeoJSON.Feature) => {
        const props = f.properties as RegionProperties;
        regionsByIdRef.current.set(props.NUTS_ID, props);
      });

      const values: number[] = geojson.features
        .map((f: GeoJSON.Feature) => f.properties?.total_lending_eur as number)
        .filter((v: number) => v > 0);
      const max = Math.max(...values);
      const min = Math.min(...values);
      setRange({ min, max });
      const breaks = quantileBreaks(values, COLORS.length);

      map.addSource(SOURCE_ID, {
        type: "geojson",
        data: geojson,
        promoteId: "NUTS_ID",
      });

      const stepExpr: unknown[] = ["step", ["get", "total_lending_eur"], COLORS[0]];
      breaks.forEach((b, i) => {
        stepExpr.push(b, COLORS[i + 1]);
      });

      map.addLayer({
        id: FILL_LAYER,
        type: "fill",
        source: SOURCE_ID,
        paint: {
          "fill-color": stepExpr as maplibregl.ExpressionSpecification,
          "fill-opacity": ["case", ["boolean", ["feature-state", "hover"], false], 0.95, 0.85],
        },
      });

      map.addLayer({
        id: LINE_LAYER,
        type: "line",
        source: SOURCE_ID,
        paint: {
          "line-color": "#0c5a4a",
          "line-width": ["case", ["boolean", ["feature-state", "hover"], false], 2, 0.5],
          "line-opacity": ["case", ["boolean", ["feature-state", "hover"], false], 1, 0.35],
        },
      });

      boundsRef.current = EUROPE_BOUNDS;
      map.fitBounds(EUROPE_BOUNDS, { padding: 24, duration: 0 });

      map.on("mousemove", FILL_LAYER, (e) => {
        if (!e.features || e.features.length === 0) return;
        const feature = e.features[0] as MapGeoJSONFeature;
        map.getCanvas().style.cursor = "pointer";

        if (hoveredId !== null) {
          map.setFeatureState({ source: SOURCE_ID, id: hoveredId }, { hover: false });
        }
        hoveredId = feature.id ?? null;
        if (hoveredId !== null) {
          map.setFeatureState({ source: SOURCE_ID, id: hoveredId }, { hover: true });
        }

        const id = feature.properties?.NUTS_ID as string | undefined;
        const p = id ? regionsByIdRef.current.get(id) : undefined;
        if (!p) return;
        setHover({
          x: e.point.x,
          y: e.point.y,
          name: p.NUTS_NAME,
          cntr: p.CNTR_CODE,
          total: p.total_lending_eur,
          count: p.project_count,
        });
      });

      map.on("mouseleave", FILL_LAYER, () => {
        map.getCanvas().style.cursor = "";
        if (hoveredId !== null) {
          map.setFeatureState({ source: SOURCE_ID, id: hoveredId }, { hover: false });
        }
        hoveredId = null;
        setHover(null);
      });

      map.on("click", FILL_LAYER, (e) => {
        if (!e.features || e.features.length === 0) return;
        const feature = e.features[0] as MapGeoJSONFeature;
        const id = feature.properties?.NUTS_ID as string | undefined;
        const p = id ? regionsByIdRef.current.get(id) : undefined;
        if (!p) return;
        setSelected(p);
        setSheetOpen(true);
      });
    });

    return () => {
      map.remove();
      mapRef.current = null;
    };
  }, []);

  const resetView = () => {
    if (mapRef.current && boundsRef.current) {
      mapRef.current.fitBounds(boundsRef.current, { padding: 24, duration: 600 });
    }
  };

  return (
    <div className="relative h-[480px] w-full overflow-hidden rounded-xl border border-border">
      <div ref={containerRef} className="h-full w-full" />

      <div className="pointer-events-none absolute left-3 top-3">
        <div className="pointer-events-auto">
          <MapLegend min={range.min} max={range.max} />
        </div>
      </div>

      <div className="absolute bottom-3 left-3">
        <Button size="sm" variant="secondary" onClick={resetView} className="shadow-md">
          Reset view
        </Button>
      </div>

      {hover && (
        <div
          className="pointer-events-none absolute z-10 rounded-lg border border-border bg-popover px-3 py-2 text-xs shadow-lg"
          style={{ left: hover.x + 14, top: hover.y + 14 }}
        >
          <p className="font-medium text-popover-foreground">
            {hover.name} <span className="text-muted-foreground">({hover.cntr})</span>
          </p>
          <p className="text-muted-foreground">{formatEUR(hover.total)}</p>
          <p className="text-muted-foreground">{formatNumber(hover.count)} projects</p>
        </div>
      )}

      <RegionDetailSheet region={selected} open={sheetOpen} onOpenChange={setSheetOpen} />
    </div>
  );
}
