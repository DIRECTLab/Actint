import time
import threading
import backend.dark_vessel.main as dark_vessel

def run():
    print("Running dark vessel startup script...")
    start_time = time.time()
    dark_vessel.run_region("brazil_eez")
    end_time = time.time()
    print(f"Dark vessel analysis time: {end_time - start_time:.2f} seconds")
    return (f"the dark vessel startup script has been run in {end_time - start_time:.2f} seconds.")