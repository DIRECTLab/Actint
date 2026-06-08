import { Geodesic } from "geographiclib";
import { Polyline, Rectangle, Circle } from 'react-leaflet'
const HEADING_THRESHOLD = 15


type props = {
    lat: number,
    lon: number,
    heading: number,
    distance_nm: number,
}

export default function Trajectory({ lat, lon, heading, distance_nm }: props) {
    console.log(lat, lon, heading, distance_nm)
    return  (
      <>
        <Polyline
            positions={generateLinePoints(lat, lon, Number(heading) - HEADING_THRESHOLD, distance_nm)}
            pathOptions={{
                color: "blue",
                weight: 5
            }}
        />

        <Polyline
            positions={generateLinePoints(lat, lon, Number(heading) + HEADING_THRESHOLD, distance_nm)}
            pathOptions={{
                color: "blue",
                weight: 5
            }}
        />

        <Circle
            center = {[lat, lon]}
            radius={60}
            color="blue"
        />
      </>
    )
}




const geod = Geodesic.WGS84;

interface DirectResult {
  lat1: number;
  lon1: number;
  azi1: number;
  s12: number;
  a12: number;
  lat2: number;
  lon2: number;
  azi2: number;
}

function projectPoint(
  lat: number,
  lon: number,
  bearing: number,
  distanceNm: number
): [number, number] {
  // Convert nautical miles to meters
  const distanceMeters = distanceNm * 1852;

  // Use type assertion to tell TypeScript the result contains lat2 and lon2
  const result = geod.Direct(
    lat,
    lon,
    bearing,
    distanceMeters
  ) as unknown as DirectResult;

  return [result.lat2, result.lon2];
}

function generateLinePoints(
  startLat: number,
  startLon: number,
  bearing: number,
  distanceNm: number
): [number, number][] {

  const points: [number, number][] = [];
  const step = Math.max(0.5, distanceNm / 20);

  for (let d = 0; d <= distanceNm; d += step) {
    points.push(projectPoint(startLat, startLon, bearing, d));
  }

  if (points.length < 2) {
    points.push(projectPoint(startLat, startLon, bearing, distanceNm));
  }
  console.log(points)
  return points;
}