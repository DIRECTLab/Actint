import { SimulationSettingsTyp } from '@/types/simulationSettings'
import { VehicleTyp } from '@/types/vehicleSettings';
import { createWebSocketConnection } from '@/functions/web_socket_functions';
import { vehicles_current_positions, vehicles_previous_positions } from '@/types/vehicleSettings';

type Props = {
  simulation_settings: SimulationSettingsTyp,
  set_simulation_settings: React.Dispatch<React.SetStateAction<SimulationSettingsTyp>>,
  setVehicleCurrentPositions: React.Dispatch<React.SetStateAction<vehicles_current_positions>>,
  setVehiclePreviousPositions: React.Dispatch<React.SetStateAction<vehicles_previous_positions>>,
};




export default function SimSettings({ simulation_settings, set_simulation_settings, setVehicleCurrentPositions, setVehiclePreviousPositions }: Props) {

    return (
            <div id='simulation_settings'>
                <h1 className="bg-blue-500 rounded p-3">Simulation Settings</h1>


                <div>
                  <label htmlFor="vehicle_type">Simulation_file</label>
                  <select 
                    id="vehicle_type"
                    value={simulation_settings.simulation_file}
                    onChange={(e) => {set_simulation_settings( prev => ({...prev, simulation_file: e.target.value}))}}
                  >
                    <option value="ship">Ship</option>
                    <option value="car">Car</option>
                    <option value="drone">Drone</option>
                  </select>
                </div>

                <div>
                  <label htmlFor="startTime">Start time:</label>
                  <input 
                    type="datetime-local" 
                    id="startTime" 
                    name="startTime"
                    className="p-2"
                    value={simulation_settings.start_time}
                    onChange={(e) => set_simulation_settings( prev => ({...prev, start_time: e.target.value})) }
                  />
                </div>
                

                <div>
                  <label htmlFor="Speed">Simulation Speed:</label>
                  <input 
                    type="number" 
                    id="Speed" 
                    name="Speed" 
                    className="p-2"
                    value={simulation_settings.simulation_speed}
                    onChange={(e) => {set_simulation_settings( prev => ({...prev, simulation_speed: parseFloat(e.target.value)})) } }
                  />
                </div>

                <button 
                  type="button" 
                  id="start_simulation"
                  onClick={() => {
                    console.log("hello")
                    createWebSocketConnection({simulation_settings, setVehicleCurrentPositions, setVehiclePreviousPositions});
                  }} 
                  
                >Start Simulation</button>

            </div>
        );
}