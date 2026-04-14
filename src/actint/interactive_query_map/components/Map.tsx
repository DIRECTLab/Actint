import PopupInputs from '@/components/PopupInput'
import { previousValsTyp } from '@/types/otherTypes'
import { useState } from 'react'

import { HandleMarkers } from '@/components/HandleMarkers'

import { vehicles_current_positions, vehicles_previous_positions } from '@/types/vehicleSettings'

'use client'

import { MapContainer, TileLayer, Marker, Popup } from 'react-leaflet'
import 'leaflet/dist/leaflet.css'
import L from 'leaflet'
import { DestinationTyp, VehicleTyp } from '@/types/vehicleSettings'
import { useMap } from 'react-leaflet'
import { useEffect } from 'react'

// We define the icon using standard Leaflet CDN assets. 
// This bypasses the Next.js image loader entirely.
const icon = L.icon({
  iconUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-icon.png',
  iconRetinaUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-icon-2x.png',
  shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-shadow.png',
  iconSize: [25, 41],
  iconAnchor: [12, 41],
  popupAnchor: [1, -34],
  shadowSize: [41, 41],
})



type Props = {
  vehiclesPreviousPositions: vehicles_previous_positions,
  vehicleCurrentPositions: vehicles_current_positions,
  map_center: [number, number],
  map_zoom: number,
  is_3D: boolean,
}
export default function Map({ vehiclesPreviousPositions, vehicleCurrentPositions, map_center, map_zoom, is_3D }: Props) {


  type ChangeViewProps = {
    center: [number, number];
    zoom: number;
  }


  function ChangeView({ center, zoom }: ChangeViewProps) {
    const map = useMap();

    useEffect(() => {
      // .setView(location, zoom, options)
      // This is what actually triggers the animation
      map.setView(center, zoom, {
        animate: true,
        duration: 3 // Duration in seconds
      });
    }, [center, zoom, map]);

    return null;
  }




  return (
    <div style={{ height: '100vh', width: '100%' }}>
      <MapContainer 
        center={[5, 10]} 
        zoom={3} 
        style={{ height: '100%', width: '100%' }}
      >

        <ChangeView center={map_center} zoom={map_zoom} />

        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />

        <HandleMarkers
          vehiclesPreviousPositions={vehiclesPreviousPositions}
          vehicleCurrentPositions={vehicleCurrentPositions}
          is_3D={is_3D}
        ></HandleMarkers>
        

      </MapContainer>
    </div>
  )
}