
// import L from 'leaflet'

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
