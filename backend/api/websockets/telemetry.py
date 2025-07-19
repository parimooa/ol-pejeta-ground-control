import json
import asyncio
import threading
from typing import Dict, List, Any

from fastapi import WebSocket, WebSocketDisconnect
from pydantic import ValidationError

from backend.services.vehicle_service import vehicle_service
from backend.schemas.telemetry import TelemetryData
from backend.config import WEBSOCKET_PING_INTERVAL


class TelemetryWebsocketManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self.vehicle_types: Dict[WebSocket, str] = {}
        self.loop = None  # Store reference to event loop
        self._loop_set = threading.Event()  # Event to signal when loop is set
        self._pending_telemetry = []  # Store telemetry when loop isn't ready

    def set_event_loop(self, loop):
        """Set the event loop reference."""
        print(f"TelemetryWebsocketManager: set_event_loop called with {loop}")
        self.loop = loop
        self._loop_set.set()
        print(f"TelemetryWebsocketManager: Event loop set successfully")

        # Process pending telemetry
        pending_count = len(self._pending_telemetry)
        if pending_count > 0:
            print(f"Processing {pending_count} pending telemetry messages")
            self._process_pending_telemetry()
        else:
            print("No pending telemetry to process")

    def wait_for_loop(self, timeout=5.0):
        """Wait for the event loop to be set."""
        return self._loop_set.wait(timeout)

    def _process_pending_telemetry(self):
        """Process any telemetry that was queued before the loop was available."""
        if self._pending_telemetry and self.loop:
            print(
                f"Processing {len(self._pending_telemetry)} pending telemetry messages"
            )
            for vehicle_type, telemetry in self._pending_telemetry:
                try:

                    def schedule_broadcast():
                        return self.loop.create_task(
                            self._broadcast_telemetry(vehicle_type, telemetry)
                        )

                    self.loop.call_soon_threadsafe(schedule_broadcast)
                except Exception as e:
                    print(f"Error processing pending telemetry: {e}")
            self._pending_telemetry.clear()

    async def connect(self, websocket: WebSocket, vehicle_type: str):
        """Connect a WebSocket client and register for telemetry updates."""
        await websocket.accept()
        self.active_connections.append(websocket)
        self.vehicle_types[websocket] = vehicle_type

        # Start ping task to keep connection alive
        asyncio.create_task(self._ping_client(websocket))

        # Register telemetry callback for this vehicle
        self._register_telemetry_callback(vehicle_type)

    def disconnect(self, websocket: WebSocket):
        """Disconnect a WebSocket client."""
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

        if websocket in self.vehicle_types:
            del self.vehicle_types[websocket]

    def _register_telemetry_callback(self, vehicle_type: str):
        """Register a callback to receive telemetry updates."""

        def telemetry_callback(data: Dict[str, Any]):
            """Callback function to handle telemetry data."""
            try:
                # Additional heartbeat check - only process telemetry with recent heartbeat
                heartbeat_timestamp = data.get("heartbeat_timestamp")
                if not heartbeat_timestamp:
                    print(f"{vehicle_type}: Telemetry callback received data without heartbeat, skipping")
                    return
                
                import time
                current_time = time.time()
                time_since_heartbeat = current_time - heartbeat_timestamp
                
                if time_since_heartbeat > 10.0:
                    print(f"{vehicle_type}: Telemetry callback received stale heartbeat ({time_since_heartbeat:.1f}s old), skipping")
                    return
                
                # Convert raw data to Pydantic model
                telemetry = TelemetryData.from_vehicle_data(data)

                # Check if event loop is available
                if self.loop and not self.loop.is_closed():
                    # Event loop is available, schedule immediately
                    try:

                        def schedule_broadcast():
                            return self.loop.create_task(
                                self._broadcast_telemetry(vehicle_type, telemetry)
                            )

                        self.loop.call_soon_threadsafe(schedule_broadcast)

                    except Exception as e:
                        print(f"Error scheduling telemetry broadcast: {e}")

                elif len(self._pending_telemetry) < 100:  # Limit pending queue size
                    # Event loop not available yet, queue the telemetry
                    self._pending_telemetry.append((vehicle_type, telemetry))
                    print(
                        f"Queued telemetry (queue size: {len(self._pending_telemetry)})"
                    )

                    # Try to wait for loop to become available (non-blocking check)
                    if not self._loop_set.is_set():
                        # Start a background thread to wait for the loop
                        def wait_and_process():
                            if self.wait_for_loop(timeout=30.0):  # Longer timeout
                                self._process_pending_telemetry()
                            else:
                                print(
                                    "WARNING: Event loop never became available, clearing pending telemetry"
                                )
                                self._pending_telemetry.clear()

                        # Only start one wait thread
                        if not hasattr(self, "_waiting_for_loop"):
                            self._waiting_for_loop = True
                            threading.Thread(
                                target=wait_and_process, daemon=True
                            ).start()
                else:
                    print("WARNING: Telemetry queue full, dropping telemetry data")

            except ValidationError as e:
                print(f"Error validating telemetry data: {e}")
            except Exception as e:
                print(f"Error in telemetry callback: {e}")

        # Register the callback with the vehicle service
        vehicle_service.register_telemetry_callback(vehicle_type, telemetry_callback)

    def broadcast_event(self, event: Dict[str, Any]):
        """
        Schedules a non-telemetry event to be broadcast to all connected clients.
        This is thread-safe and can be called from other services.
        """
        if self.loop and not self.loop.is_closed():
            # Schedule the async broadcast function to run on the main event loop
            self.loop.call_soon_threadsafe(
                self.loop.create_task, self._async_broadcast_event(event)
            )
        else:
            print(
                "WARNING: Event loop not available for broadcast_event. Event dropped."
            )

    async def _async_broadcast_event(self, event: Dict[str, Any]):
        """The async part of broadcasting an event to all clients."""
        print(f"Broadcasting event: {event}")
        message = json.dumps({"type": "coordination_event", **event})

        disconnected_clients = []
        # Iterate over a copy of the list to avoid issues if a client disconnects during the broadcast
        for websocket in self.active_connections[:]:
            try:
                await websocket.send_text(message)
            except Exception as e:
                print(f"Error sending event to client: {e}")
                disconnected_clients.append(websocket)

        # Clean up any clients that failed during the broadcast
        for websocket in disconnected_clients:
            self.disconnect(websocket)

    async def _broadcast_telemetry(self, vehicle_type: str, telemetry: TelemetryData):
        """Broadcast telemetry data to all connected clients for this vehicle."""
        # Convert telemetry to JSON
        json_data = telemetry.model_dump_json()

        # Send to each connected client for this vehicle
        disconnected_clients = []
        for websocket in self.active_connections:
            if self.vehicle_types.get(websocket) == vehicle_type:
                try:
                    await websocket.send_text(json_data)
                except Exception as e:
                    print(f"Error sending telemetry to client: {e}")
                    disconnected_clients.append(websocket)

        # Clean up disconnected clients
        for websocket in disconnected_clients:
            self.disconnect(websocket)

    async def _ping_client(self, websocket: WebSocket):
        """Send periodic pings to keep the connection alive."""
        try:
            while True:
                await asyncio.sleep(WEBSOCKET_PING_INTERVAL)
                try:
                    await websocket.send_text(json.dumps({"type": "ping"}))
                except Exception:
                    # Connection is probably closed
                    break
        except asyncio.CancelledError:
            pass
        except Exception as e:
            print(f"Error in ping task: {e}")
        finally:
            # Make sure to disconnect
            self.disconnect(websocket)


# Create a singleton instance
telemetry_manager = TelemetryWebsocketManager()
