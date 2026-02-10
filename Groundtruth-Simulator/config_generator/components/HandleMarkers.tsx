import { useMapEvents, Popup, MapContainer, TileLayer, Marker, Polyline } from 'react-leaflet'
import { useEffect, useState } from 'react'
import { previousValsTyp } from '@/types/otherTypes';
import { DestinationTyp } from '@/types/vehicleSettings';

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
  markers: DestinationTyp[],
  setMarkers: React.Dispatch<React.SetStateAction<DestinationTyp[]>>
};


export function HandleMarkers({ markers, setMarkers }: Props) {
    const [values, setValues] = useState<previousValsTyp>({
        speed: 30,
        error: 30,
    })

    const updateMarker = (index: number, LatLng: L.LatLng, height: any, speed: number, error: number) => {
        if (height) {
            var newMarker: DestinationTyp = {error: error, speed: speed, position: {LatLng: LatLng, Z: height}}
        } else {
            var newMarker: DestinationTyp = {error: error, speed: speed, position: {LatLng: LatLng}}
        }

        setMarkers((prev) => {
            const newMarkers = [...prev];
            newMarkers[index] = newMarker;
            return newMarkers;
        });
    };

    const deleteMarker = (index: number) => {
        setMarkers((prev) => prev.filter((_, i) => i !== index));
    };

    useMapEvents({
        click(e) {
            var newMarker: DestinationTyp = {speed: values.speed, error: values.error, position: {Z: values.height, LatLng: e.latlng}}
            setMarkers((prev) => [...prev, newMarker])
        }  
    })

    

    return (
        <>
            {markers.map((mark, index) => (
                <Marker 
                    key={index} 
                    position={mark.position.LatLng} 
                    icon={icon} 
                    draggable={true}
                    eventHandlers={{
                        dragend: (e) => {
                            const LatLng = e.target.getLatLng();
                            updateMarker(index, LatLng, mark.position.Z, mark.speed, mark.error);
                        },
                    }}
                >
                    <Popup>
                        <PopupInputs
                          is_3D={false}
                          previousValues={values}
                          setPreviousValues={setValues}
                          updateMarker={updateMarker}
                          deleteMarker={deleteMarker}
                          index={index}
                          marker={mark}
                        />
                    </Popup>
                </Marker>
            ))}

            {markers.length > 1 && (
                <Polyline 
                    positions={markers.map(m => m.position.LatLng)} // Polyline will automatically update when 'markers' state changes
                    color="blue" 
                    weight={3}
                    dashArray="5, 10"
                />
            )}
        </>
    )
}

