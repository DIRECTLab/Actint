from dataclasses import dataclass
from typing import Optional

@dataclass
class VesselPosition:
    """Represents a vessel's position at a point in time."""
    mmsi: int
    vessel_name: str
    timestamp: str
    lat: float
    lon: float
    sog: Optional[float] = None  # Speed Over Ground
    cog: Optional[float] = None  # Course Over Ground
    heading: Optional[float] = None
    
    def to_context_string(self) -> str:
        """Format position as a human-readable context string."""
        parts = [
            f"{self.vessel_name} (MMSI: {self.mmsi})",
            f"Position: {self.lat:.5f}°N, {self.lon:.5f}°W" if self.lon < 0 
                else f"Position: {self.lat:.5f}°N, {self.lon:.5f}°E",
            f"Last reported: {self.timestamp}",
        ]
        
        if self.sog is not None:
            parts.append(f"Speed: {self.sog:.1f} knots")
        
        if self.cog is not None:
            parts.append(f"Course: {self.cog:.1f}°")
        
        if self.heading is not None and self.heading != 511.0:  # 511 = not available
            parts.append(f"Heading: {self.heading:.1f}°")
        
        return ". ".join(parts)


@dataclass
class VesselInfo:
    """Extended vessel information from metadata."""
    mmsi: int
    vessel_name: str
    vessel_class: Optional[str] = None
    vessel_type: Optional[str] = None
    pennant_number: Optional[int] = None
    home_base: Optional[str] = None
    parent_command: Optional[str] = None
    fleet: Optional[str] = None
    
    def to_context_string(self) -> str:
        """Format vessel info as context string."""
        parts = [f"Vessel: {self.vessel_name}"]
        
        if self.vessel_type and self.pennant_number:
            parts.append(f"Designation: {self.vessel_type}-{self.pennant_number}")
        
        if self.vessel_class:
            parts.append(f"Class: {self.vessel_class}")
        
        if self.fleet:
            parts.append(f"Fleet: {self.fleet}")
        
        if self.home_base:
            parts.append(f"Home port: {self.home_base}")
        
        if self.parent_command:
            parts.append(f"Command: {self.parent_command}")
        
        return ". ".join(parts)