import { Popup, Marker, Polyline, Rectangle, Circle, Polygon } from 'react-leaflet'
import { vehicles_current_positions, vehicles_previous_positions } from '@/types/vehicleSettings';
import Trajectory from '@/components/Trajectory'

import L from 'leaflet';

const icon = L.icon({
  iconUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-icon.png',
  iconRetinaUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-icon-2x.png',
  shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-shadow.png',
  iconSize: [25, 41],       // Size of the icon
  iconAnchor: [12, 41],     // Point of the icon which will correspond to marker's location
  popupAnchor: [1, -34],    // Point from which the popup should open relative to the iconAnchor
  shadowSize: [41, 41],     // Size of the shadow
});


type Props = {
  vehiclesPreviousPositions: vehicles_previous_positions,
  vehicleCurrentPositions: vehicles_current_positions,
  AI_objects: any[],
};



export function HandleMarkers({ vehiclesPreviousPositions, vehicleCurrentPositions, AI_objects }: Props) {
    
    return (
        <>
            {/* 1. Render Polylines for Previous Positions (Trails) */}
            {Object.entries(vehiclesPreviousPositions).map(([mmsi, path]) => (
                <Polyline 
                    key={`path-${mmsi}`}
                    positions={path.map(point => [point.lat, point.lng])} 
                    pathOptions={{ 
                        color: 'blue', 
                        weight: 3, 
                        opacity: 0.6,
                        dashArray: '5, 10' // Optional: makes it look like a trail
                    }} 
                />
            ))}

            {/* 2. Render Markers for Current Positions */}
            {Object.entries(vehicleCurrentPositions).map(([mmsi, pos]) => (
                <Marker 
                    key={`marker-${mmsi}`} 
                    position={[pos.lat, pos.lng]}
                    icon={icon}
                >
                    <Popup>
                        MMSI: {mmsi} <br />
                        Status: Active
                    </Popup>
                </Marker>
            ))}

            {/* 3. Render AI Objects */}
            {AI_objects.map((obj, index) => {
            switch (obj.type) {
                case "marker":
                    return (
                        <Marker
                            key={index}
                            position={[obj.data.lat, obj.data.lon]}
                            icon={icon}
                        >
                            {obj.data.popup && (
                                <Popup>
                                    {obj.data.popup}
                                </Popup>
                            )}
                        </Marker>
                    );

                case "trajectory":
                    console.log("making trajectory")
                    return (
                        <Trajectory
                            key={index}
                            lat={obj.data.lat}
                            lon={obj.data.lon}
                            degree={obj.data.degree}
                            distance_nm={obj.data.distance_nm}
                        ></Trajectory>
                    )

                case "rectangle":
                return (
                    <Rectangle
                        key={index}
                        bounds={[
                        [obj.data.lat1, obj.data.lon1],
                        [obj.data.lat2, obj.data.lon2],
                        ]}
                        color={obj.data.color}
                    />
                );

                case "circle":
                    return <Circle
                        key={index}
                        center={[obj.data.lat, obj.data.lon]}
                        radius={obj.data.radius}
                        color={obj.data.color}
                    ></Circle>;

                case "line":
                    return <Polyline
                        key={index}
                        positions={obj.data.points}
                        color={obj.data.color}
                    ></Polyline>;

                case "polygon":
                    return <Polygon
                        key={index}
                        positions={obj.data.points}
                        pathOptions={{ color: obj.data.color }}
                    ></Polygon>;

                default:
                    return null;
            }
            })}

            
        </>
    );
}