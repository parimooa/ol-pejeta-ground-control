import math
import threading
import time
from typing import TYPE_CHECKING

from backend.api.websockets.telemetry import telemetry_manager
from backend.core.flight_modes import FlightMode
from backend.services.vehicle_service import vehicle_service
from backend.services.survey_service import survey_service


class CoordinationService:
    if TYPE_CHECKING:
        from backend.models.vehicle import Vehicle

    def __init__(self):
        self._thread = None
        self._stop_event = threading.Event()
        self._is_active = False
        self._is_following = False
        self.max_distance = 500  # meters
        self.follow_altitude = 30  # meters AGL
        self._survey_mode_detected = False
        self.proximity_threshold = 5  # meters for survey suggestion
        self._survey_button_enabled = False
        self._last_proximity_check = 0
        self._proximity_check_cooldown = 2  # seconds

    def _calculate_distance(self, pos1, pos2) -> float:
        """Calculate distance between two GPS coordinates using Haversine formula."""
        if not pos1.get("latitude") or not pos2.get("latitude"):
            return -1

        R = 6371000  # Earth radius in meters
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

    def _is_drone_surveying(self, drone: "Vehicle") -> bool:
        """Check if the drone is currently in survey mode (AUTO mode)."""
        if not drone or not drone.vehicle:
            return False

        # Get current drone telemetry
        telemetry = drone.get_current_telemetry()
        if not telemetry:
            return False

        # Check if drone is in AUTO mode (survey mode)
        current_mode = telemetry.get("custom_mode")
        return current_mode == FlightMode.AUTO.value

    def _check_proximity_and_update_ui(self, distance: float):
        """Check proximity and update survey button state."""
        current_time = time.time()

        # Throttle proximity checks to avoid spamming UI
        if current_time - self._last_proximity_check < self._proximity_check_cooldown:
            return

        self._last_proximity_check = current_time

        # Determine if survey button should be enabled
        should_enable = (
            distance <= self.proximity_threshold
            and distance > 0
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
            self._survey_mode_detected = is_surveying

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

            time.sleep(2)  # Loop runs every 2 seconds

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

        # Execute survey with constrained pattern
        success = await survey_service.execute_proximity_survey(
            survey_center,
            max_distance_from_center=self.max_distance
            * 0.8,  # 80% of max distance for safety
        )

        return success

    def start(self):
        if self._is_active:
            print("Coordination service is already active.")
            return False

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
        telemetry_manager.broadcast_event({"event": "coordination_stopped"})

        if self._thread:
            # Give it time to finish current iteration but not too long
            self._thread.join(timeout=10)
            if self._thread.is_alive():
                print("Warning: Coordination thread did not stop gracefully")


# Singleton instance
coordination_service = CoordinationService()
