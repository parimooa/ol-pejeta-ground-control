import json
import math
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

from backend.api.websockets.telemetry import telemetry_manager
from backend.core.flight_modes import FlightMode
from backend.services.survey_service import survey_service
from backend.services.vehicle_service import vehicle_service
from backend.config import CONFIG

try:
    from settings import site_name as configured_site_name
except ImportError:
    configured_site_name = CONFIG.site.DEFAULT_SITE_NAME


class CoordinationService:
    if TYPE_CHECKING:
        from backend.models.vehicle import Vehicle

    def __init__(self):
        self._thread = None
        self._stop_event = threading.Event()
        self._is_active = False
        self._is_following = False
        self.max_distance = CONFIG.coordination.MAX_FOLLOW_DISTANCE
        self.follow_altitude = CONFIG.coordination.FOLLOW_ALTITUDE
        self._survey_mode_detected = False
        self.proximity_threshold = CONFIG.coordination.PROXIMITY_THRESHOLD
        self._survey_button_enabled = False
        self._last_proximity_check = 0
        self._proximity_check_cooldown = CONFIG.coordination.PROXIMITY_CHECK_COOLDOWN
        self._last_survey_mode_state = False  # Track previous survey state
        self._survey_initiated_by_user = (
            False  # Track if we initiated the current survey
        )
        self.current_site_name = (
            configured_site_name  # Site name from settings for waypoint persistence
        )
        self._survey_start_time = None
        self._survey_end_time = None
        self._survey_initiated_waypoint_id = None

    @staticmethod
    def _calculate_distance(pos1, pos2) -> float:
        """Calculate the distance between two GPS coordinates using Haversine formula."""
        if not pos1.get("latitude") or not pos2.get("latitude"):
            return -1

        R = CONFIG.physical.EARTH_RADIUS_METERS
        lat1_rad = math.radians(pos1["latitude"])
        lon1_rad = math.radians(pos1["longitude"])
        lat2_rad = math.radians(pos2["latitude"])
        lon2_rad = math.radians(pos2["longitude"])

        dlat = lat2_rad - lat1_rad
        dlon = lon2_rad - lon1_rad
        a = (
            math.sin(dlat / 2) ** 2
            + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon / 2) ** 2
        )
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        return R * c

    def _find_closest_car_waypoint(self, car_position, car_waypoints):
        """Find the closest car waypoint to determine mission_waypoint_id."""
        if not car_waypoints or not car_position:
            return 1  # Default to waypoint 1

        closest_waypoint_id = 1
        shortest_distance = float("inf")

        for waypoint_id, waypoint in car_waypoints.items():
            waypoint_pos = {
                "latitude": waypoint.get("lat"),
                "longitude": waypoint.get("lon"),
            }
            distance = self._calculate_distance(car_position, waypoint_pos)

            if distance != -1 and distance < shortest_distance:
                shortest_distance = distance
                closest_waypoint_id = waypoint.get("seq", 1) + 1  # 1-indexed

        return closest_waypoint_id

    def _save_completed_survey(self, drone: "Vehicle", car: "Vehicle"):
        """Save completed survey data to JSON file."""
        try:
            # Ensure surveys directory exists
            surveys_dir = Path(CONFIG.directories.SURVEYED_AREA)
            surveys_dir.mkdir(exist_ok=True)

            # Get current timestamp
            timestamp = datetime.now()
            survey_id = f"survey_{drone.vehicle_id}_{int(timestamp.timestamp())}"

            duration_seconds = None
            duration_formatted = None

            if self._survey_start_time and self._survey_end_time:
                duration_seconds = (
                    self._survey_end_time - self._survey_start_time
                ).total_seconds()

                # Format duration as HH:MM:SS
                hours = int(duration_seconds // 3600)
                minutes = int((duration_seconds % 3600) // 60)
                seconds = int(duration_seconds % 60)
                duration_formatted = f"{hours:02d}:{minutes:02d}:{seconds:02d}"

                print(
                    f"Survey duration: {duration_formatted} ({duration_seconds:.1f} seconds)"
                )

            # Get car position for the closest waypoint calculation
            car_position = car.position()
            car_waypoints = car.mission_waypoints
            closest_waypoint_id = self._find_closest_car_waypoint(
                car_position, car_waypoints
            )

            # Generate filename
            site_name_clean = (
                self.current_site_name.replace(" ", "-").replace("/", "-").lower()
            )
            filename = f"site-{site_name_clean}-drone-surveyed-waypoints.json"

            # Prepare survey data
            survey_data = {
                "id": survey_id,
                "waypoints": [
                    {
                        "lat": wp.get("lat"),
                        "lon": wp.get("lon"),
                        "seq": wp.get("seq", i),
                    }
                    for i, wp in enumerate(drone.mission_waypoints.values())
                ],
                "vehicleId": str(drone.vehicle_id),
                "completedAt": timestamp.isoformat(),
                "mission_waypoint_id": self._survey_initiated_waypoint_id,
                "scan_abandoned": survey_service.scan_abandoned,
                "savedAt": timestamp.isoformat(),
                "startTime": (
                    self._survey_start_time.isoformat()
                    if self._survey_start_time
                    else None
                ),
                "endTime": (
                    self._survey_end_time.isoformat() if self._survey_end_time else None
                ),
                "durationSeconds": duration_seconds,
                "durationFormatted": duration_formatted,
            }

            # Load existing survey data if file exists
            file_path = surveys_dir / filename
            existing_surveys = []

            if file_path.exists():
                try:
                    with open(file_path, "r") as f:
                        existing_data = json.load(f)
                        if isinstance(existing_data, list):
                            existing_surveys = existing_data
                        elif isinstance(existing_data, dict):
                            existing_surveys = [existing_data]
                except (json.JSONDecodeError, IOError) as e:
                    print(f"Warning: Could not read existing file {filename}: {e}")
                    existing_surveys = []

            # Add new survey to array
            existing_surveys.append(survey_data)

            # Save updated array to file
            with open(file_path, "w") as f:
                json.dump(existing_surveys, f, indent=2)

            print(f"Survey saved successfully: {filename}")
            print(f"File path: {file_path.absolute()}")
            print(f"Total surveys in file: {len(existing_surveys)}")
            print(f"Drone waypoints: {len(survey_data['waypoints'])}")
            print(f"Closest car waypoint: {closest_waypoint_id}")
            print(f"Scan abandoned: {survey_service.scan_abandoned}")

            return True

        except Exception as e:
            print(f"Error saving survey file: {e}")
            return False

    def _is_drone_surveying(self, drone: "Vehicle") -> bool:
        """Check if the drone is currently actively surveying."""
        if not drone or not drone.vehicle:
            return False

        # Primary requirement: Survey must be initiated by  user from frontend
        if not self._survey_initiated_by_user:
            return False

        return not drone.is_mission_complete()  # Mission is complete

    def _check_proximity_and_update_ui(self, distance: float):
        """Check proximity and update survey button state."""
        current_time = time.time()

        # Throttle proximity checks to avoid spamming UI
        if current_time - self._last_proximity_check < self._proximity_check_cooldown:
            return

        self._last_proximity_check = current_time

        # Determine if survey button should be enabled
        should_enable = (
            self.proximity_threshold >= distance > 0
            and not self._survey_mode_detected
            and self._is_following
        )

        # Only broadcast if state changed
        if should_enable != self._survey_button_enabled:
            self._survey_button_enabled = should_enable
            telemetry_manager.broadcast_event(
                {
                    "event": "survey_button_state_changed",
                    "enabled": should_enable,
                    "distance": distance,
                    "threshold": self.proximity_threshold,
                }
            )

    def _coordination_loop(self):
        """The main background loop for monitoring and control."""
        print("Coordination loop started.")
        while not self._stop_event.is_set():
            drone = vehicle_service.get_vehicle("drone")
            car = vehicle_service.get_vehicle("car")

            if not (drone and drone.vehicle and car and car.vehicle):
                print("Coordination loop: Waiting for vehicles to be connected.")
                time.sleep(5)
                continue

            drone_pos = drone.position()
            car_pos = car.position()

            distance = self._calculate_distance(drone_pos, car_pos)
            if distance == -1:
                print("Could not calculate distance, missing position data.")
                for _ in range(20):  # 20 * 0.1 = 2 seconds total
                    if self._stop_event.is_set():
                        break
                    time.sleep(0.1)
                continue

            # Check if drone is currently surveying
            is_surveying = self._is_drone_surveying(drone)

            if is_surveying and not self._last_survey_mode_state:
                self._survey_start_time = datetime.now()
                print(f"Survey started at: {self._survey_start_time.isoformat()}")
                telemetry_manager.broadcast_event(
                    {
                        "event": "survey_started",
                        "start_time": self._survey_start_time.isoformat(),
                        "message": "Survey mission started",
                    }
                )

            # Check for survey completion (transition from surveying to not surveying)
            if self._last_survey_mode_state and not is_surveying:
                self._survey_end_time = datetime.now()
                print("Survey completed - drone switched back to GUIDED mode")

                # Save completed survey data to file
                if self._save_completed_survey(drone, car):
                    print("Survey data saved to file successfully")
                else:
                    print("Failed to save survey data to file")

                # Clear the survey flag when survey completes
                # self._survey_initiated_by_user = False
                telemetry_manager.broadcast_event(
                    {
                        "event": "survey_completed",
                        "end_time": self._survey_end_time.isoformat(),
                        "message": "Survey mission completed successfully",
                    }
                )

            self._survey_mode_detected = is_surveying
            self._last_survey_mode_state = is_surveying

            print(
                f"Distance: {distance:.1f}m | Surveying: {is_surveying} | Following: {self._is_following}"
            )

            # Check proximity for survey button state
            self._check_proximity_and_update_ui(distance)

            # --- COORDINATION LOGIC ---
            # When coordination is active:
            # 1. If NOT surveying -> always follow car
            # 2. If surveying and distance <= 500m -> let a survey continue
            # 3. If surveying and distance > 500m -> switch to follow mode (abandon a survey)

            if not is_surveying:
                # Not surveying - should always follow car when coordination is active
                if not self._is_following:
                    print("Drone not surveying - initiating follow mode")
                    if self._initiate_follow_sequence(drone):
                        self._is_following = True
                        telemetry_manager.broadcast_event(
                            {
                                "event": "following_triggered",
                                "reason": "coordination_active",
                                "distance": distance,
                            }
                        )
                    else:
                        print(
                            "CRITICAL: Follow sequence failed. Coordination will not engage."
                        )

                # If already following, continue following
                if self._is_following:
                    car_lat = car_pos.get("latitude")
                    car_lon = car_pos.get("longitude")
                    if car_lat and car_lon:
                        drone.go_to_location(car_lat, car_lon, self.follow_altitude)

            else:
                # Drone is surveying
                if distance > self.max_distance:
                    print(
                        f"Drone surveying but distance {distance:.1f}m > {self.max_distance}m - switching to follow mode"
                    )
                    # Abandon survey and switch to follow
                    survey_service.scan_abandoned = True
                    self._survey_initiated_by_user = (
                        False  # Clear survey flag when abandoning
                    )

                    if self._initiate_follow_sequence(drone):
                        self._is_following = True
                        telemetry_manager.broadcast_event(
                            {
                                "event": "survey_abandoned",
                                "reason": "distance_exceeded",
                                "distance": distance,
                            }
                        )
                        telemetry_manager.broadcast_event(
                            {
                                "event": "following_triggered",
                                "reason": "survey_abandoned",
                                "distance": distance,
                            }
                        )
                    else:
                        print("CRITICAL: Failed to switch from survey to follow mode.")
                else:
                    # Surveying and within distance - let survey continue
                    print(
                        f"Drone surveying within {self.max_distance}m - letting survey continue"
                    )
                    if self._is_following:
                        self._is_following = False
                        telemetry_manager.broadcast_event(
                            {
                                "event": "following_paused",
                                "reason": "survey_in_progress",
                                "distance": distance,
                            }
                        )

            time.sleep(CONFIG.coordination.LOOP_INTERVAL)

        print("Coordination loop stopped.")
        self._is_active = False
        self._is_following = False
        telemetry_manager.broadcast_event({"event": "coordination_stopped"})

    def _initiate_follow_sequence(self, drone: "Vehicle") -> bool:
        """
        Ensures the drone is armed and airborne before starting to follow.
        Returns True on success, False on failure.
        """
        is_armed = drone.position().get("armed")

        if not is_armed:
            print("Drone is not armed. Attempting to arm and takeoff...")

            # 1. Arm the vehicle
            if not drone.arm():
                telemetry_manager.broadcast_event(
                    {"event": "coordination_fault", "reason": "Failed to arm drone."}
                )
                return False

            # 2. Set GUIDED mode for takeoff
            if not drone.set_mode(FlightMode.GUIDED):
                telemetry_manager.broadcast_event(
                    {
                        "event": "coordination_fault",
                        "reason": "Failed to set GUIDED for takeoff.",
                    }
                )
                drone.disarm()  # Attempt to disarm for safety
                return False

            # 3. Takeoff to target altitude
            if not drone.takeoff(self.follow_altitude):
                telemetry_manager.broadcast_event(
                    {
                        "event": "coordination_fault",
                        "reason": f"Failed to takeoff to {self.follow_altitude}m.",
                    }
                )
                drone.disarm()  # Attempt to disarm for safety
                return False

        # At this point, the drone is armed and should be at or near takeoff altitude.
        # Now, switch to FOLLOW mode.
        print("Drone is armed and airborne. Setting FOLLOW mode.")
        if not drone.set_mode(FlightMode.GUIDED):
            telemetry_manager.broadcast_event(
                {
                    "event": "coordination_fault",
                    "reason": "Failed to set FOLLOW mode after takeoff.",
                }
            )
            return False

        print("Successfully entered FOLLOW mode.")
        return True

    def is_active(self) -> bool:
        return self._is_active

    def is_following(self) -> bool:
        return self._is_following

    def is_surveying(self) -> bool:
        """Check if drone is currently in survey mode."""
        return self._survey_mode_detected

    def is_survey_button_enabled(self) -> bool:
        """Check if survey button should be enabled."""
        return self._survey_button_enabled

    async def initiate_proximity_survey(self) -> bool:
        """Initiate a survey at the current vehicle position."""
        if not self._survey_button_enabled:
            print("Survey button not enabled - cannot initiate survey")
            return False

        drone = vehicle_service.get_vehicle("drone")
        car = vehicle_service.get_vehicle("car")

        if not (drone and car):
            print("Vehicles not available for survey")
            return False

        # Reset timing variables for new survey
        self._survey_start_time = None
        self._survey_end_time = None

        # Get current car position as survey center
        car_pos = car.position()
        if not car_pos or not car_pos.get("latitude"):
            print("Car position not available for survey")
            return False

        # Store original drone position for return
        drone_pos = drone.position()
        if drone_pos and drone_pos.get("latitude"):
            self._original_position = {
                "lat": drone_pos.get("latitude"),
                "lon": drone_pos.get("longitude"),
                "alt": self.follow_altitude,
            }
        car_waypoints = car.mission_waypoints
        self._survey_initiated_waypoint_id = self._find_closest_car_waypoint(
            car_pos, car_waypoints
        )

        # Use car position as survey center
        survey_center = {
            "lat": car_pos.get("latitude"),
            "lon": car_pos.get("longitude"),
            "alt": self.follow_altitude,
        }

        print(
            f"Initiating proximity survey at: {survey_center['lat']:.6f}, {survey_center['lon']:.6f}"
        )

        # Disable survey button while survey is active
        self._survey_button_enabled = False
        telemetry_manager.broadcast_event(
            {
                "event": "survey_button_state_changed",
                "enabled": False,
                "reason": "survey_initiated",
            }
        )

        # Mark that we initiated this survey
        self._survey_initiated_by_user = True

        # Execute  survey with a constrained pattern
        success = await survey_service.execute_proximity_survey(
            survey_center,
            max_distance_from_center=self.max_distance
            * 0.8,  # 80% of max distance for safety
        )

        # Clear the flag when survey completes
        self._survey_initiated_by_user = False

        return success

    def set_site_name(self, site_name: str):
        """Set the current site name for waypoint persistence across all vehicles."""
        self.current_site_name = site_name
        print(f"Site name set to: {site_name}")

        # Update all connected vehicles with the new site name
        for vehicle_type in ["drone", "car"]:
            vehicle = vehicle_service.get_vehicle(vehicle_type)
            if vehicle:
                vehicle.set_site_name(site_name)

    def start(self):
        if self._is_active:
            print("Coordination service is already active.")
            return False

        # Ensure all vehicles have the current site name set
        for vehicle_type in ["drone", "car"]:
            vehicle = vehicle_service.get_vehicle(vehicle_type)
            if vehicle:
                vehicle.set_site_name(self.current_site_name)

        self._stop_event.clear()
        self._thread = threading.Thread(target=self._coordination_loop, daemon=True)
        self._thread.start()
        self._is_active = True
        telemetry_manager.broadcast_event({"event": "coordination_active"})
        return True

    def stop(self):
        if not self._is_active:
            print("Coordination service is not active.")
            return

        print("Stopping coordination service...")
        self._stop_event.set()

        # Immediately mark as inactive
        self._is_active = False
        self._is_following = False
        self._survey_mode_detected = False
        self._last_survey_mode_state = False
        self._survey_button_enabled = False
        self._survey_initiated_by_user = False
        telemetry_manager.broadcast_event({"event": "coordination_stopped"})

        if self._thread:
            # Give it time to finish current iteration but not too long
            self._thread.join(timeout=10)
            if self._thread.is_alive():
                print("Warning: Coordination thread did not stop gracefully")


# Singleton instance
coordination_service = CoordinationService()
