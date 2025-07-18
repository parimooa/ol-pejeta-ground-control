import os

from fastapi import (
    APIRouter,
    HTTPException,
    WebSocket,
    WebSocketDisconnect,
    Depends,
    UploadFile,
    File,
)
from typing import Dict, Any, List
import tempfile

from backend.services.vehicle_service import vehicle_service
from backend.api.websockets.telemetry import telemetry_manager
from backend.schemas.telemetry import TelemetryData

router = APIRouter(prefix="/vehicles", tags=["vehicles"])


@router.get("/")
async def get_vehicles() -> Dict[str, str]:
    """Get a list of available vehicles."""
    return {
        vehicle_type: str(vehicle)
        for vehicle_type, vehicle in vehicle_service.vehicles.items()
    }


@router.post("/{vehicle_type}/connect")
async def connect_vehicle(vehicle_type: str) -> Dict[str, Any]:
    """Connect to a vehicle."""
    if vehicle_service.connect_vehicle(vehicle_type):
        return {"status": "connected", "vehicle_type": vehicle_type}
    else:
        raise HTTPException(
            status_code=500, detail=f"Failed to connect to {vehicle_type}"
        )


@router.post("/{vehicle_type}/disconnect")
async def disconnect_vehicle(vehicle_type: str) -> Dict[str, Any]:
    """Disconnect from a vehicle."""
    if vehicle_service.disconnect_vehicle(vehicle_type):
        return {"status": "disconnected", "vehicle_type": vehicle_type}
    else:
        raise HTTPException(
            status_code=500, detail=f"Failed to disconnect from {vehicle_type}"
        )


@router.get("/{vehicle_type}/telemetry")
async def get_telemetry(vehicle_type: str) -> Dict[str, Any]:
    """Get the latest telemetry data from a vehicle."""
    telemetry = vehicle_service.get_telemetry(vehicle_type)
    if not telemetry:
        raise HTTPException(
            status_code=404, detail=f"No telemetry data available for {vehicle_type}"
        )

    # Convert to structured data
    try:
        structured_telemetry = TelemetryData.from_vehicle_data(telemetry)
        return structured_telemetry.model_dump()
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error processing telemetry: {str(e)}"
        )


@router.post("/{vehicle_type}/mode/{mode}")
async def set_vehicle_mode(vehicle_type: str, mode: str) -> Dict[str, Any]:
    """Set the flight mode of a vehicle."""
    if vehicle_service.set_mode(vehicle_type, mode):
        return {"status": "success", "vehicle_type": vehicle_type, "mode": mode}
    else:
        raise HTTPException(
            status_code=500, detail=f"Failed to set mode {mode} for {vehicle_type}"
        )


@router.websocket("/{vehicle_type}/ws")
async def websocket_endpoint(websocket: WebSocket, vehicle_type: str):
    """WebSocket endpoint for real-time telemetry data."""
    try:
        # Connect the websocket
        await telemetry_manager.connect(websocket, vehicle_type)

        # Wait for disconnection
        while True:
            # This will receive messages from the client
            data = await websocket.receive_text()
            # Process commands if needed
            await websocket.send_text(f"Received: {data}")

    except WebSocketDisconnect:
        telemetry_manager.disconnect(websocket)
    except Exception as e:
        print(f"WebSocket error: {e}")
        telemetry_manager.disconnect(websocket)


@router.post("/{vehicle_type}/mission/upload")
async def upload_mission(
    vehicle_type: str, mission_file: UploadFile = File(...)
) -> Dict[str, Any]:
    """
     Upload a mission file to the vehicle.
    This endpoint accepts a waypoints file and uploads it to the vehicle.
    """
    # Create a temporary file to store the uploaded content
    with tempfile.NamedTemporaryFile(delete=False, suffix=".waypoints") as temp_file:
        temp_path = temp_file.name
        # Write the uploaded file content to the temporary file
        content = await mission_file.read()
        temp_file.write(content)

    try:
        # Call the service method with the file path
        result = vehicle_service.upload_mission(vehicle_type, temp_path)

        if result:
            return {
                "status": "success",
                "vehicle_type": vehicle_type,
                "waypoints_count": result,
                "filename": mission_file.filename,
            }
        else:
            raise HTTPException(
                status_code=500, detail=f"Failed to upload mission to {vehicle_type}"
            )
    finally:
        # Clean up the temporary file
        os.unlink(temp_path)
