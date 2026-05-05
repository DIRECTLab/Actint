
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
  

  
  

  return (
    <>
      <div id="simulation_settings" className="flex-none h-1/10 overflow-hidden"> {/* 20% of screen height for SimSettings */}
        <SimSettings
          simulation_settings={simulationSettings}
          set_simulation_settings={setSimulationSettings}
          setVehicleCurrentPositions={setVehicleCurrentPositions}
          setVehiclePreviousPositions={setVehiclesPreviousPositions}
        />
      </div>






      <div id="chat_map" className="flex flex-1 h-9/10"> {/* Remaining 80% height, flex horizontally */}
        <div className="w-3/4"> {/* 75% width for Map */}
          <Map
            vehiclesPreviousPositions={vehiclesPreviousPositions}
            vehicleCurrentPositions={vehicleCurrentPositions}
          />
        </div>
        <div className="w-1/4"> {/* 25% width for Chat */}
          <Chat />
        </div>
      </div>
    </>
  );
}
