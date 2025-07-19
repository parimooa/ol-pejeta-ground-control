import asyncio
import time
import math
from typing import Dict, List, Optional, Tuple
from ..models.waypoint import Waypoint
from .vehicle_service import vehicle_service

# Global scan abandon flag
scan_abandoned = False

# Lawnmower Pattern Configuration
SWATH_WIDTH = 5  # Spacing between scan lines in meters
PATTERN_LENGTH = 10  # Length of each lawnmower stripe in meters
MAX_RADIUS = 10  # The pattern will be a rectangle of PATTERN_LENGTH x (2 * MAX_RADIUS)


class SurveyService:
    """Service for coordinating car-drone survey missions"""

    def __init__(self):
        self.current_waypoint_index = 0
        self.mission_waypoints: List[Waypoint] = []
        self.scan_abandoned = False

    @staticmethod
    async def calculate_distance(pos1: Dict, pos2: Dict) -> float:
        """Calculate distance between two GPS coordinates using Haversine formula."""
        R = 6371000  # Earth radius in meters
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
        num_stripes = int((MAX_RADIUS * 2) / SWATH_WIDTH)

        for i in range(num_stripes + 1):
            y_offset = -MAX_RADIUS + (i * SWATH_WIDTH)
            x_start, x_end = -PATTERN_LENGTH / 2, PATTERN_LENGTH / 2
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
        timeout: int = 320,
        max_car_distance: float = 20,
    ) -> bool:
        """Generates lawnmower pattern and executes it in AUTO mode with car monitoring."""
        self.scan_abandoned = False  # Reset flag at start of scan

        # Get drone vehicle
        drone_vehicle = vehicle_service.get_vehicle("drone")
        car_vehicle = vehicle_service.get_vehicle(car_vehicle_type)

        if not drone_vehicle or not car_vehicle:
            return False

        print("\n--- Generating Lawnmower Scan Pattern ---")
        scan_waypoints = await self._generate_lawnmower_waypoints(
            center_waypoint, heading
        )
        num_scan_points = len(scan_waypoints)
        print(f"✅ Generated {num_scan_points} waypoints for the scan.")

        # Add a loiter waypoint at the end of the scan
        loiter_waypoint = {
            "lat": center_waypoint["lat"],
            "lon": center_waypoint["lon"],
            "alt": center_waypoint["alt"],
        }
        scan_waypoints.append(loiter_waypoint)

        # Convert to Waypoint objects for upload
        waypoint_objects = []
        for i, wp in enumerate(scan_waypoints):
            waypoint_objects.append(
                Waypoint(
                    seq=i,
                    lat=wp["lat"],
                    lon=wp["lon"],
                    alt=wp["alt"],
                    command=16,  # MAV_CMD_NAV_WAYPOINT
                    param1=0,
                    param2=0,
                    param3=0,
                    param4=0,
                )
            )

        # Upload mission to drone
        print("\n--- Uploading Lawnmower Mission to Drone ---")
        upload_success = drone_vehicle.upload_mission(waypoint_objects)
        if not upload_success:
            print("❌ Failed to upload scan mission to drone.")
            return False

        print("\n--- Executing Lawnmower Scan in AUTO Mode ---")
        if car_vehicle:
            print(
                f"🚗 Monitoring car position - will abandon scan if car moves > {max_car_distance}m from waypoint"
            )

        # Switch to AUTO mode to execute the mission
        from backend.core.flight_modes import FlightMode

        if not drone_vehicle.set_mode(FlightMode.AUTO):
            print("❌ Failed to set drone to AUTO mode.")
            return False

        # Start the mission
        if not drone_vehicle.start_mission():
            print("❌ Failed to start drone mission.")
            return False

        print("✅ Drone executing lawnmower scan mission")

        # Monitor mission progress and car position
        print("Drone executing scan mission in AUTO mode...")
        scan_start_time = time.time()
        mission_complete = False

        # Store initial car position for monitoring
        initial_car_pos = None
        if car_vehicle:
            initial_car_pos = await car_vehicle.position()
            if initial_car_pos:
                print(
                    f"🚗 Initial car position: {initial_car_pos['lat']:.6f}, {initial_car_pos['lon']:.6f}"
                )

        while time.time() - scan_start_time < timeout:
            # Check if mission is complete
            if drone_vehicle.is_mission_complete():
                print("✅ Lawnmower scan completed successfully!")
                # Automatically switch back to GUIDED mode
                print("🎮 Switching drone back to GUIDED mode...")
                drone_vehicle.set_mode(FlightMode.GUIDED)
                mission_complete = True
                break

            # Monitor car position if car_vehicle is provided
            if car_vehicle and initial_car_pos:
                current_car_pos = await car_vehicle.position()
                if current_car_pos:
                    # Calculate distance from initial car position to current car position
                    car_movement_distance = await self.calculate_distance(
                        initial_car_pos, current_car_pos
                    )

                    # Check if car has moved too far from the scan waypoint
                    if car_movement_distance > max_car_distance:
                        print(f"\n🚨 CAR MOVED TOO FAR FROM SCAN WAYPOINT!")
                        print(
                            f"🚗 Car moved {car_movement_distance:.1f}m from scan position (max: {max_car_distance}m)"
                        )
                        print(f"🚁 Abandoning scan...")

                        # Set global flag and switch to GUIDED mode
                        self.scan_abandoned = True
                        drone_vehicle.set_mode(FlightMode.GUIDED)
                        break
                    else:
                        # Show car monitoring status occasionally
                        elapsed_time = int(time.time() - scan_start_time)
                        if elapsed_time % 10 == 0:  # Every 10 seconds
                            print(
                                f"\r🔄 Scanning... Car distance: {car_movement_distance:.1f}m/{max_car_distance}m | Time: {elapsed_time}s",
                                end="",
                                flush=True,
                            )

            await asyncio.sleep(2)

        # Handle different completion scenarios
        if self.scan_abandoned:
            print(f"\n🚨 SCAN ABANDONED - Car moved too far!")
            print("🚁 Switching drone to GUIDED mode...")

            # Switch to GUIDED mode immediately
            if not drone_vehicle.set_mode(FlightMode.GUIDED):
                print("❌ Failed to switch drone to GUIDED mode.")
                return False

            print("✅ Drone ready to follow car position")
            return False  # Scan was abandoned

        elif mission_complete:
            # Mission completed successfully - already switched to GUIDED mode above
            await asyncio.sleep(2)
            return True
        else:
            # Timeout occurred without completion
            print("\n⚠️ Lawnmower scan timed out!")
            print("🎮 Switching drone back to GUIDED mode...")
            if not drone_vehicle.set_mode(FlightMode.GUIDED):
                print("❌ Failed to switch drone back to GUIDED mode.")
                return False
            await asyncio.sleep(2)
            return False

    async def execute_proximity_survey(
        self,
        center_waypoint: Dict,
        max_distance_from_center: float = 400,
        tolerance: float = 3.0,
        timeout: int = 320,
    ) -> bool:
        """Execute a proximity survey constrained to stay within max_distance_from_center."""
        self.scan_abandoned = False

        # Get drone vehicle
        drone_vehicle = vehicle_service.get_vehicle("drone")
        car_vehicle = vehicle_service.get_vehicle("car")

        if not drone_vehicle or not car_vehicle:
            return False

        print(
            f"\n--- Generating Proximity Survey Pattern (max {max_distance_from_center}m from center) ---"
        )

        # Generate constrained lawnmower pattern
        scan_waypoints = await self._generate_constrained_lawnmower_waypoints(
            center_waypoint, max_distance_from_center
        )

        num_scan_points = len(scan_waypoints)
        print(f"✅ Generated {num_scan_points} waypoints for proximity survey.")

        # Add loiter waypoint at the end
        loiter_waypoint = {
            "lat": center_waypoint["lat"],
            "lon": center_waypoint["lon"],
            "alt": center_waypoint["alt"],
        }
        scan_waypoints.append(loiter_waypoint)

        # Convert to Waypoint objects for upload
        waypoint_objects = []
        for i, wp in enumerate(scan_waypoints):
            waypoint_objects.append(
                Waypoint(
                    seq=i,
                    lat=wp["lat"],
                    lon=wp["lon"],
                    alt=wp["alt"],
                    command=16,  # MAV_CMD_NAV_WAYPOINT
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
            print("❌ Failed to upload proximity survey mission to drone.")
            return False

        print("\n--- Executing Proximity Survey in AUTO Mode ---")

        # Switch to AUTO mode using existing set_mode method
        from backend.core.flight_modes import FlightMode

        if not drone_vehicle.set_mode(FlightMode.AUTO):
            print("❌ Failed to set drone to AUTO mode.")
            return False

        # Start the mission
        if not drone_vehicle.start_mission():
            print("❌ Failed to start drone mission.")
            return False

        print("✅ Drone executing proximity survey mission")

        # Monitor mission progress
        print("🚁 Drone executing proximity survey...")
        scan_start_time = time.time()
        mission_complete = False

        # Store initial car position
        initial_car_pos = await car_vehicle.position()

        while time.time() - scan_start_time < timeout:
            # Check if mission is complete
            if drone_vehicle.is_mission_complete():
                print("✅ Proximity survey completed successfully!")
                # Automatically switch back to GUIDED mode
                print("🎮 Switching drone back to GUIDED mode...")
                drone_vehicle.set_mode(FlightMode.GUIDED)
                mission_complete = True
                break

            # Monitor car movement from survey center
            if car_vehicle and initial_car_pos:
                current_car_pos = await car_vehicle.position()
                if current_car_pos:
                    car_distance_from_center = await self.calculate_distance(
                        center_waypoint, current_car_pos
                    )

                    # Check if car moved too far from center (500m limit)
                    if car_distance_from_center > 500:
                        print(f"\n🚨 CAR MOVED TOO FAR FROM SURVEY CENTER!")
                        print(
                            f"🚗 Car is {car_distance_from_center:.1f}m from center (max: 500m)"
                        )
                        print(f"🚁 Abandoning proximity survey...")

                        self.scan_abandoned = True
                        drone_vehicle.set_mode(FlightMode.GUIDED)
                        break

            await asyncio.sleep(2)

        # Handle completion
        if self.scan_abandoned:
            print(f"\n🚨 PROXIMITY SURVEY ABANDONED!")
            drone_vehicle.set_mode(FlightMode.GUIDED)
            return False
        elif mission_complete:
            # Mission completed successfully - already switched to GUIDED mode above
            await asyncio.sleep(2)
            return True
        else:
            # Timeout occurred without completion
            print("\n⚠️ Proximity survey timed out!")
            print("🎮 Switching drone back to GUIDED mode...")
            drone_vehicle.set_mode(FlightMode.GUIDED)
            await asyncio.sleep(2)
            return False

    async def _generate_constrained_lawnmower_waypoints(
        self, center_point: Dict, max_distance: float
    ) -> List[Dict]:
        """Generate lawnmower pattern constrained within max_distance from center."""
        scan_waypoints = []

        # Calculate safe pattern dimensions to stay within max_distance
        # Use 80% of max distance for pattern radius for safety margin
        safe_radius = max_distance * 0.4  # Half the distance for radius

        # Adjust pattern size based on constraint
        pattern_length = min(PATTERN_LENGTH, safe_radius * 1.5)
        pattern_width = min(MAX_RADIUS * 2, safe_radius * 1.5)
        swath_width = SWATH_WIDTH

        print(
            f"Constrained pattern: {pattern_length}m x {pattern_width}m (max distance: {max_distance}m)"
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
        """Move vehicle to the next waypoint"""
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
        self.scan_abandoned = False


# Global instance
survey_service = SurveyService()
