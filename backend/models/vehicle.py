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
        vehicle_id: int,
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
        self.vehicle_id = vehicle_id
        self.device = ip
        self.port = port
        self.baud_rate = baud_rate
        self.protocol = protocol
        self.connection_string = None
        self.vehicle = None
        self.mission_total_waypoints = 0

        # State management for telemetry
        self._lock = threading.Lock()
        self.last_telemetry: Dict[str, Any] = self._get_initial_telemetry_dict()

        self._heartbeat_thread = None
        self._telemetry_thread = None
        self._message_listener_thread = None  # Central message handler
        self._telemetry_callback = None
        self.build_connection_string()
        self._stop_threads = threading.Event()

    def _get_initial_telemetry_dict(self) -> Dict[str, Any]:
        """Returns a clean dictionary for telemetry state."""
        return {
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
            "heartbeat_timestamp": None,
            "flight_mode": None,
            "system_status": None,
            "armed": None,
            "guided_enabled": None,
            "custom_mode": None,
            "mavlink_version": None,
            "vehicle_id": self.vehicle_id,
        }

    def build_connection_string(self):
        if self.protocol == "serial":
            self.connection_string = f"{self.port},{self.baud_rate}"
        else:
            self.connection_string = f"{self.protocol}:{self.device}:{self.port}"

    def go_to_location(self, lat: float, lon: float, alt: float) -> bool:
        """Commands the vehicle to fly to a specific GPS location in GUIDED mode."""
        if not self.vehicle:
            print("Vehicle not connected. Cannot go to location.")
            return False

        print(f"Commanding vehicle to go to Lat: {lat}, Lon: {lon}, Alt: {alt}m")
        # In GUIDED mode, we use SET_POSITION_TARGET_GLOBAL_INT
        self.vehicle.mav.set_position_target_global_int_send(
            0,  # time_boot_ms (not used)
            self.vehicle.target_system,
            self.vehicle.target_component,
            mavutil.mavlink.MAV_FRAME_GLOBAL_RELATIVE_ALT_INT,
            0b0000111111111000,  # type_mask: use position only
            int(lat * 1e7),  # lat_int
            int(lon * 1e7),  # lon_int
            alt,  # alt
            0,
            0,
            0,  # vx, vy, vz (not used)
            0,
            0,
            0,  # afx, afy, afz (not used)
            0,
            0,  # yaw, yaw_rate (not used)
        )
        return True

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

        # Start the new central message listener
        self._message_listener_thread = threading.Thread(
            target=self._message_listener_loop
        )
        self._message_listener_thread.daemon = True
        self._message_listener_thread.start()

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

    def _message_listener_loop(self):
        """Dedicated thread to listen for heartbeats and update state."""
        # Request data streams once at the beginning
        stream_rate_hz = 4  # A reasonable rate
        self.vehicle.mav.request_data_stream_send(
            self.vehicle.target_system,
            self.vehicle.target_component,
            mavutil.mavlink.MAV_DATA_STREAM_ALL,  # Request all streams
            stream_rate_hz,
            1,  # Start stream
        )

        while not self._stop_threads.is_set():
            if not self.vehicle:
                time.sleep(1)
                continue
            try:
                # Block until a message is received
                msg = self.vehicle.recv_match(blocking=True, timeout=1)
                if not msg:
                    continue

                msg_type = msg.get_type()
                with self._lock:
                    self._update_telemetry_state(msg, msg_type)

            except Exception as e:
                print(f"Error in message listener loop: {e}")
                break

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

            # Join the new thread
            if (
                self._message_listener_thread
                and self._message_listener_thread.is_alive()
            ):
                self._message_listener_thread.join(timeout=2.0)

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
            with self._lock:
                current_mode = self.last_telemetry.get("custom_mode")
                base_mode = self.last_telemetry.get("flight_mode")

            if current_mode is not None and base_mode is not None:
                if current_mode == mode_id.value and (
                    base_mode & mavutil.mavlink.MAV_MODE_FLAG_CUSTOM_MODE_ENABLED
                ):
                    print(
                        f"Mode changed to {mode_id.name} successfully (confirmed by HEARTBEAT)."
                    )
                    return True
            time.sleep(0.2)  # Check state periodically

        print(
            f"Failed to confirm mode change to {mode_id.name} within {timeout_duration} seconds."
        )
        with self._lock:
            last_mode = self.last_telemetry.get("custom_mode")
            last_sys_status = self.last_telemetry.get("system_status")
            last_armed_status = self.last_telemetry.get("armed")
            print(
                f"DIAGNOSTICS: Last known state: custom_mode={last_mode} (expected {mode_id.value}), "
                f"system_status={last_sys_status}, armed={last_armed_status}"
            )
            if last_sys_status != mavutil.mavlink.MAV_STATE_ACTIVE:
                print(
                    "DIAGNOSTICS: Vehicle is not in ACTIVE state, which may prevent mode changes."
                )
            if not last_armed_status and mode_id == FlightMode.FOLLOW:
                print(
                    "DIAGNOSTICS: Vehicle is not ARMED, which is required for FOLLOW mode."
                )
        return False

    def follow_target(self, lat: float, lon: float, alt: float):
        """
        Sends a FOLLOW_TARGET MAVLink message to the vehicle.
        The vehicle must be in a mode that supports following (e.g., Follow mode).
        """
        if not self.vehicle:
            print("Vehicle not connected. Cannot send follow target.")
            return

        # The timestamp should be the time of the estimate in microseconds.
        ts = int(time.time() * 1e6)

        # We are only providing position data. The rest can be 0.
        self.vehicle.mav.follow_target_send(
            ts,  # timestamp (microseconds)
            0,  # est_capabilities (we provide position only)
            int(lat * 1e7),  # lat (degrees * 1e7)
            int(lon * 1e7),  # lon (degrees * 1e7)
            alt,  # alt (meters)
            [0.0, 0.0, 0.0],  # vel
            [0.0, 0.0, 0.0],  # acc
            [0.0, 0.0, 0.0, 0.0],  # attitude_q
            [0.0, 0.0, 0.0],  # rates
            [0.0, 0.0, 0.0],  # position_cov
            0,  # custom_state
        )

    def arm(self) -> bool:
        """Arms the vehicle."""
        if not self.vehicle:
            print("Vehicle not connected. Cannot arm.")
            return False

        with self._lock:
            if self.last_telemetry.get("armed"):
                print("Vehicle is already armed.")
                return True

        print("Sending ARM command...")
        self.vehicle.mav.command_long_send(
            self.vehicle.target_system,
            self.vehicle.target_component,
            mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM,
            0,  # confirmation
            1,  # param1: 1 to arm, 0 to disarm
            0,
            0,
            0,
            0,
            0,
            0,  # params 2-7
        )

        # Wait for arming confirmation
        start_time = time.time()
        while time.time() - start_time < 10:  # 10-second timeout
            with self._lock:
                if self.last_telemetry.get("armed"):
                    print("Vehicle is ARMED.")
                    return True
            time.sleep(0.2)

        print("Failed to confirm vehicle arming within timeout.")
        return False

    def disarm(self) -> bool:
        """Disarms the vehicle."""
        if not self.vehicle:
            print("Vehicle not connected. Cannot disarm.")
            return False

        with self._lock:
            if not self.last_telemetry.get("armed"):
                print("Vehicle is already disarmed.")
                return True

        print("Sending DISARM command...")
        self.vehicle.mav.command_long_send(
            self.vehicle.target_system,
            self.vehicle.target_component,
            mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM,
            0,  # confirmation
            0,  # param1: 1 to arm, 0 to disarm
            0,
            0,
            0,
            0,
            0,
            0,  # params 2-7
        )

        # Wait for disarming confirmation
        start_time = time.time()
        while time.time() - start_time < 5:  # 5-second timeout
            with self._lock:
                if not self.last_telemetry.get("armed"):
                    print("Vehicle is DISARMED.")
                    return True
            time.sleep(0.2)

        print("Failed to confirm vehicle disarming within timeout.")
        return False

    def takeoff(self, altitude_meters: float) -> bool:
        """Commands the vehicle to takeoff to a specific altitude."""
        if not self.vehicle:
            print("Vehicle not connected. Cannot takeoff.")
            return False

        print(f"Commanding takeoff to {altitude_meters} meters...")
        self.vehicle.mav.command_long_send(
            self.vehicle.target_system,
            self.vehicle.target_component,
            mavutil.mavlink.MAV_CMD_NAV_TAKEOFF,
            0,  # Confirmation
            0,
            0,
            0,  # pitch, empty, empty
            math.nan,  # Yaw angle (NaN for unchanged)
            0,
            0,  # Lat, Lon (0 for current)
            altitude_meters,  # Param7: Altitude
        )

        # Wait for vehicle to reach altitude
        start_time = time.time()
        timeout_duration = 30  # Generous timeout for takeoff
        while time.time() - start_time < timeout_duration:
            with self._lock:
                current_alt = self.last_telemetry.get("relative_altitude")

            if current_alt is not None:
                print(f"Current relative altitude: {current_alt:.2f}m")
                if current_alt >= altitude_meters * 0.95:  # Reached ~95% of target alt
                    print("Reached target takeoff altitude.")
                    return True
            else:
                print("Waiting for altitude data...")
            time.sleep(1)

        print(f"Failed to reach takeoff altitude within {timeout_duration}s.")
        return False

    def _update_telemetry_state(self, msg, msg_type):
        """Updates the last_telemetry dictionary based on an incoming MAVLink message."""
        if msg_type == "GLOBAL_POSITION_INT":
            self.last_telemetry["latitude"] = msg.lat / 1e7
            self.last_telemetry["longitude"] = msg.lon / 1e7
            self.last_telemetry["altitude_msl"] = msg.alt / 1000.0
            self.last_telemetry["relative_altitude"] = msg.relative_alt / 1000.0
            self.last_telemetry["vx"] = msg.vx / 100.0
            self.last_telemetry["vy"] = msg.vy / 100.0
            self.last_telemetry["vz"] = msg.vz / 100.0
            self.last_telemetry["heading"] = (
                msg.hdg / 100.0 if msg.hdg != 65535 else None
            )
        elif msg_type == "SYS_STATUS":
            self.last_telemetry["battery_voltage"] = msg.voltage_battery / 1000.0
            self.last_telemetry["battery_remaining_percentage"] = msg.battery_remaining
        elif msg_type == "MISSION_CURRENT":
            self.last_telemetry["current_mission_wp_seq"] = msg.seq
            if (
                self.mission_total_waypoints > 0
                and msg.seq >= self.mission_total_waypoints
            ):
                self.fetch_mission_count()
            if self.mission_total_waypoints > 0 and msg.seq < (
                self.mission_total_waypoints - 1
            ):
                self.last_telemetry["next_mission_wp_seq"] = msg.seq + 1
        elif msg_type == "NAV_CONTROLLER_OUTPUT":
            self.last_telemetry["distance_to_mission_wp"] = msg.wp_dist
        elif msg_type == "VFR_HUD":
            self.last_telemetry["ground_speed"] = msg.groundspeed
            if self.last_telemetry["relative_altitude"] is None:
                self.last_telemetry["relative_altitude"] = msg.alt
        elif msg_type == "HEARTBEAT":
            self.last_telemetry["heartbeat_timestamp"] = time.time()
            self.last_telemetry["flight_mode"] = msg.base_mode
            self.last_telemetry["system_status"] = msg.system_status
            self.last_telemetry["custom_mode"] = msg.custom_mode
            self.last_telemetry["mavlink_version"] = msg.mavlink_version
            self.last_telemetry["armed"] = bool(
                msg.base_mode & mavutil.mavlink.MAV_MODE_FLAG_SAFETY_ARMED
            )
            self.last_telemetry["guided_enabled"] = bool(
                msg.base_mode & mavutil.mavlink.MAV_MODE_FLAG_GUIDED_ENABLED
            )

        # Recalculate mission progress after any update
        if (
            self.mission_total_waypoints > 1
            and self.last_telemetry.get("current_mission_wp_seq") is not None
        ):
            current_seq = self.last_telemetry["current_mission_wp_seq"]
            total_wps = self.mission_total_waypoints
            if current_seq >= total_wps - 1:
                self.last_telemetry["mission_progress_percentage"] = 100
            else:
                progress = (float(current_seq) / (total_wps - 1)) * 100.0
                self.last_telemetry["mission_progress_percentage"] = round(
                    max(0.0, min(progress, 100.0))
                )
        elif self.mission_total_waypoints <= 1:
            self.last_telemetry["mission_progress_percentage"] = 0

    def get_current_telemetry(self) -> Dict[str, Any]:
        """Returns a thread-safe copy of the latest telemetry data."""
        with self._lock:
            return self.last_telemetry.copy()

    def position(self) -> Dict[str, Any]:
        """
        Get the current telemetry data from the vehicle's state.
        This is a legacy wrapper for get_current_telemetry to maintain compatibility.

        Returns:
            Dictionary with telemetry data including position, velocity,
            mission progress, heartbeat info, and more.
        """
        return self.get_current_telemetry()

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
            if not (self.vehicle and self._telemetry_callback):
                time.sleep(0.5)
                continue
            try:
                telemetry = self.get_current_telemetry()
                self._telemetry_callback(telemetry)
            except Exception as e:
                print(f"Error in telemetry loop: {e}")
            time.sleep(0.1)  # 10Hz update rate, adjust as needed
