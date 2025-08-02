from pydantic import BaseModel
from typing import Optional
from backend.config import CONFIG


class Waypoint(BaseModel):
    seq: int
    lat: float
    lon: float
    alt: float
    command: int = CONFIG.mavlink.NAV_WAYPOINT_COMMAND
    param1: float = CONFIG.mavlink.PARAM1
    param2: float = CONFIG.mavlink.PARAM2
    param3: float = CONFIG.mavlink.PARAM3
    param4: float = CONFIG.mavlink.PARAM4
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
