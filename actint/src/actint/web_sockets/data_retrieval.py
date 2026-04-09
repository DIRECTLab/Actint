import sqlite3
import os
from datetime import datetime, timedelta
import time
import threading
import socketio
import eventlet
import asyncio
import uvicorn
from pathlib import Path

sio = socketio.AsyncServer(async_mode='asgi', cors_allowed_origins='*') # Allow your React app to connect
app = socketio.ASGIApp(sio)


BASE_DIRECTORY = Path(__file__).resolve().parent.parent.parent.parent / "data"
print(BASE_DIRECTORY)

NUMBER_PREVIOUS_DISPLAYED_DETECTIONS = 20



def create_json_packet(detection):
    json_packet = {
        "id": detection[0],
        "mmsi": detection[1],
        "base_datetime": detection[2],
        "lat": detection[3],
        "lon": detection[4],
        "sog": detection[5],
        "cog": detection[6],
        "heading": detection[7],
        "vessel_name": detection[8],
        "imo": detection[9],
        "call_sign": detection[10],
        "vessel_type": detection[11],
        "status": detection[12],
        "length": detection[13],
        "width": detection[14],
        "draft": detection[15],
        "cargo": detection[16],
        "tranciever_class": detection[17],
        "created_at": detection[18]
    }
    return json_packet




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





def get_next_detection(offset):
    with sqlite3.connect(BASE_DIRECTORY / 'db' / 'ais.db') as conn:
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



def get_positions_before_time(target_time):
    """
    Returns a list of positions that occurred before the target_time.
    target_time should be a string in 'YYYY-MM-DD HH:MM:SS' format.
    """
    with sqlite3.connect(BASE_DIRECTORY / 'db' / 'ais.db') as conn:

        cursor = conn.cursor()

        vessel_results = cursor.execute(f"SELECT * FROM vessels").fetchall()
        MMSIs = [vessel[0] for vessel in vessel_results]
        
        result = []
        for MMSI in MMSIs:
            query = f"""
                SELECT *
                FROM ais_positions 
                WHERE base_datetime <= ?
                AND mmsi = {MMSI}
                ORDER BY base_datetime DESC
                """

            cursor.execute(query, (str(target_time),))
            mmsi_locations = cursor.fetchall()
            if MMSI == 369970707:
                print(mmsi_locations)
                print(str(target_time))
            mmsi_locations = mmsi_locations[:NUMBER_PREVIOUS_DISPLAYED_DETECTIONS]
            mmsi_locations.reverse()
            mmsi_locations_result = []
            for mmsi_location in mmsi_locations:
                mmsi_locations_result.append(create_json_packet(mmsi_location))
            result.append([MMSI, mmsi_locations_result])

    return (MMSIs, result)





def get_positions_after_time(target_time):
    """
    Returns a list of positions that occurred after the target_time.
    target_time should be a string in 'YYYY-MM-DD HH:MM:SS' format.
    """
    with sqlite3.connect(BASE_DIRECTORY / 'db' / 'ais.db') as conn:
        cursor = conn.cursor()

        # We filter with WHERE and sort by time to keep it chronological
        query = """
            SELECT *
            FROM ais_positions 
            WHERE base_datetime > ?
            ORDER BY base_datetime ASC
        """
        
        # Pass variables as a tuple to the execute method
        print(target_time)
        cursor.execute(query, (str(target_time),))
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




        