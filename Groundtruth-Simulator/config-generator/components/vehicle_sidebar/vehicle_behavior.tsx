import { DestinationTyp, VehicleTyp } from "@/types/vehicleSettings"
import { useEffect } from 'react'

type Props = {
  vehicle_settings: VehicleTyp,
  set_vehicle_settings: React.Dispatch<React.SetStateAction<VehicleTyp>>,
}



export default function VehicleActions({vehicle_settings, set_vehicle_settings} : Props) {


  let show_vehicle_persue_evade = vehicle_settings.action == "Persue" || vehicle_settings.action == "Evade";
  let show_vehicle_persue_offset = vehicle_settings.action == "OffsetPersue";
  let show_vehicle_stay = vehicle_settings.action == "stay";

  useEffect(() => {
    if (
        vehicle_settings.action_properties.target_id == vehicle_settings.vehicle_id
    ) {
        set_vehicle_settings(prev => ({
        ...prev,
        action_properties: {
            ...prev.action_properties,
            target_id: prev.action_properties.target_id + 1
        }
        }));
    }
    }, [
    vehicle_settings.action_properties.target_id,
    ]);

    return (<>
    {/* Vehicle Behaviour */}
    <label htmlFor="select_behavior">Select Behavior</label>
    <select 
        id="select_behavior"
        value={vehicle_settings.action}
        onChange={(e) => set_vehicle_settings( prev => ({...prev, action: e.target.value}))}
    >
        <option value="seek">Seek</option>
        <option value="flee">Flee</option>
        <option value="pursue">Pursue</option>
        <option value="evade">Evade</option>
        <option value="follow">Follow</option>
        <option value="stay">Stay</option>
    </select>

    {show_vehicle_persue_evade && (
        <>
        <div>
        <label htmlFor="targetID">Target ID</label>
        <input
            id="targetID"
            type="number"
            value={vehicle_settings.action_properties.target_id}
            onChange={(e) => {set_vehicle_settings(prev => ({...prev, action_properties: {...prev.action_properties, target_id: parseInt(e.target.value)}}))}}
        ></input>
        </div>
        </>
    )}

    {show_vehicle_persue_offset && (
        <>
        <div>
        <label htmlFor="targetID">Target ID</label>
        <input
            id="targetID"
            type="number"
            value={vehicle_settings.action_properties.target_id}
            onChange={(e) => {set_vehicle_settings(prev => ({...prev, action_properties: {...prev.action_properties, target_id: parseInt(e.target.value)}}))}}
        ></input>
        </div>

        <div>
        <label htmlFor="offset">Offset</label>
        <input
            id="offset"
            type="number"
            value={vehicle_settings.action_properties.target_offset}
            onChange={(e) => {set_vehicle_settings(prev => ({...prev, action_properties: {...prev.action_properties, target_offset: parseInt(e.target.value)}}))}}
        ></input>
        </div>
        </>
    )}

    {show_vehicle_stay && (
        <>
        <div>
        <label htmlFor="stay_time">Stay time:</label>
        <input 
            id="stay_time"
            type="number"
            value={vehicle_settings.action_properties.stay_time}
            onChange={(e) => {set_vehicle_settings(prev => ({...prev, action_properties: {...prev.action_properties, stay_time: parseFloat(e.target.value)}}))}}
        ></input>
        </div>
        </>
    )}
    
    </>)

}
