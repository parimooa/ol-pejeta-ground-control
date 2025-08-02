import json
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any

from fastapi import APIRouter, HTTPException

from ...models.waypoint import Waypoint
from ...schemas.survey import SaveSurveyRequest, DeleteSurveyRequest
from ...services.survey_service import survey_service
from ...services.vehicle_service import vehicle_service
from ...config import CONFIG

# Survey storage configuration
SURVEYS_DIR = Path(CONFIG.directories.SURVEYED_AREA)
SURVEYS_DIR.mkdir(exist_ok=True)

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


@router.post("/save")
async def save_survey(request: SaveSurveyRequest):
    """
    Save a survey to file-based storage in the surveyed_area directory
    """
    try:
        # Ensure the filename ends with .json
        filename = request.filename
        if not filename.endswith(".json"):
            filename += ".json"

        # Create a full file path
        file_path = SURVEYS_DIR / filename

        # Prepare survey data with filename
        survey_data = request.data.dict()
        survey_data["filename"] = filename
        survey_data["savedAt"] = datetime.now().isoformat()

        # Write to a file
        with open(file_path, "w") as f:
            json.dump(survey_data, f, indent=2)

        return {
            "success": True,
            "message": f"Survey saved successfully as {filename}",
            "filename": filename,
            "path": str(file_path.absolute()),
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save survey: {str(e)}")


@router.get("/load")
async def load_surveys() -> List[Dict[str, Any]]:
    """
    Load all surveys from the surveyed_area directory
    """
    try:
        surveys = []

        if not SURVEYS_DIR.exists():
            return surveys

        for file_path in SURVEYS_DIR.glob("*drone-surveyed*.json"):
            try:
                with open(file_path, "r") as f:
                    survey_data = json.load(f)
            except json.JSONDecodeError as e:
                print(f"Warning: Could not parse survey file {file_path}: {e}")
                continue
            except Exception as e:
                print(f"Warning: Error reading survey file {file_path}: {e}")
                continue
        waypoints = [
            {"waypoints": waypoints["waypoints"]}
            for waypoints in survey_data
            if waypoints["waypoints"]
        ]
        return waypoints

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load surveys: {str(e)}")


@router.delete("/delete")
async def delete_survey(request: DeleteSurveyRequest):
    """
    Delete a survey file from the surveyed_area directory
    """
    try:
        # Ensure filename ends with .json
        filename = request.filename
        if not filename.endswith(".json"):
            filename += ".json"

        # Create full file path
        file_path = SURVEYS_DIR / filename

        # Check if file exists
        if not file_path.exists():
            raise HTTPException(
                status_code=404, detail=f"Survey file {filename} not found"
            )

        # Delete the file
        file_path.unlink()

        return {
            "success": True,
            "message": f"Survey {filename} deleted successfully",
            "filename": filename,
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to delete survey: {str(e)}"
        )


@router.get("/list")
async def list_surveys() -> List[str]:
    """
    List all survey filenames in the surveyed_area directory
    """
    try:
        filenames = []

        # Check if directory exists
        if not SURVEYS_DIR.exists():
            return filenames

        # Get all JSON filenames
        for file_path in SURVEYS_DIR.glob("*.json"):
            filenames.append(file_path.name)

        # Sort filenames (most recent first based on timestamp in filename)
        filenames.sort(reverse=True)

        return filenames

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list surveys: {str(e)}")


@router.get("/info")
async def get_surveys_info():
    """
    Get information about the surveys directory and stored surveys
    """
    try:
        # Check if directory exists
        if not SURVEYS_DIR.exists():
            return {
                "directory_exists": False,
                "directory_path": str(SURVEYS_DIR.absolute()),
                "survey_count": 0,
                "total_size_bytes": 0,
            }

        # Count files and calculate total size
        survey_files = list(SURVEYS_DIR.glob("*.json"))
        survey_count = len(survey_files)

        total_size = sum(f.stat().st_size for f in survey_files if f.exists())

        return {
            "directory_exists": True,
            "directory_path": str(SURVEYS_DIR.absolute()),
            "survey_count": survey_count,
            "total_size_bytes": total_size,
            "filenames": [f.name for f in survey_files],
        }

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to get surveys info: {str(e)}"
        )
