from datetime import time
from typing import List, Optional
from pydantic import BaseModel, Field

class ToddlerConstraints(BaseModel):
    max_daily_drive_hours: float = Field(default=3.5, description="Maximum total driving time per day")
    max_continuous_drive_hours: float = Field(default=1.5, description="Max drive time before a mandatory break")
    mandatory_stop_duration_mins: int = Field(default=45, description="Duration for toddler to burn energy")
    target_arrival_time: time = Field(default=time(15, 30), description="Target check-in time to prevent meltdowns")

class CostConstraints(BaseModel):
    has_national_parks_pass: bool = True  
    estimated_fuel_price_per_gallon: float = 4.07  # ~2026 US national average
    one_way_dropoff_fee_limit: float = 1500.0
    prefer_kitchen: bool = True  

class Waypoint(BaseModel):
    name: str
    latitude: float
    longitude: float
    is_national_park: bool = False

class RouteSegment(BaseModel):
    origin: Waypoint
    destination: Waypoint
    distance_miles: float
    drive_time_hours: float
    recommended_stops: List[str] = []