import { SimulationSettingsTyp } from '@/types/simulationSettings'

const DEFAULT_SIM_SETTIINGS: SimulationSettingsTyp = {
    simulation_file: "default_simulation.json",
    simulation_speed: 1.0,
    start_time: "2026-01-29T17:45",
    time_format: "%Y-%m-%d %H:%M:%S",
    is_3D: false,
}

export default DEFAULT_SIM_SETTIINGS

export const NUMBER_PREVIOUS_DISPLAYED_DETECTIONS = 20;