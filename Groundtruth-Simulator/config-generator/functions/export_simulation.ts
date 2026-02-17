import { SimulationSettingsTyp } from '@/types/simulationSettings'
import { VehicleTyp } from '@/types/vehicleSettings'


const export_simulation = (simulationSettings: SimulationSettingsTyp, vehiclesList: VehicleTyp[]): void => {
let saveVehiclesList = []
for (let currentVehicle of vehiclesList) {
    let saveVehicle: any = currentVehicle
    
    if(currentVehicle.destinations){
        let saveDestinations = []
        for (let destination of currentVehicle.destinations) {
            let saveDestination: any = destination
            let lat = saveDestination.position.LatLng.lat
            let lon = saveDestination.position.LatLng.lng
            
            saveDestination.position.lat = lat
            saveDestination.position.lon = lon

            delete saveDestination.position.LatLng

            saveDestinations.push(saveDestination)
        }
        saveVehicle.destinations = saveDestinations

    }

    let lat = currentVehicle.properties.position.LatLng.lat
    let lon = currentVehicle.properties.position.LatLng.lng

    saveVehicle.properties.position.lat = lat
    saveVehicle.properties.position.lon = lon

    delete saveVehicle.properties.position.LatLng

    saveVehiclesList.push(saveVehicle)
}


const data = {
    "sim_settings": simulationSettings,
    "vehicles": saveVehiclesList,
    
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

export default export_simulation