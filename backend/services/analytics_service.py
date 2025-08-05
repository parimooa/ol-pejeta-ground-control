"""
Analytics Service for Performance Data Collection
Tracks system performance metrics for research and monitoring
"""

import json
import math
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from collections import defaultdict
from backend.config import CONFIG

try:
    from settings import site_name as configured_site_name
except ImportError:
    configured_site_name = CONFIG.site.DEFAULT_SITE_NAME


@dataclass
class CoordinationEvent:
    """Represents a coordination event for tracking"""

    timestamp: str
    event_type: (
        str  # follow_start, follow_stop, survey_start, survey_complete, survey_abandon
    )
    distance: float
    drone_position: Dict[str, float]
    car_position: Dict[str, float]
    duration_seconds: Optional[float] = None
    reason: Optional[str] = None
    metadata: Optional[Dict] = None


@dataclass
class PerformanceMetric:
    """Performance metric data point"""

    timestamp: str
    metric_name: str
    value: float
    unit: str
    context: Optional[Dict] = None


@dataclass
class SystemHealthMetric:
    """System health tracking"""

    timestamp: str
    component: str
    status: str  # online, offline, error
    response_time_ms: Optional[float] = None
    error_message: Optional[str] = None


@dataclass
class VehicleTelemetryMetric:
    """Enhanced vehicle telemetry for dissertation research"""

    timestamp: str
    vehicle_id: str
    vehicle_type: str  # drone, car

    # Position and Navigation
    latitude: float
    longitude: float
    altitude_msl: float
    relative_altitude: float
    heading: float
    ground_speed: float

    # Battery and Power
    battery_voltage: float
    battery_remaining_percentage: float

    # Flight/Drive Mode (non-optional fields must come before optional ones)
    flight_mode: int
    system_status: int
    armed: bool
    guided_enabled: bool

    # Optional fields last
    power_consumption_watts: Optional[float] = None
    signal_strength_dbm: Optional[float] = None
    communication_latency_ms: Optional[float] = None
    packet_loss_percentage: Optional[float] = None
    gps_precision_meters: Optional[float] = None
    waypoint_deviation_meters: Optional[float] = None
    target_waypoint_id: Optional[int] = None


@dataclass
class MissionEffectivenessMetric:
    """Mission effectiveness and performance tracking"""

    timestamp: str
    mission_id: str
    mission_type: str  # survey, patrol, coordination

    # Time and Resource Usage (required fields first)
    mission_duration_seconds: float
    distance_traveled_meters: float

    # Success Metrics (required fields)
    objectives_completed: int
    objectives_total: int
    success_rate_percentage: float

    # Optional fields last
    area_covered_m2: Optional[float] = None
    coverage_completeness_percentage: Optional[float] = None
    survey_quality_score: Optional[float] = None  # 0-100
    energy_consumed_wh: Optional[float] = None
    weather_conditions: Optional[str] = None
    terrain_difficulty: Optional[str] = None  # easy, moderate, difficult
    time_of_day: Optional[str] = None  # dawn, day, dusk, night


@dataclass
class SafetyEvent:
    """Safety and reliability event tracking"""

    timestamp: str
    event_type: str  # near_miss, emergency_landing, collision_avoidance, system_fault
    severity: str  # low, medium, high, critical

    # Event Details (required fields)
    description: str
    vehicle_id: str
    location_lat: float
    location_lon: float
    human_intervention_required: bool

    # Optional fields last
    weather_conditions: Optional[str] = None
    system_state: Optional[Dict] = None
    resolution_time_seconds: Optional[float] = None
    resolution_method: Optional[str] = None


class AnalyticsService:
    def __init__(self):
        self.analytics_dir = Path(CONFIG.directories.ANALYTICS_DATA)
        self.analytics_dir.mkdir(exist_ok=True)

        # Persistent data files
        self.coordination_events_file = self.analytics_dir / "coordination_events.json"
        self.performance_metrics_file = self.analytics_dir / "performance_metrics.json"
        self.system_health_file = self.analytics_dir / "system_health.json"
        self.mission_stats_file = self.analytics_dir / "mission_stats.json"
        self.vehicle_telemetry_file = self.analytics_dir / "vehicle_telemetry.json"
        self.mission_effectiveness_file = (
            self.analytics_dir / "mission_effectiveness.json"
        )
        self.safety_events_file = self.analytics_dir / "safety_events.json"

        # In-memory storage for real-time metrics
        self.coordination_events: List[CoordinationEvent] = []
        self.performance_metrics: List[PerformanceMetric] = []
        self.system_health: List[SystemHealthMetric] = []
        self.vehicle_telemetry: List[VehicleTelemetryMetric] = []
        self.mission_effectiveness: List[MissionEffectivenessMetric] = []
        self.safety_events: List[SafetyEvent] = []

        # Tracking state
        self.current_session_start = datetime.now()
        self.last_persistence_time = datetime.now()
        self.persistence_interval = CONFIG.analytics.PERSISTENCE_INTERVAL

        # Counters for efficiency calculations
        self.mission_stats = {
            "total_missions": 0,
            "completed_missions": 0,
            "abandoned_missions": 0,
            "total_waypoints": 0,
            "completed_waypoints": 0,
        }

        # Load existing data on startup
        self._load_persisted_data()

    def _load_persisted_data(self):
        """Load existing analytics data from disk on startup"""
        try:
            # Load coordination events
            if self.coordination_events_file.exists():
                with open(self.coordination_events_file, "r") as f:
                    events_data = json.load(f)
                    self.coordination_events = [
                        CoordinationEvent(**event) for event in events_data
                    ]
                print(
                    f"Loaded {len(self.coordination_events)} coordination events from disk"
                )

            # Load performance metrics
            if self.performance_metrics_file.exists():
                with open(self.performance_metrics_file, "r") as f:
                    metrics_data = json.load(f)
                    self.performance_metrics = [
                        PerformanceMetric(**metric) for metric in metrics_data
                    ]
                print(
                    f"Loaded {len(self.performance_metrics)} performance metrics from disk"
                )

            # Load system health data
            if self.system_health_file.exists():
                with open(self.system_health_file, "r") as f:
                    health_data = json.load(f)
                    self.system_health = [
                        SystemHealthMetric(**health) for health in health_data
                    ]
                print(
                    f"Loaded {len(self.system_health)} system health records from disk"
                )

            # Load mission stats
            if self.mission_stats_file.exists():
                with open(self.mission_stats_file, "r") as f:
                    self.mission_stats = json.load(f)
                print(f"Loaded mission statistics from disk")

            # Load vehicle telemetry
            if self.vehicle_telemetry_file.exists():
                with open(self.vehicle_telemetry_file, "r") as f:
                    telemetry_data = json.load(f)
                    self.vehicle_telemetry = [
                        VehicleTelemetryMetric(**telemetry)
                        for telemetry in telemetry_data
                    ]
                print(
                    f"Loaded {len(self.vehicle_telemetry)} vehicle telemetry records from disk"
                )

            # Load mission effectiveness data
            if self.mission_effectiveness_file.exists():
                with open(self.mission_effectiveness_file, "r") as f:
                    effectiveness_data = json.load(f)
                    self.mission_effectiveness = [
                        MissionEffectivenessMetric(**effectiveness)
                        for effectiveness in effectiveness_data
                    ]
                print(
                    f"Loaded {len(self.mission_effectiveness)} mission effectiveness records from disk"
                )

            # Load safety events
            if self.safety_events_file.exists():
                with open(self.safety_events_file, "r") as f:
                    safety_data = json.load(f)
                    self.safety_events = [SafetyEvent(**event) for event in safety_data]
                print(f"Loaded {len(self.safety_events)} safety events from disk")

        except Exception as e:
            print(f"Error loading persisted analytics data: {e}")
            print("Starting with empty analytics data")

    def track_coordination_event(
        self,
        event_type: str,
        distance: float,
        drone_pos: Dict,
        car_pos: Dict,
        duration_seconds: Optional[float] = None,
        reason: Optional[str] = None,
        metadata: Optional[Dict] = None,
    ):
        """Track a coordination event"""
        event = CoordinationEvent(
            timestamp=datetime.now().isoformat(),
            event_type=event_type,
            distance=distance,
            drone_position=drone_pos,
            car_position=car_pos,
            duration_seconds=duration_seconds,
            reason=reason,
            metadata=metadata or {},
        )

        self.coordination_events.append(event)

        # Update mission statistics
        if event_type == "survey_start":
            self.mission_stats["total_missions"] += 1
        elif event_type == "survey_complete":
            self.mission_stats["completed_missions"] += 1
        elif event_type == "survey_abandon":
            self.mission_stats["abandoned_missions"] += 1

        self._maybe_persist_data()

    def track_performance_metric(
        self, metric_name: str, value: float, unit: str, context: Optional[Dict] = None
    ):
        """Track a performance metric"""
        metric = PerformanceMetric(
            timestamp=datetime.now().isoformat(),
            metric_name=metric_name,
            value=value,
            unit=unit,
            context=context or {},
        )

        self.performance_metrics.append(metric)
        self._maybe_persist_data()

    def track_system_health(
        self,
        component: str,
        status: str,
        response_time_ms: Optional[float] = None,
        error_message: Optional[str] = None,
    ):
        """Track system health metrics"""
        health_metric = SystemHealthMetric(
            timestamp=datetime.now().isoformat(),
            component=component,
            status=status,
            response_time_ms=response_time_ms,
            error_message=error_message,
        )

        self.system_health.append(health_metric)
        self._maybe_persist_data()

    def track_vehicle_telemetry(
        self, vehicle_id: str, vehicle_type: str, position_data: Dict, **kwargs
    ):
        """Track enhanced vehicle telemetry data for research analysis"""

        # Calculate GPS precision and waypoint deviation if data available
        gps_precision = kwargs.get("gps_precision_meters")
        waypoint_deviation = kwargs.get("waypoint_deviation_meters")

        # Estimate power consumption based on system activity
        power_consumption = self._estimate_power_consumption(
            vehicle_type,
            position_data.get("ground_speed", 0),
            position_data.get("flight_mode", 0),
        )

        telemetry = VehicleTelemetryMetric(
            timestamp=datetime.now().isoformat(),
            vehicle_id=str(vehicle_id),
            vehicle_type=vehicle_type,
            # Position data
            latitude=position_data.get("latitude", 0.0),
            longitude=position_data.get("longitude", 0.0),
            altitude_msl=position_data.get("altitude_msl", 0.0),
            relative_altitude=position_data.get("relative_altitude", 0.0),
            heading=position_data.get("heading", 0.0),
            ground_speed=position_data.get("ground_speed", 0.0),
            # Battery and power
            battery_voltage=position_data.get("battery_voltage", 0.0),
            battery_remaining_percentage=position_data.get(
                "battery_remaining_percentage", 0
            ),
            power_consumption_watts=power_consumption,
            # Communication (estimated/measured)
            signal_strength_dbm=kwargs.get("signal_strength_dbm"),
            communication_latency_ms=kwargs.get("communication_latency_ms"),
            packet_loss_percentage=kwargs.get("packet_loss_percentage"),
            # Navigation accuracy
            gps_precision_meters=gps_precision,
            waypoint_deviation_meters=waypoint_deviation,
            target_waypoint_id=position_data.get("current_mission_wp_seq"),
            # System status
            flight_mode=position_data.get("flight_mode", 0),
            system_status=position_data.get("system_status", 0),
            armed=position_data.get("armed", False),
            guided_enabled=position_data.get("guided_enabled", False),
        )

        self.vehicle_telemetry.append(telemetry)
        self._maybe_persist_data()

    def track_mission_effectiveness(
        self,
        mission_id: str,
        mission_type: str,
        mission_duration_seconds: float,
        distance_traveled_meters: float,
        objectives_completed: int,
        objectives_total: int,
        **kwargs,
    ):
        """Track mission effectiveness metrics for research analysis"""

        success_rate = (
            (objectives_completed / objectives_total * 100)
            if objectives_total > 0
            else 0
        )

        effectiveness = MissionEffectivenessMetric(
            timestamp=datetime.now().isoformat(),
            mission_id=mission_id,
            mission_type=mission_type,
            # Coverage and quality
            area_covered_m2=kwargs.get("area_covered_m2"),
            coverage_completeness_percentage=kwargs.get(
                "coverage_completeness_percentage"
            ),
            survey_quality_score=kwargs.get("survey_quality_score"),
            # Performance
            mission_duration_seconds=mission_duration_seconds,
            distance_traveled_meters=distance_traveled_meters,
            energy_consumed_wh=kwargs.get("energy_consumed_wh"),
            # Success metrics
            objectives_completed=objectives_completed,
            objectives_total=objectives_total,
            success_rate_percentage=success_rate,
            # Environmental context
            weather_conditions=kwargs.get("weather_conditions"),
            terrain_difficulty=kwargs.get("terrain_difficulty"),
            time_of_day=self._get_time_of_day(),
        )

        self.mission_effectiveness.append(effectiveness)
        self._maybe_persist_data()

    def track_safety_event(
        self,
        event_type: str,
        severity: str,
        description: str,
        vehicle_id: str,
        location_lat: float,
        location_lon: float,
        **kwargs,
    ):
        """Track safety events for research and regulatory compliance"""

        safety_event = SafetyEvent(
            timestamp=datetime.now().isoformat(),
            event_type=event_type,
            severity=severity,
            description=description,
            vehicle_id=str(vehicle_id),
            location_lat=location_lat,
            location_lon=location_lon,
            human_intervention_required=kwargs.get(
                "human_intervention_required", False
            ),
            # Optional context
            weather_conditions=kwargs.get("weather_conditions"),
            system_state=kwargs.get("system_state"),
            resolution_time_seconds=kwargs.get("resolution_time_seconds"),
            resolution_method=kwargs.get("resolution_method"),
        )

        self.safety_events.append(safety_event)
        self._maybe_persist_data()

    def _estimate_power_consumption(
        self, vehicle_type: str, ground_speed: float, flight_mode: int
    ) -> Optional[float]:
        """Estimate power consumption based on vehicle activity"""
        if vehicle_type == "drone":
            # Base consumption + speed-dependent + mode-dependent
            base_consumption = 200  # watts
            speed_factor = ground_speed * 5  # watts per m/s
            mode_factor = 50 if flight_mode in [3, 4, 16] else 0  # AUTO/GUIDED modes
            return base_consumption + speed_factor + mode_factor
        elif vehicle_type == "car":
            # Car power consumption estimation
            base_consumption = 100  # watts for electronics
            speed_factor = ground_speed * 2
            return base_consumption + speed_factor
        return None

    def _get_time_of_day(self) -> str:
        """Classify current time of day for environmental context"""
        hour = datetime.now().hour
        if 5 <= hour < 8:
            return "dawn"
        elif 8 <= hour < 18:
            return "day"
        elif 18 <= hour < 21:
            return "dusk"
        else:
            return "night"

    def get_coordination_statistics(self, hours_back: int = 24) -> Dict[str, Any]:
        """Get coordination performance statistics"""
        cutoff_time = datetime.now() - timedelta(hours=hours_back)
        recent_events = [
            e
            for e in self.coordination_events
            if datetime.fromisoformat(e.timestamp) > cutoff_time
        ]

        if not recent_events:
            return {"error": "No recent coordination events found for this period."}

        survey_starts = [e for e in recent_events if e.event_type == "survey_start"]
        survey_completes = [
            e for e in recent_events if e.event_type == "survey_complete"
        ]
        survey_abandons = [e for e in recent_events if e.event_type == "survey_abandon"]

        # Calculate survey success rate
        survey_success_rate = 0
        if survey_starts:
            survey_success_rate = len(survey_completes) / len(survey_starts) * 100

        # Calculate average duration for completed surveys
        completed_durations = [
            e.duration_seconds
            for e in survey_completes
            if e.duration_seconds is not None
        ]
        avg_duration = (
            sum(completed_durations) / len(completed_durations)
            if completed_durations
            else 0
        )

        return {
            "time_period_hours": hours_back,
            "total_events": len(recent_events),
            "survey_success_rate": round(survey_success_rate, 1),
            "avg_survey_duration_seconds": round(avg_duration, 1),
            "surveys_started": len(survey_starts),
            "surveys_completed": len(survey_completes),
            "surveys_abandoned": len(survey_abandons),
        }

    def get_performance_summary(self, hours_back: int = 24) -> Dict[str, Any]:
        """Get performance metrics summary"""
        cutoff_time = datetime.now() - timedelta(hours=hours_back)
        recent_metrics = [
            m
            for m in self.performance_metrics
            if datetime.fromisoformat(m.timestamp) > cutoff_time
        ]

        # Group metrics by name
        metrics_by_name = defaultdict(list)
        for metric in recent_metrics:
            metrics_by_name[metric.metric_name].append(metric.value)

        # Calculate mission success rate from session stats
        total_missions = self.mission_stats.get("total_missions", 0)
        completed_missions = self.mission_stats.get("completed_missions", 0)
        mission_success_rate = (
            round((completed_missions / total_missions) * 100, 1)
            if total_missions > 0
            else 0
        )

        # Get average API response time (assuming it's tracked as 'api_response_time')
        api_response_times = metrics_by_name.get("api_response_time", [])
        avg_api_response_time_ms = (
            round(sum(api_response_times) / len(api_response_times), 1)
            if api_response_times
            else 0
        )

        return {
            "time_period_hours": hours_back,
            "mission_success_rate": mission_success_rate,
            "avg_api_response_time_ms": avg_api_response_time_ms,
            "total_missions": total_missions,
        }

    def get_system_health_report(self, hours_back: int = 24) -> Dict[str, Any]:
        """Get system health report"""
        cutoff_time = datetime.now() - timedelta(hours=hours_back)
        recent_health = [
            h
            for h in self.system_health
            if datetime.fromisoformat(h.timestamp) > cutoff_time
        ]

        if not recent_health:
            return {"error": "No recent health data found"}

        # Group by component
        health_by_component = defaultdict(list)
        for health in recent_health:
            health_by_component[health.component].append(health)

        component_health = {}
        for component, health_records in health_by_component.items():
            online_count = len([h for h in health_records if h.status == "online"])
            error_count = len([h for h in health_records if h.status == "error"])

            response_times = [
                h.response_time_ms for h in health_records if h.response_time_ms
            ]
            avg_response = (
                sum(response_times) / len(response_times) if response_times else None
            )

            component_health[component] = {
                "total_checks": len(health_records),
                "online_count": online_count,
                "error_count": error_count,
                "uptime_percent": round(online_count / len(health_records) * 100, 2),
                "avg_response_time_ms": (
                    round(avg_response, 2) if avg_response else None
                ),
                "latest_status": (
                    health_records[-1].status if health_records else "unknown"
                ),
            }

        return {
            "time_period_hours": hours_back,
            "component_health": [
                {
                    "component": component,
                    "uptime_percent": health_data["uptime_percent"],
                    "avg_response_time_ms": health_data["avg_response_time_ms"],
                    "latest_status": health_data["latest_status"],
                    "total_checks": health_data["total_checks"],
                    "error_count": health_data["error_count"],
                }
                for component, health_data in component_health.items()
            ],
            "total_health_checks": len(recent_health),
        }

    def export_research_data(self, format_type: str = "json") -> Dict[str, Any]:
        """Export all data for research analysis"""
        data = {
            "export_timestamp": datetime.now().isoformat(),
            "session_start": self.current_session_start.isoformat(),
            "coordination_events": [
                asdict(event) for event in self.coordination_events
            ],
            "performance_metrics": [
                asdict(metric) for metric in self.performance_metrics
            ],
            "system_health": [asdict(health) for health in self.system_health],
            "mission_statistics": self.mission_stats,
            "summary_statistics": {
                "coordination_stats": self.get_coordination_statistics(
                    hours_back=168
                ),  # 1 week
                "performance_summary": self.get_performance_summary(hours_back=168),
                "health_report": self.get_system_health_report(hours_back=168),
            },
        }

        if format_type == "json":
            # Save to file
            export_file = (
                self.analytics_dir / f"research_export_{int(time.time())}.json"
            )
            with open(export_file, "w") as f:
                json.dump(data, f, indent=2)
            data["export_file"] = str(export_file.absolute())

        return data

    def get_mission_effectiveness_analysis(
        self, hours_back: int = 24
    ) -> Dict[str, Any]:
        """Get mission effectiveness analysis for research"""
        cutoff_time = datetime.now() - timedelta(hours=hours_back)
        recent_missions = [
            m
            for m in self.mission_effectiveness
            if datetime.fromisoformat(m.timestamp) > cutoff_time
        ]

        if not recent_missions:
            return {"error": "No mission effectiveness data found for this period"}

        # Analyze mission performance
        total_missions = len(recent_missions)
        total_area_covered = sum(
            m.area_covered_m2 for m in recent_missions if m.area_covered_m2
        )
        total_distance = sum(m.distance_traveled_meters for m in recent_missions)
        total_duration = sum(m.mission_duration_seconds for m in recent_missions)

        success_rates = [m.success_rate_percentage for m in recent_missions]
        quality_scores = [
            m.survey_quality_score for m in recent_missions if m.survey_quality_score
        ]

        # Time-based analysis
        time_periods = {}
        for mission in recent_missions:
            period = mission.time_of_day or "unknown"
            if period not in time_periods:
                time_periods[period] = []
            time_periods[period].append(mission)

        time_analysis = {}
        for period, missions in time_periods.items():
            avg_success = sum(m.success_rate_percentage for m in missions) / len(
                missions
            )
            quality_missions = [m for m in missions if m.survey_quality_score]
            avg_quality = (
                sum(m.survey_quality_score for m in quality_missions)
                / len(quality_missions)
                if quality_missions
                else 0
            )
            time_analysis[period] = {
                "mission_count": len(missions),
                "avg_success_rate": round(avg_success, 1),
                "avg_quality_score": round(avg_quality, 1) if avg_quality else None,
            }

        return {
            "time_period_hours": hours_back,
            "overall_stats": {
                "total_missions": total_missions,
                "total_area_covered_m2": round(total_area_covered, 1),
                "total_distance_traveled_m": round(total_distance, 1),
                "total_flight_time_hours": round(total_duration / 3600, 1),
                "avg_success_rate": (
                    round(sum(success_rates) / len(success_rates), 1)
                    if success_rates
                    else 0
                ),
                "avg_quality_score": (
                    round(sum(quality_scores) / len(quality_scores), 1)
                    if quality_scores
                    else 0
                ),
            },
            "time_of_day_analysis": time_analysis,
            "efficiency_metrics": {
                "area_coverage_rate_m2_per_hour": (
                    round(total_area_covered / (total_duration / 3600), 1)
                    if total_duration > 0
                    else 0
                ),
                "avg_mission_duration_minutes": (
                    round(total_duration / total_missions / 60, 1)
                    if total_missions > 0
                    else 0
                ),
                "distance_efficiency_m_per_minute": (
                    round(total_distance / (total_duration / 60), 1)
                    if total_duration > 0
                    else 0
                ),
            },
        }

    def get_safety_events_summary(self, hours_back: int = 24) -> Dict[str, Any]:
        """Get safety events summary for risk analysis"""
        cutoff_time = datetime.now() - timedelta(hours=hours_back)
        recent_events = [
            e
            for e in self.safety_events
            if datetime.fromisoformat(e.timestamp) > cutoff_time
        ]

        if not recent_events:
            return {"message": "No safety events recorded for this period (good news!)"}

        # Analyze by severity
        severity_counts = {}
        for event in recent_events:
            severity = event.severity
            if severity not in severity_counts:
                severity_counts[severity] = 0
            severity_counts[severity] += 1

        # Analyze by event type
        event_type_counts = {}
        for event in recent_events:
            event_type = event.event_type
            if event_type not in event_type_counts:
                event_type_counts[event_type] = 0
            event_type_counts[event_type] += 1

        # Resolution analysis
        resolved_events = [
            e for e in recent_events if e.resolution_time_seconds is not None
        ]
        human_intervention_count = len(
            [e for e in recent_events if e.human_intervention_required]
        )

        return {
            "time_period_hours": hours_back,
            "total_safety_events": len(recent_events),
            "severity_breakdown": severity_counts,
            "event_type_breakdown": event_type_counts,
            "resolution_stats": {
                "resolved_events": len(resolved_events),
                "avg_resolution_time_seconds": (
                    sum(e.resolution_time_seconds for e in resolved_events)
                    / len(resolved_events)
                    if resolved_events
                    else 0
                ),
                "human_intervention_required": human_intervention_count,
                "autonomous_resolution_rate": (
                    round(
                        (len(resolved_events) - human_intervention_count)
                        / len(resolved_events)
                        * 100,
                        1,
                    )
                    if resolved_events
                    else 0
                ),
            },
            "recent_events": [
                {
                    "timestamp": e.timestamp,
                    "event_type": e.event_type,
                    "severity": e.severity,
                    "description": e.description,
                    "vehicle_id": e.vehicle_id,
                    "resolved": e.resolution_time_seconds is not None,
                }
                for e in sorted(recent_events, key=lambda x: x.timestamp, reverse=True)[
                    :10
                ]
            ],
        }

    def _maybe_persist_data(self):
        """Persist data to disk if enough time has passed"""
        now = datetime.now()
        if (now - self.last_persistence_time).seconds > self.persistence_interval:
            self._persist_to_disk()
            self.last_persistence_time = now

    def _persist_to_disk(self):
        """Save current data to persistent files"""
        try:
            # Save coordination events
            with open(self.coordination_events_file, "w") as f:
                json.dump(
                    [asdict(event) for event in self.coordination_events], f, indent=2
                )

            # Save performance metrics
            with open(self.performance_metrics_file, "w") as f:
                json.dump(
                    [asdict(metric) for metric in self.performance_metrics], f, indent=2
                )

            # Save system health
            with open(self.system_health_file, "w") as f:
                json.dump(
                    [asdict(health) for health in self.system_health], f, indent=2
                )

            # Save mission statistics
            with open(self.mission_stats_file, "w") as f:
                json.dump(self.mission_stats, f, indent=2)

            # Save vehicle telemetry
            with open(self.vehicle_telemetry_file, "w") as f:
                json.dump(
                    [asdict(telemetry) for telemetry in self.vehicle_telemetry],
                    f,
                    indent=2,
                )

            # Save mission effectiveness data
            with open(self.mission_effectiveness_file, "w") as f:
                json.dump(
                    [
                        asdict(effectiveness)
                        for effectiveness in self.mission_effectiveness
                    ],
                    f,
                    indent=2,
                )

            # Save safety events
            with open(self.safety_events_file, "w") as f:
                json.dump([asdict(event) for event in self.safety_events], f, indent=2)

            print(
                f"Enhanced analytics data persisted to disk at {datetime.now().isoformat()}"
            )

        except Exception as e:
            print(f"Error persisting analytics data: {e}")

    def force_persist(self):
        """Force immediate persistence of all data to disk"""
        self._persist_to_disk()
        self.last_persistence_time = datetime.now()

    def reset_session_data(self):
        """Reset session data (useful for testing)"""
        self.coordination_events.clear()
        self.performance_metrics.clear()
        self.system_health.clear()
        self.vehicle_telemetry.clear()
        self.mission_effectiveness.clear()
        self.safety_events.clear()
        self.mission_stats = {
            "total_missions": 0,
            "completed_missions": 0,
            "abandoned_missions": 0,
            "total_waypoints": 0,
            "completed_waypoints": 0,
        }
        self.current_session_start = datetime.now()
        # Persist the reset state
        self._persist_to_disk()


# Singleton instance
analytics_service = AnalyticsService()
