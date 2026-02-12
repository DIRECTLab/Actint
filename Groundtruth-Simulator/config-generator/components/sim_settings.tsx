import { SimulationSettingsTyp } from '@/types/simulationSettings'
import { VehicleTyp } from '@/types/vehicleSettings';

type Props = {
  simulation_settings: SimulationSettingsTyp,
  set_simulation_settings: React.Dispatch<React.SetStateAction<SimulationSettingsTyp>>,
  vehiclesList: VehicleTyp[],
  setVehiclesList: React.Dispatch<React.SetStateAction<VehicleTyp[]>>
  saveSimulation: (simulationSettiings: SimulationSettingsTyp, vehiclesList: VehicleTyp[]) => void,
};




export default function SimSettings({ simulation_settings, set_simulation_settings, vehiclesList, setVehiclesList, saveSimulation }: Props) {
  
    const handleImport = async (event: any) => {
      if(confirm("WARNING: If you choose to continue, everything you have created will be replaced by your uploaded file. Be sure to save your work. \nContinue?")) {
        const file = event.target.files[0]
        let text;
        try {
          text = await file.text()
        }catch{
          console.log("Failed to parse the file")
        }
        let json_config_files
        try{
          json_config_files = JSON.parse(text)
        } catch {
          console.log("failed to parse file into json.")
        }
        console.log(json_config_files)

        const imported_sim_settings = json_config_files['sim_settings']
        const imported_vehicles = json_config_files['vehicles']
        try {
          set_simulation_settings(imported_sim_settings)
        } catch {
          console.log("Error: It seems like your simulation settings are formatted wrong.")
        }
        try { 
          setVehiclesList(imported_vehicles)
        } catch {
          console.log("Error: it seems like you vehicles are formatted wrong.")
        }
      }
    }
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
                  <label style={{ cursor: "pointer"}} htmlFor="file_import">Import File</label>
                  <input id="file_import" name="file_import" type="file" style={{ display: "none" }} onChange={handleImport}></input>
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