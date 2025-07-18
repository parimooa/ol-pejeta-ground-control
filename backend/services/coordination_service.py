import math
import threading
import time
from typing import TYPE_CHECKING

from backend.api.websockets.telemetry import telemetry_manager
from backend.core.flight_modes import FlightMode
from backend.services.vehicle_service import vehicle_service


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
            print(f"Distance: {distance:.1f}m")
            if distance == -1:
                print("Could not calculate distance, missing position data.")
                for _ in range(20):  # 20 * 0.1 = 2 seconds total
                    if self._stop_event.is_set():
                        break
                    time.sleep(0.1)
                continue

            # --- Trigger Logic ---
            if distance > self.max_distance and not self._is_following:
                if self._initiate_follow_sequence(drone):
                    self._is_following = True
                    telemetry_manager.broadcast_event(
                        {"event": "following_triggered", "distance": distance}
                    )
                else:
                    # Fault event is broadcast from within the helper method
                    print(
                        "CRITICAL: Follow sequence failed. Coordination will not engage."
                    )

            elif 0 < distance < 10 and self._is_following:
                print(
                    f"INFO: Distance {distance:.1f}m < {self.max_distance}m. Stopping follow mode."
                )
                # As a safe default, have the drone loiter or RTL.
                if drone.set_mode(FlightMode.LOITER):
                    self._is_following = False
                    telemetry_manager.broadcast_event(
                        {"event": "following_stopped", "distance": distance}
                    )

            # --- Action Logic ---
            if self._is_following:
                # Command the drone to the car's position
                car_lat = car_pos.get("latitude")
                car_lon = car_pos.get("longitude")
                if car_lat and car_lon:
                    drone.go_to_location(car_lat, car_lon, self.follow_altitude)

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
        telemetry_manager.broadcast_event({"event": "coordination_stopped"})

        if self._thread:
            # Give it time to finish current iteration but not too long
            self._thread.join(timeout=10)
            if self._thread.is_alive():
                print("Warning: Coordination thread did not stop gracefully")


# Singleton instance
coordination_service = CoordinationService()
