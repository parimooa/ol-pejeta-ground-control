from fastapi import APIRouter, HTTPException
from typing import List, Dict, Optional
from ...services.survey_service import survey_service
from ...services.vehicle_service import vehicle_service
from ...models.waypoint import Waypoint

router = APIRouter(prefix="/survey", tags=["survey"])


@router.post("/start")
async def start_survey_mission(vehicle_types: List[str] = ["car", "drone"]):
    """Start a coordinated survey mission"""
    # Check if vehicles are connected
    for vehicle_type in vehicle_types:
        vehicle = vehicle_service.get_vehicle(vehicle_type)
        if not vehicle:
            raise HTTPException(
                status_code=400, detail=f"Vehicle {vehicle_type} is not connected"
            )

    # Get waypoints from the first vehicle (usually car)
    main_vehicle = vehicle_service.get_vehicle(vehicle_types[0])
    if not main_vehicle:
        raise HTTPException(status_code=400, detail="Main vehicle not found")

    # For now, we'll need to implement waypoint retrieval from the vehicle
    # This would require extending your Vehicle class with waypoint download capability

    return {"message": "Survey mission started", "status": "success"}


@router.get("/waypoint/next")
async def get_next_waypoint(vehicle_type: str = "car"):
    """Get information about the next waypoint"""
    try:
        waypoint_info = await survey_service.get_next_waypoint_info(vehicle_type)
        if not waypoint_info:
            raise HTTPException(status_code=404, detail="No next waypoint found")
        return waypoint_info
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/waypoint/move")
async def move_to_next_waypoint(vehicle_type: str = "car"):
    """Move vehicle to the next waypoint"""
    try:
        success = await survey_service.move_to_next_waypoint(vehicle_type)
        if not success:
            raise HTTPException(
                status_code=400, detail="Failed to move to next waypoint"
            )
        return {"message": "Moving to next waypoint", "status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/waypoint/advance")
async def advance_waypoint():
    """Advance to the next waypoint in the mission"""
    try:
        success = await survey_service.advance_to_next_waypoint()
        if not success:
            raise HTTPException(
                status_code=400, detail="No more waypoints or failed to advance"
            )
        return {"message": "Advanced to next waypoint", "status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/scan/execute")
async def execute_scan(
    center_lat: float,
    center_lon: float,
    center_alt: float,
    heading: float,
    car_vehicle_type: str = "car",
    max_car_distance: float = 20.0,
):
    """Execute a lawnmower scan pattern at the specified location"""
    try:
        center_waypoint = {"lat": center_lat, "lon": center_lon, "alt": center_alt}

        success = await survey_service.execute_lawnmower_scan(
            center_waypoint=center_waypoint,
            heading=heading,
            car_vehicle_type=car_vehicle_type,
            max_car_distance=max_car_distance,
        )

        if not success:
            raise HTTPException(status_code=400, detail="Scan execution failed")

        return {"message": "Scan completed successfully", "status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status")
async def get_survey_status():
    """Get the current survey mission status"""
    try:
        return {
            "current_waypoint_index": survey_service.current_waypoint_index,
            "total_waypoints": len(survey_service.mission_waypoints),
            "scan_abandoned": survey_service.scan_abandoned,
            "mission_complete": survey_service.current_waypoint_index
            >= len(survey_service.mission_waypoints),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/mission/set")
async def set_mission_waypoints(waypoints: List[Dict]):
    """Set the mission waypoints"""
    try:
        waypoint_objects = []
        for i, wp in enumerate(waypoints):
            waypoint_objects.append(
                Waypoint(
                    seq=i,
                    lat=wp["lat"],
                    lon=wp["lon"],
                    alt=wp.get("alt", 20),
                    command=wp.get("command", 16),
                    param1=wp.get("param1", 0),
                    param2=wp.get("param2", 0),
                    param3=wp.get("param3", 0),
                    param4=wp.get("param4", 0),
                )
            )

        survey_service.set_mission_waypoints(waypoint_objects)
        return {"message": "Mission waypoints set", "status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/mission/reset")
async def reset_mission():
    """Reset the mission to the beginning"""
    try:
        survey_service.reset_mission()
        return {"message": "Mission reset", "status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
