import { SimulationSettingsTyp } from "./simulationSettings"
import { VehicleSettingsTyp } from './vehicleSettings'

export type CompleteExport = {
    sim_settings: SimulationSettingsTyp;
    vehicles: [VehicleSettingsTyp]
}