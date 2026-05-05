import { vehicles_current_positions, vehicles_previous_positions } from "@/types/vehicleSettings"

type Props = {
//   VehicleCurrentPositions: vehicle_current_positions
  setVehicleCurrentPositions: React.Dispatch<React.SetStateAction<vehicles_current_positions>>,
//   VehiclePreviousPositions: vehicles_previous_positions
  setVehiclePreviousPositions: React.Dispatch<React.SetStateAction<vehicles_previous_positions>>,
  data: any,
};


// Change the name here...
export const initializeVehicleData = ({setVehicleCurrentPositions, setVehiclePreviousPositions, data}: Props) => {
    const MMSIs = data["MMSIs"]
    const data_results = data["results"]
    const current_positions: vehicles_current_positions = {};
    const previous_positions: vehicles_previous_positions = {};

    data_results.forEach((data: any) => {
        
        const mmsi = data[0];
        const detections = data[1];
        console.log("Data", detections)
        
        let lat_lon_list: { lat: number; lng: number }[] = []
        let current_lat_lon: { lat: number; lng: number } = {lat: 0, lng: 0};
        let newest_time: string;
        // Go through all the detections and add them to the previous positions for this MMSI
        detections.forEach((detection: any) => {
            if(!newest_time || new Date(detection['base_datetime']) > new Date(newest_time)) {
                newest_time = detection['base_datetime'];
                current_lat_lon = { "lat": detection['lat'], "lng": detection['lon'] };
            }
            const lat = detection['lat'];
            const lon = detection['lon'];
            lat_lon_list.push({ "lat": lat, "lng": lon });
        });
        current_positions[mmsi] = current_lat_lon;
        // Set the previous positions for this MMSI
        previous_positions[mmsi] = lat_lon_list;

        
    });

    console.log(current_positions)
    console.log(previous_positions)

    setVehicleCurrentPositions(current_positions);
    setVehiclePreviousPositions(previous_positions);
}


export const update_position = ({setVehicleCurrentPositions, setVehiclePreviousPositions, data}: Props) => {
    console.log("update position", data);
    const mmsi = data['mmsi'];
    const lat = data['lat'];
    const lon = data['lon'];

    setVehicleCurrentPositions(prev => ({ ...prev, [mmsi]: { lat, lng: lon } }));
    setVehiclePreviousPositions(prev => {
        const prev_positions = prev[mmsi] || [];
        const new_positions = [...prev_positions, { lat, lng: lon }].slice(-20); // Keep only the last 20 positions
        return { ...prev, [mmsi]: new_positions };
    });
}





















