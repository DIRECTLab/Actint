import sqlite3
import os
from datetime import datetime, timedelta
import time
import threading
import socketio
import eventlet
import asyncio
import uvicorn

sio = socketio.AsyncServer(async_mode='asgi', cors_allowed_origins='*') # Allow your React app to connect
app = socketio.ASGIApp(sio)

BASE_DIRECTORY = os.path.dirname(os.path.abspath(__file__))

def setup():
    with sqlite3.connect('live_ais.db') as conn:
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS ais_positions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                MMSI INTEGER,
                base_datetime TEXT,
                lat REAL,
                lon REAL,
                sog REAL,
                cog REAL,
                heading REAL,
                vessel_name TEXT, 
                imo TEXT,
                call_sign TEXT,
                vessel_type TEXT,
                status REAL,
                length REAL,
                width REAL,
                draft REAL,
                cargo REAL,
                tranciever_class REAL,
                created_at TEXT
            )
        ''')

        conn.commit()

def get_chronological_history(offset):
    with sqlite3.connect('../db/ais.db') as conn:
        cursor = conn.cursor()


        query = f"""
            SELECT *
            FROM ais_positions 
            ORDER BY base_datetime ASC
            LIMIT 1 OFFSET {offset}
        """
        
        cursor.execute(query)
        result = cursor.fetchall()

    return result

def append_item_to_db(data):
    with sqlite3.connect('live_ais.db') as conn:
        cursor = conn.cursor()
        query = """
            INSERT INTO ais_positions (id, mmsi, base_datetime, lat, lon, sog, cog, heading, vessel_name, imo, call_sign, vessel_type, status, length, width, draft, cargo, tranciever_class, created_at) 
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        cursor.execute(query, (data))

        conn.commit()


@sio.event
async def connect(sid, environ):
    print(f"User connected: {sid}")

@sio.event
async def disconnect(sid):
    print(f"User disconnected: {sid}")




async def run_live_database():

    detection_number = 0
    setup()
    start_time = datetime.strptime(get_chronological_history(0)[0][2], "%Y-%m-%dT%H:%M:%S.%f") - timedelta(seconds = 1)

    while(True):
        next_detection = get_chronological_history(detection_number)[0]
        wait_time = datetime.strptime(next_detection[2], "%Y-%m-%dT%H:%M:%S.%f") - start_time
        
        asyncio.sleep(wait_time.total_seconds())
        # time.sleep(wait_time.total_seconds())
        append_item_to_db(next_detection)
        
        detection_number += 1

        print(next_detection)
        print("Sent an update for a new ship detection")
        await sio.emit('ship_update', {
                "id": next_detection[0],
                "mmsi": next_detection[1],
                "lat": next_detection[3],
                "lon": next_detection[4],
                "sog": next_detection[8],
                "cog": next_detection[9],
            })








async def main():
    # Start your loop as a background task in the event loop
    asyncio.create_task(run_live_database())
    
    # Start Uvicorn
    config = uvicorn.Config(app, host="0.0.0.0", port=2500)
    server = uvicorn.Server(config)
    await server.serve()

if __name__ == '__main__':
    
    asyncio.run(main()) 