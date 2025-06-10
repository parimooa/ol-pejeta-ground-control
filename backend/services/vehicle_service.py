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

    def upload_mission(
        self, vehicle_type: str, waypoints_file: str = "wp.waypoints"
    ) -> int:
        """Upload mission waypoints to the vehicle.

        Args:
            vehicle_type: The type of vehicle to upload the mission to
            waypoints_file: Path to the waypoints file (default: "wp.waypoints")

        Returns:
            Number of waypoints uploaded or False if it failed
        """
        vehicle = self.get_vehicle(vehicle_type)
        if not vehicle or not vehicle.vehicle:
            print(f"Vehicle {vehicle_type} not connected. Cannot upload mission.")
            return False

        try:
            from pymavlink import mavwp, mavutil

            wploader = mavwp.MAVWPLoader()
            try:
                mission_total_waypoints = wploader.load(waypoints_file)
                print(
                    f"Loaded {mission_total_waypoints} waypoints from '{waypoints_file}'"
                )
            except FileNotFoundError:
                print(f"Error: Waypoint file '{waypoints_file}' not found.")
                return False

            if mission_total_waypoints == 0:
                print(f"No waypoints found in '{waypoints_file}'")
                return False

            print("Clearing existing mission...")
            vehicle.vehicle.mav.mission_clear_all_send(
                vehicle.vehicle.target_system, vehicle.vehicle.target_component
            )
            ack_msg = vehicle.vehicle.recv_match(
                type="MISSION_ACK", blocking=True, timeout=5
            )

            if ack_msg is None:
                print("Mission clear timed out. No MISSION_ACK received.")
                return False
            if ack_msg.type != mavutil.mavlink.MAV_MISSION_ACCEPTED:
                print(f"Mission clear failed with error: {ack_msg.type}")
                return False
            print("Existing mission cleared.")

            print(f"Sending waypoint count: {mission_total_waypoints}")
            vehicle.vehicle.waypoint_count_send(mission_total_waypoints)

            for i in range(mission_total_waypoints):
                msg = vehicle.vehicle.recv_match(
                    type=["MISSION_REQUEST", "MISSION_REQUEST_INT"],
                    blocking=True,
                    timeout=10,
                )
                if not msg:
                    print(
                        f"No mission request received for waypoint {i}. Upload failed."
                    )
                    return False

                print(f"Received mission request for sequence {msg.seq}")
                if msg.seq != i:
                    print(
                        f"Expected waypoint {i} but received request for {msg.seq}. Upload failed."
                    )
                    return False

                wp = wploader.wp(i)
                if hasattr(vehicle.vehicle.mav, "mission_item_int_send"):
                    vehicle.vehicle.mav.mission_item_int_send(
                        vehicle.vehicle.target_system,
                        vehicle.vehicle.target_component,
                        wp.seq,
                        wp.frame,
                        wp.command,
                        wp.current,
                        wp.autocontinue,
                        wp.param1,
                        wp.param2,
                        wp.param3,
                        wp.param4,
                        int(wp.x * 1e7),
                        int(wp.y * 1e7),
                        wp.z,
                    )
                else:
                    vehicle.vehicle.mav.mission_item_send(
                        vehicle.vehicle.target_system,
                        vehicle.vehicle.target_component,
                        wp.seq,
                        wp.frame,
                        wp.command,
                        wp.current,
                        wp.autocontinue,
                        wp.param1,
                        wp.param2,
                        wp.param3,
                        wp.param4,
                        wp.x,
                        wp.y,
                        wp.z,
                    )
                print(f"Sent waypoint {i}: CMD {wp.command} ({wp.x}, {wp.y}, {wp.z})")

            ack_msg = vehicle.vehicle.recv_match(
                type="MISSION_ACK", blocking=True, timeout=15
            )
            if not ack_msg or ack_msg.type != mavutil.mavlink.MAV_MISSION_ACCEPTED:
                print(
                    f"Mission upload failed with error: {ack_msg.type if ack_msg else 'Timeout'}"
                )
                return False

            print("Mission upload successful.")
            return mission_total_waypoints

        except Exception as e:
            print(f"An error occurred during mission upload: {e}")
            import traceback

            traceback.print_exc()
            return False


# Create a singleton instance
vehicle_service = VehicleService()
