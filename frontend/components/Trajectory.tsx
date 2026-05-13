import { Geodesic } from "geographiclib";
import { Polyline, Rectangle, Circle } from 'react-leaflet'
const DEGREE_THRESHOLD = 15


type props = {
    lat: number,
    lon: number,
    degree: number,
    distance_nm: number,
}

export default function Trajectory({ lat, lon, degree, distance_nm }: props) {
    console.log(lat, lon, degree, distance_nm)
    return  (
      <>
        <Polyline
            positions={generateLinePoints(lat, lon, Number(degree) - DEGREE_THRESHOLD, distance_nm)}
            pathOptions={{
                color: "blue",
                weight: 5
            }}
        />

        <Polyline
            positions={generateLinePoints(lat, lon, Number(degree) + DEGREE_THRESHOLD, distance_nm)}
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

function projectPoint(
  lat: number,
  lon: number,
  bearing: number,
  distanceNm: number
): [number, number] {
  // Convert nautical miles to meters
  const distanceMeters = distanceNm * 1852;

  const result = geod.Direct(
    lat,
    lon,
    bearing,
    distanceMeters
  );
  return [result.lat2, result.lon2]
  
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