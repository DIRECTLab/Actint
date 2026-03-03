import { SimulationSettingsTyp } from '@/types/simulationSettings'
import { VehicleTyp } from '@/types/vehicleSettings';

import { handleImport } from '@/functions/import_simulation';

type Props = {
  simulation_settings: SimulationSettingsTyp,
  set_simulation_settings: React.Dispatch<React.SetStateAction<SimulationSettingsTyp>>,
  vehiclesList: VehicleTyp[],
  setVehiclesList: React.Dispatch<React.SetStateAction<VehicleTyp[]>>
  saveSimulation: (simulationSettiings: SimulationSettingsTyp, vehiclesList: VehicleTyp[]) => void,
};




export default function SimSettings({ simulation_settings, set_simulation_settings, vehiclesList, setVehiclesList, saveSimulation }: Props) {
  

    return (
            <div id='simulation_settings'>
                <h1 className="bg-blue-500 rounded p-3">Simulation Settings</h1>
                <div>
                  <label htmlFor="output_name_2d">Output Name 2D</label>
                  <input 
                    type="text" 
                    id="output_name_2d" 
                    name="output_name_2d" 
                    className="p-2"
                    value={simulation_settings.output_file_2d}
                    onChange={(e) =>
                    set_simulation_settings(prev => ({
                        ...prev,
                        output_file_2d: e.target.value,
                        }))
                    }
                    
                  />
                </div>

                <div>
                  <label htmlFor="output_name_3d">Output Name 3D</label>
                  <input 
                    type="text" 
                    id="output_name_3d" 
                    name="output_name_3d"
                    className="p-2"
                    value={simulation_settings.output_file_3d}
                    onChange={(e) => set_simulation_settings(prev => ({
                        ...prev,
                        output_file_3d: e.target.value,
                        }))
                    }
                  />
                </div>

                <div>
                  <label htmlFor="starttime">Start time:</label>
                  <input 
                    type="datetime-local" 
                    id="starttime" 
                    name="starttime"
                    className="p-2"
                    value={simulation_settings.start_time}
                    onChange={(e) => set_simulation_settings( prev => ({...prev, start_time: e.target.value})) }
                  />
                </div>
                

                <div>
                  <label htmlFor="timestep">Timestep:</label>
                  <input 
                    type="number" 
                    id="timestep" 
                    name="timestep" 
                    className="p-2"
                    value={simulation_settings.time_step}
                    onChange={(e) => {set_simulation_settings( prev => ({...prev, time_step: parseFloat(e.target.value)})) } }
                  />
                </div>


                <div>
                  <label htmlFor="sim_lattitude">Latitude:</label>
                  <input
                  type="number"
                  id="sim_lattitude"
                  name="sim_lattitude"
                  className="p-2"
                  value={simulation_settings.latlon_origin.latitude}
                  onChange={(e) => set_simulation_settings( prev => ({...prev, latlon_origin: {...prev.latlon_origin, latitude: parseFloat(e.target.value)}})) }
                  />
                </div>


                <div>
                  <label htmlFor="sim_longitude">Longitude:</label>
                  <input
                  type="number"
                  id="sim_longitude"
                  name="sim_longitude"
                  className="p-2"
                  value={simulation_settings.latlon_origin.longitude}
                  onChange={(e) => set_simulation_settings( prev => ({...prev, latlon_origin: {...prev.latlon_origin, longitude: parseFloat(e.target.value)}})) }
                  />
                </div>


                <div>
                  <label htmlFor="sim_height">Height:</label>
                  <input
                  type="number"
                  id="sim_height"
                  name="sim_height"
                  className="p-2"
                  value={simulation_settings.latlon_origin.height}
                  onChange={(e) => set_simulation_settings( prev => ({...prev, latlon_origin: {...prev.latlon_origin, height: parseFloat(e.target.value)}})) }
                  />
                </div>


                <div>
                  <label style={{ cursor: "pointer"}} htmlFor="file_import">Import File</label>
                  <input id="file_import" name="file_import" type="file" style={{ display: "none" }} onChange={(e) => {handleImport(e, set_simulation_settings, setVehiclesList)}}></input>
                </div>

                <button 
                  type="button" 
                  id="export_settings"
                  onClick={() => {
                    saveSimulation(simulation_settings, vehiclesList)
                  }} 
                  
                >Export Settings</button>

            </div>
        );
}