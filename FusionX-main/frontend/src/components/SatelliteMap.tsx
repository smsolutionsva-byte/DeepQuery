import { useEffect, useMemo, useRef } from "react";
import Globe from "react-globe.gl";

type GlobePoint = {
  lat: number;
  lng: number;
  size: number;
  color: string;
  label: string;
};

type SatelliteMapProps = {
  points?: Array<{ id: string; lat: number; lng: number }>;
  autoRotateSpeed?: number;
  highlightedPointId?: string;
  onPointSelect?: (id: string) => void;
};

export default function SatelliteMap({
  points,
  autoRotateSpeed = 0.45,
  highlightedPointId,
  onPointSelect,
}: SatelliteMapProps) {
  const globeRef = useRef<any>(null);

  const globePoints = useMemo<GlobePoint[]>(
    () =>
      (points ?? [
        { id: "patch-1", lat: -3.4653, lng: -62.2159 },
        { id: "patch-2", lat: 34.0522, lng: -118.2437 },
        { id: "patch-3", lat: 25.2048, lng: 55.2708 },
        { id: "patch-4", lat: -33.8688, lng: 151.2093 },
        { id: "patch-5", lat: 48.8566, lng: 2.3522 },
      ]).map((p) => ({
        lat: p.lat,
        lng: p.lng,
        size: p.id === highlightedPointId ? 0.65 : 0.35,
        color: p.id === highlightedPointId ? "#9fd0ff" : "#5ca7ff",
        label: p.id,
      })),
    [points, highlightedPointId],
  );

  useEffect(() => {
    if (!globeRef.current) return;
    globeRef.current.pointOfView({ lat: 18, lng: 8, altitude: 2.05 }, 0);
    globeRef.current.controls().autoRotate = true;
    globeRef.current.controls().autoRotateSpeed = autoRotateSpeed;
    globeRef.current.controls().enablePan = false;
    globeRef.current.controls().minDistance = 160;
    globeRef.current.controls().maxDistance = 480;
  }, [autoRotateSpeed]);

  return (
    <div className="map-wrap">
      <Globe
        ref={globeRef}
        width={900}
        height={700}
        globeImageUrl="https://unpkg.com/three-globe/example/img/earth-blue-marble.jpg"
        bumpImageUrl="https://unpkg.com/three-globe/example/img/earth-topology.png"
        backgroundColor="rgba(0,0,0,0)"
        pointsData={globePoints}
        pointLat="lat"
        pointLng="lng"
        pointColor="color"
        pointAltitude="size"
        pointRadius={0.55}
        pointsMerge
        pointLabel="label"
        onPointClick={(point) => {
          if (!onPointSelect) return;
          const id = (point as { label?: string }).label;
          if (id) onPointSelect(id);
        }}
      />
    </div>
  );
}
