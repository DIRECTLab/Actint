import { VehicleTyp, DestinationTyp } from '@/types/vehicleSettings'
import { VehiclesOptionsList } from '@/components/vehicle_sidebar/VehiclesOptionsList';
import VehicleActions from '@/components/vehicle_sidebar/vehicle_behavior'
import DEFAULT_VEHICLE from '@/defaults/vehicle_defaults';
import { useState, useEffect, cloneElement } from 'react'
import L from 'leaflet'


type Props = {
  vehicle_settings: VehicleTyp,
  set_vehicle_settings: React.Dispatch<React.SetStateAction<VehicleTyp>>,
  markers: DestinationTyp[],
  setMarkers: React.Dispatch<React.SetStateAction<DestinationTyp[]>>,
  setVehiclesList: React.Dispatch<React.SetStateAction<VehicleTyp[]>>,
  vehiclesList: VehicleTyp[],
  createNewVehicle: (vehicleSettings: VehicleTyp, setVehicleSettings: React.Dispatch<React.SetStateAction<VehicleTyp>>, setVehiclesList: React.Dispatch<React.SetStateAction<VehicleTyp[]>>, markers: DestinationTyp[]) => void,
};

export default function VehicleSidebar({vehicle_settings, set_vehicle_settings, markers, setMarkers, vehiclesList, setVehiclesList, createNewVehicle}: Props) {

  
    
    return(<>

            {/* Vehicle Settings */}
            <div id="vehicle_settings">
              <div id="column">
                <h1 className="bg-blue-500 p-3 rounded">Vehicle Settings</h1> 

                {/* <label htmlFor="name">Vehicle Name</label>
                <input type="text" id="name" value={vehicleName} onChange={(e) => {setVehicleName(e.target.value)}}></input> */}


                {/* Vehicle ID */}
                <label htmlFor="vehicle_id">Vehicle ID</label>
                <input 
                  type="number" 
                  id="vehicle_id" 
                  value={vehicle_settings.vehicle_id}
                  onChange={(e) => {set_vehicle_settings( prev => ({...prev, vehicle_id : parseInt(e.target.value)}))}}
                />
                

                {/* Vehicle Dimension */}
                <label htmlFor="dimension">2D or 3D</label>
                <select 
                  id="dimension"
                  value={vehicle_settings.is_3D ? "true" : "false"}
                  onChange={(e) => {e.target.value =="true"? set_vehicle_settings(prev => ({...prev, is_3D: true, Z: 10})) : set_vehicle_settings( prev => ({...prev, is_3D: false, Z: undefined})); console.log(vehicle_settings.is_3D) }}
                >
                    <option value="false">2D</option>
                    <option value="true" >3D</option>
                </select>


                {/* Vehicle type */}
                <label htmlFor="vehicle_type">Vehicle Type</label>
                <select 
                  id="vehicle_type"
                  value={vehicle_settings.vehicle_type}
                  onChange={(e) => {set_vehicle_settings( prev => ({...prev, vehicle_type: e.target.value}))}}
                >
                  <option value="ship">Ship</option>
                  <option value="car">Car</option>
                  <option value="drone">Drone</option>
                </select>


                {/* Vehicle speed */}
                <label htmlFor="max_speed">Max Speed (meter/second)</label>
                <input 
                  type="number" 
                  id="max_speed" 
                  value={vehicle_settings.properties.max_speed}
                  onChange={(e) => {set_vehicle_settings(prev => ({
                    ...prev,
                    properties: {
                      ...prev.properties,
                      max_speed: parseInt(e.target.value)
                    }
                  }));
                  }}
                />
                

                {/* Vehicle force */}
                <label htmlFor="max_force">Max Force (Newtons)</label>
                <input 
                  type="number" 
                  id="max_force" 
                  value={vehicle_settings.properties.max_force}
                  onChange={(e) => {set_vehicle_settings(prev => ({
                    ...prev,
                    properties: {
                      ...prev.properties,
                      max_force: parseInt(e.target.value)
                    }
                  }));
                  }}
                />
                

                {/* Vehicle Behavior */}
                <VehicleActions
                  vehicle_settings={vehicle_settings}
                  set_vehicle_settings={set_vehicle_settings}
                ></VehicleActions>
                
                
                {/* Vehicle Position X */}
                <label htmlFor="positionX">Position X: </label>
                <input 
                  type="number" 
                  id="positionX" 
                  name="positionX"
                  value={vehicle_settings.properties.position.LatLng.lng}
                  onChange={
                    
                    (e) => {
                      var newLatLng = L.latLng(vehicle_settings.properties.position.LatLng.lat, parseFloat(e.target.value))
                      set_vehicle_settings( prev => ({
                    ...prev, properties:  
                    {...prev.properties, 
                      position: 
                      {
                        ...prev.properties.position, 
                        LatLng: newLatLng
                      }
                    }
                  })
                )}}
                />


                {/* Vehicle Position Y */}
                <label htmlFor="positionY">Position Y: </label>
                <input 
                  type="number"
                  id="positionY"
                  name="positionY"
                  value={vehicle_settings.properties.position.LatLng.lat}
                  onChange={(e) => {
                    var newLatLng = L.latLng(parseFloat(e.target.value), vehicle_settings.properties.position.LatLng.lng)
                    set_vehicle_settings(prev => ({...prev, properties: {...prev.properties, position: {...prev.properties.position, LatLng: newLatLng}}}))
                  }}
                />


                {/* Vehicle Position Z */}
                {(vehicle_settings.is_3D && <>
                  <label htmlFor="PositionZ">Position Z: </label>
                  <input 
                  id="positionZ"
                  name="positionZ"
                  value={vehicle_settings.properties.position.Z}
                  onChange={(e) => set_vehicle_settings( prev => ({...prev, properties: {...prev.properties, position: {...prev.properties.position, Z: parseInt(e.target.value)}}}))}
                />
                </>)}


                {/* Save Track */}
                <button 
                type="button"
                id="save_track"
                className="bg-green-500 p-1.5"
                onClick={(e) => {
                  if (vehiclesList.some(v => v.vehicle_id == vehicle_settings.vehicle_id)) {
                    if(confirm(`You are about to make changes to vehicle ${vehicle_settings.vehicle_id}. Are you sure?`)) {
                      const new_vehicle: VehicleTyp = structuredClone(vehicle_settings)
                      setVehiclesList(prevList => 
                          prevList.map(vehicle => vehicle.vehicle_id === vehicle_settings.vehicle_id ? { ...vehicle, ...new_vehicle }: vehicle)
                      );
                    } 
                  } else {
                    var newVehicle: VehicleTyp = {...vehicle_settings, destinations: markers}
                    createNewVehicle(vehicle_settings, set_vehicle_settings, setVehiclesList, markers)
                    const ids = vehiclesList.map(v => v.vehicle_id)
                    ids.push(newVehicle.vehicle_id)
                    let id = undefined
                    for (let n = 1; !id; n++) {
                      if (!ids.includes(n)){
                        id=n
                      }
                    }
                    newVehicle = DEFAULT_VEHICLE
                    newVehicle.vehicle_id = id
                    set_vehicle_settings(newVehicle)
                    console.log(newVehicle)
                  }
                }}
                >
                  Save/Create Vehicle
                </button>



            {/* Vehicle Options List */}
            <div className="text-yellow-500">Click the specific vehicle to show that vehicle's markers</div>
            <VehiclesOptionsList 
              markers={markers}
              setMarkers={setMarkers}
              vehiclesList={vehiclesList}
              vehicle_settings={vehicle_settings}
              set_vehicle_settings={set_vehicle_settings}
              // vehicleName={vehicleName}
            ></VehiclesOptionsList>


            {/* Dekete Vehicle */}
            <button 
              type="button"
              onClick={() => {
                if(confirm(`You are about to delete the vehicle with ID ${vehicle_settings.vehicle_id}. Are you sure?`)){
                  setVehiclesList((prev) => prev.filter(vehicle => vehicle.vehicle_id !== vehicle_settings.vehicle_id));
                  setMarkers([])
                  console.log(vehiclesList)
                }
              }}
              className="bg-red-500 p-1"
            >Delete Vehicle</button>
              

            {/* Clear Markers */}
            <button 
              type="button"
              onClick={() => {
                setMarkers([])
              }}
              className="bg-yellow-500 p-1"
            >Clear Markers</button>
            
            </div>
          </div>
            </>);
}

