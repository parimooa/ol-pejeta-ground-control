import asyncio
import math
import time
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from pymavlink import mavutil

from backend.core.flight_modes import FlightMode
from .vehicle_service import vehicle_service
from .analytics_service import analytics_service
from ..config import CONFIG
from ..models.waypoint import Waypoint

# Global scan abandon flag
survey_abandoned = False


class SurveyService:
    """Service for coordinating car-drone survey missions"""

    def __init__(self):
        self.current_waypoint_index = 0
        self.mission_waypoints: List[Waypoint] = []
        self.survey_abandoned = False
        self.is_paused = False
        self.survey_in_progress = False

    async def pause_survey(self) -> bool:
        """Pause the ongoing survey using MAVLink mission pause."""
        drone_vehicle = vehicle_service.get_vehicle("drone")
        car_vehicle = vehicle_service.get_vehicle("car")
        
        if not drone_vehicle:
            print("Drone vehicle not available.")
            return False

        print("Pausing survey using MAVLink mission pause...")
        self.pause_time = datetime.now()

        # Get positions for analytics
        drone_pos = drone_vehicle.position()
        car_pos = car_vehicle.position() if car_vehicle else None
        distance = -1
        
        if drone_pos and car_pos:
            distance = await self.calculate_distance(
                {"lat": drone_pos.get("latitude", 0), "lon": drone_pos.get("longitude", 0)},
                {"lat": car_pos.get("latitude", 0), "lon": car_pos.get("longitude", 0)}
            )

        # Use set_mode with pause_mission=True to pause the mission
        success = False
        if drone_vehicle.set_mode(FlightMode.AUTO, pause_mission=True):
            self.is_paused = True
            success = True
            print("Survey paused successfully.")
        else:
            print("Failed to pause survey using MAVLink command.")
            # Fallback to LOITER mode
            print("Falling back to LOITER mode...")
            if drone_vehicle.set_mode(
                FlightMode.LOITER, loiter_altitude=CONFIG.survey.TAKEOFF_ALTITUDE
            ):
                self.is_paused = True
                success = True
                print("Survey paused using LOITER mode fallback.")
            else:
                print("Failed to pause survey with both methods.")

        # Track analytics event for survey pause
        if success:
            analytics_service.track_coordination_event(
                event_type="survey_pause",
                distance=distance,
                drone_pos=drone_pos,
                car_pos=car_pos,
                metadata={
                    "pause_time": self.pause_time.isoformat(),
                    "reason": "user_requested",
                    "method": "rest_api"
                }
            )

        return success

    async def resume_survey(self) -> bool:
        """Resume the paused survey."""
        drone_vehicle = vehicle_service.get_vehicle("drone")
        car_vehicle = vehicle_service.get_vehicle("car")
        
        if not drone_vehicle:
            print("Drone vehicle not available.")
            return False

        print("Resuming survey...")
        self.resume_time = datetime.now()
        
        # Calculate pause duration
        pause_duration_seconds = None
        if hasattr(self, 'pause_time') and self.pause_time:
            pause_duration_seconds = (self.resume_time - self.pause_time).total_seconds()

        # Get positions for analytics
        drone_pos = drone_vehicle.position()
        car_pos = car_vehicle.position() if car_vehicle else None
        distance = -1
        
        if drone_pos and car_pos:
            distance = await self.calculate_distance(
                {"lat": drone_pos.get("latitude", 0), "lon": drone_pos.get("longitude", 0)},
                {"lat": car_pos.get("latitude", 0), "lon": car_pos.get("longitude", 0)}
            )

        # Check current armed status and altitude
        position_data = drone_vehicle.position()
        is_armed = position_data.get("armed", False)
        current_altitude = position_data.get("relative_alt", 0)
        target_altitude = CONFIG.survey.TAKEOFF_ALTITUDE

        print(f"Current state: armed={is_armed}, altitude={current_altitude}m")

        # If not armed, arm the drone
        if not is_armed:
            print("Drone not armed - arming...")
            if not drone_vehicle.arm():
                print("Failed to arm drone.")
                return False
            print("Drone armed successfully.")
        else:
            print("Drone already armed.")

        # Check if we need to take off (if altitude is significantly below target)
        altitude_threshold = 2.0  # meters - consider "on ground" if below this
        if current_altitude < altitude_threshold:
            print(f"Taking off to {target_altitude}m...")
            if not drone_vehicle.takeoff(target_altitude):
                print("Failed to takeoff.")
                drone_vehicle.disarm()
                return False
            print(f"Takeoff successful to {target_altitude}m.")
        else:
            print(
                f"Already at sufficient altitude ({current_altitude}m), skipping takeoff."
            )

        # Try to continue the mission using MAVLink continue command
        success = False
        print("Attempting to continue mission using MAVLink...")
        if drone_vehicle.set_mode(FlightMode.AUTO, pause_mission=False):
            self.is_paused = False
            success = True
            print("Survey resumed successfully using MAVLink continue.")
        else:
            # Fallback to setting AUTO mode directly
            print("MAVLink continue failed, falling back to AUTO mode...")
            if drone_vehicle.set_mode(FlightMode.AUTO):
                self.is_paused = False
                success = True
                print("Survey resumed using AUTO mode fallback.")
            else:
                print("Failed to resume survey with both methods.")

        # Track analytics event for survey resume
        if success:
            analytics_service.track_coordination_event(
                event_type="survey_resume",
                distance=distance,
                drone_pos=drone_pos,
                car_pos=car_pos,
                duration_seconds=pause_duration_seconds,
                metadata={
                    "resume_time": self.resume_time.isoformat(),
                    "pause_duration_seconds": pause_duration_seconds,
                    "reason": "user_requested",
                    "method": "rest_api"
                }
            )

        return success

    @staticmethod
    async def calculate_distance(pos1: Dict, pos2: Dict) -> float:
        """Calculate distance between two GPS coordinates using Haversine formula."""
        R = CONFIG.physical.EARTH_RADIUS_METERS
        lat1_rad, lat2_rad = math.radians(pos1["lat"]), math.radians(pos2["lat"])
        dlat = math.radians(pos2["lat"] - pos1["lat"])
        dlon = math.radians(pos2["lon"] - pos1["lon"])
        a = (
            math.sin(dlat / 2) ** 2
            + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon / 2) ** 2
        )
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        return R * c

    async def calculate_bearing(self, pos1: Dict, pos2: Dict) -> float:
        """Calculate the bearing from position 1 to position 2."""
        lat1_rad, lon1_rad = math.radians(pos1["lat"]), math.radians(pos1["lon"])
        lat2_rad, lon2_rad = math.radians(pos2["lat"]), math.radians(pos2["lon"])
        dLon = lon2_rad - lon1_rad

        y = math.sin(dLon) * math.cos(lat2_rad)
        x = math.cos(lat1_rad) * math.sin(lat2_rad) - math.sin(lat1_rad) * math.cos(
            lat2_rad
        ) * math.cos(dLon)

        bearing_rad = math.atan2(y, x)
        return (math.degrees(bearing_rad) + 360) % 360

    @staticmethod
    def bearing_to_direction(bearing: float) -> str:
        """Converts a bearing in degrees to a compass direction string."""
        val = int((bearing / 45) + 0.5)
        directions = [
            "North",
            "Northeast",
            "East",
            "Southeast",
            "South",
            "Southwest",
            "West",
            "Northwest",
        ]
        return directions[val % 8]

    @staticmethod
    def _meters_to_latlon_offset(
        dx_meters: float, dy_meters: float, reference_lat: float
    ) -> Tuple[float, float]:
        """Converts meters offset to latitude/longitude offset."""
        dlat = dy_meters / 111320.0  # Approximate meters per degree latitude
        dlon = dx_meters / (111320.0 * math.cos(math.radians(reference_lat)))
        return dlat, dlon

    async def _generate_lawnmower_waypoints(
        self, center_point: Dict, heading_deg: float
    ) -> List[Dict]:
        """Generates a rotated lawnmower pattern around a center point."""
        scan_waypoints = []
        # The angle for the pattern lines should be perpendicular to the vehicle's heading
        pattern_angle_rad = math.radians((heading_deg + 90) % 360)
        num_stripes = int((CONFIG.survey.MAX_RADIUS * 2) / CONFIG.survey.SWATH_WIDTH)

        for i in range(num_stripes + 1):
            y_offset = -CONFIG.survey.MAX_RADIUS + (i * CONFIG.survey.SWATH_WIDTH)
            x_start, x_end = (
                -CONFIG.survey.PATTERN_LENGTH / 2,
                CONFIG.survey.PATTERN_LENGTH / 2,
            )
            if i % 2 != 0:
                x_start, x_end = x_end, x_start

            for x_offset in [x_start, x_end]:
                xr = x_offset * math.cos(pattern_angle_rad) - y_offset * math.sin(
                    pattern_angle_rad
                )
                yr = x_offset * math.sin(pattern_angle_rad) + y_offset * math.cos(
                    pattern_angle_rad
                )
                dlat, dlon = self._meters_to_latlon_offset(xr, yr, center_point["lat"])
                scan_waypoints.append(
                    {
                        "lat": center_point["lat"] + dlat,
                        "lon": center_point["lon"] + dlon,
                        "alt": center_point["alt"],
                    }
                )
        return scan_waypoints

    async def execute_lawnmower_scan(
        self,
        center_waypoint: Dict,
        heading: float,
        car_vehicle_type: str = "car",
        tolerance: float = 3.0,
        timeout: int = CONFIG.survey.TIMEOUT_SECONDS,
        max_car_distance: float = 20,
    ) -> bool:
        """Generates a lawnmower pattern and executes it in AUTO mode with car monitoring."""
        self.survey_abandoned = False
        self.is_paused = False
        self.survey_in_progress = True

        # Get drone vehicle
        drone_vehicle = vehicle_service.get_vehicle("drone")
        car_vehicle = vehicle_service.get_vehicle(car_vehicle_type)

        if not drone_vehicle or not car_vehicle:
            self.survey_in_progress = False
            return False

        print("\n--- Generating Lawnmower Scan Pattern ---")
        scan_waypoints = await self._generate_lawnmower_waypoints(
            center_waypoint, heading
        )
        num_scan_points = len(scan_waypoints)
        print(f"Generated {num_scan_points} waypoints for the scan.")

        waypoint_objects = []
        for i, wp in enumerate(scan_waypoints):
            waypoint_objects.append(
                Waypoint(
                    seq=i,
                    lat=wp["lat"],
                    lon=wp["lon"],
                    alt=wp["alt"],
                    command=mavutil.mavlink.MAV_CMD_NAV_WAYPOINT,
                    param1=0,
                    param2=0,
                    param3=0,
                    param4=0,
                )
            )

        loiter_radius = CONFIG.survey.LOITER_RADIUS_STANDARD
        waypoint_objects.append(
            Waypoint(
                seq=len(scan_waypoints),
                lat=center_waypoint["lat"],
                lon=center_waypoint["lon"],
                alt=center_waypoint["alt"],
                command=mavutil.mavlink.MAV_CMD_NAV_LOITER_UNLIM,
                param1=0,
                param2=loiter_radius,
                param3=0,
                param4=0,
            )
        )

        print("\n--- Uploading Lawnmower Mission to Drone ---")
        upload_success = drone_vehicle.upload_mission(waypoint_objects)
        if not upload_success:
            print("Failed to upload scan mission to drone.")
            self.survey_in_progress = False
            return False

        print("\n--- Executing Lawnmower Scan in AUTO Mode ---")
        if car_vehicle:
            print(
                f"Monitoring car position - will abandon scan if car moves > {max_car_distance}m from waypoint"
            )

        if not drone_vehicle.set_mode(FlightMode.AUTO):
            print("Failed to set drone to AUTO mode.")
            self.survey_in_progress = False
            return False

        if not drone_vehicle.start_mission():
            print("Failed to start drone mission.")
            self.survey_in_progress = False
            return False

        print("Drone executing lawnmower scan mission")

        scan_start_time = time.time()
        mission_complete = False

        initial_car_pos = None
        if car_vehicle:
            initial_car_pos = await car_vehicle.position()
            if initial_car_pos:
                print(
                    f"Initial car position: {initial_car_pos['lat']:.6f}, {initial_car_pos['lon']:.6f}"
                )

        while time.time() - scan_start_time < timeout:
            if self.is_paused:
                scan_start_time += 1
                await asyncio.sleep(1)
                continue

            if drone_vehicle.is_mission_complete():
                print("Lawnmower scan completed successfully!")
                print("Switching drone back to GUIDED mode...")
                drone_vehicle.set_mode(FlightMode.GUIDED)
                mission_complete = True
                break

            if car_vehicle and initial_car_pos:
                current_car_pos = await car_vehicle.position()
                if current_car_pos:
                    car_movement_distance = await self.calculate_distance(
                        initial_car_pos, current_car_pos
                    )

                    if car_movement_distance > max_car_distance:
                        print(f"\n🚨 CAR MOVED TOO FAR FROM SCAN WAYPOINT!")
                        print(
                            f"🚗 Car moved {car_movement_distance:.1f}m from scan position (max: {max_car_distance}m)"
                        )
                        print(f"🚁 Abandoning scan...")
                        self.survey_abandoned = True
                        drone_vehicle.set_mode(FlightMode.GUIDED)
                        break
                    else:
                        elapsed_time = int(time.time() - scan_start_time)
                        if elapsed_time % CONFIG.survey.PROGRESS_UPDATE_INTERVAL == 0:
                            print(
                                f"\r🔄 Scanning... Car distance: {car_movement_distance:.1f}m/{max_car_distance}m | Time: {elapsed_time}s",
                                end="",
                                flush=True,
                            )

            await asyncio.sleep(2)

        if self.survey_abandoned:
            print(f"\nSCAN ABANDONED - Car moved too far!")
            print("Switching drone to GUIDED mode...")
            if not drone_vehicle.set_mode(FlightMode.GUIDED):
                print("Failed to switch drone to GUIDED mode.")
            self.survey_in_progress = False
            return False

        elif mission_complete:
            await asyncio.sleep(2)
            self.survey_in_progress = False
            return True
        else:
            print("\nLawnmower scan timed out!")
            print("Switching drone back to GUIDED mode...")
            if not drone_vehicle.set_mode(FlightMode.GUIDED):
                print("Failed to switch drone back to GUIDED mode.")
            self.survey_in_progress = False
            return False

    async def execute_proximity_survey(
        self,
        center_waypoint: Dict,
        max_distance_from_center: float = CONFIG.survey.MAX_RADIUS,
        tolerance: float = 3.0,
        timeout: int = 320,
    ) -> bool:
        """Execute a proximity survey constrained to stay within max_distance_from_center."""
        self.survey_abandoned = False
        survey_result = False

        # Get drone vehicle
        drone_vehicle = vehicle_service.get_vehicle("drone")
        car_vehicle = vehicle_service.get_vehicle("car")

        if not drone_vehicle or not car_vehicle:
            return False
        return_home_position = drone_vehicle.position()
        if not return_home_position or not return_home_position.get("latitude"):
            print("Could not get drone's current position to set as return point.")
            return False

        print(
            f"Setting return point to current drone position: {return_home_position['latitude']:.6f}, {return_home_position['longitude']:.6f}"
        )
        print(
            f"\n--- Generating Proximity Survey Pattern (max {max_distance_from_center}m from center) ---"
        )

        # Generate constrained lawnmower pattern
        scan_waypoints = await self._generate_constrained_lawnmower_waypoints(
            center_waypoint, max_distance_from_center
        )

        num_scan_points = len(scan_waypoints)
        print(f"Generated {num_scan_points} waypoints for proximity survey.")

        # Convert to Waypoint objects for upload
        waypoint_objects = []

        # Add regular waypoints for the proximity survey pattern
        for i, wp in enumerate(scan_waypoints):
            waypoint_objects.append(
                Waypoint(
                    seq=i,
                    lat=wp["lat"],
                    lon=wp["lon"],
                    alt=wp["alt"],
                    command=mavutil.mavlink.MAV_CMD_NAV_WAYPOINT,
                    param1=0,
                    param2=0,
                    param3=0,
                    param4=0,
                )
            )

        # Add unlimited loiter waypoint at the end of the proximity survey
        loiter_radius = CONFIG.survey.LOITER_RADIUS_PROXIMITY
        waypoint_objects.append(
            Waypoint(
                seq=len(scan_waypoints),
                lat=return_home_position["latitude"],
                lon=return_home_position["longitude"],
                # Use the drone's current altitude for the return trip
                alt=return_home_position.get("relative_altitude")
                or center_waypoint["alt"],
                command=mavutil.mavlink.MAV_CMD_NAV_WAYPOINT,
                param1=0,
                param2=0,
                param3=0,
                param4=0,
            )
        )

        # Upload mission to drone
        print("\n--- Uploading Proximity Survey Mission to Drone ---")
        upload_success = drone_vehicle.upload_mission(waypoint_objects)
        if not upload_success:
            print("Failed to upload proximity survey mission to drone.")
            return False

        print("\n--- Executing Proximity Survey in AUTO Mode ---")

        # Switch to AUTO mode using existing set_mode method
        if not drone_vehicle.set_mode(FlightMode.AUTO):
            print("Failed to set drone to AUTO mode.")
            return False

        # Start the mission
        if not drone_vehicle.start_mission():
            print("Failed to start drone mission.")
            return False

    async def _generate_constrained_lawnmower_waypoints(
        self, center_point: Dict, max_distance: float
    ) -> List[Dict]:
        """Generate lawnmower pattern constrained within max_distance from center."""
        scan_waypoints = []

        # To maximize the survey area, we'll create a square pattern that fits
        # snugly within the circular `max_distance` constraint.
        # The side of a square inscribed in a circle of radius 'r' is r * sqrt(2).
        # We use a 99% factor for a small safety margin against GPS drift.
        side_length = max_distance * math.sqrt(2) * 0.99

        # Adjust pattern size based on the calculated side_length and global config limits
        pattern_length = min(CONFIG.survey.PATTERN_LENGTH, side_length)
        pattern_width = min(CONFIG.survey.MAX_RADIUS * 2, side_length)
        swath_width = CONFIG.survey.SWATH_WIDTH

        print(
            f"Constrained pattern: {pattern_length:.1f}m x {pattern_width:.1f}m (max distance: {max_distance}m)"
        )

        num_stripes = int(pattern_width / swath_width)

        for i in range(num_stripes + 1):
            y_offset = -pattern_width / 2 + (i * swath_width)
            x_start, x_end = -pattern_length / 2, pattern_length / 2
            if i % 2 != 0:
                x_start, x_end = x_end, x_start

            for x_offset in [x_start, x_end]:
                # Convert meters to lat/lon offset
                dlat, dlon = self._meters_to_latlon_offset(
                    x_offset, y_offset, center_point["lat"]
                )

                waypoint_lat = center_point["lat"] + dlat
                waypoint_lon = center_point["lon"] + dlon

                # Verify waypoint is within constraint
                waypoint_dict = {"lat": waypoint_lat, "lon": waypoint_lon}
                distance_from_center = await self.calculate_distance(
                    center_point, waypoint_dict
                )

                if distance_from_center <= max_distance:
                    scan_waypoints.append(
                        {
                            "lat": waypoint_lat,
                            "lon": waypoint_lon,
                            "alt": center_point["alt"],
                        }
                    )
                else:
                    print(
                        f"Skipping waypoint {distance_from_center:.1f}m from center (exceeds {max_distance}m)"
                    )

        return scan_waypoints

    async def get_next_waypoint_info(self, vehicle_type: str = "car") -> Optional[Dict]:
        """Get information about the next waypoint"""
        vehicle = vehicle_service.get_vehicle(vehicle_type)
        if not vehicle or self.current_waypoint_index >= len(self.mission_waypoints):
            return None

        target_waypoint = self.mission_waypoints[self.current_waypoint_index]
        current_pos = await vehicle.position()

        if not current_pos:
            return None

        distance = await self.calculate_distance(
            current_pos,
            {
                "lat": target_waypoint.lat,
                "lon": target_waypoint.lon,
                "alt": target_waypoint.alt,
            },
        )

        bearing = await self.calculate_bearing(
            current_pos,
            {
                "lat": target_waypoint.lat,
                "lon": target_waypoint.lon,
                "alt": target_waypoint.alt,
            },
        )

        direction = self.bearing_to_direction(bearing)

        return {
            "waypoint_index": self.current_waypoint_index,
            "waypoint_number": self.current_waypoint_index + 1,
            "total_waypoints": len(self.mission_waypoints),
            "target_waypoint": target_waypoint,
            "distance": distance,
            "bearing": bearing,
            "direction": direction,
        }

    async def move_to_next_waypoint(self, vehicle_type: str = "car") -> bool:
        """Move the vehicle to the next waypoint"""
        vehicle = vehicle_service.get_vehicle(vehicle_type)
        if not vehicle or self.current_waypoint_index >= len(self.mission_waypoints):
            return False

        target_waypoint = self.mission_waypoints[self.current_waypoint_index]

        # Send move command (this would need to be implemented in your Vehicle class)
        # For now, just return True
        return True

    async def advance_to_next_waypoint(self) -> bool:
        """Advance to the next waypoint in the mission"""
        if self.current_waypoint_index < len(self.mission_waypoints) - 1:
            self.current_waypoint_index += 1
            return True
        return False

    def set_mission_waypoints(self, waypoints: List[Waypoint]):
        """Set the mission waypoints"""
        self.mission_waypoints = waypoints
        self.current_waypoint_index = 0

    def reset_mission(self):
        """Reset the mission to the beginning"""
        self.current_waypoint_index = 0
        self.survey_abandoned = False


# Global instance
survey_service = SurveyService()
