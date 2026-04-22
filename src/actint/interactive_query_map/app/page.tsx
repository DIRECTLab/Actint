
"use client";

import { useState, useMemo, useEffect } from "react";
import "leaflet/dist/leaflet.css";

import { vehicles_current_positions, vehicles_previous_positions } from "@/types/vehicleSettings";


// ********************************************** Components *********************************************//
import SimSettings from '../components/sim_settings';
import { Chat } from '../components/chat';
import dynamic from "next/dynamic";

const Map = dynamic(() => import('../components/Map'), { 
  ssr: false,
  loading: () => <p>Loading Map...</p>
})

// ********************************************** Types **************************************************//
// all types end in Typ
import { SimulationSettingsTyp } from '@/types/simulationSettings'


// ********************************************** Functions **********************************************//
import { create_map_functions } from '@/functions/web_socket_functions';

// ********************************************** Defaults ***********************************************//
import DEFAULT_SIM_SETTIINGS from "@/defaults/sim_settings_defauluts";




export default function Home() {


// ********************************************** Variable Definitions ************************************//
  
  const [vehiclesPreviousPositions, setVehiclesPreviousPositions] = useState<vehicles_previous_positions>({});
  const [vehicleCurrentPositions, setVehicleCurrentPositions] = useState<vehicles_current_positions>({});
  const [simulationSettings, setSimulationSettings] = useState<SimulationSettingsTyp>(DEFAULT_SIM_SETTIINGS);
  

  
  

  return (<>
    <div id="main">
    <div id="row">
      <div id="column">
        

        <SimSettings
          simulation_settings={simulationSettings}
          set_simulation_settings={setSimulationSettings}
          setVehicleCurrentPositions={setVehicleCurrentPositions}
          setVehiclePreviousPositions={setVehiclesPreviousPositions}
        />

        <Map 
          vehiclesPreviousPositions={vehiclesPreviousPositions}
          vehicleCurrentPositions={vehicleCurrentPositions}
        />


      </div>
      <Chat />
      {/* Put the chat interface here */}
    </div>
    </div>
  </>)
  }