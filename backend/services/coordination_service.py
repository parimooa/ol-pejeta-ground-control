import json
import math
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Optional

from backend.api.websockets.telemetry import telemetry_manager
from backend.config import CONFIG
from backend.core.flight_modes import FlightMode
from backend.schemas.survey import SurveyData
from backend.services.survey_service import survey_service
from backend.services.vehicle_service import vehicle_service
from backend.services.analytics_service import analytics_service

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
        self._survey_paused = False
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
        
        # Separate proximity tracking thread
        self._proximity_thread = None
        self._proximity_stop_event = threading.Event()
        self._proximity_tracking_active = False

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

            survey_data = SurveyData(
                id=survey_id,
                waypoints=list(drone.mission_waypoints.values()),
                vehicleId=str(drone.vehicle_id),
                completed_at=timestamp.isoformat(),
                mission_waypoint_id=self._survey_initiated_waypoint_id,
                survey_abandoned=survey_service.survey_abandoned,
                saved_at=timestamp.isoformat(),
                start_time=(
                    self._survey_start_time.isoformat()
                    if self._survey_start_time
                    else None
                ),
                end_time=(
                    self._survey_end_time.isoformat() if self._survey_end_time else None
                ),
            )

            # Convert the validated model to a dictionary for JSON storage.
            survey_data_to_save = survey_data.model_dump(exclude_none=True)

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
            existing_surveys.append(survey_data_to_save)

            # Save updated array to file
            with open(file_path, "w") as f:
                json.dump(existing_surveys, f, indent=2)

            print(f"Survey saved successfully: {filename}")
            print(f"File path: {file_path.absolute()}")
            print(f"Total surveys in file: {len(existing_surveys)}")
            print(f"Drone waypoints: {len(survey_data.waypoints)}")
            print(f"Closest car waypoint: {closest_waypoint_id}")
            print(f"Scan abandoned: {survey_data.survey_abandoned}")

            return True

        except Exception as e:
            import traceback

            print(f"Error saving survey file: {e}")
            traceback.print_exc()
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

                # Track analytics event
                analytics_service.track_coordination_event(
                    event_type="survey_start",
                    distance=distance,
                    drone_pos=drone_pos,
                    car_pos=car_pos,
                    metadata={"start_time": self._survey_start_time.isoformat()},
                )

                telemetry_manager.broadcast_event(
                    {
                        "event": "survey_started",
                        "start_time": self._survey_start_time.isoformat(),
                        "message": "Survey mission started",
                    }
                )

            # Check for survey completion
            if self._last_survey_mode_state and not is_surveying:
                self._survey_paused = False
                self._survey_end_time = datetime.now()
                print("Survey completed - drone switched back to GUIDED mode")

                # Calculate survey duration
                duration_seconds = None
                if self._survey_start_time:
                    duration_seconds = (
                        self._survey_end_time - self._survey_start_time
                    ).total_seconds()

                # Track analytics event for survey completion
                analytics_service.track_coordination_event(
                    event_type="survey_complete",
                    distance=distance,
                    drone_pos=drone_pos,
                    car_pos=car_pos,
                    duration_seconds=duration_seconds,
                    metadata={
                        "end_time": self._survey_end_time.isoformat(),
                        "abandoned": survey_service.survey_abandoned,
                    },
                )

                # Track mission effectiveness for completed survey
                self._track_mission_effectiveness(
                    drone, car, duration_seconds, survey_service.survey_abandoned
                )

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

            # Track enhanced vehicle telemetry for research (every 5th iteration to avoid spam)
            if hasattr(self, "_telemetry_counter"):
                self._telemetry_counter += 1
            else:
                self._telemetry_counter = 0

            if self._telemetry_counter % 5 == 0:  # Track every 5th loop iteration
                self._track_vehicle_telemetry(drone, car, distance)
            
            # Note: Proximity tracking is now handled by separate continuous thread

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

                        # Track analytics event for follow start
                        analytics_service.track_coordination_event(
                            event_type="follow_start",
                            distance=distance,
                            drone_pos=drone_pos,
                            car_pos=car_pos,
                            reason="coordination_active",
                        )

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
                    survey_service.survey_abandoned = True
                    self._survey_initiated_by_user = (
                        False  # Clear survey flag when abandoning
                    )

                    # Calculate survey duration for abandonment
                    duration_seconds = None
                    if self._survey_start_time:
                        duration_seconds = (
                            datetime.now() - self._survey_start_time
                        ).total_seconds()

                    # Track analytics event for survey abandonment
                    analytics_service.track_coordination_event(
                        event_type="survey_abandon",
                        distance=distance,
                        drone_pos=drone_pos,
                        car_pos=car_pos,
                        duration_seconds=duration_seconds,
                        reason="distance_exceeded",
                        metadata={"max_distance": self.max_distance},
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

                        # Track analytics event for follow stop
                        analytics_service.track_coordination_event(
                            event_type="follow_stop",
                            distance=distance,
                            drone_pos=drone_pos,
                            car_pos=car_pos,
                            reason="survey_in_progress",
                        )

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

    def _track_vehicle_telemetry(
        self, drone: "Vehicle", car: "Vehicle", distance: float
    ):
        """Track enhanced vehicle telemetry for research analysis"""
        try:
            # Track drone telemetry
            if drone and drone.vehicle:
                drone_pos = drone.position()
                if drone_pos:
                    # Calculate GPS precision estimate (simplified)
                    gps_precision = self._estimate_gps_precision(drone_pos)

                    # Calculate waypoint deviation
                    waypoint_deviation = self._calculate_waypoint_deviation(
                        drone, drone_pos
                    )

                    # Estimate communication quality
                    comm_quality = self._estimate_communication_quality(drone_pos)

                    analytics_service.track_vehicle_telemetry(
                        vehicle_id=drone.vehicle_id,
                        vehicle_type="drone",
                        position_data=drone_pos,
                        gps_precision_meters=gps_precision,
                        waypoint_deviation_meters=waypoint_deviation,
                        signal_strength_dbm=comm_quality.get("signal_strength"),
                        communication_latency_ms=comm_quality.get("latency"),
                        packet_loss_percentage=comm_quality.get("packet_loss"),
                    )

            # Track car telemetry
            if car and car.vehicle:
                car_pos = car.position()
                if car_pos:
                    # Calculate GPS precision estimate
                    gps_precision = self._estimate_gps_precision(car_pos)

                    # Calculate waypoint deviation
                    waypoint_deviation = self._calculate_waypoint_deviation(
                        car, car_pos
                    )

                    # Estimate communication quality
                    comm_quality = self._estimate_communication_quality(car_pos)

                    analytics_service.track_vehicle_telemetry(
                        vehicle_id=car.vehicle_id,
                        vehicle_type="car",
                        position_data=car_pos,
                        gps_precision_meters=gps_precision,
                        waypoint_deviation_meters=waypoint_deviation,
                        signal_strength_dbm=comm_quality.get("signal_strength"),
                        communication_latency_ms=comm_quality.get("latency"),
                        packet_loss_percentage=comm_quality.get("packet_loss"),
                    )

        except Exception as e:
            print(f"Error tracking vehicle telemetry: {e}")

    def _estimate_gps_precision(self, position_data: dict) -> float:
        """Estimate GPS precision based on available data"""
        # Simple estimation based on ground speed and system status
        ground_speed = position_data.get("ground_speed", 0)
        system_status = position_data.get("system_status", 0)

        # Better precision when stationary and armed
        base_precision = 2.5  # meters
        if ground_speed < 0.1:  # Stationary
            base_precision = 1.5
        if system_status == 4:  # Armed and active
            base_precision *= 0.8

        return base_precision

    def _calculate_waypoint_deviation(
        self, vehicle: "Vehicle", position_data: dict
    ) -> Optional[float]:
        """Calculate deviation from target waypoint"""
        try:
            current_wp_seq = position_data.get("current_mission_wp_seq")
            if current_wp_seq is None or not vehicle.mission_waypoints:
                return None

            # Get target waypoint
            target_wp = vehicle.mission_waypoints.get(current_wp_seq)
            if not target_wp:
                return None

            # Calculate distance to target waypoint
            current_lat = position_data.get("latitude")
            current_lon = position_data.get("longitude")
            target_lat = target_wp.get("lat")
            target_lon = target_wp.get("lon")

            if all([current_lat, current_lon, target_lat, target_lon]):
                return self._calculate_distance(
                    {"latitude": current_lat, "longitude": current_lon},
                    {"latitude": target_lat, "longitude": target_lon},
                )
        except Exception:
            pass
        return None

    def _estimate_communication_quality(self, position_data: dict) -> dict:
        """Estimate communication quality metrics"""
        # Simple estimation based on system health and battery
        battery_voltage = position_data.get("battery_voltage", 12.0)
        system_status = position_data.get("system_status", 0)

        # Signal strength estimation (-40 to -100 dBm)
        signal_strength = -50 - (
            abs(12.6 - battery_voltage) * 10
        )  # Lower voltage = weaker signal
        signal_strength = max(-100, min(-40, signal_strength))

        # Latency estimation (10-100ms)
        latency = 20 + (abs(12.6 - battery_voltage) * 15)
        if system_status != 4:  # Not fully operational
            latency += 30

        # Packet loss estimation (0-5%)
        packet_loss = (
            max(0, (12.6 - battery_voltage) * 2) if battery_voltage < 12.0 else 0
        )

        return {
            "signal_strength": signal_strength,
            "latency": latency,
            "packet_loss": packet_loss,
        }

    def _track_proximity_data(self, drone: "Vehicle", car: "Vehicle", distance: float, is_surveying: bool):
        """Track proximity data for heatmap analysis"""
        try:
            drone_pos = drone.position()
            car_pos = car.position()
            
            if not drone_pos.get("latitude") or not car_pos.get("latitude"):
                return
            
            # Determine activity states
            drone_activity_state = "surveying" if is_surveying else ("following" if self._is_following else "idle")
            
            # Estimate rover activity based on ground speed
            rover_speed = car_pos.get("ground_speed", 0)
            if rover_speed > 1.0:
                rover_activity_state = "moving"
            elif is_surveying:
                rover_activity_state = "surveying"
            else:
                rover_activity_state = "stationary"
            
            # Get communication quality
            comm_quality = self._estimate_communication_quality(drone_pos)
            
            # Determine if car is near a waypoint
            near_waypoint = self._is_near_waypoint(car, car_pos)
            
            # Track the proximity data point with enhanced scenario context
            analytics_service.track_proximity_data(
                drone_pos=drone_pos,
                rover_pos=car_pos,
                distance_meters=distance,
                drone_activity_state=drone_activity_state,
                rover_activity_state=rover_activity_state,
                survey_active=is_surveying,
                survey_paused=survey_service.is_paused,
                # Additional context
                terrain_type="grassland",  # Could be enhanced with GIS data
                weather_condition="clear",  # Could be enhanced with weather API
                communication_quality=comm_quality["signal_strength"],
                # Scenario-specific context
                coordination_active=self._is_active,
                current_waypoint_seq=car_pos.get("current_mission_wp_seq"),
                near_waypoint=near_waypoint,
                survey_abandoned=getattr(survey_service, 'survey_abandoned', False),
            )
            
        except Exception as e:
            print(f"Error tracking proximity data: {e}")

    def _is_near_waypoint(self, car: "Vehicle", car_pos: dict) -> bool:
        """Check if car is near its current target waypoint"""
        try:
            current_wp_seq = car_pos.get("current_mission_wp_seq")
            if current_wp_seq is None or not car.mission_waypoints:
                return False
            
            target_wp = car.mission_waypoints.get(current_wp_seq)
            if not target_wp:
                return False
            
            # Calculate distance to target waypoint
            waypoint_pos = {
                "latitude": target_wp.get("lat"),
                "longitude": target_wp.get("lon"),
            }
            distance_to_waypoint = self._calculate_distance(car_pos, waypoint_pos)
            
            # Consider "near" if within 20 meters of waypoint
            return distance_to_waypoint != -1 and distance_to_waypoint < 20
            
        except Exception:
            return False

    def _continuous_proximity_tracking_loop(self):
        """Continuous proximity tracking loop that runs independently of coordination status."""
        print("Continuous proximity tracking started.")
        while not self._proximity_stop_event.is_set():
            try:
                drone = vehicle_service.get_vehicle("drone")
                car = vehicle_service.get_vehicle("car")

                if not (drone and drone.vehicle and car and car.vehicle):
                    # Wait for vehicles to be connected
                    time.sleep(5)
                    continue

                drone_pos = drone.position()
                car_pos = car.position()

                distance = self._calculate_distance(drone_pos, car_pos)
                if distance == -1:
                    # Wait and try again if position data is missing
                    time.sleep(2)
                    continue

                # Only track meaningful proximity data (within 1km)
                if distance <= 1000:
                    # Check if drone is currently surveying
                    is_surveying = self._is_drone_surveying(drone)
                    
                    # Track proximity data with coordination and following states
                    self._track_proximity_data(drone, car, distance, is_surveying)

                # Sleep for proximity tracking interval (every 10 seconds)
                time.sleep(3)

            except Exception as e:
                print(f"Error in continuous proximity tracking: {e}")
                time.sleep(5)

        print("Continuous proximity tracking stopped.")

    def _track_mission_effectiveness(
        self, drone: "Vehicle", car: "Vehicle", duration_seconds: float, abandoned: bool
    ):
        """Track mission effectiveness metrics for  analysis"""
        try:
            if not duration_seconds:
                return

            # Calculate mission metrics
            mission_id = f"survey_{int(time.time())}"

            # Estimate distance traveled (simplified)
            distance_traveled = 0
            if drone and drone.mission_waypoints:
                # Rough estimate based on waypoint pattern
                waypoint_count = len(drone.mission_waypoints)
                if waypoint_count > 1:
                    # Assume average 50m between waypoints for survey pattern
                    distance_traveled = waypoint_count * 50

            # Calculate objectives
            total_waypoints = (
                len(drone.mission_waypoints) if drone and drone.mission_waypoints else 0
            )
            visited_waypoints = (
                len(drone.position().get("visited_waypoints", [])) if drone else 0
            )

            # Calculate coverage area (simplified rectangular estimate)
            area_covered = None
            if total_waypoints > 4:  # Minimum for rectangular pattern
                # Rough estimate: 200m x 100m survey area
                area_covered = 20000  # m²
                if abandoned:
                    # Reduce area if abandoned
                    completion_ratio = (
                        visited_waypoints / total_waypoints
                        if total_waypoints > 0
                        else 0
                    )
                    area_covered = area_covered * completion_ratio

            # Survey quality score (0-100)
            quality_score = 85  # Base quality
            if abandoned:
                quality_score = 60  # Lower quality for abandoned surveys
            if duration_seconds < 60:  # Very short surveys
                quality_score = 40
            elif duration_seconds > 600:  # Very long surveys might be comprehensive
                quality_score = 95

            # Calculate success metrics
            objectives_completed = (
                visited_waypoints if not abandoned else max(0, visited_waypoints - 2)
            )
            objectives_total = total_waypoints

            # Environmental context
            weather_conditions = "clear"  # TODO integrate Weather API
            terrain_difficulty = "moderate"  # TODO

            analytics_service.track_mission_effectiveness(
                mission_id=mission_id,
                mission_type="survey",
                mission_duration_seconds=duration_seconds,
                distance_traveled_meters=distance_traveled,
                objectives_completed=objectives_completed,
                objectives_total=objectives_total,
                area_covered_m2=area_covered,
                coverage_completeness_percentage=(
                    (visited_waypoints / total_waypoints * 100)
                    if total_waypoints > 0
                    else 0
                ),
                survey_quality_score=quality_score,
                weather_conditions=weather_conditions,
                terrain_difficulty=terrain_difficulty,
            )

        except Exception as e:
            print(f"Error tracking mission effectiveness: {e}")

    def is_active(self) -> bool:
        return self._is_active

    def is_following(self) -> bool:
        return self._is_following

    def is_survey_paused(self) -> bool:
        return self._survey_paused

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

        # Execute survey with a constrained pattern
        success = await survey_service.execute_proximity_survey(
            survey_center, max_distance_from_center=self.max_distance
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

        # Track system health - coordination service starting
        analytics_service.track_system_health(
            component="coordination_service", status="online", response_time_ms=None
        )

        # Ensure all vehicles have the current site name set
        for vehicle_type in ["drone", "car"]:
            vehicle = vehicle_service.get_vehicle(vehicle_type)
            if vehicle:
                vehicle.set_site_name(self.current_site_name)

        # Start coordination loop
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._coordination_loop, daemon=True)
        self._thread.start()
        self._is_active = True
        
        # Start continuous proximity tracking
        self._proximity_stop_event.clear()
        self._proximity_thread = threading.Thread(target=self._continuous_proximity_tracking_loop, daemon=True)
        self._proximity_thread.start()
        self._proximity_tracking_active = True
        
        telemetry_manager.broadcast_event({"event": "coordination_active"})
        return True

    def stop(self):
        if not self._is_active:
            print("Coordination service is not active.")
            return

        print("Stopping coordination service...")
        self._stop_event.set()

        # Track system health - coordination service stopping
        analytics_service.track_system_health(
            component="coordination_service", status="offline", response_time_ms=None
        )

        # Immediately mark as inactive
        self._is_active = False
        self._is_following = False
        self._survey_mode_detected = False
        self._last_survey_mode_state = False
        self._survey_button_enabled = False
        self._survey_initiated_by_user = False
        
        # Stop proximity tracking
        self._proximity_stop_event.set()
        self._proximity_tracking_active = False
        
        telemetry_manager.broadcast_event({"event": "coordination_stopped"})

        if self._thread:
            # Give it time to finish current iteration but not too long
            self._thread.join(timeout=10)
            if self._thread.is_alive():
                print("Warning: Coordination thread did not stop gracefully")
                
        if self._proximity_thread:
            # Give proximity thread time to stop
            self._proximity_thread.join(timeout=10)
            if self._proximity_thread.is_alive():
                print("Warning: Proximity tracking thread did not stop gracefully")
    
    def start_proximity_tracking(self):
        """Start only proximity tracking (independent of coordination service)"""
        if self._proximity_tracking_active:
            print("Proximity tracking is already active.")
            return False
            
        print("Starting continuous proximity tracking...")
        self._proximity_stop_event.clear()
        self._proximity_thread = threading.Thread(target=self._continuous_proximity_tracking_loop, daemon=True)
        self._proximity_thread.start()
        self._proximity_tracking_active = True
        return True
    
    def stop_proximity_tracking(self):
        """Stop only proximity tracking"""
        if not self._proximity_tracking_active:
            print("Proximity tracking is not active.")
            return
            
        print("Stopping proximity tracking...")
        self._proximity_stop_event.set()
        self._proximity_tracking_active = False
        
        if self._proximity_thread:
            self._proximity_thread.join(timeout=10)
            if self._proximity_thread.is_alive():
                print("Warning: Proximity tracking thread did not stop gracefully")


# Singleton instance
coordination_service = CoordinationService()
