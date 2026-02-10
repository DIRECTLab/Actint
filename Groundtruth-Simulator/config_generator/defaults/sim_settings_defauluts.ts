import { SimulationSettingsTyp } from '@/types/simulationSettings'

const DEFAULT_SIM_SETTIINGS: SimulationSettingsTyp = {
    output_file_2d: "JFN-Groundtruth-Simulator_result_2D.csv",
    output_file_3d: "JFN-Groundtruth-Simulator_result_3D.csv",
    time_step: 0.4,
    start_time: "2026-01-29T17:45",
    time_format: "%Y-%m-%d %H:%M:%S"
}

export default DEFAULT_SIM_SETTIINGS