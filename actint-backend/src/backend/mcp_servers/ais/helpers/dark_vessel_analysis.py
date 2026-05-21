import time
import threading
import backend.dark_vessel.main as dark_vessel

print("Running dark vessel startup script...")
start_time = time.time()
#dark_vessel.main()
dark_vessel.run_region("brazil_eez")
end_time = time.time()
print(f"Dark vessel analysis time: {end_time - start_time:.2f} seconds")