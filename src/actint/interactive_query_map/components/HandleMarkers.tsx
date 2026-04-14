import { useMapEvents, Popup, MapContainer, TileLayer, Marker, Polyline } from 'react-leaflet'
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
  is_3D: boolean,
};



// Use a hook to create and update a list of a list of positions for what the last 20 ship positions were.
// Use the .map method to display all of those positinons to the screen with the polyline going through it
// Have a list of thhe most curreent positions and use those to display a marker on the map. 
// Also us a hook to update the most current poositions.




// Assuming vehicles_previous_positions is { [mmsi: number]: { lat: number, lng: number }[] }
// Assuming vehicles_current_positions is { [mmsi: number]: { lat: number, lng: number } }

export function HandleMarkers({ vehiclesPreviousPositions, vehicleCurrentPositions, is_3D }: Props) {
    
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
        </>
    );
}