import { DestinationTyp} from "@/types/vehicleSettings";
import { useState } from 'react'

import { useMapEvents } from 'react-leaflet'

import { previousValsTyp } from "@/types/otherTypes"

import L from 'leaflet';

interface PopupProps {
  is_3D: boolean,
  previousValues: previousValsTyp,
  setPreviousValues: React.Dispatch<React.SetStateAction<previousValsTyp>>,
  updateMarker: (index: number, LatLng: {lat: number, lng: number}, height: any, speed: number,  error: number) => void;
  deleteMarker: (index: number) => void,
  index: number,
  marker: DestinationTyp,
  };

export default function PopupInputs({ is_3D, previousValues, setPreviousValues, updateMarker, deleteMarker, index, marker }: PopupProps) {
    
    

  return (
    <div 
      className="p-2 min-w-[320px] text-slate-800" 
      onKeyDown={(e) => e.stopPropagation()}
    >
      <header className="mb-4 border-b pb-2">
        <h3 className="text-lg font-bold">Add Waypoint</h3>
      </header>

      <form 
        className="flex flex-col gap-4"
        onSubmit={(e) => {
          e.preventDefault();
          const formData = new FormData(e.currentTarget);
        //   onSubmit(Object.fromEntries(formData));
        }}
      >
        {/* Grid Container for Inputs */}
        <div className="grid grid-cols-2 gap-x-4 gap-y-3">
          
          {/* Latitude */}
          <div className="flex flex-col gap-1">
            <label htmlFor="X" className="text-xs font-semibold uppercase text-slate-500">Latitude</label>
            <input 
              type="number" 
              id="X" 
              name="X" 
              step="any" 
              value={marker.position.LatLng.lat}
              onChange={(e) => {var newVal = parseFloat(e.target.value); updateMarker(index, L.latLng(newVal, marker.position.LatLng.lng), marker.position.Z, marker.speed, marker.error)}}
              className="rounded border border-slate-300 p-1.5 text-sm focus:ring-2 focus:ring-blue-500 outline-none"
            />
          </div>

          {/* Longitude */}
          <div className="flex flex-col gap-1">
            <label htmlFor="Y" className="text-xs font-semibold uppercase text-slate-500">Longitude</label>
            <input 
              type="number" 
              id="Y" 
              name="Y" 
              step="any" 
              value={marker.position.LatLng.lng}
              onChange={(e) => {var newVal = parseFloat(e.target.value); updateMarker(index, L.latLng(marker.position.LatLng.lat, newVal), marker.position.Z, marker.speed, marker.error)}}              
              className="rounded border border-slate-300 p-1.5 text-sm focus:ring-2 focus:ring-blue-500 outline-none"
            />
          </div>

          {/* Conditional Height - Spans full width if 3D */}
          {is_3D && (
            <div className="flex flex-col gap-1 col-span-2">
              <label htmlFor="Z" className="text-xs font-semibold uppercase text-slate-500">Height (meters)</label>
              <input 
                type="number" id="Z" name="Z" autoFocus value={marker.position.Z} defaultValue={previousValues.height} onChange={(e) => {setPreviousValues( prev => ({...prev, height: parseFloat(e.target.value)})); updateMarker(index, marker.position.LatLng, marker.position.Z, parseInt(e.target.value), marker.error)}}
                className="rounded border border-slate-300 p-1.5 text-sm focus:ring-2 focus:ring-blue-500 outline-none"
              />
            </div>
          )}

          {/* Speed */}
          <div className="flex flex-col gap-1">
            <label htmlFor="speed" className="text-xs font-semibold uppercase text-slate-500">Speed</label>
            <input 
              type="number" id="speed" name="speed" defaultValue={previousValues.speed} value={marker.speed} onChange={(e) => {setPreviousValues( prev => ({...prev, speed: parseInt(e.target.value)})); updateMarker(index, marker.position.LatLng, marker.position.Z, parseInt(e.target.value), marker.error)}}
              className="rounded border border-slate-300 p-1.5 text-sm focus:ring-2 focus:ring-blue-500 outline-none"
            />
          </div>

          {/* Error */}
          <div className="flex flex-col gap-1">
            <label htmlFor="error" className="text-xs font-semibold uppercase text-slate-500">Error Margin</label>
            <input 
              type="number" id="error" name="error" defaultValue={previousValues.error} value={marker.error} onChange={(e) => {setPreviousValues( prev => ({...prev, error: parseInt(e.target.value)})); updateMarker(index, marker.position.LatLng, marker.position.Z, marker.speed, parseInt(e.target.value))}}
              className="rounded border border-slate-300 p-1.5 text-sm focus:ring-2 focus:ring-blue-500 outline-none"
            />
          </div>
        </div>

        <button 
          type="button"
          className="mt-2 w-full bg-red-600 hover:bg-red-700 text-white font-bold py-2 rounded transition-colors"
          onClick={(e) => {L.DomEvent.stopPropagation(e.nativeEvent); deleteMarker(index)}}
        >
          Delete Marker
        </button>
      </form>
    </div>
  );
}