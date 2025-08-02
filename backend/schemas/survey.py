# Survey file storage models
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

from pydantic import BaseModel, Field, model_validator


class SurveyData(BaseModel):
    id: str
    waypoints: List[Dict[str, Any]]
    vehicleId: str = "unknown"
    completed_at: str
    mission_waypoint_id: Optional[int] = None
    scan_abandoned: bool
    saved_at: str
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    duration_seconds: Optional[float] = None
    duration_formatted: Optional[str] = None

    @model_validator(mode="after")
    def calculate_duration(self) -> "SurveyData":
        """
        Calculates and sets the duration_seconds and duration_formatted fields
        based on start_time and end_time.
        """
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
        return self


class ListSurveysResponse(BaseModel):
    surveys: List[SurveyData]


class SaveSurveyRequest(BaseModel):
    filename: str = Field(..., description="Filename for the survey")
    data: SurveyData = Field(..., description="Survey data to save")


class DeleteSurveyRequest(BaseModel):
    filename: str = Field(..., description="Filename to delete")
