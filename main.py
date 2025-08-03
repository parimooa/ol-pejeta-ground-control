import asyncio

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.routes import survey_logs
from backend.api.routes import vehicle, survey, coordination,analytics
from backend.api.websockets.telemetry import telemetry_manager
from backend.services.vehicle_service import vehicle_service
from backend.services.analytics_service import analytics_service

app = FastAPI(
    title="Drone Control API",
    description="API for controlling drones via MAVLink",
    version="1.0.0",
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify the frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(vehicle.router)
app.include_router(survey.router)
app.include_router(coordination.router)
app.include_router(survey_logs.router)
app.include_router(analytics.router)
@app.get("/")
async def root():
    return {"message": "Welcome to the Drone Control API"}


@app.on_event("startup")
async def startup_event():
    print("=" * 50)
    print("STARTUP EVENT IS RUNNING!")
    print("=" * 50)

    # Get the current running event loop
    loop = asyncio.get_running_loop()
    print(f"Current event loop: {loop}")

    # Set it in vehicle_service
    if hasattr(vehicle_service, "set_event_loop"):
        vehicle_service.set_event_loop(loop)
        print("Set event loop in vehicle_service")
    else:
        print("vehicle_service does not have set_event_loop method")

    # Set it in telemetry manager
    telemetry_manager.set_event_loop(loop)
    print("Called telemetry_manager.set_event_loop()")

    # Verify it was set
    print(f"Telemetry manager loop is set: {telemetry_manager.loop is not None}")
    print(
        f"Telemetry manager pending queue size: {len(telemetry_manager._pending_telemetry)}"
    )
    print("=" * 50)


@app.on_event("shutdown")
async def shutdown_event():
    # Persist analytics data before shutdown
    try:
        analytics_service.force_persist()
        print("Analytics data persisted before shutdown")
    except Exception as e:
        print(f"Error persisting analytics data on shutdown: {e}")

    # Disconnect all vehicles
    for vehicle_type in vehicle_service.vehicles:
        vehicle_service.disconnect_vehicle(vehicle_type)

    print("Drone Control API is shutting down...")


# @app.get("/debug/set-event-loop")
# async def debug_set_event_loop():
#     """Debug endpoint to manually set the event loop"""
#     loop = asyncio.get_running_loop()
#
#     # Set it in the telemetry manager
#     telemetry_manager.set_event_loop(loop)
#
#     return {
#         "message": "Event loop set manually",
#         "loop": str(loop),
#         "pending_telemetry_count": len(telemetry_manager._pending_telemetry),
#         "loop_is_set": telemetry_manager.loop is not None,
#     }


# @app.get("/debug/telemetry-status")
# async def debug_telemetry_status():
#     """Debug endpoint to check telemetry status"""
#     return {
#         "loop_is_set": telemetry_manager.loop is not None,
#         "pending_telemetry_count": len(telemetry_manager._pending_telemetry),
#         "active_connections": len(telemetry_manager.active_connections),
#         "loop_set_event": telemetry_manager._loop_set.is_set(),
#     }


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
