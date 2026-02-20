"use client"

import { VehicleTyp, PropertiesTyp } from '@/types/vehicleSettings'
// import type L from 'leaflet'

const DEFAULT_VEHICLE: VehicleTyp = {
    vehicle_id: 1,
    vehicle_type: "ship",
    is_3D: false,
    action: "stay",
    action_properties: {
      target_id: 0,
      target_offset: 0,
      stay_time: 0,
    },
    properties: {
      max_speed: 50,
      max_force: 50,
      max_altitude: 1200,
      position: {
        LatLng: { lat: 0, lng: 0 }
      }
    }
};

export default DEFAULT_VEHICLE