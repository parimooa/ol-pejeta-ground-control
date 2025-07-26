# Survey file storage models
from typing import List, Optional, Dict, Any

from pydantic import BaseModel, Field


class SurveyData(BaseModel):
    id: str
    waypoints: List[Dict[str, Any]]
    vehicleId: str = "unknown"
    completedAt: str
    siteName: Optional[str] = None
    closestWaypoint: Optional[int] = None
    filename: Optional[str] = None


class SaveSurveyRequest(BaseModel):
    filename: str = Field(..., description="Filename for the survey")
    data: SurveyData = Field(..., description="Survey data to save")


class DeleteSurveyRequest(BaseModel):
    filename: str = Field(..., description="Filename to delete")
