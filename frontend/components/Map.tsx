import { HandleMarkers } from '@/components/HandleMarkers'
import { vehicles_current_positions, vehicles_previous_positions } from '@/types/vehicleSettings'
import { MapContainer, TileLayer } from 'react-leaflet'
import 'leaflet/dist/leaflet.css'
import L from 'leaflet'
import { useEffect } from 'react'
import { Map as LeafletMap } from 'leaflet'; // Import the type
import { create_map_functions } from '@/functions/web_socket_functions'
import { useRef, useState } from 'react'
import { useMap } from 'react-leaflet'
import 'leaflet.heat'
import { socket } from "@/defaults/web_socket";

'use client'

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
}

function HeatMapLayer({ points }: { points: number[][] }) {
  const map = useMap()
  //console.log("heatLayer exists:", (L as any).heatLayer)

  useEffect(() => {
    //if (!points || points.length === 0) return


    const test = [
      [40.7, -111.9, 1],
      [40.71, -111.91, 0.8],
      [40.72, -111.92, 0.6],
    ]

    const heat = (L as any).heatLayer(points, {
      radius: 15,
      blur: 10,
      maxZoom: 10,
      minOpacity: 0.3,
    })

    heat.addTo(map)

    return () => {
      map.removeLayer(heat)
    }
  }, [map, points])

  return null
}


//Some different themes, uncomment the one you want to use and comment the others

// URL for different themes:https://leaflet-extras.github.io/leaflet-providers/preview/


export default function Map({ vehiclesPreviousPositions, vehicleCurrentPositions }: Props) {
  const [AI_objects, setAI_objects] = useState<any[]>([]);

  const [heatMapPoints, setHeatMapPoints] = useState<number[][]>([])

  const mapRef = useRef<LeafletMap | null>(null);

  const handleManualMove = (lat: number, lng: number, zoom: number) => {
    if (mapRef.current) {
      mapRef.current.flyTo([lat, lng], zoom, {
        duration: 2 
      });
    }
  };

  useEffect(() => {
    create_map_functions({
    handleManualMove,
    setAI_objects,
    setHeatmapData: (data: any) => {
      console.log("heatmap received", data)
      setHeatMapPoints(data.points || [])
    }
    });
  }, [])

  useEffect(() => {
    socket.emit("get_heatmap")
  }, [])
  
  return (
    <div style={{ height: '100%', width: '100%', background: '#000'}}>
      

      <MapContainer 
        center={[5, 10]} 
        zoom={3} 
        style={{ height: '100%', width: '100%', background: '#000' }}
        ref={mapRef}
      >
        
        {/* A bunch of different themes you can pick from: */}

        {/* Basic map */}
        <TileLayer 
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" 
          />

        {/* Google 2012 night satellite image */}
        {/* <TileLayer
          attribution='Imagery provided by services from the Global Imagery Browse Services (GIBS), operated by the NASA/GSFC/Earth Science Data and Information System (ESDIS)'
          url="https://map1.vis.earthdata.nasa.gov/wmts-webmerc/VIIRS_CityLights_2012/default/GoogleMapsCompatible_Level8/{z}/{y}/{x}.jpg"
          minZoom={1}
          maxZoom={8}
        /> */}

        {/* Grey-green military map */}
        {/* <TileLayer
          attribution='&copy; <a href="https://www.stadiamaps.com/" target="_blank">Stadia Maps</a> &copy; <a href="https://openmaptiles.org/" target="_blank">OpenMapTiles</a> &copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
          url="https://tiles.stadiamaps.com/tiles/alidade_smooth_dark/{z}/{x}/{y}{r}.png"
          minZoom={0}
          maxZoom={20}
        /> */}

        {/* American topical map */}
        {/* <TileLayer
          attribution='&copy; CNES, Distribution Airbus DS, © Airbus DS, © PlanetObserver (Contains Copernicus Data) | &copy; <a href="https://www.stadiamaps.com/" target="_blank">Stadia Maps</a> &copy; <a href="https://openmaptiles.org/" target="_blank">OpenMapTiles</a> &copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
          url="https://tiles.stadiamaps.com/tiles/alidade_satellite/{z}/{x}/{y}{r}.jpg"
          minZoom={0}
          maxZoom={20}
        /> */}

        {/* Dark with white borders */}
        {/* <TileLayer
          attribution='&copy; <a href="https://www.stadiamaps.com/" target="_blank">Stadia Maps</a> &copy; <a href="https://www.stamen.com/" target="_blank">Stamen Design</a> &copy; <a href="https://openmaptiles.org/" target="_blank">OpenMapTiles</a> &copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
          url="https://tiles.stadiamaps.com/tiles/stamen_toner_dark/{z}/{x}/{y}{r}.png"
          minZoom={0}
          maxZoom={20}
        /> */}

        {/* Dark with grey borders */}
        {/* <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>'
          url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
          subdomains="abcd"
          maxZoom={20}
        /> */}


        {/* Topical colorful German */}
        {/* <TileLayer
          attribution='Map data: &copy; <a href="http://www.govdata.de/dl-de/by-2-0">dl-de/by-2-0</a>'
          url="https://sgx.geodatenzentrum.de/wmts_topplus_open/tile/1.0.0/web/default/WEBMERCATOR/{z}/{y}/{x}.png"
          maxZoom={18}
        /> */}

        <HeatMapLayer
          points={heatMapPoints}
        />

        <HandleMarkers
          vehiclesPreviousPositions={vehiclesPreviousPositions}
          vehicleCurrentPositions={vehicleCurrentPositions}
          AI_objects={AI_objects}
        ></HandleMarkers>
      </MapContainer>
    </div>
  );
}
