
"use client";

import { useState, useMemo, useEffect } from "react";
import "leaflet/dist/leaflet.css";


// ********************************************** Components *********************************************//
import SimSettings from '../components/sim_settings';
import dynamic from "next/dynamic";

const Map = dynamic(() => import('../components/Map/Map'), { 
  ssr: false,
  loading: () => <p>Loading Map...</p>
})

const VehicleSidebar = dynamic(() => import('../components/vehicle_sidebar/vehicle_sidebar'), { 
  ssr: false,
  loading: () => <p>Loading Map...</p>
})


// ********************************************** Types **************************************************//
// all types end in Typ
import { PositionTyp, PointTyp, PropertiesTyp, VehicleTyp, DestinationTyp } from '@/types/vehicleSettings'
import { SimulationSettingsTyp } from '@/types/simulationSettings'


// ********************************************** Functions **********************************************//
import export_simulation from "@/functions/export_simulation";
import { createNewVehicle } from "@/functions/vehicle_functions";

// ********************************************** Defaults ***********************************************//
import DEFAULT_VEHICLE from "@/defaults/vehicle_defaults";
import DEFAULT_SIM_SETTIINGS from "@/defaults/sim_settings_defauluts";



export default function Home() {


// ********************************************** Variable Definitions ************************************//
  const [vehicleSettings, setVehicleSettings] = useState<VehicleTyp>(DEFAULT_VEHICLE)
  const [simulationSettings, setSimulationSettings] = useState<SimulationSettingsTyp>(DEFAULT_SIM_SETTIINGS)
  const [markers, setMarkers] = useState<DestinationTyp[]>([])
  const [vehiclesList, setVehiclesList] = useState<VehicleTyp[]>([]);


  
  function vehicleIs3D () {
    if(!markers[0]) {
      return false
    }
    if (!markers[0].position.Z){
      return false
    }
    return true
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
          saveSimulation={export_simulation}
        />

        <Map 
          markers={markers}
          setMarkers={setMarkers}
          vehicles_3d={vehicleIs3D()}
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