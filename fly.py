#!/usr/bin/env python3

import time
import math
import threading
from pymavlink import mavutil

# Connection parameters
connection_string = "udp:127.0.0.1:14551"  # Use secondary port for script


def connect_vehicle():
    """Connect to the vehicle and wait for a heartbeat"""
    print(f"Connecting to vehicle on: {connection_string}")
    vehicle = mavutil.mavlink_connection(connection_string, source_system=255)

    # Wait for the first heartbeat
    print("Waiting for heartbeat...")
    vehicle.wait_heartbeat()
    print(
        f"Connected to system {vehicle.target_system} component {vehicle.target_component}"
    )
    vehicle.mav.statustext_send(
        mavutil.mavlink.MAV_SEVERITY_NOTICE, "QGC will read this".encode()
    )

    # Start sending heartbeats to vehicle
    def heartbeat_loop():
        while True:
            vehicle.mav.heartbeat_send(
                mavutil.mavlink.MAV_TYPE_GCS,
                mavutil.mavlink.MAV_AUTOPILOT_INVALID,
                0,
                0,
                0,
            )
            time.sleep(1)

    heartbeat_thread = threading.Thread(target=heartbeat_loop)
    heartbeat_thread.daemon = True
    heartbeat_thread.start()

    return vehicle


def send_rc_override(vehicle):
    """Send RC override to simulate RC inputs"""
    print("Sending RC overrides...")
    # Channels: 1=Roll, 2=Pitch, 3=Throttle, 4=Yaw, 5+=other
    # Values: 1000-2000 (microseconds)
    # 1500 is mid-position for channels 1,2,4
    # For throttle, set it above minimum but not too high
    rc_channels = [1500, 1500, 1100, 1500, 0, 0, 0, 0]

    vehicle.mav.rc_channels_override_send(
        vehicle.target_system, vehicle.target_component, *rc_channels
    )
    time.sleep(0.5)


def set_mode_and_wait(vehicle, mode):
    """Set the specified flight mode and wait for confirmation"""
    mode_mapping = {
        "STABILIZE": 0,
        "GUIDED": 4,
        "RTL": 6,
        "LAND": 9,
    }

    mode_id = mode_mapping.get(mode)
    if mode_id is None:
        print(f"Unknown mode: {mode}")
        return False

    print(f"Setting mode to {mode} (mode_id: {mode_id})")

    vehicle.mav.command_long_send(
        vehicle.target_system,
        vehicle.target_component,
        mavutil.mavlink.MAV_CMD_DO_SET_MODE,
        0,
        mavutil.mavlink.MAV_MODE_FLAG_CUSTOM_MODE_ENABLED,
        mode_id,
        0,
        0,
        0,
        0,
        0,
    )

    # Wait for mode change confirmation
    start_time = time.time()
    while time.time() - start_time < 5:  # 5 second timeout
        msg = vehicle.recv_match(type="HEARTBEAT", blocking=True, timeout=1)
        if msg and msg.base_mode & mavutil.mavlink.MAV_MODE_FLAG_CUSTOM_MODE_ENABLED:
            custom_mode = msg.custom_mode
            if custom_mode == mode_id:
                print(f"Mode changed to {mode} successfully")
                return True

    print(f"Failed to change to {mode} mode")
    return False


def disable_prearm_checks(vehicle):
    """Disable arming checks for SITL testing"""
    print("Disabling pre-arm checks...")
    params = [
        ("ARMING_CHECK", 0),  # Disable all arming checks
        ("BRD_SAFETYENABLE", 0),  # Disable safety switch
        ("FS_THR_ENABLE", 0),  # Disable throttle failsafe
        ("PILOT_THR_BHV", 0),  # Disable throttle behavior check
        ("RC1_MIN", 1000),  # Set RC minimums to allow arming
        ("RC1_MAX", 2000),
        ("RC3_MIN", 1000),
        ("RC3_MAX", 2000),
        ("SIM_RC_FAIL", 0),  # Disable RC failsafe simulation
    ]

    for param_name, param_value in params:
        # Send parameter set command
        vehicle.mav.param_set_send(
            vehicle.target_system,
            vehicle.target_component,
            param_name.encode("utf-8"),  # This is correct - encode for sending
            param_value,
            mavutil.mavlink.MAV_PARAM_TYPE_REAL32,
        )

        # Wait for parameter confirmation
        msg = vehicle.recv_match(type="PARAM_VALUE", blocking=True, timeout=5)
        if msg:
            # Handle param_id based on its type
            received_param_id = msg.param_id
            if isinstance(received_param_id, bytes):
                received_param_id = received_param_id.decode("utf-8")

            if received_param_id == param_name:
                print(f"Successfully set {param_name} to {param_value}")
            else:
                print(f"Received different parameter: {received_param_id}")
        else:
            print(f"No confirmation for {param_name}")

        time.sleep(1)


def set_mode(vehicle, mode):
    """Set the specified flight mode"""
    # Mode mappings for ArduPilot
    mode_mapping = {
        "STABILIZE": 0,
        "GUIDED": 4,
        "RTL": 6,
        "LAND": 9,
    }

    # Get the mode ID
    mode_id = mode_mapping.get(mode)
    if mode_id is None:
        print(f"Unknown mode: {mode}")
        return False

    print(f"Setting mode to {mode} (mode_id: {mode_id})")

    # Try both methods of setting mode
    vehicle.mav.command_long_send(
        vehicle.target_system,
        vehicle.target_component,
        mavutil.mavlink.MAV_CMD_DO_SET_MODE,
        0,
        mavutil.mavlink.MAV_MODE_FLAG_CUSTOM_MODE_ENABLED,
        mode_id,
        0,
        0,
        0,
        0,
        0,
    )

    vehicle.mav.set_mode_send(
        vehicle.target_system,
        mavutil.mavlink.MAV_MODE_FLAG_CUSTOM_MODE_ENABLED,
        mode_id,
    )

    # Repeat the command for reliability
    time.sleep(1)
    vehicle.mav.set_mode_send(
        vehicle.target_system,
        mavutil.mavlink.MAV_MODE_FLAG_CUSTOM_MODE_ENABLED,
        mode_id,
    )

    return True


def arm_vehicle(vehicle):
    """Arm the vehicle"""
    print("Arming vehicle...")
    vehicle.mav.command_long_send(
        vehicle.target_system,
        vehicle.target_component,
        mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM,
        0,
        1,
        0,
        0,
        0,
        0,
        0,
        0,
    )

    # Wait for command ACK
    msg = vehicle.recv_match(type="COMMAND_ACK", blocking=True, timeout=5)
    if msg and msg.command == mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM:
        if msg.result == mavutil.mavlink.MAV_RESULT_ACCEPTED:
            print("Vehicle armed successfully")
            return True
        else:
            print(f"Arm command rejected: result={msg.result}")
            return False
    else:
        print("No arming confirmation received on first attempt")

    # Send the command again for reliability
    time.sleep(1)
    vehicle.mav.command_long_send(
        vehicle.target_system,
        vehicle.target_component,
        mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM,
        0,
        1,
        0,
        0,
        0,
        0,
        0,
        0,
    )

    # Wait for command ACK again
    msg = vehicle.recv_match(type="COMMAND_ACK", blocking=True, timeout=5)
    if msg and msg.command == mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM:
        if msg.result == mavutil.mavlink.MAV_RESULT_ACCEPTED:
            print("Vehicle armed successfully on second attempt")
            return True
        else:
            print(f"Arm command rejected again: result={msg.result}")
            return False

    print("No arming confirmation received")
    return False


def get_current_position(vehicle):
    """Get the current position of the vehicle"""
    # Request position
    vehicle.mav.command_long_send(
        vehicle.target_system,
        vehicle.target_component,
        mavutil.mavlink.MAV_CMD_REQUEST_MESSAGE,
        0,
        mavutil.mavlink.MAVLINK_MSG_ID_GLOBAL_POSITION_INT,
        0,
        0,
        0,
        0,
        0,
        0,
    )

    # Wait for position message
    msg = vehicle.recv_match(type="GLOBAL_POSITION_INT", blocking=True, timeout=5)
    if msg:
        lat = msg.lat / 1e7
        lon = msg.lon / 1e7
        alt = msg.relative_alt / 1000  # Convert mm to meters
        print(f"Current position: Lat={lat}, Lon={lon}, Alt={alt}m")
        return lat, lon, alt
    else:
        print("Failed to get position")
        return None, None, None


def goto_position(vehicle, lat, lon, alt):
    """Go to specified position"""
    print(f"Going to position: Lat={lat}, Lon={lon}, Alt={alt}m")

    # Set GUIDED mode
    set_mode(vehicle, "GUIDED")

    # Send waypoint command
    vehicle.mav.mission_item_send(
        vehicle.target_system,
        vehicle.target_component,
        0,  # seq
        0,  # frame
        mavutil.mavlink.MAV_CMD_NAV_WAYPOINT,
        2,  # current - guided mode waypoint
        0,  # autocontinue
        0,
        0,
        0,
        0,  # param1-4
        lat,
        lon,
        alt,  # x, y, z
    )

    # Alternative method using SET_POSITION_TARGET_GLOBAL_INT
    vehicle.mav.set_position_target_global_int_send(
        0,  # timestamp
        vehicle.target_system,
        vehicle.target_component,
        mavutil.mavlink.MAV_FRAME_GLOBAL_RELATIVE_ALT_INT,
        0b0000111111111000,  # type mask (only positions enabled)
        int(lat * 1e7),
        int(lon * 1e7),
        alt,  # positions
        0,
        0,
        0,  # velocity
        0,
        0,
        0,  # acceleration
        0,
        0,  # yaw, yaw rate
    )

    # Send it again for reliability
    time.sleep(1)
    vehicle.mav.set_position_target_global_int_send(
        0,  # timestamp
        vehicle.target_system,
        vehicle.target_component,
        mavutil.mavlink.MAV_FRAME_GLOBAL_RELATIVE_ALT_INT,
        0b0000111111111000,  # type mask (only positions enabled)
        int(lat * 1e7),
        int(lon * 1e7),
        alt,  # positions
        0,
        0,
        0,  # velocity
        0,
        0,
        0,  # acceleration
        0,
        0,  # yaw, yaw rate
    )

    print("Waypoint command sent")
    return True


def get_distance_metres(lat1, lon1, lat2, lon2):
    """Calculate distance between two points using Haversine formula"""
    # Approximate radius of earth in meters
    R = 6371000

    # Convert latitude and longitude from degrees to radians
    lat1_rad = math.radians(lat1)
    lon1_rad = math.radians(lon1)
    lat2_rad = math.radians(lat2)
    lon2_rad = math.radians(lon2)

    # Haversine formula
    dlon = lon2_rad - lon1_rad
    dlat = lat2_rad - lat1_rad
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    distance = R * c

    return distance


def return_to_launch(vehicle):
    """Return to launch"""
    print("Returning to launch point (RTL mode)")
    set_mode(vehicle, "RTL")


def takeoff(vehicle, target_altitude):
    """Command the vehicle to takeoff to specified altitude"""
    print(f"Taking off to {target_altitude} meters...")

    # Send takeoff command
    vehicle.mav.command_long_send(
        vehicle.target_system,
        vehicle.target_component,
        mavutil.mavlink.MAV_CMD_NAV_TAKEOFF,
        0,
        0,
        0,
        0,
        0,
        0,
        0,
        target_altitude,  # The last parameter is target altitude
    )

    # Send the command again for reliability
    time.sleep(1)
    vehicle.mav.command_long_send(
        vehicle.target_system,
        vehicle.target_component,
        mavutil.mavlink.MAV_CMD_NAV_TAKEOFF,
        0,
        0,
        0,
        0,
        0,
        0,
        0,
        target_altitude,
    )

    print(f"Takeoff command sent to {target_altitude}m")

    # Wait for the vehicle to reach target altitude (with timeout)
    start_time = time.time()
    reached_altitude = False

    while time.time() - start_time < 60:  # 60 second timeout
        # Request position
        msg = vehicle.recv_match(type="GLOBAL_POSITION_INT", blocking=True, timeout=1)
        if msg:
            alt = msg.relative_alt / 1000  # Convert mm to meters
            print(f"Current altitude: {alt:.1f}m")

            # Consider target reached if within 1 meter
            if abs(alt - target_altitude) < 1.0:
                print(f"Reached target altitude of {target_altitude}m")
                reached_altitude = True
                break

        time.sleep(1)

    if not reached_altitude:
        print("Warning: Takeoff timeout - vehicle may not have reached target altitude")

    return reached_altitude


def main():
    # Connect to the vehicle
    vehicle = connect_vehicle()

    try:
        # Disable pre-arm checks
        disable_prearm_checks(vehicle)

        print("Waiting a moment for parameters to take effect...")
        time.sleep(3)

        # Send RC overrides to simulate RC input
        # send_rc_override(vehicle)

        # Set to GUIDED mode and wait for confirmation
        if not set_mode_and_wait(vehicle, "GUIDED"):
            print("Failed to enter" " GUIDED mode. Exiting.")
            return

        # Send RC override again
        # send_rc_override(vehicle)

        # Arm the vehicle
        if not arm_vehicle(vehicle):
            print("Failed to arm. Exiting.")
            return

        print("Successfully armed! Taking off...")

        # Continue sending RC overrides periodically to prevent disarming
        def rc_thread():
            while True:
                send_rc_override(vehicle)
                time.sleep(2)

        rc_override_thread = threading.Thread(target=rc_thread)
        rc_override_thread.daemon = True
        rc_override_thread.start()

        # Take off to 5 meters altitude
        if not takeoff(vehicle, 5):
            print("Takeoff may not have completed properly. Continuing anyway...")

        # Wait a moment after takeoff
        print("Waiting for stability after takeoff...")
        time.sleep(5)

        # Get the initial position
        init_lat, init_lon, init_alt = get_current_position(vehicle)
        if init_lat is None:
            print("Couldn't get initial position. Exiting.")
            return

        # Save initial position
        print(
            f"Saved initial position: Lat={init_lat}, Lon={init_lon}, Alt={init_alt}m"
        )

        # Calculate a point 100 meters north
        # Approximate 0.001 degrees as 111 meters (varies with latitude)
        target_lat = init_lat + (100 / 111111)
        target_lon = init_lon
        target_alt = 5  # Fixed altitude of 5 meters

        print(f"Target position: Lat={target_lat}, Lon={target_lon}, Alt={target_alt}m")

        # Go to the target position
        goto_position(vehicle, target_lat, target_lon, target_alt)

        # Wait for 15 seconds to allow vehicle to move
        print("Moving to target position... (waiting 15 seconds)")
        time.sleep(15)

        # Get current position to confirm movement
        current_lat, current_lon, current_alt = get_current_position(vehicle)
        if current_lat is not None:
            dist = get_distance_metres(init_lat, init_lon, current_lat, current_lon)
            print(f"Moved {dist:.2f} meters from starting position")

        # Wait for a few more seconds at the target
        print("Waiting at target for 5 seconds...")
        time.sleep(5)

        # Return to initial position
        print("Returning to initial position...")
        goto_position(vehicle, init_lat, init_lon, target_alt)

        # Wait for 15 seconds to allow vehicle to return
        print("Moving back to initial position... (waiting 15 seconds)")
        time.sleep(15)

        # Check final position
        final_lat, final_lon, final_alt = get_current_position(vehicle)
        if final_lat is not None:
            dist_from_start = get_distance_metres(
                init_lat, init_lon, final_lat, final_lon
            )
            print(f"Distance from starting position: {dist_from_start:.2f} meters")

        # Return to launch to finish the mission
        return_to_launch(vehicle)

    except Exception as e:
        print(f"Error: {e}")
        # Try to return home if an error occurs
        try:
            return_to_launch(vehicle)
        except:
            pass

    print("Mission complete!")


if __name__ == "__main__":
    main()
