import time
from typing import Dict, Any, Optional, List, Callable
import json

from backend.models.vehicle import Vehicle
from backend.core.flight_modes import FlightMode
from backend.config import get_vehicle_settings


class VehicleService:
    def __init__(self):
        self.vehicles: Dict[str, Vehicle] = {}
        self.telemetry_callbacks: Dict[str, List[Callable]] = {}
        self._initialize_vehicles()

    def _initialize_vehicles(self):
        """
        Initialises vehicles based on the configuration settings.

        This method reads vehicle settings, creates instances of the `Vehicle` class
        for each configured vehicle, and stores them in the `vehicles` dictionary.
        Additionally, initialises telemetry callback lists for each vehicle type.

        :param self: The current instance of the class. This is used to set the
            initialised `vehicles` and `telemetry_callbacks`.

        :return: None
        """
        vehicle_settings = get_vehicle_settings()

        for settings in vehicle_settings:
            vehicle_type = settings.get("type")
            if not vehicle_type:
                continue

            vehicle = Vehicle(
                vehicle_type=vehicle_type,
                ip=settings.get("connection", "127.0.0.1"),
                port=settings.get("port", "14551"),
                protocol=settings.get("protocol", "udp"),
            )

            self.vehicles[vehicle_type] = vehicle
            self.telemetry_callbacks[vehicle_type] = []

    def get_vehicle(self, vehicle_type: str) -> Optional[Vehicle]:
        """Get a vehicle by type."""
        return self.vehicles.get(vehicle_type)

    def connect_vehicle(self, vehicle_type: str) -> bool:
        """Connect to a vehicle."""
        vehicle = self.get_vehicle(vehicle_type)
        if not vehicle:
            print(f"Vehicle of type {vehicle_type} not found")
            return False

        try:
            vehicle.connect_vehicle()

            # Start telemetry streaming if we have callbacks
            if self.telemetry_callbacks.get(vehicle_type):
                vehicle.start_telemetry_stream(
                    lambda data: self._handle_telemetry(vehicle_type, data)
                )

            return True
        except Exception as e:
            print(f"Error connecting to vehicle {vehicle_type}: {e}")
            return False

    def disconnect_vehicle(self, vehicle_type: str) -> bool:
        """Disconnect from a vehicle."""
        vehicle = self.get_vehicle(vehicle_type)
        if not vehicle:
            return False

        try:
            vehicle.disconnect_vehicle()
            return True
        except Exception as e:
            print(f"Error disconnecting from vehicle {vehicle_type}: {e}")
            return False

    def register_telemetry_callback(self, vehicle_type: str, callback: Callable):
        """Register a callback for telemetry data."""
        if vehicle_type not in self.telemetry_callbacks:
            self.telemetry_callbacks[vehicle_type] = []

        self.telemetry_callbacks[vehicle_type].append(callback)

        # If vehicle is already connected, start telemetry
        vehicle = self.get_vehicle(vehicle_type)
        if vehicle and vehicle.vehicle:
            vehicle.start_telemetry_stream(
                lambda data: self._handle_telemetry(vehicle_type, data)
            )

    def _handle_telemetry(self, vehicle_type: str, telemetry_data: Dict[str, Any]):
        """Handle telemetry data and send to all callbacks."""
        for callback in self.telemetry_callbacks.get(vehicle_type, []):
            try:
                callback(telemetry_data)
            except Exception as e:
                print(f"Error in telemetry callback: {e}")

    def set_mode(self, vehicle_type: str, mode: str) -> bool:
        """Set the flight mode of a vehicle."""
        vehicle = self.get_vehicle(vehicle_type)
        if not vehicle:
            return False

        try:
            # Convert string mode to FlightMode enum
            flight_mode = getattr(FlightMode, mode.upper(), None)
            if not flight_mode:
                print(f"Invalid flight mode: {mode}")
                return False

            return vehicle.set_mode(flight_mode)
        except Exception as e:
            print(f"Error setting mode for vehicle {vehicle_type}: {e}")
            return False

    def get_telemetry(self, vehicle_type: str) -> Dict[str, Any]:
        """Get the latest telemetry data from a vehicle."""
        vehicle = self.get_vehicle(vehicle_type)
        if not vehicle or not vehicle.vehicle:
            return {}

        return vehicle.position()


# Create a singleton instance
vehicle_service = VehicleService()