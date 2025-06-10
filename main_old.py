from pymavlink import mavutil
import time

connection_string = "udp:127.0.0.1:14551"
# Connect to the vehicle
vehicle = mavutil.mavlink_connection(
    connection_string
)  # Replace with your connection string
print("Waiting for heartbeat...")
vehicle.wait_heartbeat()
print(f"Connected to {vehicle.target_system} component {vehicle.target_component}")
print("Disabling pre-arm checks...")
params = [
    ("ARMING_CHECK", 0),  # Disable all arming checks
    ("BRD_SAFETYENABLE", 0),  # Disable safety switch
]


for param_name, param_value in params:
    vehicle.mav.param_set_send(
        vehicle.target_system,
        vehicle.target_component,
        param_name.encode("utf-8"),
        param_value,
        mavutil.mavlink.MAV_PARAM_TYPE_REAL32,
    )
    time.sleep(1)
vehicle.mav.command_long_send(
    vehicle.target_system,
    vehicle.target_component,
    mavutil.mavlink.MAV_CMD_DO_SET_MODE,
    0,
    mavutil.mavlink.MAV_MODE_FLAG_CUSTOM_MODE_ENABLED,
    4,
    0,
    0,
    0,
    0,
    0,
)
vehicle.mav.set_mode_send(
    vehicle.target_system, mavutil.mavlink.MAV_MODE_FLAG_CUSTOM_MODE_ENABLED, 4
)
time.sleep(1)
vehicle.mav.set_mode_send(
    vehicle.target_system, mavutil.mavlink.MAV_MODE_FLAG_CUSTOM_MODE_ENABLED, 4
)
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

print("Arm command sent")
print("Waiting 5 seconds after arming...")
time.sleep(5)
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
    target_lat = lat + (100 / 111111)
    target_lon = lon
    target_alt = 5  # Fixed altitude of 5 meters
else:
    print("Failed to get position")


vehicle.mav.command_long_send(
    vehicle.target_system,
    vehicle.target_component,
    mavutil.mavlink.MAV_CMD_DO_SET_MODE,
    0,
    mavutil.mavlink.MAV_MODE_FLAG_CUSTOM_MODE_ENABLED,
    4,
    0,
    0,
    0,
    0,
    0,
)
vehicle.mav.set_mode_send(
    vehicle.target_system, mavutil.mavlink.MAV_MODE_FLAG_CUSTOM_MODE_ENABLED, 4
)
time.sleep(1)
vehicle.mav.set_mode_send(
    vehicle.target_system, mavutil.mavlink.MAV_MODE_FLAG_CUSTOM_MODE_ENABLED, 4
)

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
    target_lat,
    target_lon,
    target_alt,  # x, y, z
)

# Alternative method using SET_POSITION_TARGET_GLOBAL_INT
vehicle.mav.set_position_target_global_int_send(
    0,  # timestamp
    vehicle.target_system,
    vehicle.target_component,
    mavutil.mavlink.MAV_FRAME_GLOBAL_RELATIVE_ALT_INT,
    0b0000111111111000,  # type mask (only positions enabled)
    int(target_lat * 1e7),
    int(target_lon * 1e7),
    target_alt,  # positions
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
    int(target_lat * 1e7),
    int(target_lon * 1e7),
    target_alt,  # positions
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
