import time
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field


class Position(BaseModel):
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    altitude_msl: Optional[float] = None
    relative_altitude: Optional[float] = None


class Velocity(BaseModel):
    vx: Optional[float] = None
    vy: Optional[float] = None
    vz: Optional[float] = None
    ground_speed: Optional[float] = None
    heading: Optional[float] = None


class Battery(BaseModel):
    voltage: Optional[float] = None
    remaining_percentage: Optional[float] = None


class MissionStatus(BaseModel):
    current_wp_seq: Optional[int] = None
    next_wp_seq: Optional[int] = None
    distance_to_wp: Optional[float] = None
    progress_percentage: Optional[float] = None


class Heartbeat(BaseModel):
    timestamp: Optional[float] = None
    flight_mode: Optional[int] = None
    system_status: Optional[int] = None
    armed: Optional[bool] = None
    guided_enabled: Optional[bool] = None
    custom_mode: Optional[int] = None
    mavlink_version: Optional[int] = None


class TelemetryData(BaseModel):
    position: Position = Field(default_factory=Position)
    velocity: Velocity = Field(default_factory=Velocity)
    battery: Battery = Field(default_factory=Battery)
    mission: MissionStatus = Field(default_factory=MissionStatus)
    heartbeat: Heartbeat = Field(default_factory=Heartbeat)
    timestamp: float = Field(default_factory=lambda: time.time())

    @classmethod
    def from_vehicle_data(cls, data: Dict[str, Any]) -> "TelemetryData":
        """Convert raw vehicle telemetry data to structured TelemetryData."""
        return cls(
            position=Position(
                latitude=data.get("latitude"),
                longitude=data.get("longitude"),
                altitude_msl=data.get("altitude_msl"),
                relative_altitude=data.get("relative_altitude"),
            ),
            velocity=Velocity(
                vx=data.get("vx"),
                vy=data.get("vy"),
                vz=data.get("vz"),
                ground_speed=data.get("ground_speed"),
                heading=data.get("heading"),
            ),
            battery=Battery(
                voltage=data.get("battery_voltage"),
                remaining_percentage=data.get("battery_remaining_percentage"),
            ),
            mission=MissionStatus(
                current_wp_seq=data.get("current_mission_wp_seq"),
                next_wp_seq=data.get("next_mission_wp_seq"),
                distance_to_wp=data.get("distance_to_mission_wp"),
                progress_percentage=data.get("mission_progress_percentage"),
            ),
            heartbeat=Heartbeat(
                timestamp=data.get("heartbeat_timestamp"),
                flight_mode=data.get("flight_mode"),
                system_status=data.get("system_status"),
                armed=data.get("armed"),
                guided_enabled=data.get("guided_enabled"),
                custom_mode=data.get("custom_mode"),
                mavlink_version=data.get("mavlink_version"),
            ),
        )
