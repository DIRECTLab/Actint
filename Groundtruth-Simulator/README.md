# JFN Groundtruth Simulator

A Python-based vehicle simulation framework for generating groundtruth trajectory scenarios for both 2D and 3D vehicles. The simulator supports multiple steering behaviors (seek, flee, arrive) and generates timestamped position data in CSV format.

## Table of Contents
- [Overview](#overview)
- [Features](#features)
- [How to Run](#how-to-run)
- [Input Format](#input-format)
- [Output Format](#output-format)
- [Class Documentation](#class-documentation)
- [Steering Behaviors](#steering-behaviors)
- [Example Usage](#example-usage)

## Overview

The JFN Groundtruth Simulator is designed to create realistic vehicle movement patterns for testing and validation purposes. It simulates vehicles moving through a series of waypoints using physics-based steering behaviors. The simulator supports both 2D vehicles (e.g., cars, ground vehicles) and 3D vehicles (e.g., drones, aircraft).

## Features

- **Multi-dimensional simulation**: Support for both 2D and 3D vehicle types
- **Steering behaviors**: Seek, flee, and arrive behaviors for realistic movement
- **Queue-based waypoint navigation**: Vehicles follow a series of destinations
- **Physics simulation**: Force-based steering with internal velocity/acceleration state
- **CSV-based I/O**: Easy-to-use CSV format for input configuration and output data
- **Timestamped output**: Precise tracking of vehicle state over time

## How to Run

### Running the Simulation

The main entry point is [main.py](main.py). Run the simulation by providing an input CSV file as a command-line argument:

```bash
python main.py simulation_data.csv
```

**Files involved:**
- **Input file**: `simulation_data.csv` (or any CSV file matching the input format)
- **Output file**: `JFN-Groudtruth-Simulator_result.csv` (auto-generated)

If the output file already exists, the program automatically creates a numbered version (e.g., `JFN-Groudtruth-Simulator_result_1.csv`, `JFN-Groudtruth-Simulator_result_2.csv`, etc.).

### Alternative: Test Run

You can also test the simulation without the main loop using [runfile.py](runfile.py):

```bash
python runfile.py
```

This runs a predefined test scenario with `simulation_data.csv`.

## Input Format

The simulation reads configuration from a CSV file. The file contains rows for vehicle definitions and destination waypoints, distinguished by the `is_destination` and `is_3d` columns.

### Required Columns for Vehicle2D

| Column | Type | Description | Units |
|--------|------|-------------|-------|
| `vehicle_id` | int | Unique identifier for each vehicle | - |
| `vehicle_type` | string | Type of vehicle (e.g., "car", "truck") | - |
| `is_3d` | boolean | Must be FALSE for 2D vehicles | - |
| `is_destination` | boolean | Must be FALSE for vehicle rows | - |
| `position_x` | float | Initial X coordinate | meters |
| `position_y` | float | Initial Y coordinate | meters |

Optional columns (defaults used if omitted):

| Column | Type | Description | Units |
|--------|------|-------------|-------|
| `max_speed` | float | Maximum speed (default: 100.0) | meters/second |
| `max_force` | float | Maximum steering force (default: 200.0) | newtons |
| `scale` | float | Visual scale for rendering (default: 10.0) | arbitrary |
| `max_turn_rate` | float | Maximum turn rate (default: 3.14159) | radians/second |
| `time_step` | float | Simulation time step (default: 1.0) | seconds |
| `action` | string | Steering behavior: "seek", "flee", "arrive" (default: "done") | - |

### Additional Required Columns for Vehicle3D

No additional required columns beyond Vehicle2D, except that `is_3d` must be TRUE.

Optional columns (defaults used if omitted):

| Column | Type | Description | Units |
|--------|------|-------------|-------|
| `position_z` | float | Initial Z coordinate (default: 0.0) | meters |
| `max_altitude` | int | Maximum altitude constraint (default: 1000) | meters |

### Required Columns for Destination2D

| Column | Type | Description | Units |
|--------|------|-------------|-------|
| `vehicle_id` | int | ID of vehicle this destination belongs to | - |
| `is_3d` | boolean | Must be FALSE for 2D destinations | - |
| `is_destination` | boolean | Must be TRUE for destination rows | - |
| `position_x` | float | Destination X coordinate | meters |
| `position_y` | float | Destination Y coordinate | meters |


### Additional Required Columns for Destination3D

No additional required columns beyond Destination2D, except that `is_3d` must be TRUE.

Optional columns (defaults used if omitted):

| Column | Type | Description | Units |
|--------|------|-------------|-------|
| `position_z` | float | Destination Z coordinate (default: 0.0) | meters |
| `dest_speed` | float | Target speed when approaching (default: 50.0) | meters/second |
| `dest_error` | float | Distance tolerance for arrival (default: 5.0) | meters |


#### Optional columns (defaults used if omitted):

| Column | Type | Description | Units |
|--------|------|-------------|-------|
| `dest_speed` | float | Target speed when approaching (default: 50.0) | meters/second |
| `dest_error` | float | Distance tolerance for arrival (default: 5.0) | meters |


### Input File Structure

The CSV file contains two types of rows:

1. **Vehicle definition rows** (`is_destination=FALSE`): Define initial vehicle state and properties
2. **Destination rows** (`is_destination=TRUE`): Define waypoints for each vehicle

Destinations are assigned to vehicles based on matching `vehicle_id` values. They are processed in the order they appear in the file.

### Example Input File (simulation_data.csv)

```csv
vehicle_id,vehicle_type,is_3d,is_destination,position_x,position_y,position_z,max_speed,max_force,scale,max_turn_rate,max_altitude,time_step,dest_speed,dest_error,action
1,car,FALSE,FALSE,0,0,,100,200,10,3.14159,,0.4,,,arrive
2,drone,TRUE,FALSE,0,0,0,150,300,10,2.5,1000,0.4,,,arrive
1,,FALSE,TRUE,1000,1000,,,,,,,,,25,5,
1,,FALSE,TRUE,500,1000,,,,,,,,,50,5,
1,,FALSE,TRUE,500,500,,,,,,,,,75,5,
1,,FALSE,TRUE,1000,500,,,,,,,,,100,5,
2,,TRUE,TRUE,1000,1000,1000,,,,,,,,30,10,
2,,TRUE,TRUE,500,1000,500,,,,,,,,60,10,
2,,TRUE,TRUE,500,500,1000,,,,,,,,90,10,
2,,TRUE,TRUE,1000,500,500,,,,,,,,120,10,
```

In this example:
- Vehicle 1 is a 2D car with 4 waypoints
- Vehicle 2 is a 3D drone with 4 waypoints

## Output Format

The simulation generates a CSV file containing timestamped vehicle position data. Each row represents the vehicle's position at a specific time step.

### Output Columns

| Column | Type | Description | Units |
|--------|------|-------------|-------|
| `vehicle_id` | int | Vehicle identifier | - |
| `time_stamp` | float | Simulation time (cumulative) | seconds |
| `position_x` | float | X position | meters |
| `position_y` | float | Y position | meters |
| `position_z` | float | Z position (0 for 2D vehicles) | meters |

### Example Output (JFN-Groudtruth-Simulator_result.csv)

```csv
vehicle_id,time_stamp,position_x,position_y,position_z
1,0.4,0.0234,0.0234,0.0
1,0.8,0.0703,0.0703,0.0
2,0.4,0.0312,0.0312,0.0312
2,0.8,0.0937,0.0937,0.0937
```

The output file grows with each simulation time step until all vehicles reach their final destinations (action becomes "done").

## Class Documentation

### Position Classes

#### `Position` (Abstract Base Class)
Abstract base class for all position representations.

**Abstract Methods:**
- `vector`: Returns position as numpy array
- `distance_to(position)`: Calculates distance to another position
- `get_heading(position)`: Calculates heading angle to another position

#### `Position2D`
Represents a 2D Cartesian position.

**Properties:**
- `x` (float): X coordinate [meters]
- `y` (float): Y coordinate [meters]
- `vector` (ndarray): Position as numpy array [meters]

**Methods:**
- `distance_to(position)`: Euclidean distance to another position [meters]
- `get_heading(position)`: Heading angle in radians (0 = north, clockwise) [radians]
- `get_heading_deg(position)`: Heading angle in degrees [degrees]

**Operators:**
- `+`: Add two Position2D objects
- `-`: Subtract two Position2D objects
- `==`: Check equality

#### `Position3D`
Represents a 3D Cartesian position (inherits from Position2D).

**Properties:**
- `x` (float): X coordinate [meters]
- `y` (float): Y coordinate [meters]
- `z` (float): Z coordinate [meters]
- `vector` (ndarray): Position as numpy array [meters]

**Methods:**
- `distance_to(position)`: Euclidean distance (3D when comparing 3D positions, 2D when comparing with 2D) [meters]
- `get_direction_vector(position)`: Returns normalized 3D direction vector to target [unitless]

**Operators:**
- `+`: Add two Position3D objects
- `-`: Subtract two Position3D objects
- `==`: Check equality

### Destination Classes

#### `Destination` (Abstract Base Class)
Represents a waypoint destination for vehicles.

**Properties:**
- `position` (Position): The geometric position of the destination [meters]
- `target_speed_to_next_destination` (float): Target speed when approaching [meters/second]
- `error` (float): Distance tolerance for reaching destination [meters]
- `heading_error` (float): Angular tolerance (default ~10 degrees) [radians]

**Methods:**
- `has_reached(position)`: Returns True if position is within error margin [boolean]

#### `Destination2D`
2D destination (inherits from Destination).

**Properties:**
- `position` (Position2D): 2D position [meters]
- `target_speed_to_next_destination` (float): Target approach speed [meters/second]
- `error` (float): Distance tolerance [meters]

#### `Destination3D`
3D destination (inherits from Destination).

**Properties:**
- `position` (Position3D): 3D position [meters]
- `target_speed_to_next_destination` (float): Target approach speed [meters/second]
- `error` (float): Distance tolerance [meters]

### Vehicle Classes

#### `Vehicle` (Base Class)
Abstract base class for all vehicle types.

**Properties:**
- `vehicle_type` (str): Type identifier (e.g., "car", "drone") [-]
- `vehicle_id` (int): Unique vehicle identifier [-]
- `time_step` (float): Simulation time step [seconds]
- `destination_queue` (Queue): Queue of destinations to visit [-]
- `next_destination` (Destination): Current target destination [-]
- `action` (str): Current behavior ("seek", "flee", "arrive", "done") [-]

**Methods:**
- `update()`: Update vehicle state (must be overridden by subclasses)
- `target_speed()`: Returns target speed to next destination [meters/second]

#### `Vehicle2D`
Simulates a 2D vehicle with physics-based steering (inherits from Vehicle).

**Properties:**
- `position` (Position2D): Current position [meters]
- `velocity` (Position2D): Current velocity vector [meters/second]
- `velocity_x` (float): X velocity component [meters/second]
- `velocity_y` (float): Y velocity component [meters/second]
- `acceleration` (Position2D): Current acceleration vector [meters/second²]
- `acceleration_x` (float): X acceleration component [meters/second²]
- `acceleration_y` (float): Y acceleration component [meters/second²]
- `max_speed` (float): Maximum velocity magnitude [meters/second]
- `max_force` (float): Maximum steering force [newtons]
- `max_turn_rate` (float): Maximum angular velocity [radians/second]
- `heading` (float): Current heading angle [radians]
- `scale` (float): Visual scale factor for rendering [-]
- `target` (Position2D): Current target position [meters]

**Methods:**
- `update(dt, window_w, window_h)`: Update position, velocity, and state
  - `dt` (float): Delta time [seconds]
  - `window_w` (int): Window width for wrapping [meters or pixels]
  - `window_h` (int): Window height for wrapping [meters or pixels]
- `seek()`: Calculate steering force toward target [newtons]
- `flee()`: Calculate steering force away from target [newtons]
- `arrive()`: Calculate steering force to smoothly reach target [newtons]

#### `Vehicle3D`
Simulates a 3D vehicle with physics-based steering (inherits from Vehicle).

**Properties:**
- `position` (Position3D): Current position [meters]
- `velocity` (Position3D): Current velocity vector [meters/second]
- `velocity_x` (float): X velocity component [meters/second]
- `velocity_y` (float): Y velocity component [meters/second]
- `velocity_z` (float): Z velocity component [meters/second]
- `acceleration` (Position3D): Current acceleration vector [meters/second²]
- `acceleration_x` (float): X acceleration component [meters/second²]
- `acceleration_y` (float): Y acceleration component [meters/second²]
- `acceleration_z` (float): Z acceleration component [meters/second²]
- `max_speed` (float): Maximum velocity magnitude [meters/second]
- `max_force` (float): Maximum steering force [newtons]
- `max_altitude` (int): Maximum altitude constraint [meters]
- `max_turn_rate` (float): Maximum angular velocity [radians/second]
- `heading` (float): Current heading angle in XY plane [radians]
- `scale` (float): Visual scale factor for rendering [-]
- `target` (Position3D): Current target position [meters]

**Methods:**
- `update(dt, window_w, window_h)`: Update position, velocity, and state
  - `dt` (float): Delta time [seconds]
  - `window_w` (int): Window width for X wrapping [meters]
  - `window_h` (int): Window height for Y wrapping [meters]
- `seek()`: Calculate 3D steering force toward target [newtons]
- `flee()`: Calculate 3D steering force away from target [newtons]
- `arrive()`: Calculate 3D steering force to smoothly reach target [newtons]

## Steering Behaviors

The simulator implements three steering behaviors based on autonomous agent steering:

### 1. Seek
Steers directly toward the target at maximum speed.
- **Use case**: Intercepting or chasing a target
- **Formula**: `desired_velocity = normalize(target - position) * target_speed`
- **Action value**: `"seek"`

### 2. Flee
Steers directly away from the target at maximum speed.
- **Use case**: Evasion or avoidance
- **Formula**: `desired_velocity = normalize(position - target) * target_speed`
- **Action value**: `"flee"`
- **Note**: Only activates when within 300 units of target

### 3. Arrive
Slows down smoothly when approaching the target.
- **Use case**: Waypoint navigation with smooth stops
- **Formula**: Speed scales down based on distance (< 200 units)
- **Action value**: `"arrive"`
- **Behavior**: Comes to a near-stop within error margin of destination

## Example Usage

### Basic 2D Vehicle Simulation

1. Create an input file `my_simulation.csv`:
```csv
vehicle_id,vehicle_type,is_3d,is_destination,position_x,position_y,max_speed,max_force,time_step,dest_speed,dest_error,action
1,car,FALSE,FALSE,0,0,80,150,0.5,,,arrive
1,,FALSE,TRUE,100,100,,,,,,,30,3,
1,,FALSE,TRUE,100,200,,,,,,,40,3,
1,,FALSE,TRUE,200,200,,,,,,,50,3,
```

2. Run the simulation:
```bash
python main.py my_simulation.csv
```

3. Output will be generated in `JFN-Groudtruth-Simulator_result.csv`

### Mixed 2D and 3D Simulation

Create a CSV with both 2D and 3D vehicles:
```csv
vehicle_id,vehicle_type,is_3d,is_destination,position_x,position_y,position_z,action,dest_speed,dest_error
1,car,FALSE,FALSE,0,0,,arrive,,
2,drone,TRUE,FALSE,0,0,0,arrive,,
1,,FALSE,TRUE,500,500,,,40,5
2,,TRUE,TRUE,500,500,300,,60,10
```

## Notes and Limitations

- **Coordinate system**: Uses Cartesian coordinates (not geographic lat/lon for primary operations)
- **Wrapping behavior**: 2D positions wrap around window boundaries (modulo operation)
- **Z-axis constraints**: 3D vehicles respect `max_altitude` and cannot go below 0
- **Time stepping**: Uses fixed time steps; smaller time steps = more accurate but slower simulation
- **Destination order**: Destinations are visited in the order they appear in the CSV for each vehicle
- **Termination**: Simulation runs until all vehicles reach `action="done"` (all destinations visited)

## Project Structure

```
JFN-Groundtruth-Simulator/
├── main.py                  # Main simulation entry point
├── runfile.py              # CSV parser and vehicle factory
├── csv_print.py            # CSV output utilities
├── simulation_data.csv     # Example input file
├── README.md               # This file
├── classes/
│   ├── __init__.py
│   ├── Position.py         # Position2D, Position3D classes
│   ├── Destination.py      # Destination2D, Destination3D classes
│   ├── Vehicle.py          # Base Vehicle class
│   ├── Vehicle2D.py        # 2D vehicle implementation
│   └── Vehicle3D.py        # 3D vehicle implementation
└── env/                    # Virtual environment
```

## Dependencies

- **numpy** (>=1.20.0): Numerical operations and vector math
- **pyglet** (>=2.0.0): Graphics library (for future visualization features)
