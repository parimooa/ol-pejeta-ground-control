import os
from dataclasses import dataclass
from typing import Dict, List, Any, Optional

from pydantic import BaseModel

from settings import vehicle_settings


# TODO Merge settings.py with this config
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


# TODO: Create connection string here

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


# =============================================================================
# APP CONFIGURATION : Add any constants here or update existing
# =============================================================================


@dataclass(frozen=True)
class PhysicalConstants:
    """Physical constants used throughout the system."""

    EARTH_RADIUS_METERS: int = 6371000  # Earth radius for Haversine calculations


@dataclass(frozen=True)
class NetworkConstants:
    """Network and communication configuration."""

    MAVLINK_CONNECTION_STRING: str = os.getenv(
        "MAVLINK_CONNECTION_STRING", "udp:127.0.0.1:14551"
    )
    WEBSOCKET_PING_INTERVAL: int = int(os.getenv("WEBSOCKET_PING_INTERVAL", "5"))
    MAVLINK_SOURCE_SYSTEM: int = 255  # Source system ID for MAVLink


@dataclass(frozen=True)
class TimeoutConstants:
    """Timeout values for various operations."""

    HEARTBEAT: int = 10  # seconds
    MODE_CHANGE: int = 15  # seconds
    TAKEOFF: int = 30  # seconds
    ARM: int = 10  # seconds
    DISARM: int = 5  # seconds
    MISSION_UPLOAD_PER_WAYPOINT: int = 10  # seconds
    MISSION_COUNT: int = 3  # seconds
    MISSION_ITEM: int = 3  # seconds
    MISSION_ACK_SHORT: int = 5  # seconds
    MISSION_ACK_LONG: int = 15  # seconds
    MAVLINK_MESSAGE: int = 1  # seconds


@dataclass(frozen=True)
class VehicleConstants:
    """Vehicle-specific configuration constants."""

    WAYPOINT_VISIT_THRESHOLD: float = 3.0  # meters
    WAYPOINT_CONFIRMATION_DELAY: float = 2.0  # seconds
    TELEMETRY_STREAM_RATE: int = 4  # Hz
    EXTENDED_STATUS_RATE: int = 2  # Hz
    MISSION_CURRENT_REQUEST_INTERVAL: float = 2.0  # seconds


@dataclass(frozen=True)
class SurveyConstants:
    """Survey and mission planning constants."""

    SWATH_WIDTH: int = 50  # 50 meters - spacing between scan lines
    PATTERN_LENGTH: int = 1000  # 1000 meters - length of lawnmower stripe
    MAX_RADIUS: int = (
        500  # 500 meters - maximum survey radius , rectangular pattern PATTERN_LENGTH x (2 * MAX_RADIUS)
    )

    LOITER_RADIUS_STANDARD: float = 15.0  # meters
    LOITER_RADIUS_PROXIMITY: float = 20.0  # meters
    PROGRESS_UPDATE_INTERVAL: int = 10  # seconds
    TIMEOUT_SECONDS: int = 320  #
    TAKEOFF_ALTITUDE: float = 30.0


@dataclass(frozen=True)
class CoordinationConstants:
    """Drone-car coordination configuration."""

    MAX_FOLLOW_DISTANCE: int = 500  # meters
    FOLLOW_ALTITUDE: int = 30  # meters AGL
    PROXIMITY_THRESHOLD: int = 5  # meters
    PROXIMITY_CHECK_COOLDOWN: int = 2  # seconds
    LOOP_INTERVAL: int = 2  # seconds


@dataclass(frozen=True)
class DirectoryConstants:
    """File system paths and directories."""

    SURVEYED_AREA: str = "surveyed_area"
    ANALYTICS_DATA: str = "analytics_data"


@dataclass(frozen=True)
class SiteConstants:
    """Site-specific configuration."""

    DEFAULT_SITE_NAME: str = "ol-pejeta"


@dataclass(frozen=True)
class AnalyticsConstants:
    """Analytics and reporting configuration."""

    PERSISTENCE_INTERVAL: int = 300  # seconds
    DEFAULT_REPORT_HOURS: int = 24  # hours
    WEEKLY_REPORT_HOURS: int = 168  # hours


@dataclass(frozen=True)
class MAVLinkDefaults:
    """Default MAVLink command parameters."""

    NAV_WAYPOINT_COMMAND: int = 16  # MAV_CMD_NAV_WAYPOINT
    PARAM1: float = 0.0
    PARAM2: float = 0.0
    PARAM3: float = 0.0
    PARAM4: float = 0.0


@dataclass(frozen=True)
class AppConfig:
    """Main application configuration container."""

    physical: PhysicalConstants = PhysicalConstants()
    network: NetworkConstants = NetworkConstants()
    timeouts: TimeoutConstants = TimeoutConstants()
    vehicle: VehicleConstants = VehicleConstants()
    survey: SurveyConstants = SurveyConstants()
    coordination: CoordinationConstants = CoordinationConstants()
    directories: DirectoryConstants = DirectoryConstants()
    site: SiteConstants = SiteConstants()
    analytics: AnalyticsConstants = AnalyticsConstants()
    mavlink: MAVLinkDefaults = MAVLinkDefaults()


# Global configuration instance
CONFIG = AppConfig()
