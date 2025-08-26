from fastapi import APIRouter
from typing import Dict, Any
from backend.services.vehicle_service import vehicle_service
from backend.api.websockets.telemetry import telemetry_manager
from backend.services.coordination_service import coordination_service
from backend.services.survey_service import survey_service

router = APIRouter(prefix="/coordination", tags=["coordination"])


@router.post("/start")
async def start_coordination() -> Dict[str, Any]:
    """Activates the autonomous coordination and monitoring service."""
    success = coordination_service.start()
    if success:
        return {"status": "success", "message": "Coordination service started."}
    return {"status": "error", "message": "Coordination service already running."}


@router.post("/stop")
async def stop_coordination() -> Dict[str, Any]:
    """Deactivates the coordination service."""
    coordination_service.stop()
    return {"status": "success", "message": "Coordination service stopped."}


@router.get("/status")
async def get_coordination_status() -> Dict[str, Any]:
    """Get current coordination service status."""
    return {
        "active": coordination_service.is_active(),
        "following": coordination_service.is_following(),
        "surveying": coordination_service.is_surveying(),
        "survey_button_enabled": coordination_service.is_survey_button_enabled(),
        "survey_paused": survey_service.is_paused,
    }


@router.post("/initiate-proximity-survey")
async def initiate_proximity_survey() -> Dict[str, Any]:
    """Initiate a proximity survey at current vehicle position."""
    try:
        success = await coordination_service.initiate_proximity_survey()
        if success:
            return {"status": "success", "message": "Proximity survey initiated."}
        else:
            return {
                "status": "error",
                "message": "Failed to initiate proximity survey.",
            }
    except Exception as e:
        return {"status": "error", "message": f"Error initiating survey: {str(e)}"}


@router.post("/start-proximity-tracking")
async def start_proximity_tracking() -> Dict[str, Any]:
    """Start continuous proximity data tracking (independent of coordination service)."""
    success = coordination_service.start_proximity_tracking()
    if success:
        return {"status": "success", "message": "Proximity tracking started."}
    return {"status": "error", "message": "Proximity tracking already running."}


@router.post("/stop-proximity-tracking")
async def stop_proximity_tracking() -> Dict[str, Any]:
    """Stop continuous proximity data tracking."""
    coordination_service.stop_proximity_tracking()
    return {"status": "success", "message": "Proximity tracking stopped."}
