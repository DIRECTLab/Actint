import { io } from "socket.io-client";
import { SimulationSettingsTyp } from '@/types/simulationSettings'
import { NUMBER_PREVIOUS_DISPLAYED_DETECTIONS } from "@/defaults/sim_settings_defauluts";
import { initializeVehicleData, update_position } from "./vehicle_position_functions";
import { vehicles_current_positions, vehicles_previous_positions } from "@/types/vehicleSettings";
import { socket } from "@/defaults/web_socket";





type Props = {
  simulation_settings: SimulationSettingsTyp,
//   VehicleCurrentPositions: vehicle_current_positions
  setVehicleCurrentPositions: React.Dispatch<React.SetStateAction<vehicles_current_positions>>,
//   VehiclePreviousPositions: vehicles_previous_positions
  setVehiclePreviousPositions: React.Dispatch<React.SetStateAction<vehicles_previous_positions>>,
};


export const createWebSocketConnection = ({simulation_settings, setVehicleCurrentPositions, setVehiclePreviousPositions}: Props) => {
    console.log("send web crap");

    const starting_data = {
        "simulation_file": simulation_settings.simulation_file,
        "simulation_speed": simulation_settings.simulation_speed,
        "start_time": simulation_settings.start_time,
        "time_format": simulation_settings.time_format,
        "is_3D": simulation_settings.is_3D,
    }

    // Sending data
    socket.emit("simulation_init", starting_data);
    
    // Receiving specific data
    socket.on("previous_data", (data) => {
      console.log(data);
      initializeVehicleData({ setVehicleCurrentPositions, setVehiclePreviousPositions, data });
      //go through all the data and put everything into the current and previous positons data.
    });

    socket.on("private_response", (data) => {
      console.log(data.msg);
      
    });

    socket.on("new_detection", (data) => {
      console.log(data);
      update_position({ setVehicleCurrentPositions, setVehiclePreviousPositions, data });
      // When a new detection is recieved, replace the current destination with the new one, put the new destination at the top of the previous destinations, and get rid of the latest previous destination
    });
  
}
