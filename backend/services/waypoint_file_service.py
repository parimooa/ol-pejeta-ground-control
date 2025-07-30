import json
import os
from pathlib import Path
from typing import List, Optional, Dict, Any


class WaypointFileService:
    def __init__(self):
        self.surveyed_area_dir = Path("surveyed_area")
        self.surveyed_area_dir.mkdir(exist_ok=True)

    @staticmethod
    def generate_waypoint_filename(site_name: str, vehicle_id: str) -> str:
        """Generate filename for visited waypoints file"""
        clean_site_name = site_name.replace(" ", "-").replace("/", "-").lower()
        return f"site-{clean_site_name}-{vehicle_id}-visited-waypoints.json"

    def get_visited_waypoints_file_path(self, site_name: str, vehicle_id: str) -> Path:
        """Get the full path to the visited waypoints file"""
        filename = self.generate_waypoint_filename(site_name, vehicle_id)
        return self.surveyed_area_dir / filename

    def get_visited_waypoints(self, site_name: str, vehicle_id: str) -> List[int]:
        """Load visited waypoints from file"""
        file_path = self.get_visited_waypoints_file_path(site_name, vehicle_id)

        if not file_path.exists():
            return []

        try:
            with open(file_path, "r") as f:
                data = json.load(f)
                return data.get("visited_waypoints", [])
        except (json.JSONDecodeError, IOError) as e:
            print(f"Error reading waypoints file {file_path}: {e}")
            return []

    def update_visited_waypoint(
        self, site_name: str, vehicle_id: str, waypoint_seq: int
    ) -> bool:
        """Add a waypoint to the visited list and save to file"""
        file_path = self.get_visited_waypoints_file_path(site_name, vehicle_id)

        # Load existing data or create new
        visited_waypoints = self.get_visited_waypoints(site_name, vehicle_id)

        # Add new waypoint if not already present
        if waypoint_seq not in visited_waypoints:
            visited_waypoints.append(waypoint_seq)
            visited_waypoints.sort()  # Keep sorted for easier reading

        # Prepare data to save
        waypoint_data = {
            "site_name": site_name,
            "vehicle_id": vehicle_id,
            "visited_waypoints": visited_waypoints,
            "last_updated": self._get_current_timestamp(),
            "total_visited": len(visited_waypoints),
        }

        try:
            # Overwrite the file with updated data
            with open(file_path, "w") as f:
                json.dump(waypoint_data, f, indent=2)
            return True
        except IOError as e:
            print(f"Error writing waypoints file {file_path}: {e}")
            return False

    def clear_visited_waypoints(self, site_name: str, vehicle_id: str) -> bool:
        """Clear all visited waypoints for a site/vehicle combination"""
        file_path = self.get_visited_waypoints_file_path(site_name, vehicle_id)

        try:
            if file_path.exists():
                file_path.unlink()
                print(f"Cleared waypoints file: {file_path}")
            return True
        except IOError as e:
            print(f"Error clearing waypoints file {file_path}: {e}")
            return False

    def get_waypoint_progress(self, site_name: str, vehicle_id: str) -> Dict[str, Any]:
        """Get detailed progress information"""
        file_path = self.get_visited_waypoints_file_path(site_name, vehicle_id)

        if not file_path.exists():
            return {
                "visited_waypoints": [],
                "total_visited": 0,
                "last_updated": None,
                "file_exists": False,
            }

        try:
            with open(file_path, "r") as f:
                data = json.load(f)
                data["file_exists"] = True
                return data
        except (json.JSONDecodeError, IOError) as e:
            print(f"Error reading progress from {file_path}: {e}")
            return {
                "visited_waypoints": [],
                "total_visited": 0,
                "last_updated": None,
                "file_exists": False,
                "error": str(e),
            }

    @staticmethod
    def _get_current_timestamp() -> str:
        """Get the current timestamp in ISO format"""
        from datetime import datetime

        return datetime.now().isoformat()


waypoint_file_service = WaypointFileService()
