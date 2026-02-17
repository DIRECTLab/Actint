import { VehicleTyp, DestinationTyp } from "@/types/vehicleSettings";
import DEFAULT_VEHICLE from "@/defaults/vehicle_defaults";


export const createNewVehicle = (vehicleSettings: VehicleTyp, setVehicleSettings: React.Dispatch<React.SetStateAction<VehicleTyp>>, setVehiclesList: React.Dispatch<React.SetStateAction<VehicleTyp[]>>, markers: DestinationTyp[]): void => {
  var newVehicle: VehicleTyp = {...vehicleSettings, destinations: markers }
  setVehiclesList((prev) => [...prev, newVehicle]);
  setVehicleSettings(DEFAULT_VEHICLE)
}

