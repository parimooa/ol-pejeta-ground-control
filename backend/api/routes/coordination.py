from fastapi import APIRouter
from typing import Dict, Any

from backend.services.coordination_service import coordination_service

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
