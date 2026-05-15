import { Popup, Marker, Polyline, Rectangle, Circle } from 'react-leaflet'
import { vehicles_current_positions, vehicles_previous_positions } from '@/types/vehicleSettings';


import L from 'leaflet';
import markerIcon2x from 'leaflet/dist/images/marker-icon-2x.png';
import markerIcon from 'leaflet/dist/images/marker-icon.png';
import markerShadow from 'leaflet/dist/images/marker-shadow.png';

delete L.Icon.Default.prototype._getIconUrl;

L.Icon.Default.mergeOptions({
    iconRetinaUrl: markerIcon2x,
    iconUrl: markerIcon,
    shadowUrl: markerShadow,
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
                case "marker":
                    return (<Marker
                        key={index}
                        position={[obj.data.lat, obj.data.lon]}
                    >
                        {obj.data.popup_msg !== "" && <Popup>obj.data.popup_msg</Popup>}
                    </Marker>);
                default:
                    return null;
            }
            })}

            
        </>
    );
}