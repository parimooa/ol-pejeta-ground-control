from enum import Enum


class FlightMode(Enum):
    """Flight modes for drone control."""
    STABILIZE = 0
    GUIDED = 4
    RTL = 6
    LAND = 9
    AUTO = 3