
// import L from 'leaflet'

export type PositionTyp = {
  LatLng: { lat: number, lng: number }
  Z?: number;
}


export type DestinationTyp = {
  position: PositionTyp;
  speed: number;
  error: number;
}


export type PointTyp = {
  position: PositionTyp
  lattitude: number;
  longtude: number;
  height?: number;
  
}


export type PropertiesTyp = {
  max_speed: number;
  max_force: number;
  max_altitude: number;
  position: PositionTyp;
}


export type ActionPropertiesTyp = {
  target_id: number;
  target_offset: PositionTyp;
  stay_time: number;
}


export type VehicleTyp = {
  mmsi: number;
  current_detection: DetectionTyp | null
  previous_detections: DetectionTyp[];
};

export type DetectionTyp = {
  id: number;
  mmsi: number;
  base_datetime: string;
  lat: number;
  lon:number;
  sog: number;
  cog: number;
  heading: number;
  vessel_name: string;
  imo: string | null;
  callsign: string;
  vessel_type: string;
  status: number;
  length: number|null;
  width: number|null;
  draft: number|null;
  cargo: number;
  transceiver_class: string;
  created_at: string;  
}


export type vehicles_previous_positions = { [mmsi: number]: { lat: number, lng: number }[] }

export type vehicles_current_positions = { [mmsi: number]: { lat: number, lng: number } }
