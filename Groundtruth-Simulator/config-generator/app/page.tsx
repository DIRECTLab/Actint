
"use client";

import { useState, useMemo, useEffect } from "react";
import "leaflet/dist/leaflet.css";


// ********************************************** Components *********************************************//
// import VehicleSidebar from '@/components/vehicle_sidebar';
import SimSettings from '../components/sim_settings';

import dynamic from "next/dynamic";

const Map = dynamic(() => import('../components/Map'), { 
  ssr: false,
  loading: () => <p>Loading Map...</p>
})

const VehicleSidebar = dynamic(() => import('../components/vehicle_sidebar'), { 
  ssr: false,
  loading: () => <p>Loading Map...</p>
})

// ********************************************** Types **************************************************//

  // all types end in Typ
import { PositionTyp, PointTyp, PropertiesTyp, VehicleTyp, DestinationTyp } from '@/types/vehicleSettings'
import { SimulationSettingsTyp } from '@/types/simulationSettings'
import { CompleteExport } from '@/types/completeExport'




// ********************************************** Simulation Setting Vars *********************************//
import DEFAULT_VEHICLE from "@/defaults/vehicle_defaults";
import DEFAULT_SIM_SETTIINGS from "@/defaults/sim_settings_defauluts";

export default function Home() {

  const [vehicleSettings, setVehicleSettings] = useState<VehicleTyp>(DEFAULT_VEHICLE)
  const [simulationSettings, setSimulationSettings] = useState<SimulationSettingsTyp>(DEFAULT_SIM_SETTIINGS)
  
  const [markers, setMarkers] = useState<DestinationTyp[]>([])
  
  const [vehiclesList, setVehiclesList] = useState<VehicleTyp[]>([]);

  const createNewVehicle = (vehicleSettings: VehicleTyp, setVehicleSettings: React.Dispatch<React.SetStateAction<VehicleTyp>>, setVehiclesList: React.Dispatch<React.SetStateAction<VehicleTyp[]>>, markers: DestinationTyp[]): void => {
    var newVehicle: VehicleTyp = {...vehicleSettings, destinations: markers }
    
    setVehiclesList((prev) => [...prev, newVehicle]);
    setVehicleSettings(DEFAULT_VEHICLE)
    
  }
  
  function vehiclesAre3D () {
    if(!markers[0]) {
      return false
    }
    if (!markers[0].position.Z){
      return false
    }
    return true
  }

  const save_simulation = (simulationSettings: SimulationSettingsTyp, vehiclesList: VehicleTyp[]): void => {
    
    const data = {
      "sim_settings": simulationSettings,
      "vehicles": vehiclesList,
    }

    alert("Saving Data")
    fetch("http://localhost:5000/points", {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify(data)
    })
    .then(res => res.json())
    .then(data => {
      alert("Saved by Python!");
    })
    .catch(err => {
      alert("Python server not running");
      console.error(err);
    });
  }
  
  

  return (<>
    <div id="main">
    <div id="row">
      <div id="column">
        

        <SimSettings
          simulation_settings={simulationSettings}
          set_simulation_settings={setSimulationSettings}
          vehiclesList={vehiclesList}
          setVehiclesList={setVehiclesList}
          saveSimulation={save_simulation}
        />

        <Map 
          markers={markers}
          setMarkers={setMarkers}
          vehicles_3d={vehiclesAre3D()}
          is_3D={vehicleSettings.is_3D}
        />

      </div>
      <VehicleSidebar
        vehicle_settings={vehicleSettings}
        set_vehicle_settings={setVehicleSettings}
        markers={markers}
        setMarkers={setMarkers}
        vehiclesList={vehiclesList}
        setVehiclesList={setVehiclesList}
        createNewVehicle={createNewVehicle}
      />

      </div>
      </div>
  </>)
  }