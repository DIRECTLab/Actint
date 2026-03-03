import { SimulationSettingsTyp } from "@/types/simulationSettings";
import { VehicleTyp } from "@/types/vehicleSettings";


export const handleImport = async (event: any, set_simulation_settings: React.Dispatch<React.SetStateAction<SimulationSettingsTyp>>, setVehiclesList: React.Dispatch<React.SetStateAction<VehicleTyp[]>>) => {
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

    try{
        console.log("converting lat lon to LatLng: {lat, lng}")
        if(json_config_files.vehicles) {
            let saveVehicles = [];
            for (let vehicle of json_config_files.vehicles) {
                console.log(vehicle)
                let saveVehicle = structuredClone(vehicle)

                let lat = vehicle.properties.position.lat
                let lon = vehicle.properties.position.lon
                
                saveVehicle.properties.position.LatLng = { lat: lat, lng: lon }

                delete saveVehicle.properties.position.lat
                delete saveVehicle.properties.position.lon

                let saveDestinations = []
                if (vehicle.destinations) {
                    for (let destination of vehicle.destinations) {
                        let saveDestination = destination
                        let lon = saveDestination.position.lon
                        let lat = saveDestination.position.lat
                        saveDestination.position.LatLng = { lat: lat, lng: lon }
                        delete saveDestination.position.lat
                        delete saveDestination.position.lon
                        
                        saveDestinations.push(saveDestination)
                    }
                    saveVehicle.destinations = saveDestinations
                }

                
                let defaultActionProperties = {
                    target_id: 0,
                    target_offset: 0,
                    stay_time: 0,
                }

                switch(vehicle.action){
                    case "stay":
                        defaultActionProperties.stay_time = vehicle.stay_time;
                        break;

                    case "Persue":
                    case "Evade":
                        defaultActionProperties.target_id = vehicle.target_id;
                        break;
                    
                    case "OffsetPersue":
                        defaultActionProperties.target_id = vehicle.target_id;
                        defaultActionProperties.target_offset = vehicle.target_offset;
                        break;
                }
                
                saveVehicle.action_properties = defaultActionProperties;

                saveVehicles.push(saveVehicle)

                json_config_files.vehicles = saveVehicles

            }
        } 
    }
    catch (err) {
        console.log("failed to convert stonesoup { lat, lon } to leaflet { lat, lng }", err)
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
