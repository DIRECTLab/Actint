"use client";


/*********************************************************** Fix for default icon ******************************************************/
import L from "leaflet";
import markerIcon2x from "leaflet/dist/images/marker-icon-2x.png";
import markerIcon from "leaflet/dist/images/marker-icon.png";
import markerShadow from "leaflet/dist/images/marker-shadow.png";

L.Icon.Default.mergeOptions({
  iconRetinaUrl: markerIcon2x,
  iconUrl: markerIcon,
  shadowUrl: markerShadow,
});

/**************************************************************** Imports **************************************************************/

import { VehicleSettingsTyp } from "@/types/vehicleSettings";
import { PositionTyp } from "@/types/vehicleSettings";
import { DestinationTyp} from "@/types/vehicleSettings";
import { previousValsTyp } from "@/types/otherTypes";

import { useEffect, useRef } from "react";
import {useState } from 'react'
import "leaflet/dist/leaflet.css";

import Popup from '@/components/PopupInput'
import ReactDOMServer from "react-dom/server";

import { createRoot } from "react-dom/client";

import { PopupInputs } from '@/components/PopupInput'


//creates the popup string so it can be passed to the marker


/*********************************************************** Essential Variables *******************************************************/
var markerList = []




//Props
type MapProps = {
  onClick?: (lat: number, lng: number) => void,
  vehicle_settings: VehicleSettingsTyp,
  set_vehicle_settings: React.Dispatch<React.SetStateAction<VehicleSettingsTyp>>
};

//Begin Map component
export default function Map({ onClick, vehicle_settings, set_vehicle_settings }: MapProps) {

  const [previousValues, setPreviousValues] = useState<previousValsTyp>({height: 0, error: 5, speed: 0})

  const settingsRef = useRef(vehicle_settings);

  useEffect(() => {
    settingsRef.current = vehicle_settings;
  }, [vehicle_settings]);
  


  const prevValsRef = useRef(previousValues);

  useEffect(() => {
    prevValsRef.current = previousValues;
  }, [previousValues]);
  
  
  const [destination, setDestination] = useState<DestinationTyp>({
    position: {X:0, Y:0},
    speed: 0,
    error: 0
  })


//I might need another useRef for the markers


  const mapDivRef = useRef<HTMLDivElement | null>(null);
  const mapInstanceRef = useRef<any>(null);
  



  useEffect(() => {
    let isMounted = true;

    (async () => {
      const L = (await import("leaflet")).default;

      if (!mapDivRef.current || mapInstanceRef.current || !isMounted) return;

      const map = L.map(mapDivRef.current).setView([51.505, -0.09], 13);
      mapInstanceRef.current = map;

      L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
        attribution: "© OpenStreetMap",
      }).addTo(map);








      // 🖱️ CLICK EVENT
      map.on("click", (e: any) => {
        
        const { lat, lng } = e.latlng;

        setDestination((prev) => ({...prev, position: {X:0, Y:0}}))

        // 1. Create a physical container element
        const container = document.createElement("div");
        
        // 2. Initialize a React Root inside that container
        const root = createRoot(container);

        // 3. Render your Popup component with props
        root.render(
          <Popup 
            destination={destination}
            setDestination={setDestination}
            lat={lat}
            lng={lng}
            is_3D={settingsRef.current.is_3D}
            previousValues={prevValsRef.current}
            setPreviousValues={setPreviousValues}
          />
        );
        
        

        const marker = L.marker([lat, lng], { draggable: true}).addTo(map)
        .bindPopup(container, { minWidth: 300 }) 
          .openPopup();


        // onClick?.(lat, lng);
      
        markerList.push(marker)
      















      
      // DRAG EVENT 
      map.on("drag", (e: any) => {
        
      })
      
      
      
      
      
      
      
      
      });
    })();

    
    return () => {
      isMounted = false;
      mapInstanceRef.current?.remove();
      mapInstanceRef.current = null;
    };
    
  }, []); 
  

  return (
    <div
      ref={mapDivRef}
      style={{ height: "100vh", width: "100%" }}
      id="map"
    />
  );
}

