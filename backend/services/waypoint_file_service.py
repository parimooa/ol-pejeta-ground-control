import json
import os
from datetime import datetime
from pathlib import Path
from typing import Set, Optional


class WaypointFileService:
    def __init__(self):
        self.base_dir = Path("surveyed_area")
        self.base_dir.mkdir(exist_ok=True)

    def generate_waypoint_filename(self, site_name: str, vehicle_id: str) -> str:
        """Generate filename for visited waypoints file"""
        # Clean site name
        clean_site_name = site_name.replace(" ", "-").replace("/", "-").lower()

        return f"site-{clean_site_name}-{vehicle_id}-visited-waypoints.json"

    def save_visited_waypoints(
        self, site_name: str, vehicle_id: str, visited_waypoints: Set[int]
    ) -> str:
        """Save visited waypoints to file"""
        filename = self.generate_waypoint_filename(site_name, vehicle_id)
        file_path = self.base_dir / filename

        waypoint_data = {
            "site_name": site_name,
            "vehicle_id": vehicle_id,
            "visited_waypoints": list(visited_waypoints),
            "timestamp": datetime.now().isoformat(),
            "total_visited": len(visited_waypoints),
        }

        with open(file_path, "w") as f:
            json.dump(waypoint_data, f, indent=2)

        print(f"Saved visited waypoints to {filename}")
        return filename

    def load_visited_waypoints(self, site_name: str, vehicle_id: str) -> Set[int]:
        """Load visited waypoints from file for this site and vehicle"""
        filename = self.generate_waypoint_filename(site_name, vehicle_id)
        file_path = self.base_dir / filename

        if not file_path.exists():
            return set()

        try:
            with open(file_path, "r") as f:
                data = json.load(f)
                visited_waypoints = set(data.get("visited_waypoints", []))
                print(
                    f"Loaded {len(visited_waypoints)} visited waypoints from {filename}"
                )
                return visited_waypoints
        except (json.JSONDecodeError, KeyError) as e:
            print(f"Error loading waypoints from {filename}: {e}")
            return set()

    def update_visited_waypoint(
        self, site_name: str, vehicle_id: str, waypoint_seq: int
    ) -> bool:
        """Add a single waypoint to the visited list and save incrementally"""
        if not site_name:
            print("Warning: Cannot save waypoint without site name")
            return False

        # Load existing waypoints
        visited_waypoints = self.load_visited_waypoints(site_name, vehicle_id)

        # Add new waypoint if not already visited
        if waypoint_seq not in visited_waypoints:
            visited_waypoints.add(waypoint_seq)

            # Save updated list
            try:
                self.save_visited_waypoints(site_name, vehicle_id, visited_waypoints)
                print(
                    f"Waypoint {waypoint_seq} saved for vehicle {vehicle_id} at site {site_name}"
                )
                return True
            except Exception as e:
                print(f"Failed to save waypoint {waypoint_seq}: {e}")
                return False
        else:
            print(f"Waypoint {waypoint_seq} already visited")
            return True

    def get_current_visited_file(
        self, site_name: str, vehicle_id: str
    ) -> Optional[str]:
        """Get the path to the visited waypoints file"""
        filename = self.generate_waypoint_filename(site_name, vehicle_id)
        file_path = self.base_dir / filename

        if file_path.exists():
            return str(file_path)
        return None


# Singleton instance
waypoint_file_service = WaypointFileService()
