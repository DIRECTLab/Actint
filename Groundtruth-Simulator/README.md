# Groundtruth Simulator

A Python-based vehicle movement simulator that generates groundtruth position data for both 2D and 3D vehicles. The simulator supports multiple vehicle types (cars, drones, etc.) with configurable movement parameters and outputs data in CSV format with geodetic coordinates.

## Features

- **2D and 3D Vehicle Simulation**: Support for both ground-based (2D) and aerial (3D) vehicles
- **Flexible Configuration**: JSON-based runfile configuration for simulation parameters
- **Geodetic Coordinate Output**: Converts local ENU coordinates to WGS-84 latitude/longitude
- **Multiple Vehicles**: Simulate multiple vehicles simultaneously with different properties
- **Destination-Based Movement**: Vehicles follow a queue of destinations with configurable speed and error tolerance
- **Time-Stepped Simulation**: Configurable time step for simulation accuracy

## Requirements

- Python 3.x
- numpy
- pandas

## Usage

### Basic Usage

Run the simulator with the default example configuration:

```bash
python main.py
```

### Custom Configuration

Run the simulator with a custom runfile:

```bash
python main.py path/to/your_runfile.json
```

## Configuration File Format

The simulator uses a JSON configuration file (runfile) to define simulation parameters and vehicles. See [example_ground_truth_runfile.json](example_ground_truth_runfile.json) for a complete example.

### Configuration Structure

```json
{
  "sim_settings": {
    "output_file_2d": "output_2D.csv",
    "output_file_3d": "output_3D.csv",
    "time_step": 0.4,
    "start_time": "2025-01-27 02:58:45",
    "time_format": "%Y-%m-%d %H:%M:%S",
    "latlon_origin": {
      "latitude": 20.590305,
      "longitude": -157.697742,
      "height": 0.0
    }
  },
  "vehicles": [...]
}
```

### Simulation Settings Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `output_file_2d` | string | Filename for 2D vehicle output CSV |
| `output_file_3d` | string | Filename for 3D vehicle output CSV |
| `time_step` | float | Simulation time step in seconds |
| `start_time` | string | Simulation start time |
| `time_format` | string | Time format string (Python strftime format) |
| `latlon_origin` | object | Origin point for coordinate conversion |
| `latlon_origin.latitude` | float | Origin latitude in degrees |
| `latlon_origin.longitude` | float | Origin longitude in degrees |
| `latlon_origin.height` | float | Origin height in meters (typically 0.0 for sea level) |

**Note on Coordinate Origin Accuracy:**
- **0-10 km**: Sub-meter errors - excellent for harbor/port simulations
- **10-50 km**: 1-10 meter errors - good for coastal areas
- **50-100 km**: 10-50 meter errors - acceptable for regional simulations
- **100-200 km**: 50-200 meter errors - marginal accuracy
- **200+ km**: 200+ meter errors - significant distortion

### Vehicle Configuration

Each vehicle in the `vehicles` array has the following structure:

#### 2D Vehicle Example
```json
{
  "id": 1,
  "type": "car",
  "is_3d": false,
  "action": "seek",
  "properties": {
    "max_speed": 100.0,
    "max_force": 200.0,
    "position": { "x": 200.00, "y": 200.00 }
  },
  "destinations": [
    {
      "position": { "x": 500.0, "y": 500.0 },
      "speed": 50.0,
      "error": 30.0
    }
  ]
}
```

#### 3D Vehicle Example
```json
{
  "id": 2,
  "type": "drone",
  "is_3d": true,
  "action": "seek",
  "properties": {
    "max_speed": 100.0,
    "max_force": 200.0,
    "max_altitude": 1200,
    "position": { "x": 200.00, "y": 200.00, "z": 200.00 }
  },
  "destinations": [
    {
      "position": { "x": 500.0, "y": 500.0, "z": 500.0 },
      "speed": 50.0,
      "error": 30.0
    }
  ]
}
```

### Vehicle Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `id` | integer | Yes | Unique vehicle identifier |
| `type` | string | Yes | Vehicle type (e.g., "car", "drone", "ship") |
| `is_3d` | boolean | Yes | Whether vehicle operates in 3D space |
| `action` | string | Yes | Movement behavior (typically "seek") |
| `properties.max_speed` | float | Yes | Maximum speed in meters per second |
| `properties.max_force` | float | Yes | Maximum acceleration force |
| `properties.max_altitude` | float | 3D only | Maximum altitude in meters |
| `properties.position` | object | Yes | Starting position (x, y for 2D; x, y, z for 3D) |
| `destinations` | array | Yes | Array of destination waypoints |

### Destination Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `position` | object | Target position (x, y for 2D; x, y, z for 3D) in meters |
| `speed` | float | Desired speed to this destination in meters per second |
| `error` | float | Distance tolerance in meters (vehicle reaches destination when within this distance) |

## Output Format

The simulator generates two CSV files (if both 2D and 3D vehicles are present):

### 2D Output Columns (AIS Format)
- `MMSI`: Maritime Mobile Service Identity (uses vehicle ID)
- `BaseDateTime`: Simulation timestamp (YYYY-MM-DD HH:MM:SS)
- `LAT`: Latitude in degrees
- `LON`: Longitude in degrees
- `SOG`: Speed Over Ground in knots
- `COG`: Course Over Ground in degrees
- `Heading`: Vessel heading in degrees
- `VesselName`: Name/type of vessel (e.g., "CAR")
- `VesselType`: Type of vehicle (e.g., "car", "ship")
- `Length`: Vessel length in meters
- `Width`: Vessel width in meters

### 3D Output Columns (ADS-B Format)
- `date`: Date (YYYY-MM-DD)
- `time`: Time (HH:MM:SS)
- `icao_hex`: ICAO 24-bit address (uses vehicle ID in hex format)
- `latitude`: Latitude in degrees
- `longitude`: Longitude in degrees
- `altitude`: Altitude above origin in meters
- `altitude_unit`: Unit of altitude measurement (meters)
- `vertical_rate`: Rate of climb/descent
- `vertical_rate_unit`: Unit of vertical rate (meters/minute)

## How It Works

1. **Initialization**: The simulator reads the runfile and creates vehicle objects with their destinations
2. **Simulation Loop**: 
   - Each vehicle updates its position based on its current destination
   - Positions are logged to CSV files with geodetic coordinates
   - Time advances by the configured time step
   - Loop continues until all vehicles reach their final destinations
3. **Coordinate Conversion**: Local ENU (East-North-Up) coordinates are converted to WGS-84 latitude/longitude using the specified origin point

## File Structure

- `main.py`: Main entry point for the simulator
- `runfile.py`: JSON configuration file parser
- `csv_print.py`: CSV output and coordinate conversion functions
- `classes/`: Vehicle and supporting classes
  - `Vehicle2D.py`: 2D vehicle implementation
  - `Vehicle3D.py`: 3D vehicle implementation
  - `Position.py`: Position data structures
  - `Destination.py`: Destination data structures
  - `Settings.py`: Simulation settings class

## Tips

- Ensure the coordinate origin is close to your simulation area for best accuracy
- Use smaller time steps (e.g., 0.1-0.5 seconds) for smoother trajectories
- Vehicles will move to each destination in order from the destinations array
