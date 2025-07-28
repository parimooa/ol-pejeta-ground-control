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

        if self.vehicle_type == "car" and self.current_site_name:
            self.load_previous_visited_waypoints()

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

    def load_previous_visited_waypoints(self):
        """Load previously visited waypoints from persistent storage."""
        if self.vehicle_type != "car":
            return

        if not self.current_site_name:
            print("Warning: Cannot load waypoints - no site name set")
            return

        try:
            visited_waypoints = waypoint_file_service.get_visited_waypoints(
                self.current_site_name, str(self.vehicle_id)
            )

            if visited_waypoints:
                self.visited_waypoints = set(visited_waypoints)
                print(f"📂 Loaded {len(visited_waypoints)} previously visited waypoints: {sorted(visited_waypoints)}")

                # Find the closest unvisited waypoint to resume from
                if self.mission_waypoints:
                    self._resume_from_closest_waypoint()
            else:
                print("📂 No previous waypoint progress found - starting fresh mission")
                self.visited_waypoints = set()

        except Exception as e:
            print(f"Error loading previous waypoints: {e}")
            self.visited_waypoints = set()

    def _resume_from_closest_waypoint(self):
        """Resume mission from the closest unvisited waypoint."""
        if not self.mission_waypoints or not hasattr(self, 'last_telemetry'):
            return

        current_lat = self.last_telemetry.get("latitude")
        current_lon = self.last_telemetry.get("longitude")

        if current_lat is None or current_lon is None:
            print("Cannot resume - no current position available")
            return

        # Find all unvisited waypoints
        unvisited_waypoints = []
        for seq, waypoint in self.mission_waypoints.items():
            if seq not in self.visited_waypoints:
                distance = self._calculate_distance(
                    current_lat, current_lon,
                    waypoint["lat"], waypoint["lon"]
                )
                unvisited_waypoints.append((seq, distance))

        if unvisited_waypoints:
            # Sort by distance and select the closest
            closest_waypoint_seq = min(unvisited_waypoints, key=lambda x: x[1])[0]
            self.current_waypoint_seq = closest_waypoint_seq
            print(f"🎯 Resuming mission from closest unvisited waypoint: {closest_waypoint_seq + 1}")
        else:
            print("✅ All waypoints have been visited - mission complete")

    def _save_waypoint_to_file(self, waypoint_seq: int):
        """Save a visited waypoint to persistent storage (only for car vehicles)."""
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
                print(f"💾 Waypoint {waypoint_seq + 1} saved to disk for site {self.current_site_name}")
            else:
                print(f"⚠️ Failed to save waypoint {waypoint_seq + 1} to disk")
        except Exception as e:
            print(f"Error saving waypoint {waypoint_seq}: {e}")

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

        # Request essential data streams. In a real GCS, this is often done once on connect.
        stream_rate_hz = 4  # A reasonable rate for polling
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

        try:
            # Wait and collect all relevant messages
            start_fetch_time = time.time()
            fetch_timeout = 0.2  # Shorter timeout is fine for polling basic telemetry

            while time.time() - start_fetch_time < fetch_timeout:
                msg = self.vehicle.recv_match(
                    type=[
                        "GLOBAL_POSITION_INT",
                        "SYS_STATUS",
                        "VFR_HUD",
                    ],
                    blocking=False,
                    timeout=0.05,
                )

                if not msg:
                    time.sleep(0.01)  # Don't busy-wait
                    continue

                msg_type = msg.get_type()

                if msg_type == "GLOBAL_POSITION_INT":
                    telemetry["latitude"] = msg.lat / 1e7
                    telemetry["longitude"] = msg.lon / 1e7
                    telemetry["altitude_msl"] = msg.alt / 1000.0
                    telemetry["relative_altitude"] = msg.relative_alt / 1000.0

                elif msg_type == "SYS_STATUS":
                    telemetry["battery_voltage"] = (
                        msg.voltage_battery / 1000.0
                    )  # mV to V
                    telemetry["battery_remaining_percentage"] = (
                        msg.battery_remaining
                    )  # Percentage

                elif msg_type == "VFR_HUD":
                    telemetry["ground_speed"] = msg.groundspeed  # m/s
                    telemetry["heading"] = msg.heading  # degrees

        except Exception as e:
            print(f"Error getting position data: {e}")
            import traceback

            traceback.print_exc()

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
