from backend.transport.start_web_socket import sio
from datetime import datetime
import asyncio
from backend.simulation.simulation_data import get_positions_before_time, get_positions_after_time, create_json_packet # These functions are deleted but in the git history
import sys


@sio.on("simulation_init")
async def handle_simulation_init(sid, data):
    print(f"Simulation init from {sid}: {data}", file=sys.stderr)
    
    start_time = str(data["start_time"]+":07.000000")
    # Send to EVERYONE else
    await sio.emit("private_response", {"msg": f"Sending simulation data up to {data["start_time"]}"}, to=sid)

    (MMSIs, results) = get_positions_before_time(start_time)

    await sio.emit("previous_data", {"MMSIs": MMSIs, "results": results}, to=sid)
    await sio.emit("private_response", {"msg": f"Finished sending simulation data up to {data["start_time"]}"}, to=sid)

    future_detections = get_positions_after_time(start_time)
    await send_simulation_updates(sid, future_detections, start_time)



async def send_simulation_updates(sid, data, start_time):
    current_time = start_time
    for detection in data:
        time_between = datetime.strptime(detection[2], '%Y-%m-%dT%H:%M:%S.%f') - datetime.strptime(current_time, '%Y-%m-%dT%H:%M:%S.%f')
        if(time_between.total_seconds() > 0):
            await asyncio.sleep(time_between.total_seconds())
        json_packet = create_json_packet(detection) 
        await sio.emit("new_detection", json_packet, to=sid)
        current_time = detection[2]
