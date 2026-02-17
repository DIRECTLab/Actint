import { SimulationSettingsTyp } from "./simulationSettings"
import { VehicleTyp } from './vehicleSettings'

export type CompleteExport = {
    sim_settings: SimulationSettingsTyp;
    vehicles: [VehicleTyp]
}