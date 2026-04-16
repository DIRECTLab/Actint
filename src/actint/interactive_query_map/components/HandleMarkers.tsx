import { useMapEvents, Popup, MapContainer, TileLayer, Marker, Polyline, Rectangle, Circle } from 'react-leaflet'
import { useEffect, useState } from 'react'
import { previousValsTyp } from '@/types/otherTypes';
import { DestinationTyp, vehicles_current_positions, VehicleTyp, vehicles_previous_positions } from '@/types/vehicleSettings';
import PopupInputs from '@/components/PopupInput'


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
  is_3D: boolean,
};





export function HandleMarkers({ vehiclesPreviousPositions, vehicleCurrentPositions, AI_objects, is_3D }: Props) {
    
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
                case "rectangle":
                return (
                    <Rectangle
                        key={index}
                        bounds={[
                        [obj.data.lat1, obj.data.lon1],
                        [obj.data.lat2, obj.data.lon2],
                        ]}
                    />
                );

                case "circle":
                    return <Circle
                        key={index}
                        center={[obj.data.lat, obj.data.lon]}
                        radius={obj.data.radius}
                    ></Circle>;

                case "line":
                    return <Polyline
                        key={index}
                        positions={obj.data.points}
                    ></Polyline>;

                default:
                    return null;
            }
            })}

            
        </>
    );
}