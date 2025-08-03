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


class AnalyticsService:
    def __init__(self):
        self.analytics_dir = Path(CONFIG.directories.ANALYTICS_DATA)
        self.analytics_dir.mkdir(exist_ok=True)

        # Persistent data files
        self.coordination_events_file = self.analytics_dir / "coordination_events.json"
        self.performance_metrics_file = self.analytics_dir / "performance_metrics.json"
        self.system_health_file = self.analytics_dir / "system_health.json"
        self.mission_stats_file = self.analytics_dir / "mission_stats.json"

        # In-memory storage for real-time metrics
        self.coordination_events: List[CoordinationEvent] = []
        self.performance_metrics: List[PerformanceMetric] = []
        self.system_health: List[SystemHealthMetric] = []

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
                with open(self.coordination_events_file, 'r') as f:
                    events_data = json.load(f)
                    self.coordination_events = [
                        CoordinationEvent(**event) for event in events_data
                    ]
                print(f"Loaded {len(self.coordination_events)} coordination events from disk")

            # Load performance metrics
            if self.performance_metrics_file.exists():
                with open(self.performance_metrics_file, 'r') as f:
                    metrics_data = json.load(f)
                    self.performance_metrics = [
                        PerformanceMetric(**metric) for metric in metrics_data
                    ]
                print(f"Loaded {len(self.performance_metrics)} performance metrics from disk")

            # Load system health data
            if self.system_health_file.exists():
                with open(self.system_health_file, 'r') as f:
                    health_data = json.load(f)
                    self.system_health = [
                        SystemHealthMetric(**health) for health in health_data
                    ]
                print(f"Loaded {len(self.system_health)} system health records from disk")

            # Load mission stats
            if self.mission_stats_file.exists():
                with open(self.mission_stats_file, 'r') as f:
                    self.mission_stats = json.load(f)
                print(f"Loaded mission statistics from disk")

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
        survey_abandons = [
            e for e in recent_events if e.event_type == "survey_abandon"
        ]

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
                    "error_count": health_data["error_count"]
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

            print(f"Analytics data persisted to disk at {datetime.now().isoformat()}")

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
