import math
import threading
import time
from enum import Enum

from pymavlink import mavutil, mavwp


class FlightMode(Enum):
    STABILIZE = 0
    GUIDED = 4
    RTL = 6
    LAND = 9
    AUTO = 3


class Vehicle:
    def __init__(self, vehicle_type, ip, port, protocol):
        self.vehicle_type = vehicle_type
        self.device = ip
        self.port = port
        self.protocol = protocol
        self.connection_string = f"{protocol}:{ip}:{port}"
        self.vehicle = None
        self.mission_total_waypoints = 0

    def __repr__(self):
        return (
            f"Vehicle({self.vehicle_type}, {self.device}, {self.port}, {self.protocol})"
        )

    def connect_vehicle(self):
        print(
            f"Connecting to vehicle on: {self.vehicle_type} at {self.connection_string}"
        )
        self.vehicle = mavutil.mavlink_connection(
            self.connection_string, source_system=255
        )

        print("Waiting for heartbeat...")
        self.vehicle.wait_heartbeat()
        print(
            f"Connected to system {self.vehicle.target_system} component {self.vehicle.target_component}"
        )
        self.vehicle.mav.statustext_send(
            mavutil.mavlink.MAV_SEVERITY_NOTICE, "QGC will read this".encode()
        )

        def heartbeat_loop():
            while True:
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

        heartbeat_thread = threading.Thread(target=heartbeat_loop)
        heartbeat_thread.daemon = True
        heartbeat_thread.start()

        return self.vehicle

    def disconnect_vehicle(self):
        if self.vehicle:
            print(f"Disconnecting vehicle: {self.vehicle_type}")
            self.vehicle.close()
            self.vehicle = None
            print("Vehicle disconnected.")
        else:
            print("No vehicle connected to disconnect.")

    def upload_mission(self):
        if not self.vehicle:
            print("Vehicle not connected. Cannot upload mission.")
            return False
        try:
            wploader = mavwp.MAVWPLoader()
            try:
                self.mission_total_waypoints = wploader.load("wp.waypoints")
                print(
                    f"Loaded {self.mission_total_waypoints} waypoints from 'wp.waypoints'"
                )
            except FileNotFoundError:
                print("Error: Waypoint file 'wp.waypoints' not found.")
                return False

            if self.mission_total_waypoints == 0:
                print("No waypoints found in 'wp.waypoints'")
                return False

            print("Clearing existing mission...")
            self.vehicle.mav.mission_clear_all_send(
                self.vehicle.target_system, self.vehicle.target_component
            )
            ack_msg = self.vehicle.recv_match(
                type="MISSION_ACK", blocking=True, timeout=5
            )

            if ack_msg is None:
                print("Mission clear timed out. No MISSION_ACK received.")
                return False
            if ack_msg.type != mavutil.mavlink.MAV_MISSION_ACCEPTED:
                print(f"Mission clear failed with error: {ack_msg.type}")
                return False
            print("Existing mission cleared.")

            print(f"Sending waypoint count: {self.mission_total_waypoints}")
            self.vehicle.waypoint_count_send(self.mission_total_waypoints)

            for i in range(self.mission_total_waypoints):
                msg = self.vehicle.recv_match(
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
                if hasattr(self.vehicle.mav, "mission_item_int_send"):
                    self.vehicle.mav.mission_item_int_send(
                        self.vehicle.target_system,
                        self.vehicle.target_component,
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
                    self.vehicle.mav.mission_item_send(
                        self.vehicle.target_system,
                        self.vehicle.target_component,
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

            ack_msg = self.vehicle.recv_match(
                type="MISSION_ACK", blocking=True, timeout=15
            )
            if not ack_msg or ack_msg.type != mavutil.mavlink.MAV_MISSION_ACCEPTED:
                print(
                    f"Mission upload failed with error: {ack_msg.type if ack_msg else 'Timeout'}"
                )
                return False

            print("Mission upload successful.")
            return self.mission_total_waypoints

        except Exception as e:
            print(f"An error occurred during mission upload: {e}")
            import traceback

            traceback.print_exc()
            return False

    def set_mode(self, mode_id: FlightMode):
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

        start_time = time.time()
        timeout_duration = 10
        while time.time() - start_time < timeout_duration:
            ack_msg = self.vehicle.recv_match(
                type="COMMAND_ACK", blocking=False, timeout=0.1
            )
            if ack_msg and ack_msg.command == mavutil.mavlink.MAV_CMD_DO_SET_MODE:
                if ack_msg.result == mavutil.mavlink.MAV_RESULT_ACCEPTED:
                    print(f"Mode change to {mode_id.name} acknowledged by vehicle.")
                    hb_msg = self.vehicle.recv_match(
                        type="HEARTBEAT", blocking=True, timeout=2
                    )
                    if hb_msg and hb_msg.custom_mode == mode_id.value:
                        print(
                            f"Mode changed to {mode_id.name} successfully (verified by HEARTBEAT)."
                        )
                        return True
                    elif hb_msg:
                        print(
                            f"Mode change acknowledged, but HEARTBEAT shows mode {hb_msg.custom_mode} (expected {mode_id.value})."
                        )
                    else:
                        print(
                            "Mode change acknowledged, but no HEARTBEAT received for verification."
                        )
                    return False
                else:
                    print(
                        f"Mode change command rejected by vehicle with result: {ack_msg.result}"
                    )
                    return False

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

    def set_guided_mode(self):
        print(f"Setting mode to GUIDED")
        return self.set_mode(FlightMode.GUIDED)

    def set_auto_mode(self):
        print(f"Setting mode to AUTO")
        return self.set_mode(FlightMode.AUTO)

    def arm_vehicle(self):
        if not self.vehicle:
            print("Vehicle not connected. Cannot arm.")
            return False

        print("Arming vehicle...")
        self.vehicle.mav.command_long_send(
            self.vehicle.target_system,
            self.vehicle.target_component,
            mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM,
            0,
            1,  # 1 to arm
            0,
            0,
            0,
            0,
            0,
            0,
        )

        start_time = time.time()
        timeout_duration = 7
        while time.time() - start_time < timeout_duration:
            msg = self.vehicle.recv_match(type="COMMAND_ACK", blocking=True, timeout=1)
            if msg and msg.command == mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM:
                if msg.result == mavutil.mavlink.MAV_RESULT_ACCEPTED:
                    print("Vehicle armed successfully (COMMAND_ACK).")
                    hb_msg = self.vehicle.recv_match(
                        type="HEARTBEAT", blocking=True, timeout=2
                    )
                    if hb_msg and (
                        hb_msg.base_mode & mavutil.mavlink.MAV_MODE_FLAG_SAFETY_ARMED
                    ):
                        print("Arming confirmed by HEARTBEAT.")
                        return True
                    elif hb_msg:
                        print(
                            "Arm command accepted, but HEARTBEAT does not show armed state."
                        )
                        return False
                    else:
                        print(
                            "Arm command accepted, but no HEARTBEAT received for verification."
                        )
                        return False
                elif msg.result == mavutil.mavlink.MAV_RESULT_IN_PROGRESS:
                    print(f"Arming in progress (result={msg.result}). Waiting...")
                else:
                    print(f"Arm command rejected or failed: result={msg.result}")
                    statustext_msg = self.vehicle.recv_match(
                        type="STATUSTEXT", blocking=False, timeout=0.5
                    )
                    if statustext_msg:
                        print(f"STATUSTEXT: {statustext_msg.text}")
                    return False
            if not msg:
                time.sleep(0.1)

        print(
            f"No arming confirmation or failure ACK received within {timeout_duration} seconds."
        )
        return False

    def set_home_position(self, lat, lon, alt):
        if not self.vehicle:
            print("Vehicle not connected. Cannot set home position.")
            return False
        lat_int = int(lat * 1e7)
        lon_int = int(lon * 1e7)

        print(f"Sending SET_HOME command: Lat={lat}, Lon={lon}, Alt={alt}m (AMSL)")
        self.vehicle.mav.command_long_send(
            self.vehicle.target_system,
            self.vehicle.target_component,
            mavutil.mavlink.MAV_CMD_DO_SET_HOME,
            0,
            1,  # param1: 1 to use lat/lon/alt from this command
            0,
            0,
            0,
            lat_int,
            lon_int,
            float(alt),
        )

        start_time = time.time()
        timeout_duration = 5
        while time.time() - start_time < timeout_duration:
            msg = self.vehicle.recv_match(type="COMMAND_ACK", blocking=True, timeout=1)
            if msg and msg.command == mavutil.mavlink.MAV_CMD_DO_SET_HOME:
                if msg.result == mavutil.mavlink.MAV_RESULT_ACCEPTED:
                    print("Home position set successfully!")
                    return True
                else:
                    print(
                        f"Home position setting failed with COMMAND_ACK result: {msg.result}"
                    )
                    return False

        print(f"No COMMAND_ACK for SET_HOME received within {timeout_duration}s.")
        return False

    def takeoff(self, altitude_meters: float):
        """Commands the vehicle to takeoff to a specific altitude."""
        if not self.vehicle:
            print("Vehicle not connected. Cannot takeoff.")
            return False

        # For copters, it's common to be in GUIDED mode for takeoff
        # You might want to ensure this or let the user manage modes.
        # For simplicity, we assume the mode is appropriate (e.g., GUIDED).
        print(f"Commanding takeoff to {altitude_meters} meters...")
        self.vehicle.mav.command_long_send(
            self.vehicle.target_system,
            self.vehicle.target_component,
            mavutil.mavlink.MAV_CMD_NAV_TAKEOFF,
            0,  # Confirmation
            0,  # Param1: Min pitch (ignored by copter)
            0,  # Param2: Empty
            0,  # Param3: Empty
            0,  # Param4: Yaw angle (0 for North, NaN for unchanged)
            0,  # Param5: Latitude (0 for current)
            0,  # Param6: Longitude (0 for current)
            altitude_meters,  # Param7: Altitude
        )

        start_time = time.time()
        timeout_duration = 15  # Takeoff can take time
        while time.time() - start_time < timeout_duration:
            msg = self.vehicle.recv_match(type="COMMAND_ACK", blocking=True, timeout=1)
            if msg and msg.command == mavutil.mavlink.MAV_CMD_NAV_TAKEOFF:
                if msg.result == mavutil.mavlink.MAV_RESULT_ACCEPTED:
                    print(
                        f"Takeoff command accepted. Vehicle ascending to {altitude_meters}m."
                    )
                    return True
                elif msg.result == mavutil.mavlink.MAV_RESULT_IN_PROGRESS:
                    print(f"Takeoff in progress (result={msg.result}). Waiting...")
                else:
                    print(
                        f"Takeoff command failed or rejected with result: {msg.result}"
                    )
                    statustext_msg = self.vehicle.recv_match(
                        type="STATUSTEXT", blocking=False, timeout=0.5
                    )
                    if statustext_msg:
                        print(f"STATUSTEXT: {statustext_msg.text}")
                    return False
            if not msg:  # Allow loop to check time if no message
                time.sleep(0.1)

        print(f"No COMMAND_ACK for TAKEOFF received within {timeout_duration} seconds.")
        return False

    def start_mission(self, first_item: int = 0, last_item: int = 0):
        """Commands the vehicle to start or resume the mission."""
        if not self.vehicle:
            print("Vehicle not connected. Cannot start mission.")
            return False

        # Vehicle should typically be in AUTO mode to start a mission.
        # For ArduPilot, switching to AUTO after arming often starts the mission.
        # This command can be used to explicitly start or resume.
        print(f"Commanding mission start (from item {first_item} to {last_item})...")
        self.vehicle.mav.command_long_send(
            self.vehicle.target_system,
            self.vehicle.target_component,
            mavutil.mavlink.MAV_CMD_MISSION_START,
            0,  # Confirmation
            float(first_item),  # Param1: First item
            float(last_item),  # Param2: Last item (0 for last wp)
            0,  # Param3: Empty
            0,  # Param4: Empty
            0,  # Param5: Empty
            0,  # Param6: Empty
            0,  # Param7: Empty
        )

        start_time = time.time()
        timeout_duration = 10
        while time.time() - start_time < timeout_duration:
            msg = self.vehicle.recv_match(type="COMMAND_ACK", blocking=True, timeout=1)
            if msg and msg.command == mavutil.mavlink.MAV_CMD_MISSION_START:
                if msg.result == mavutil.mavlink.MAV_RESULT_ACCEPTED:
                    print("Mission start command accepted.")
                    return True
                elif msg.result == mavutil.mavlink.MAV_RESULT_IN_PROGRESS:
                    print(
                        f"Mission start in progress (result={msg.result}). Waiting..."
                    )
                else:
                    print(
                        f"Mission start command failed or rejected with result: {msg.result}"
                    )
                    return False
            if not msg:
                time.sleep(0.1)

        print(
            f"No COMMAND_ACK for MISSION_START received within {timeout_duration} seconds."
        )
        return False

    def get_waypoint_position(self, wp_seq):
        """Get the position of a specific waypoint by sequence number."""
        if not self.vehicle:
            print("Vehicle not connected. Cannot get waypoint position.")
            return None

        # Request the specific waypoint
        self.vehicle.mav.mission_request_int_send(
            self.vehicle.target_system, self.vehicle.target_component, wp_seq
        )

        # Wait for response
        start_time = time.time()
        timeout = 2.0  # seconds

        while time.time() - start_time < timeout:
            msg = self.vehicle.recv_match(
                type=["MISSION_ITEM", "MISSION_ITEM_INT"], blocking=False, timeout=0.1
            )

            if msg and (msg.seq == wp_seq):
                # Extract position from waypoint
                wp_pos = {
                    "latitude": (
                        msg.x if hasattr(msg, "x") else msg.x / 1e7
                    ),  # Convert int to float if needed
                    "longitude": msg.y if hasattr(msg, "y") else msg.y / 1e7,
                    "altitude": msg.z,
                    "command": msg.command,
                    "frame": msg.frame,
                }
                return wp_pos

        print(f"Failed to get position for waypoint {wp_seq}")
        return None

    def calculate_distance(self, lat1, lon1, lat2, lon2):
        """Calculate the distance between two points using Haversine formula."""
        # Earth radius in meters
        R = 6371000.0

        # Convert latitude and longitude from degrees to radians
        lat1_rad = math.radians(lat1)
        lon1_rad = math.radians(lon1)
        lat2_rad = math.radians(lat2)
        lon2_rad = math.radians(lon2)

        # Differences in coordinates
        dlat = lat2_rad - lat1_rad
        dlon = lon2_rad - lon1_rad

        # Haversine formula
        a = (
            math.sin(dlat / 2) ** 2
            + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon / 2) ** 2
        )
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        distance = R * c

        return distance

    def position(self) -> dict:
        """Get comprehensive vehicle position and mission information.

        Returns a dictionary with telemetry data including position, velocity,
        mission progress, and accurate distance to waypoint.
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

        # Step 1: Request specific data streams with higher rates for navigation data
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
        self.vehicle.mav.request_data_stream_send(
            self.vehicle.target_system,
            self.vehicle.target_component,
            mavutil.mavlink.MAV_DATA_STREAM_EXTRA1,
            stream_rate_hz,
            1,
        )  # VFR_HUD
        self.vehicle.mav.request_data_stream_send(
            self.vehicle.target_system,
            self.vehicle.target_component,
            mavutil.mavlink.MAV_DATA_STREAM_EXTRA2,
            stream_rate_hz,
            1,
        )  # Mission data

        # Step 2: Request the current mission item information
        # Use command_long_send with MAV_CMD_REQUEST_MESSAGE instead of non-existent mission_request_current_send
        self.vehicle.mav.command_long_send(
            self.vehicle.target_system,
            self.vehicle.target_component,
            mavutil.mavlink.MAV_CMD_REQUEST_MESSAGE,
            0,  # confirmation
            mavutil.mavlink.MAVLINK_MSG_ID_MISSION_CURRENT,  # param1: message ID to request
            0,
            0,
            0,
            0,
            0,
            0,  # unused parameters
        )

        # Step 3: Directly request NAV_CONTROLLER_OUTPUT for accurate distance
        self.vehicle.mav.command_long_send(
            self.vehicle.target_system,
            self.vehicle.target_component,
            mavutil.mavlink.MAV_CMD_REQUEST_MESSAGE,
            0,
            mavutil.mavlink.MAVLINK_MSG_ID_NAV_CONTROLLER_OUTPUT,  # param1: message ID
            0,
            0,
            0,
            0,
            0,
            0,  # unused parameters
        )

        try:
            # Wait and collect all relevant messages
            start_fetch_time = time.time()
            fetch_timeout = 0.5  # shorter timeout for responsiveness

            got_global_pos = False
            got_sys_status = False
            got_mission_current = False
            got_nav_controller = False
            got_vfr_hud = False

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
                    # If we have all essential data, we can break early
                    if got_global_pos and got_mission_current and got_nav_controller:
                        break
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
                    got_global_pos = True

                elif msg_type == "SYS_STATUS":
                    telemetry["battery_voltage"] = (
                        msg.voltage_battery / 1000.0
                    )  # mV to V
                    telemetry["battery_remaining_percentage"] = (
                        msg.battery_remaining
                    )  # Percentage
                    got_sys_status = True

                elif msg_type == "MISSION_CURRENT":
                    telemetry["current_mission_wp_seq"] = msg.seq
                    if self.mission_total_waypoints > 0:
                        current_seq = msg.seq
                        if current_seq < (self.mission_total_waypoints - 1):
                            telemetry["next_mission_wp_seq"] = current_seq + 1
                    got_mission_current = True

                elif msg_type == "NAV_CONTROLLER_OUTPUT":
                    telemetry["distance_to_mission_wp"] = msg.wp_dist  # In meters
                    telemetry["target_bearing"] = msg.target_bearing  # In degrees
                    telemetry["nav_roll"] = msg.nav_roll  # In degrees
                    telemetry["nav_pitch"] = msg.nav_pitch  # In degrees
                    got_nav_controller = True

                elif msg_type == "VFR_HUD":
                    # VFR_HUD contains additional useful information
                    telemetry["airspeed"] = msg.airspeed  # m/s
                    telemetry["ground_speed"] = msg.groundspeed  # m/s
                    telemetry["heading"] = msg.heading  # degrees
                    telemetry["throttle"] = msg.throttle  # percentage
                    telemetry["climb_rate"] = msg.climb  # m/s
                    # VFR_HUD alt is useful as a backup
                    if telemetry["relative_altitude"] is None:
                        telemetry["relative_altitude"] = msg.alt
                    got_vfr_hud = True

            # If we didn't get NAV_CONTROLLER_OUTPUT but have position, fallback to distance calculation
            if not got_nav_controller and got_mission_current and got_global_pos:
                # We need to request the current waypoint position for calculation
                if telemetry["current_mission_wp_seq"] is not None:
                    wp_seq = telemetry["current_mission_wp_seq"]
                    wp_pos = self.get_waypoint_position(wp_seq)

                    if wp_pos and wp_pos.get("latitude") is not None:
                        # Calculate distance using Haversine formula
                        distance = self.calculate_distance(
                            telemetry["latitude"],
                            telemetry["longitude"],
                            wp_pos["latitude"],
                            wp_pos["longitude"],
                        )
                        telemetry["distance_to_mission_wp"] = distance
                        telemetry["distance_calculation_method"] = (
                            "haversine"  # For debugging
                        )

            # Calculate mission progress percentage
            if (
                self.mission_total_waypoints > 1
                and telemetry["current_mission_wp_seq"] is not None
            ):
                current_seq = telemetry["current_mission_wp_seq"]
                total_wps = self.mission_total_waypoints

                # If we've reached the last waypoint, progress is 100%
                if current_seq >= total_wps - 1:
                    telemetry["mission_progress_percentage"] = 100.0
                else:
                    # Calculate progress as percentage of completed waypoints
                    progress = (float(current_seq) / (total_wps - 1)) * 100.0
                    telemetry["mission_progress_percentage"] = max(
                        0.0, min(progress, 100.0)
                    )
            elif self.mission_total_waypoints <= 1:
                telemetry["mission_progress_percentage"] = 0.0

        except Exception as e:
            print(f"Error getting position data: {e}")
            import traceback

            traceback.print_exc()

        return telemetry

    def position_orig(self):
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
            print("Vehicle not connected. Cannot get position.")
            return telemetry

        # Request necessary data streams (simplified: request every time)
        # In a robust GCS, set stream rates once after connection.
        stream_rate_hz = 10  # Common rate for telemetry updates

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
        # NAV_CONTROLLER_OUTPUT is often part of MAV_DATA_STREAM_EXTENDED_STATUS on ArduPilot
        # If not, MAV_DATA_STREAM_EXTRA1 might be needed for NAV_CONTROLLER_OUTPUT or VFR_HUD

        try:
            # Loop to try and get all relevant messages within a short time window
            # This is a simple approach; a more robust GCS would handle messages asynchronously.
            start_fetch_time = time.time()
            fetch_timeout = 1.0  # seconds to wait for all messages

            got_global_pos = False
            got_sys_status = False
            got_mission_current = False
            got_nav_controller = False

            while time.time() - start_fetch_time < fetch_timeout:
                msg = self.vehicle.recv_match(
                    type=[
                        "GLOBAL_POSITION_INT",
                        "SYS_STATUS",
                        "MISSION_CURRENT",
                        "NAV_CONTROLLER_OUTPUT",
                    ],
                    blocking=False,  # Non-blocking read
                    timeout=0.05,  # Short timeout for each read attempt
                )
                if not msg:
                    if (
                        got_global_pos
                        and got_sys_status
                        and got_mission_current
                        and got_nav_controller
                    ):
                        break  # Got all we need
                    time.sleep(0.01)  # Small delay before retrying
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
                    # Calculate ground speed from vx, vy
                    if telemetry["vx"] is not None and telemetry["vy"] is not None:
                        telemetry["ground_speed"] = math.sqrt(
                            telemetry["vx"] ** 2 + telemetry["vy"] ** 2
                        )
                    got_global_pos = True

                elif msg_type == "SYS_STATUS":
                    telemetry["battery_voltage"] = (
                        msg.voltage_battery / 1000.0
                    )  # mV to V
                    telemetry["battery_remaining_percentage"] = (
                        msg.battery_remaining
                    )  # Percentage
                    got_sys_status = True

                elif msg_type == "MISSION_CURRENT":
                    telemetry["current_mission_wp_seq"] = msg.seq
                    print(f"WP: {msg.seq}")
                    # Calculate next mission waypoint sequence
                    if (
                        telemetry["current_mission_wp_seq"] is not None
                        and self.mission_total_waypoints > 0
                    ):
                        current_seq = telemetry["current_mission_wp_seq"]
                        if current_seq < (self.mission_total_waypoints - 1):
                            telemetry["next_mission_wp_seq"] = current_seq + 1

                    got_mission_current = True

                elif msg_type == "NAV_CONTROLLER_OUTPUT":
                    telemetry["distance_to_mission_wp"] = msg.wp_dist  # In meters
                    got_nav_controller = True

                # Break if all desired messages received
                if (
                    got_global_pos
                    and got_sys_status
                    and got_mission_current
                    and got_nav_controller
                ):
                    break

            # Calculate mission progress percentage
            if (
                self.mission_total_waypoints > 0
                and telemetry["current_mission_wp_seq"] is not None
            ):
                current_seq = telemetry["current_mission_wp_seq"]
                total_wps = self.mission_total_waypoints

                # MISSION_CURRENT.seq is the *next* target.
                # If seq is 0, 0% done. If seq is total_wps, 100% done.
                if (
                    total_wps > 0
                ):  # Avoid division by zero if mission has 0 waypoints (though unlikely if loaded)
                    progress = (float(current_seq) / total_wps) * 100.0
                    telemetry["mission_progress_percentage"] = max(
                        0.0, min(progress, 100.0)
                    )  # Clamp between 0 and 100
            elif self.mission_total_waypoints == 0:
                telemetry["mission_progress_percentage"] = 0.0

        except Exception as e:
            print(f"Failed to get extended position data: {e}")
            import traceback

            traceback.print_exc()
        print(telemetry)
        return telemetry


if __name__ == "__main__":
    try:
        from settings import vehicle_settings
    except ImportError:
        print(
            "Could not import vehicle_settings from settings.py. Using placeholder data."
        )
        vehicle_settings = [
            {
                "type": "drone",
                "connection": "127.0.0.1",
                "port": 14550,
                "protocol": "udpin",
                "home_location": {"lat": -35.363262, "lon": 149.165237, "alt": 584.0},
            },  # SITL Default Home
        ]

    drone_config = next((v for v in vehicle_settings if v["type"] == "drone"), None)

    if not drone_config:
        print("Drone configuration not found in settings.")
        exit()

    drone = Vehicle(
        drone_config["type"],
        drone_config["connection"],
        drone_config["port"],
        drone_config["protocol"],
    )

    takeoff_altitude = 10.0  # meters

    if drone.connect_vehicle():
        print("\nDrone connected.")

        home_loc = drone_config.get("home_location")
        # print(home_loc)
        # drone.set_home_position(home_loc['lat'], home_loc['lon'], home_loc['alt'])
        # if home_loc:
        #     print(
        #         f"\nSetting Home Position to Lat: {home_loc['lat']}, Lon: {home_loc['lon']}, Alt: {home_loc['alt']}m AMSL")
        #     if drone.set_home_position(home_loc['lat'], home_loc['lon'], home_loc['alt']):
        #         print("Home position successfully set.")
        #     else:
        #         print("Failed to set home position.")
        # else:
        #     print("Home location not defined in drone_config.")

        print("\nAttempting to upload mission...")
        if drone.upload_mission():
            print("Mission uploaded successfully.")

            print(f"\nAttempting to set GUIDED mode for takeoff...")
            if drone.set_guided_mode():  # Takeoff is often done in GUIDED mode
                print("Vehicle in GUIDED mode.")

                print("\nAttempting to arm vehicle...")
                if drone.arm_vehicle():
                    print("Vehicle is ARMED.")

                    print(f"\nAttempting to takeoff to {takeoff_altitude}m...")
                    if drone.takeoff(takeoff_altitude):
                        print(
                            f"Takeoff to {takeoff_altitude}m initiated. Waiting for vehicle to reach altitude..."
                        )
                        # Simple wait loop, in a real GCS you'd monitor altitude
                        # This is a blocking wait for demonstration
                        while True:
                            pos = drone.position()
                            current_rel_alt = pos.get("relative_altitude")
                            if current_rel_alt is not None:
                                print(
                                    f"Current relative altitude: {current_rel_alt:.2f}m"
                                )
                                if (
                                    current_rel_alt >= takeoff_altitude * 0.95
                                ):  # Reached ~95% of target alt
                                    print("Reached target takeoff altitude.")
                                    break
                            else:
                                print("Waiting for altitude data...")
                            time.sleep(1)

                        print("\nAttempting to set AUTO mode...")
                        if drone.set_auto_mode():
                            print("Vehicle is in AUTO mode.")

                            # Optionally, explicitly start the mission
                            # For ArduPilot, setting AUTO mode often starts the mission if armed and mission loaded.
                            # MAV_CMD_MISSION_START can be used for more control or to resume.
                            print(
                                "\nAttempting to explicitly start mission (MAV_CMD_MISSION_START)..."
                            )
                            if drone.start_mission():
                                print("Mission start command sent successfully.")
                            else:
                                print(
                                    "Failed to send mission start command or it was rejected."
                                )

                            print(
                                "Monitoring mission execution (first few position updates):"
                            )
                            while True:  # Monitor for a short period
                                pos = drone.position()
                                if pos:
                                    # Create formatted strings that handle None values
                                    lat = pos.get("latitude")
                                    lat_str = f"{lat:.6f}" if lat is not None else "N/A"

                                    lon = pos.get("longitude")
                                    lon_str = f"{lon:.6f}" if lon is not None else "N/A"

                                    alt_rel = pos.get("relative_altitude")
                                    alt_rel_str = (
                                        f"{alt_rel:.1f}"
                                        if alt_rel is not None
                                        else "N/A"
                                    )

                                    mission_progress = pos.get(
                                        "mission_progress_percentage"
                                    )
                                    mission_progress_str = (
                                        f"{mission_progress:.1f}"
                                        if mission_progress is not None
                                        else "N/A"
                                    )

                                    print(
                                        f"Mission Pos: Lat={lat_str}, "
                                        + f"Lon={lon_str}, "
                                        + f"AltRel={alt_rel_str}m, "
                                        + f"Current-WP={pos.get('current_mission_wp_seq', 'N/A')}, "
                                        + f"Next-WP={pos.get('next_mission_wp_seq', 'N/A')}, "
                                        + f"Mission Progress={mission_progress_str}%, "
                                        + f"Distance={pos.get('distance_to_mission_wp', 'N/A')}m"
                                    )
                                time.sleep(1)

                        else:
                            print("Failed to set AUTO mode.")
                    else:
                        print("Failed to takeoff.")
                else:
                    print("Failed to arm vehicle.")
            else:
                print("Failed to set GUIDED mode.")
        else:
            print("Failed to upload mission.")

        drone.disconnect_vehicle()
    else:
        print("Failed to connect to drone.")
