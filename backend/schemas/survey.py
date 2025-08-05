# Survey file storage models
import math
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

from pydantic import BaseModel, Field, model_validator


class SurveyData(BaseModel):
    id: str
    waypoints: List[Dict[str, Any]]
    vehicleId: str = "unknown"
    completed_at: str
    mission_waypoint_id: Optional[int] = None
    survey_abandoned: bool
    saved_at: str
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    duration_seconds: Optional[float] = None
    duration_formatted: Optional[str] = None
    area_square_meters: Optional[float] = None

    @staticmethod
    def calculate_polygon_area(waypoints: List[Dict[str, Any]]) -> float:
        """Calculate the area of a polygon formed by waypoints using the Shoelace formula.

        Args:
            waypoints: List of waypoints with 'lat' and 'lon' keys

        Returns:
            Area in square meters
        """
        if len(waypoints) < 3:
            return 0.0

        # Convert lat/lon to local cartesian coordinates (meters)
        # Use the first waypoint as the origin
        origin = waypoints[0]
        local_points = []

        for wp in waypoints:
            # Convert degrees to meters using approximate conversion
            # 1 degree latitude ≈ 111,320 meters
            # 1 degree longitude ≈ 111,320 * cos(latitude) meters
            dlat = wp["lat"] - origin["lat"]
            dlon = wp["lon"] - origin["lon"]

            x = dlon * 111320.0 * math.cos(math.radians(origin["lat"]))
            y = dlat * 111320.0

            local_points.append((x, y))

        # Apply Shoelace formula
        n = len(local_points)
        area = 0.0

        for i in range(n):
            j = (i + 1) % n
            area += local_points[i][0] * local_points[j][1]
            area -= local_points[j][0] * local_points[i][1]

        return round(abs(area) / 2.0, 2)  # upto 2 decimals

    @model_validator(mode="after")
    def calculate_duration_and_area(self) -> "SurveyData":
        """
        Calculates and sets the duration_seconds, duration_formatted, area_square_meters,
        and area_hectares fields based on start_time, end_time, and waypoints.
        """
        # Calculate duration
        if self.start_time and self.end_time:
            try:
                start = datetime.fromisoformat(self.start_time)
                end = datetime.fromisoformat(self.end_time)
                duration = end - start

                # Ensure duration is not negative
                if duration.total_seconds() < 0:
                    duration = timedelta(seconds=0)

                self.duration_seconds = round(duration.total_seconds(), 2)

                # Format as HH:MM:SS
                hours, remainder = divmod(duration.total_seconds(), 3600)
                minutes, seconds = divmod(remainder, 60)
                self.duration_formatted = (
                    f"{int(hours):02d}:{int(minutes):02d}:{int(seconds):02d}"
                )
            except (ValueError, TypeError):
                # In case of parsing errors, leave duration fields as None
                self.duration_seconds = None
                self.duration_formatted = None

        # Calculate area if not already set and we have enough waypoints
        if self.area_square_meters is None and len(self.waypoints) >= 3:
            try:
                self.area_square_meters = self.calculate_polygon_area(self.waypoints)

            except (KeyError, TypeError, ValueError):
                # In case of missing lat/lon keys or other errors
                self.area_square_meters = 0.0
        elif self.area_square_meters is None:
            # Not enough waypoints for area calculation
            self.area_square_meters = 0.0

        return self


class ListSurveysResponse(BaseModel):
    surveys: List[SurveyData]


class SaveSurveyRequest(BaseModel):
    filename: str = Field(..., description="Filename for the survey")
    data: SurveyData = Field(..., description="Survey data to save")


class DeleteSurveyRequest(BaseModel):
    filename: str = Field(..., description="Filename to delete")


class SurveyInstance(BaseModel):
    """A compact representation of a single survey event for the timeline details."""

    id: str
    completed_at: str
    duration_formatted: Optional[str] = "N/A"
    survey_abandoned: bool
    waypoint_count: int = 0


class GroupedSurveyLog(BaseModel):
    """Represents a group of surveys for a single mission waypoint."""

    mission_waypoint_id: int
    survey_count: int
    last_surveyed_at: str
    instances: List[SurveyInstance]


class SurveyLogResponse(BaseModel):
    """The response model for the paginated survey logs endpoint."""

    logs: List[GroupedSurveyLog]
    total: int
