
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
  target_offset: number;
  stay_time: number;
}


export type VehicleTyp = {
  vehicle_id: number;
  vehicle_type: string;
  is_3D: boolean;
  action: string;
  action_properties: ActionPropertiesTyp;
  properties: PropertiesTyp;
  destinations?: DestinationTyp[]
};

