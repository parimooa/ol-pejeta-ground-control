from pydantic import BaseModel
from typing import Optional


class Waypoint(BaseModel):
    seq: int
    lat: float
    lon: float
    alt: float
    command: int = 16  # MAV_CMD_NAV_WAYPOINT
    param1: float = 0
    param2: float = 0
    param3: float = 0
    param4: float = 0
    autocontinue: bool = True
    current: bool = False

    class Config:
        schema_extra = {
            "example": {
                "seq": 0,
                "lat": -1.2345,
                "lon": 36.7890,
                "alt": 20.0,
                "command": 16,
                "param1": 0,
                "param2": 0,
                "param3": 0,
                "param4": 0,
                "autocontinue": True,
                "current": False,
            }
        }
