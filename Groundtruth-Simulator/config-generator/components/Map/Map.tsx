import PopupInputs from '@/components/Map/PopupInput'
import { previousValsTyp } from '@/types/otherTypes'
import { useState } from 'react'

import { HandleMarkers } from '@/components/Map/HandleMarkers'

'use client'

import { MapContainer, TileLayer, Marker, Popup } from 'react-leaflet'
import 'leaflet/dist/leaflet.css'
import L from 'leaflet'
import { DestinationTyp } from '@/types/vehicleSettings'

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
  markers: DestinationTyp[]
  setMarkers: React.Dispatch<React.SetStateAction<DestinationTyp[]>>,
  vehicles_3d: boolean,
  is_3D: boolean,
}
export default function Map({ markers, setMarkers, vehicles_3d, is_3D }: Props) {

  return (
    <div style={{ height: '100vh', width: '100%' }}>
      <MapContainer 
        center={[20.75, -157]} 
        zoom={8} 
        style={{ height: '100%', width: '100%' }}
      >
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />

        <HandleMarkers
          markers={markers}
          setMarkers={setMarkers}
          vehicles_3d={vehicles_3d}
          is_3D={is_3D}
        ></HandleMarkers>
        

      </MapContainer>
    </div>
  )
}