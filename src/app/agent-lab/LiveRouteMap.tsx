"use client";

import { useEffect, useRef, useState } from "react";

type GeoPoint = { latitude: number; longitude: number };

type LiveRouteMapProps = {
  latitude: number;
  longitude: number;
  destinationLatitude: number | null;
  destinationLongitude: number | null;
  destination: string;
  routePolyline: GeoPoint[];
};

export default function LiveRouteMap({
  latitude,
  longitude,
  destinationLatitude,
  destinationLongitude,
  destination,
  routePolyline,
}: LiveRouteMapProps) {
  const elementRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<import("leaflet").Map | null>(null);
  const leafletRef = useRef<typeof import("leaflet") | null>(null);
  const routeLayerRef = useRef<import("leaflet").LayerGroup | null>(null);
  const [mapReady, setMapReady] = useState(false);
  const [tileError, setTileError] = useState(false);

  useEffect(() => {
    let cancelled = false;

    void import("leaflet").then((L) => {
      if (cancelled || !elementRef.current) return;
      setTileError(false);

      const map = L.map(elementRef.current, {
        zoomControl: false,
        attributionControl: true,
        preferCanvas: true,
      });
      mapRef.current = map;
      leafletRef.current = L;

      L.control.zoom({ position: "bottomright" }).addTo(map);
      L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
        maxZoom: 19,
        attribution: "&copy; OpenStreetMap contributors",
        crossOrigin: true,
      })
        .on("tileerror", () => setTileError(true))
        .addTo(map);
      setMapReady(true);
    });

    return () => {
      cancelled = true;
      routeLayerRef.current = null;
      mapRef.current?.off();
      mapRef.current?.remove();
      mapRef.current = null;
      leafletRef.current = null;
    };
  }, []);

  useEffect(() => {
    const L = leafletRef.current;
    const map = mapRef.current;
    if (!mapReady || !L || !map) return;

    routeLayerRef.current?.remove();
    const layer = L.layerGroup().addTo(map);
    routeLayerRef.current = layer;
    const start: [number, number] = [latitude, longitude];
    const route = routePolyline.map(
      (point) => [point.latitude, point.longitude] as [number, number],
    );
    const endpoint = destinationLatitude !== null && destinationLongitude !== null
      ? [destinationLatitude, destinationLongitude] as [number, number]
      : route.at(-1);

    L.circleMarker(start, {
      radius: 8,
      color: "#dbeafe",
      weight: 4,
      fillColor: "#2563eb",
      fillOpacity: 1,
    }).bindTooltip(Object.assign(document.createElement("span"), { textContent: "当前位置" })).addTo(layer);

    if (route.length >= 2) {
      L.polyline(route, { color: "#0f172a", weight: 11, opacity: 0.5 }).addTo(layer);
      const line = L.polyline(route, {
        color: "#38bdf8",
        weight: 6,
        opacity: 0.95,
        lineCap: "round",
        lineJoin: "round",
      }).addTo(layer);
      map.fitBounds(line.getBounds(), { padding: [42, 42], maxZoom: 15 });
    } else {
      map.setView(start, 11);
    }

    if (endpoint) {
      L.circleMarker(endpoint, {
        radius: 9,
        color: "#d1fae5",
        weight: 4,
        fillColor: "#10b981",
        fillOpacity: 1,
      }).bindTooltip(Object.assign(document.createElement("span"), { textContent: destination || "目的地" })).addTo(layer);
    }
  }, [destination, destinationLatitude, destinationLongitude, latitude, longitude, mapReady, routePolyline]);

  return (
    <div className="relative h-full min-h-[380px] w-full overflow-hidden bg-slate-900">
      <div ref={elementRef} className="absolute inset-0" aria-label="基于 OpenStreetMap 的道路路线地图" />
      {tileError && (
        <div className="pointer-events-none absolute left-4 top-4 rounded-xl border border-amber-400/30 bg-slate-950/90 px-4 py-3 text-sm text-amber-100 shadow-xl backdrop-blur">
          地图瓦片暂时无法加载，路线数据仍保留在会话中。
        </div>
      )}
    </div>
  );
}
