import math
import threading
import time
from typing import Dict, Optional, Any

from pymavlink import mavutil, mavwp

from backend.core.flight_modes import FlightMode


class Vehicle:
    def __init__(
        self,
        vehicle_type: str,
        ip: str,
        port: str,
        protocol: str,
        baud_rate: int = None,
    ):
        """
        Initialize a Vehicle instance.

        Args:
            vehicle_type: Type of vehicle (e.g., "drone", "operator")
            ip: IP address or hostname
            port: Port number
            protocol: Protocol (e.g., "udp", "tcp")
        """
        self.vehicle_type = vehicle_type
        self.device = ip
        self.port = port
        self.baud_rate = baud_rate
        self.protocol = protocol
        self.connection_string = None
        self.vehicle = None
        self.mission_total_waypoints = 0
        self._heartbeat_thread = None
        self._telemetry_thread = None
        self._telemetry_callback = None
        self.build_connection_string()
        self._stop_threads = threading.Event()

    def build_connection_string(self):
        if self.protocol == "serial":
            self.connection_string = f"{self.port},{self.baud_rate}"
        else:
            self.connection_string = f"{self.protocol}:{self.device}:{self.port}"

    def __repr__(self):
        return (
            f"Vehicle({self.vehicle_type}, {self.device}, {self.port}, {self.protocol})"
        )

    def connect_vehicle(self):
        """Connect to the vehicle and start heartbeat thread."""
        print(
            f"Connecting to vehicle on: {self.vehicle_type} at {self.connection_string}"
        )
        self.vehicle = mavutil.mavlink_connection(
            self.connection_string, source_system=255
        )

        print("Waiting for heartbeat...")
        self.vehicle.wait_heartbeat(timeout=10)
        print(
            f"Connected to system {self.vehicle.target_system} component {self.vehicle.target_component}"
        )
        self.vehicle.mav.statustext_send(
            mavutil.mavlink.MAV_SEVERITY_NOTICE,
            "Connected to drone control system".encode(),
        )

        # Reset the stop flag if it was set
        self._stop_threads.clear()

        # Start heartbeat thread
        self._heartbeat_thread = threading.Thread(target=self._heartbeat_loop)
        self._heartbeat_thread.daemon = True
        self._heartbeat_thread.start()

        # Fetch the mission count to sync state
        self.fetch_mission_count()

        return self.vehicle

    def _heartbeat_loop(self):
        """Send heartbeat messages to the vehicle."""
        while not self._stop_threads.is_set():
            if self.vehicle and self.vehicle.mav:
                try:
                    self.vehicle.mav.heartbeat_send(
                        mavutil.mavlink.MAV_TYPE_GCS,
                        mavutil.mavlink.MAV_AUTOPILOT_INVALID,
                        0,
                        0,
                        0,
                    )
                except Exception as e:
                    print(f"Error sending heartbeat: {e}")
                    break
            else:
                print("Heartbeat loop: Vehicle connection lost or not initialized.")
                break
            time.sleep(1)

    def disconnect_vehicle(self):
        """Disconnect from the vehicle and stop all threads."""
        if self.vehicle:
            print(f"Disconnecting vehicle: {self.vehicle_type}")
            # Signal threads to stop
            self._stop_threads.set()

            # Wait for threads to finish
            if self._heartbeat_thread and self._heartbeat_thread.is_alive():
                self._heartbeat_thread.join(timeout=2.0)

            if self._telemetry_thread and self._telemetry_thread.is_alive():
                self._telemetry_thread.join(timeout=2.0)

            # Close the connection
            self.vehicle.close()
            self.vehicle = None
            print("Vehicle disconnected.")
        else:
            print("No vehicle connected to disconnect.")

    def fetch_mission_count(self):
        """Requests the mission waypoint count from the vehicle to sync state."""
        if not self.vehicle:
            return

        print("Requesting mission count from vehicle...")
        try:
            self.vehicle.mav.mission_request_list_send(
                self.vehicle.target_system, self.vehicle.target_component
            )

            msg = self.vehicle.recv_match(
                type="MISSION_COUNT", blocking=True, timeout=3
            )
            if msg:
                self.mission_total_waypoints = msg.count
                print(
                    f"Vehicle has {self.mission_total_waypoints} waypoints in its mission."
                )
            else:
                print("Did not receive mission count from vehicle (timeout).")
        except Exception as e:
            print(f"Error fetching mission count: {e}")

    def set_mode(self, mode_id: FlightMode) -> bool:
        """Set the flight mode of the vehicle."""
        if not self.vehicle:
            print("Vehicle not connected. Cannot set mode.")
            return False
        if not isinstance(mode_id, FlightMode):
            print(f"Invalid mode_id type: {type(mode_id)}. Expected FlightMode enum.")
            return False

        print(f"Setting mode to {mode_id.name} (mode_id: {mode_id.value})")

        self.vehicle.mav.command_long_send(
            self.vehicle.target_system,
            self.vehicle.target_component,
            mavutil.mavlink.MAV_CMD_DO_SET_MODE,
            0,
            mavutil.mavlink.MAV_MODE_FLAG_CUSTOM_MODE_ENABLED,
            mode_id.value,
            0,
            0,
            0,
            0,
            0,
        )

        # Wait for confirmation
        start_time = time.time()
        timeout_duration = 10
        while time.time() - start_time < timeout_duration:
            msg = self.vehicle.recv_match(type="HEARTBEAT", blocking=True, timeout=1)
            if msg:
                if msg.custom_mode == mode_id.value and (
                    msg.base_mode & mavutil.mavlink.MAV_MODE_FLAG_CUSTOM_MODE_ENABLED
                ):
                    print(
                        f"Mode changed to {mode_id.name} successfully (confirmed by HEARTBEAT)."
                    )
                    return True

        print(
            f"Failed to confirm mode change to {mode_id.name} within {timeout_duration} seconds."
        )
        return False

    def position(self) -> Dict[str, Any]:
        """
        Get the current position and telemetry data from the vehicle.

        Returns:
            Dictionary with telemetry data including position, velocity,
            mission progress, and more.
        """
        telemetry = {
            "latitude": None,
            "longitude": None,
            "altitude_msl": None,
            "relative_altitude": None,
            "vx": None,
            "vy": None,
            "vz": None,
            "heading": None,
            "ground_speed": None,
            "battery_voltage": None,
            "battery_remaining_percentage": None,
            "current_mission_wp_seq": None,
            "distance_to_mission_wp": None,
            "next_mission_wp_seq": None,
            "mission_progress_percentage": None,
        }

        if not self.vehicle:
            print("Vehicle not connected. Cannot get position data.")
            return telemetry

        # Request data streams
        stream_rate_hz = 10  # Higher rate for better responsiveness
        self.vehicle.mav.request_data_stream_send(
            self.vehicle.target_system,
            self.vehicle.target_component,
            mavutil.mavlink.MAV_DATA_STREAM_POSITION,
            stream_rate_hz,
            1,
        )
        self.vehicle.mav.request_data_stream_send(
            self.vehicle.target_system,
            self.vehicle.target_component,
            mavutil.mavlink.MAV_DATA_STREAM_EXTENDED_STATUS,
            stream_rate_hz,
            1,
        )

        try:
            # Wait for messages
            start_fetch_time = time.time()
            fetch_timeout = 0.5  # shorter timeout for responsiveness

            while time.time() - start_fetch_time < fetch_timeout:
                msg = self.vehicle.recv_match(
                    type=[
                        "GLOBAL_POSITION_INT",
                        "SYS_STATUS",
                        "MISSION_CURRENT",
                        "NAV_CONTROLLER_OUTPUT",
                        "VFR_HUD",
                    ],
                    blocking=False,
                    timeout=0.05,
                )

                if not msg:
                    time.sleep(0.01)
                    continue

                msg_type = msg.get_type()

                if msg_type == "GLOBAL_POSITION_INT":
                    telemetry["latitude"] = msg.lat / 1e7
                    telemetry["longitude"] = msg.lon / 1e7
                    telemetry["altitude_msl"] = msg.alt / 1000.0
                    telemetry["relative_altitude"] = msg.relative_alt / 1000.0
                    telemetry["vx"] = msg.vx / 100.0  # cm/s to m/s
                    telemetry["vy"] = msg.vy / 100.0  # cm/s to m/s
                    telemetry["vz"] = msg.vz / 100.0  # cm/s to m/s
                    telemetry["heading"] = msg.hdg / 100.0 if msg.hdg != 65535 else None

                elif msg_type == "SYS_STATUS":
                    telemetry["battery_voltage"] = (
                        msg.voltage_battery / 1000.0
                    )  # mV to V
                    telemetry["battery_remaining_percentage"] = (
                        msg.battery_remaining
                    )  # Percentage

                elif msg_type == "MISSION_CURRENT":
                    telemetry["current_mission_wp_seq"] = msg.seq
                    # Self-healing: If the current waypoint from the vehicle is out of bounds
                    # with our known total, it means the mission has changed externally.
                    # We need to re-fetch the mission count to re-sync.
                    if (
                        self.mission_total_waypoints > 0
                        and msg.seq >= self.mission_total_waypoints
                    ):
                        print(
                            f"Mission inconsistency detected (seq {msg.seq} >= total {self.mission_total_waypoints}). Re-syncing."
                        )
                        self.fetch_mission_count()

                    if self.mission_total_waypoints > 0:
                        current_seq = msg.seq
                        if current_seq < (self.mission_total_waypoints - 1):
                            telemetry["next_mission_wp_seq"] = current_seq + 1

                elif msg_type == "NAV_CONTROLLER_OUTPUT":
                    telemetry["distance_to_mission_wp"] = msg.wp_dist  # In meters

                elif msg_type == "VFR_HUD":
                    telemetry["ground_speed"] = msg.groundspeed  # m/s
                    if telemetry["relative_altitude"] is None:
                        telemetry["relative_altitude"] = msg.alt

            # Calculate mission progress percentage
            if (
                self.mission_total_waypoints > 1
                and telemetry["current_mission_wp_seq"] is not None
            ):
                current_seq = telemetry["current_mission_wp_seq"]
                total_wps = self.mission_total_waypoints

                # If we've reached the last waypoint, progress is 100%
                if current_seq >= total_wps - 1:
                    telemetry["mission_progress_percentage"] = 100
                else:
                    # Calculate progress as percentage of completed waypoints
                    progress = (float(current_seq) / (total_wps - 1)) * 100.0
                    telemetry["mission_progress_percentage"] = round(
                        max(0.0, min(progress, 100.0))
                    )
            elif self.mission_total_waypoints <= 1:
                telemetry["mission_progress_percentage"] = 0

        except Exception as e:
            print(f"Error getting position data: {e}")
            import traceback

            traceback.print_exc()

        return telemetry

    def start_telemetry_stream(self, callback):
        """
        Start a telemetry streaming thread that calls the callback with telemetry data.

        Args:
            callback: Function to call with telemetry data
        """
        if self._telemetry_thread and self._telemetry_thread.is_alive():
            print("Telemetry thread already running")
            return

        self._telemetry_callback = callback
        self._telemetry_thread = threading.Thread(target=self._telemetry_loop)
        self._telemetry_thread.daemon = True
        self._telemetry_thread.start()
        print("Telemetry streaming started")

    def _telemetry_loop(self):
        """Background thread to continuously send telemetry data."""
        while not self._stop_threads.is_set():
            if self.vehicle and self._telemetry_callback:
                try:
                    telemetry = self.position()
                    self._telemetry_callback(telemetry)
                except Exception as e:
                    print(f"Error in telemetry loop: {e}")
            time.sleep(0.1)  # 10Hz update rate
