from enum import Enum


class FlightMode(Enum):
    """Flight modes for drone control."""

    STABILIZE = 0
    ALT_HOLD = 2
    GUIDED = 4
    RTL = 6
    LAND = 9
    AUTO = 3
    FOLLOW = 23
    LOITER = 5
