import { DestinationTyp, VehicleTyp } from "@/types/vehicleSettings"

type Props = {
    markers: DestinationTyp[],
    setMarkers: React.Dispatch<React.SetStateAction<DestinationTyp[]>>,
    vehiclesList: VehicleTyp[],
    vehicle_settings: VehicleTyp,
    set_vehicle_settings: React.Dispatch<React.SetStateAction<VehicleTyp>>,
    // vehicleName: string,
}

export function VehiclesOptionsList({markers, setMarkers, vehiclesList, vehicle_settings, set_vehicle_settings}: Props) {
    

    return(
        <div id="vehiclesOptionsList">
            {vehiclesList.map((vehicle, index) => {
                const isSelected = vehicle_settings.vehicle_id === vehicle.vehicle_id;
                return (
                <div 
                key={index}
                id="vehicle_option"
                className={`${isSelected ? 'bg-blue-600 text-white' : 'bg-transparent text-gray-700 hover:bg-gray-100'}`}
                onClick={() => {
                    set_vehicle_settings(vehicle)
                    if(vehicle.destinations){
                        
                        setMarkers(vehicle.destinations)
                    } else {
                        setMarkers([])
                    }
                    // setCurrentVehicle(vehicle)
                }}
                >View Vehicle {vehicle.vehicle_id}</div>)
})}
        </div>
        
    )
}
