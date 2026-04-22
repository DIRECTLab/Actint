import { SimulationSettingsTyp } from '@/types/simulationSettings'
import { initializeVehicleData, update_position } from "./vehicle_position_functions";
import { vehicles_current_positions, vehicles_previous_positions } from "@/types/vehicleSettings";
import { socket } from "@/defaults/web_socket";



type Props1 = {
  simulation_settings: SimulationSettingsTyp,
//   VehicleCurrentPositions: vehicle_current_positions
  setVehicleCurrentPositions: React.Dispatch<React.SetStateAction<vehicles_current_positions>>,
//   VehiclePreviousPositions: vehicles_previous_positions
  setVehiclePreviousPositions: React.Dispatch<React.SetStateAction<vehicles_previous_positions>>,
};


export const start_simulation = ({simulation_settings, setVehicleCurrentPositions, setVehiclePreviousPositions}: Props1) => {
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
type Props2 = {
  handleManualMove: (lat: number, lng: number, zoom: number) => void;
  setAI_objects: React.Dispatch<React.SetStateAction<any[]>>,
}

export const create_map_functions = ({handleManualMove, setAI_objects}: Props2) =>{
  socket.on("set_map_position", (data) => {
      console.log("set map position", data);
      handleManualMove(data.lat, data.lon, data.zoom)
  });

  socket.on("draw_rectangle", (data) => {
    setAI_objects(prev => [...prev, { type: "rectangle", data }]);
    console.log("set AI objects", data);
  })
  
  socket.on("draw_circle", (data) => {
      console.log("set AI objects", data);
      setAI_objects(prev => [...prev, { type: "circle", data }]);
  })

  socket.on("draw_line", (data) => {
      console.log("set AI objects", data);
      setAI_objects(prev => [...prev, { type: "line", data }]);
  })
}

