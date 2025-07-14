from typing import Dict, List, Any, Optional
import os
from pydantic import BaseModel, Field
from settings import vehicle_settings


class HomeLocation(BaseModel):
    lat: float
    lon: float
    alt: float


class VehicleConfig(BaseModel):
    type: str
    connection: str
    port: str
    protocol: str
    baud_rate: Optional[str] = None
    home_location: Optional[HomeLocation] = None


# Default settings if settings.py is not available
DEFAULT_VEHICLE_SETTINGS = [
    {
        "type": "drone",
        "connection": "127.0.0.1",
        "port": "14551",
        "protocol": "udp",
        "home_location": {"lat": 0.0271556, "lon": 36.903084, "alt": 10},
    },
    {"type": "operator", "connection": "127.0.0.1", "port": "14552", "protocol": "udp"},
]


def get_vehicle_settings() -> List[Dict[str, Any]]:
    """
    Get vehicle settings from settings.py or use defaults.
    """
    try:
        return vehicle_settings
    except ImportError:
        print(
            "Could not import vehicle_settings from settings.py. Using default values."
        )
        return DEFAULT_VEHICLE_SETTINGS


# Environment variables
MAVLINK_CONNECTION_STRING = os.getenv(
    "MAVLINK_CONNECTION_STRING", "udp:127.0.0.1:14551"
)
WEBSOCKET_PING_INTERVAL = int(os.getenv("WEBSOCKET_PING_INTERVAL", "5"))  # seconds
