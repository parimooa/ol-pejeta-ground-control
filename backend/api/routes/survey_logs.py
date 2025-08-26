from fastapi import APIRouter, HTTPException, Query

from backend.services.survey_log_service import survey_log_service
from backend.schemas.survey import SurveyLogResponse

router = APIRouter(prefix="/survey-logs", tags=["Survey Logs"])


# TODO Revisit, this may not be needed
@router.get("/", response_model=SurveyLogResponse)
async def get_survey_logs(
    page: int = Query(1, ge=1, description="Page number for pagination"),
    limit: int = Query(10, ge=1, le=100, description="Number of items per page"),
):
    """
    Get a paginated list of all completed surveys, grouped by mission waypoint.
    This provides a historical timeline of all survey activities.
    """
    try:
        logs, total_count = await survey_log_service.get_grouped_logs_paginated(
            page=page, limit=limit
        )
        return SurveyLogResponse(logs=logs, total=total_count)
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to retrieve survey logs: {str(e)}"
        )
