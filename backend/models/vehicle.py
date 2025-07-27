import math
import threading
import time
from typing import Dict, Optional, Any

from pymavlink import mavutil, mavwp

from backend.core.flight_modes import FlightMode
from backend.services.waypoint_file_service import waypoint_file_service


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
        self.visited_waypoints = set()
        self.mission_waypoints = {}
        self.current_waypoint_seq = None
        self.next_waypoint_seq = None
        self.last_waypoint_reach_time = None
        self.waypoint_visit_threshold = 3.0  # meters
        self.waypoint_confirmation_delay = 2.0  # seconds
        self._survey_mission_complete = False
        self.last_waypoint_seq = -1
        self.current_site_name = None  # Site name for waypoint persistence

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
        # The nested function definition has been removed.
        # This method now correctly returns the dictionary.
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
            "mission_total_waypoints": 0,
            "mission_waypoints": {},
            "visited_waypoints": [],
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
        heartbeat_msg = self.vehicle.wait_heartbeat(timeout=10)
        if heartbeat_msg:
            print(
                f"Connected to system {self.vehicle.target_system} component {self.vehicle.target_component}"
            )
        else:
            print(
                f"{self.vehicle_type}: ERROR - No heartbeat received within 10 seconds!"
            )
            raise Exception(
                f"No heartbeat received from {self.vehicle_type} at {self.connection_string}"
            )
        self.vehicle.mav.statustext_send(
            mavutil.mavlink.MAV_SEVERITY_NOTICE,
            "Connected to drone control system".encode(),
        )

        # Reset the stop flag if it was set
        self._stop_threads.clear()

        # Fetch mission waypoints synchronously BEFORE starting the listener thread.
        self.fetch_mission_waypoints()

        # --- Start of Change ---
        # Set the initial current and next waypoints now that the mission is loaded.
        self._update_current_next_waypoints()
        # --- End of Change ---

        # Start heartbeat thread
        self._heartbeat_thread = threading.Thread(target=self._heartbeat_loop)
        self._heartbeat_thread.daemon = True
        self._heartbeat_thread.start()

        # Now, start the central message listener for continuous telemetry
        self._message_listener_thread = threading.Thread(
            target=self._message_listener_loop
        )
        self._message_listener_thread.daemon = True
        self._message_listener_thread.start()

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

        # Request extended status to get mission current info
        self.vehicle.mav.request_data_stream_send(
            self.vehicle.target_system,
            self.vehicle.target_component,
            mavutil.mavlink.MAV_DATA_STREAM_EXTENDED_STATUS,
            2,  # 2 Hz rate for mission status
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

    def set_site_name(self, site_name: str):
        """Set the current site name for waypoint persistence."""
        self.current_site_name = site_name
        print(f"Site name set to: {site_name}")

        # Load previously visited waypoints for this site if they exist
        if site_name:
            self.load_previous_visited_waypoints()

    def load_previous_visited_waypoints(self):
        """Load previously visited waypoints from disk for the current site."""
        if not self.current_site_name:
            return

        try:
            previous_waypoints = waypoint_file_service.load_visited_waypoints(
                self.current_site_name, str(self.vehicle_id)
            )

            if previous_waypoints:
                self.visited_waypoints.update(previous_waypoints)
                print(f"Loaded {len(previous_waypoints)} previously visited waypoints")
                self._update_current_next_waypoints()
            else:
                print("No previous waypoint data found for this site")

        except Exception as e:
            print(f"Error loading previous waypoint data: {e}")

    def fetch_mission_waypoints(self):
        """Fetch all mission waypoints for visit detection."""
        if not self.vehicle:
            return

        try:
            self.vehicle.mav.mission_request_list_send(
                self.vehicle.target_system, self.vehicle.target_component
            )

            msg = self.vehicle.recv_match(
                type="MISSION_COUNT", blocking=True, timeout=3
            )
            if not msg:
                return

            waypoint_count = msg.count
            self.mission_total_waypoints = waypoint_count
            self.mission_waypoints = {}

            for i in range(waypoint_count):
                self.vehicle.mav.mission_request_int_send(
                    self.vehicle.target_system, self.vehicle.target_component, i
                )

                wp_msg = self.vehicle.recv_match(
                    type="MISSION_ITEM_INT", blocking=True, timeout=3
                )
                if wp_msg:
                    self.mission_waypoints[i] = {
                        "lat": wp_msg.x / 1e7,
                        "lon": wp_msg.y / 1e7,
                        "alt": wp_msg.z,
                        "seq": wp_msg.seq,
                    }

            print(
                f"Loaded {len(self.mission_waypoints)} waypoints for visit detection."
            )

            # Load previously visited waypoints after fetching mission
            if self.current_site_name:
                self.load_previous_visited_waypoints()

        except Exception as e:
            print(f"Error fetching mission waypoints: {e}")

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
        timeout_duration = 15
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
        The vehicle must be in a guided mode for this to work.
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
        """Arms the vehicle. Ensures vehicle is in GUIDED mode before arming."""
        if not self.vehicle:
            print("Vehicle not connected. Cannot arm.")
            return False

        with self._lock:
            if self.last_telemetry.get("armed"):
                print("Vehicle is already armed.")
                return True

            # Check if vehicle is in GUIDED mode
            current_mode = self.last_telemetry.get("custom_mode")

        # If not in GUIDED mode, switch to GUIDED mode first
        if current_mode != FlightMode.GUIDED.value:
            print(
                "Vehicle is not in GUIDED mode. Setting to GUIDED mode before arming..."
            )
            if not self.set_mode(FlightMode.GUIDED):
                print("Failed to set GUIDED mode. Cannot proceed with arming.")
                return False
            print("Successfully set to GUIDED mode.")

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
        """Commands the vehicle to take off to a specific altitude."""
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

    def clear_mission(self) -> bool:
        """Clear the current mission from the drone."""
        if not self.vehicle:
            print("Vehicle not connected. Cannot clear mission.")
            return False

        print("Clearing existing mission...")
        try:
            # Send mission clear command
            self.vehicle.mav.mission_clear_all_send(
                self.vehicle.target_system, self.vehicle.target_component
            )

            # Wait for acknowledgment
            start_time = time.time()
            while time.time() - start_time < 5:
                msg = self.vehicle.recv_match(
                    type="MISSION_ACK", blocking=False, timeout=1
                )
                if msg and msg.type == mavutil.mavlink.MAV_MISSION_ACCEPTED:
                    print("Mission cleared successfully")
                    return True
                elif msg and msg.type != mavutil.mavlink.MAV_MISSION_ACCEPTED:
                    print(f"Mission clear failed with error: {msg.type}")
                    return False

            print("Mission clear acknowledgment timeout")
            return False

        except Exception as e:
            print(f"Error clearing mission: {e}")
            return False

    def _get_command_name(self, command_id: int) -> str:
        """Get human-readable name for MAVLink command."""
        command_names = {
            mavutil.mavlink.MAV_CMD_NAV_WAYPOINT: "WAYPOINT",
            mavutil.mavlink.MAV_CMD_NAV_LOITER_UNLIM: "LOITER_UNLIM",
            mavutil.mavlink.MAV_CMD_NAV_LOITER_TIME: "LOITER_TIME",
            mavutil.mavlink.MAV_CMD_NAV_LOITER_TURNS: "LOITER_TURNS",
            mavutil.mavlink.MAV_CMD_NAV_RETURN_TO_LAUNCH: "RTL",
            mavutil.mavlink.MAV_CMD_NAV_LAND: "LAND",
            mavutil.mavlink.MAV_CMD_NAV_TAKEOFF: "TAKEOFF",
        }
        return command_names.get(command_id, f"CMD_{command_id}")

    def upload_mission(self, waypoints) -> bool:
        """Upload a mission to the drone."""
        if not self.vehicle:
            print("Vehicle not connected. Cannot upload mission.")
            return False

        if not waypoints:
            print("No waypoints provided for mission upload.")
            return False

        # Log mission details including command types for better debugging
        command_counts = {}
        for wp in waypoints:
            cmd_name = self._get_command_name(wp.command)
            command_counts[cmd_name] = command_counts.get(cmd_name, 0) + 1

        command_summary = ", ".join(
            [f"{count} {cmd}" for cmd, count in command_counts.items()]
        )
        print(f"Uploading mission with {len(waypoints)} waypoints: {command_summary}")

        try:
            # First, clear any existing mission from the vehicle
            if not self.clear_mission():
                print("❌ Failed to clear existing mission before upload.")
                return False

            # --- START OF FIX ---
            # Reset the survey completion flag for the new mission.
            # This ensures we don't carry over a "complete" state from a previous run.
            with self._lock:
                self._survey_mission_complete = False
                self.last_waypoint_seq = -1

            # Find the sequence number of the last actual survey waypoint.
            # We iterate in reverse to find the first waypoint that is NOT a final command.
            # This will be our trigger for marking the survey as complete.
            for wp in reversed(waypoints):
                if wp.command not in [
                    mavutil.mavlink.MAV_CMD_NAV_RETURN_TO_LAUNCH,
                    mavutil.mavlink.MAV_CMD_NAV_LAND,
                ]:
                    self.last_waypoint_seq = wp.seq
                    break

            print(
                f"ℹ️ Mission completion will be triggered after reaching waypoint sequence: {self.last_waypoint_seq}"
            )
            # --- END OF FIX ---

            # Send the total number of waypoints to the vehicle
            self.vehicle.mav.mission_count_send(
                self.vehicle.target_system,
                self.vehicle.target_component,
                len(waypoints),
            )

            # Upload each waypoint one by one, waiting for the vehicle to request it
            for i, waypoint in enumerate(waypoints):
                # Wait for the vehicle to request the next waypoint (MISSION_REQUEST)
                start_time = time.time()
                while time.time() - start_time < 10:  # 10-second timeout per waypoint
                    msg = self.vehicle.recv_match(
                        type="MISSION_REQUEST", blocking=False, timeout=1
                    )
                    if msg and msg.seq == i:
                        break  # Vehicle is ready for this waypoint
                else:
                    print(f"❌ Timeout waiting for vehicle to request waypoint {i}")
                    return False

                # Send the waypoint details
                cmd_name = self._get_command_name(waypoint.command)
                print(
                    f"  -> Uploading waypoint {i + 1}/{len(waypoints)}: {cmd_name} (seq: {waypoint.seq})"
                )
                self.vehicle.mav.mission_item_int_send(
                    self.vehicle.target_system,
                    self.vehicle.target_component,
                    waypoint.seq,
                    mavutil.mavlink.MAV_FRAME_GLOBAL_RELATIVE_ALT_INT,
                    waypoint.command,
                    0,  # current (0 for non-active waypoints)
                    1,  # autocontinue
                    waypoint.param1,
                    waypoint.param2,
                    waypoint.param3,
                    waypoint.param4,
                    int(waypoint.lat * 1e7),
                    int(waypoint.lon * 1e7),
                    waypoint.alt,
                )

            # Finally, wait for the mission acknowledgment (MISSION_ACK)
            start_time = time.time()
            while time.time() - start_time < 10:
                msg = self.vehicle.recv_match(
                    type="MISSION_ACK", blocking=False, timeout=1
                )
                if msg:
                    if msg.type == mavutil.mavlink.MAV_MISSION_ACCEPTED:
                        print("✅ Mission uploaded successfully")
                        # Refresh the local copy of the mission from the vehicle
                        self.fetch_mission_waypoints()
                        return True
                    else:
                        print(f"❌ Mission upload failed with error code: {msg.type}")
                        return False

            print("⚠️ Mission upload acknowledgment timeout")
            return False

        except Exception as e:
            print(f"An exception occurred during mission upload: {e}")
            return False

    def is_mission_complete(self) -> bool:
        """
        Check if the survey portion of the mission is complete.
        This is based on a reliable flag set by the 'MISSION_ITEM_REACHED' message listener.
        """
        with self._lock:
            return self._survey_mission_complete

    def _update_telemetry_state(self, msg, msg_type):
        """Updates the last_telemetry dictionary based on an incoming MAVLink message."""
        if msg_type == "MISSION_ITEM_REACHED":
            print(f"MISSION_ITEM_REACHED: Waypoint sequence {msg.seq} reached.")

            # Save waypoint to persistent storage immediately
            self._save_waypoint_to_file(msg.seq)

            # Check if the reached waypoint is the last one of the survey pattern
            if self.last_waypoint_seq != -1 and msg.seq >= self.last_waypoint_seq:
                print(
                    f"Survey portion of the mission is complete. Reached final survey waypoint {msg.seq}."
                )
                self._survey_mission_complete = True
        elif msg_type == "GLOBAL_POSITION_INT":
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

            # Check for waypoint visits when position updates
            self._check_waypoint_visits()

        elif msg_type == "SYS_STATUS":
            self.last_telemetry["battery_voltage"] = msg.voltage_battery / 1000.0
            self.last_telemetry["battery_remaining_percentage"] = msg.battery_remaining

        elif msg_type == "MISSION_CURRENT":
            # Update current waypoint sequence from autopilot
            self.current_waypoint_seq = msg.seq
            self.last_telemetry["current_mission_wp_seq"] = msg.seq

            # Update next waypoint based on current
            if self.mission_waypoints:
                sorted_waypoints = sorted(self.mission_waypoints.keys())
                next_wp = None
                for wp_seq in sorted_waypoints:
                    if wp_seq > msg.seq:
                        next_wp = wp_seq
                        break
                self.next_waypoint_seq = next_wp
                self.last_telemetry["next_mission_wp_seq"] = next_wp

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

        # Add waypoint data to every packet for consistency
        self.last_telemetry["mission_total_waypoints"] = len(self.mission_waypoints)
        self.last_telemetry["visited_waypoints"] = list(self.visited_waypoints)

        # Recalculate mission progress based on custom visit detection
        total_wps = len(self.mission_waypoints)
        if total_wps > 0:
            visited_count = len(self.visited_waypoints)
            progress = (float(visited_count) / total_wps) * 100.0
            self.last_telemetry["mission_progress_percentage"] = round(
                max(0.0, min(progress, 100.0))
            )
        else:
            self.last_telemetry["mission_progress_percentage"] = 0
        # --- End of New/Modified Section ---

    def get_current_telemetry(self) -> Dict[str, Any]:
        """Returns a thread-safe copy of the latest telemetry data."""
        with self._lock:
            return self.last_telemetry.copy()

    # def _update_waypoint_sequences(self):
    #     """Update current and next waypoint sequences based on visited waypoints."""
    #     if not hasattr(self, 'mission_waypoints') or not self.mission_waypoints:
    #         return
    #
    #     # Find the highest visited waypoint sequence
    #     if self.visited_waypoints:
    #         highest_visited = max(self.visited_waypoints)
    #
    #         # Current waypoint is the next unvisited waypoint after the highest visited
    #         for seq in sorted(self.mission_waypoints.keys()):
    #             if seq not in self.visited_waypoints:
    #                 self.current_waypoint_seq = seq
    #                 self.last_telemetry["current_mission_wp_seq"] = seq
    #                 break
    #         else:
    #             # All waypoints visited
    #             self.current_waypoint_seq = highest_visited
    #             self.last_telemetry["current_mission_wp_seq"] = highest_visited
    #     else:
    #         # No waypoints visited yet, current is the first waypoint
    #         if self.mission_waypoints:
    #             first_seq = min(self.mission_waypoints.keys())
    #             self.current_waypoint_seq = first_seq
    #             self.last_telemetry["current_mission_wp_seq"] = first_seq
    #
    #     # Set next waypoint
    #     current_seq = self.current_waypoint_seq
    #     if current_seq is not None:
    #         # Find next unvisited waypoint
    #         next_seq = None
    #         for seq in sorted(self.mission_waypoints.keys()):
    #             if seq > current_seq and seq not in self.visited_waypoints:
    #                 next_seq = seq
    #                 break
    #
    #         self.next_waypoint_seq = next_seq
    #         self.last_telemetry["next_mission_wp_seq"] = next_seq

    def get_waypoint_visit_status(self):
        """Get the current waypoint visit status for UI display."""
        return {
            "visited_waypoints": list(self.visited_waypoints),
            "total_waypoints": self.mission_total_waypoints,
            "current_waypoint": self.current_waypoint_seq,
            "next_waypoint": self.next_waypoint_seq,
            "visited_count": len(self.visited_waypoints),
        }

    def _update_current_next_waypoints(self):
        """Update current and next waypoint based on visited waypoints."""
        if not self.mission_waypoints:
            return

        sorted_waypoints = sorted(self.mission_waypoints.keys())

        # Find current waypoint (first unvisited)
        current_wp = None
        for wp_seq in sorted_waypoints:
            if wp_seq not in self.visited_waypoints:
                current_wp = wp_seq
                break

        if current_wp is None:
            # All waypoints visited
            current_wp = sorted_waypoints[-1]

        # Find next waypoint
        next_wp = None
        for wp_seq in sorted_waypoints:
            if wp_seq > current_wp and wp_seq not in self.visited_waypoints:
                next_wp = wp_seq
                break

        self.current_waypoint_seq = current_wp
        self.next_waypoint_seq = next_wp
        self.last_telemetry["current_mission_wp_seq"] = current_wp
        self.last_telemetry["next_mission_wp_seq"] = next_wp

    def _check_waypoint_visits(self):
        """Check if vehicle has visited any unvisited waypoints within tolerance."""
        current_lat = self.last_telemetry.get("latitude")
        current_lon = self.last_telemetry.get("longitude")

        if current_lat is None or current_lon is None or not self.mission_waypoints:
            return

        current_time = time.time()

        for wp_seq, waypoint in self.mission_waypoints.items():
            if wp_seq in self.visited_waypoints:
                continue

            distance = self._calculate_distance(
                current_lat, current_lon, waypoint["lat"], waypoint["lon"]
            )

            if distance <= self.waypoint_visit_threshold:
                if not hasattr(self, "_waypoint_visit_candidates"):
                    self._waypoint_visit_candidates = {}

                if wp_seq not in self._waypoint_visit_candidates:
                    self._waypoint_visit_candidates[wp_seq] = current_time
                elif (
                    current_time - self._waypoint_visit_candidates[wp_seq]
                    >= self.waypoint_confirmation_delay
                ):
                    self.visited_waypoints.add(wp_seq)
                    self._update_current_next_waypoints()
                    print(
                        f"🎯 Waypoint {wp_seq} visited! Distance: {distance:.2f}m, Current: {self.current_waypoint_seq}, Next: {self.next_waypoint_seq}"
                    )

                    # Save waypoint to persistent storage
                    self._save_waypoint_to_file(wp_seq)

                    del self._waypoint_visit_candidates[wp_seq]
            else:
                if (
                    hasattr(self, "_waypoint_visit_candidates")
                    and wp_seq in self._waypoint_visit_candidates
                ):
                    del self._waypoint_visit_candidates[wp_seq]

    def _save_waypoint_to_file(self, waypoint_seq: int):
        """Save a visited waypoint to persistent storage (only for car vehicles)."""
        # Only save waypoints for car vehicles
        if self.vehicle_type != "car":
            return

        if not self.current_site_name:
            print(f"Warning: Cannot save waypoint {waypoint_seq} - no site name set")
            return

        try:
            success = waypoint_file_service.update_visited_waypoint(
                self.current_site_name, str(self.vehicle_id), waypoint_seq
            )
            if success:
                print(
                    f"💾 Waypoint {waypoint_seq} saved to disk for site {self.current_site_name}"
                )
            else:
                print(f"⚠️ Failed to save waypoint {waypoint_seq} to disk")
        except Exception as e:
            print(f"Error saving waypoint {waypoint_seq}: {e}")

    def _calculate_distance(self, lat1, lon1, lat2, lon2):
        """Calculate the distance between two GPS coordinates using Haversine formula."""
        if None in (lat1, lon1, lat2, lon2):
            return float("inf")

        # Convert latitude and longitude from degrees to radians
        lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])

        # Haversine formula
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        a = (
            math.sin(dlat / 2) ** 2
            + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
        )
        c = 2 * math.asin(math.sqrt(a))

        # Radius of earth in meters
        r = 6371000
        return c * r

    # Create a singleton instance

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

                # Only send telemetry if we have a recent heartbeat
                heartbeat_timestamp = telemetry.get("heartbeat_timestamp")
                if heartbeat_timestamp:
                    current_time = time.time()
                    time_since_heartbeat = current_time - heartbeat_timestamp

                    # Only send telemetry if the heartbeat is less than 10 seconds old
                    if time_since_heartbeat < 10.0:
                        self._telemetry_callback(telemetry)
                    else:
                        print(
                            f"{self.vehicle_type}: No recent heartbeat ({time_since_heartbeat:.1f}s ago), not sending telemetry"
                        )
                else:
                    print(
                        f"{self.vehicle_type}: No heartbeat received, not sending telemetry"
                    )

            except Exception as e:
                print(f"Error in telemetry loop: {e}")
            time.sleep(0.1)  # 10Hz update rate, adjust as needed
