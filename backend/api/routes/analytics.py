"""
Analytics API Routes for Performance Data Collection
Provides endpoints for accessing system performance and research data
"""

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any, Optional

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse

from ...services.analytics_service import analytics_service

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/performance")
async def get_performance_metrics(hours_back: int = Query(24, ge=1, le=168)):
    """
    Get system performance metrics for the specified time period
    """
    try:
        return analytics_service.get_performance_summary(hours_back=hours_back)
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to get performance metrics: {str(e)}"
        )


@router.get("/coordination")
async def get_coordination_statistics(hours_back: int = Query(24, ge=1, le=168)):
    """
    Get vehicle coordination performance statistics
    """
    try:
        return analytics_service.get_coordination_statistics(hours_back=hours_back)
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to get coordination statistics: {str(e)}"
        )


@router.get("/system-health")
async def get_system_health_report(hours_back: int = Query(24, ge=1, le=168)):
    """
    Get system health and reliability report
    """
    try:
        return analytics_service.get_system_health_report(hours_back=hours_back)
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to get system health report: {str(e)}"
        )


@router.get("/export")
async def export_research_data(format_type: str = Query("json", regex="^(json|csv)$")):
    """
    Export all analytics data for research analysis
    """
    try:
        export_data = analytics_service.export_research_data(format_type=format_type)

        if format_type == "json":
            return export_data
        elif format_type == "csv":
            # For CSV format, return the file path for download
            csv_file = _convert_to_csv(export_data)
            return FileResponse(
                path=csv_file,
                filename=f"analytics_export_{int(datetime.now().timestamp())}.csv",
                media_type="text/csv",
            )
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to export research data: {str(e)}"
        )


@router.get("/dashboard-data")
async def get_dashboard_data():
    """
    Get comprehensive data for analytics dashboard
    """
    try:
        return {
            "current_time": datetime.now().isoformat(),
            "session_start": analytics_service.current_session_start.isoformat(),
            "coordination_stats_24h": analytics_service.get_coordination_statistics(
                hours_back=24
            ),
            "coordination_stats_7d": analytics_service.get_coordination_statistics(
                hours_back=168
            ),
            "performance_summary_24h": analytics_service.get_performance_summary(
                hours_back=24
            ),
            "system_health_24h": analytics_service.get_system_health_report(
                hours_back=24
            ),
            "mission_statistics": analytics_service.mission_stats.copy(),
            "recent_events": _get_recent_events(limit=10),
        }
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to get dashboard data: {str(e)}"
        )


@router.get("/events/recent")
async def get_recent_events(limit: int = Query(50, ge=1, le=1000)):
    """
    Get recent coordination events
    """
    try:
        return _get_recent_events(limit=limit)
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to get recent events: {str(e)}"
        )


@router.get("/metrics/distance-analysis")
async def get_distance_analysis(hours_back: int = Query(24, ge=1, le=168)):
    """
    Get detailed distance-based performance analysis
    """
    try:
        cutoff_time = datetime.now() - timedelta(hours=hours_back)
        recent_events = [
            e
            for e in analytics_service.coordination_events
            if datetime.fromisoformat(e.timestamp) > cutoff_time
        ]

        if not recent_events:
            return {"error": "No recent events found"}

        # Detailed distance analysis
        distance_buckets = {
            "0-50m": [],
            "50-100m": [],
            "100-200m": [],
            "200-300m": [],
            "300-400m": [],
            "400-500m": [],
            ">500m": [],
        }

        for event in recent_events:
            distance = event.distance
            if distance < 50:
                distance_buckets["0-50m"].append(event)
            elif distance < 100:
                distance_buckets["50-100m"].append(event)
            elif distance < 200:
                distance_buckets["100-200m"].append(event)
            elif distance < 300:
                distance_buckets["200-300m"].append(event)
            elif distance < 400:
                distance_buckets["300-400m"].append(event)
            elif distance < 500:
                distance_buckets["400-500m"].append(event)
            else:
                distance_buckets[">500m"].append(event)

        analysis = {}
        for bucket_name, events in distance_buckets.items():
            if events:
                survey_starts = [e for e in events if e.event_type == "survey_start"]
                survey_completes = [
                    e for e in events if e.event_type == "survey_complete"
                ]
                survey_abandons = [
                    e for e in events if e.event_type == "survey_abandon"
                ]
                follow_starts = [e for e in events if e.event_type == "follow_start"]

                durations = [e.duration_seconds for e in events if e.duration_seconds]
                avg_duration = sum(durations) / len(durations) if durations else None

                analysis[bucket_name] = {
                    "total_events": len(events),
                    "survey_starts": len(survey_starts),
                    "survey_completes": len(survey_completes),
                    "survey_abandons": len(survey_abandons),
                    "follow_starts": len(follow_starts),
                    "avg_duration_seconds": avg_duration,
                    "success_rate": (
                        len(survey_completes) / len(survey_starts) * 100
                        if survey_starts
                        else 0
                    ),
                }

        return {
            "time_period_hours": hours_back,
            "total_events_analyzed": len(recent_events),
            "distance_analysis": analysis,
        }

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to get distance analysis: {str(e)}"
        )


@router.get("/metrics/efficiency")
async def get_efficiency_metrics(hours_back: int = Query(24, ge=1, le=168)):
    """
    Calculate mission efficiency and operational metrics
    """
    try:
        cutoff_time = datetime.now() - timedelta(hours=hours_back)
        recent_events = [
            e
            for e in analytics_service.coordination_events
            if datetime.fromisoformat(e.timestamp) > cutoff_time
        ]

        if not recent_events:
            return {"error": "No recent events found"}

        # Calculate efficiency metrics
        survey_starts = [e for e in recent_events if e.event_type == "survey_start"]
        survey_completes = [
            e for e in recent_events if e.event_type == "survey_complete"
        ]
        survey_abandons = [e for e in recent_events if e.event_type == "survey_abandon"]

        total_surveys = len(survey_starts)
        completed_surveys = len(survey_completes)
        abandoned_surveys = len(survey_abandons)

        # Duration analysis
        completed_durations = [
            e.duration_seconds for e in survey_completes if e.duration_seconds
        ]
        abandoned_durations = [
            e.duration_seconds for e in survey_abandons if e.duration_seconds
        ]

        return {
            "time_period_hours": hours_back,
            "operational_efficiency": {
                "total_surveys_started": total_surveys,
                "surveys_completed": completed_surveys,
                "surveys_abandoned": abandoned_surveys,
                "completion_rate_percent": (
                    round(completed_surveys / total_surveys * 100, 2)
                    if total_surveys > 0
                    else 0
                ),
                "abandonment_rate_percent": (
                    round(abandoned_surveys / total_surveys * 100, 2)
                    if total_surveys > 0
                    else 0
                ),
            },
            "duration_analysis": {
                "completed_surveys": {
                    "count": len(completed_durations),
                    "avg_duration_seconds": (
                        round(sum(completed_durations) / len(completed_durations), 2)
                        if completed_durations
                        else None
                    ),
                    "min_duration_seconds": (
                        min(completed_durations) if completed_durations else None
                    ),
                    "max_duration_seconds": (
                        max(completed_durations) if completed_durations else None
                    ),
                },
                "abandoned_surveys": {
                    "count": len(abandoned_durations),
                    "avg_duration_seconds": (
                        round(sum(abandoned_durations) / len(abandoned_durations), 2)
                        if abandoned_durations
                        else None
                    ),
                    "min_duration_seconds": (
                        min(abandoned_durations) if abandoned_durations else None
                    ),
                    "max_duration_seconds": (
                        max(abandoned_durations) if abandoned_durations else None
                    ),
                },
            },
        }

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to calculate efficiency metrics: {str(e)}"
        )


@router.post("/reset-session")
async def reset_session_data():
    """
    Reset session analytics data (useful for testing)
    """
    try:
        analytics_service.reset_session_data()
        return {
            "message": "Session analytics data reset successfully",
            "new_session_start": analytics_service.current_session_start.isoformat(),
        }
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to reset session data: {str(e)}"
        )


@router.post("/persist")
async def force_persist_data():
    """
    Force immediate persistence of analytics data to disk
    """
    try:
        analytics_service.force_persist()
        return {
            "message": "Analytics data persisted to disk successfully",
            "persisted_at": datetime.now().isoformat(),
            "coordination_events": len(analytics_service.coordination_events),
            "performance_metrics": len(analytics_service.performance_metrics),
            "system_health_records": len(analytics_service.system_health),
        }
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to persist analytics data: {str(e)}"
        )


def _get_recent_events(limit: int = 50) -> List[Dict]:
    """Get recent coordination events"""
    recent_events = sorted(
        analytics_service.coordination_events, key=lambda x: x.timestamp, reverse=True
    )[:limit]

    return [
        {
            "timestamp": event.timestamp,
            "event_type": event.event_type,
            "distance": event.distance,
            "duration_seconds": event.duration_seconds,
            "reason": event.reason,
            "metadata": event.metadata,
        }
        for event in recent_events
    ]


def _convert_to_csv(export_data: Dict) -> str:
    """Convert export data to CSV format"""
    import csv
    from io import StringIO

    csv_file_path = (
        analytics_service.analytics_dir
        / f"export_{int(datetime.now().timestamp())}.csv"
    )

    with open(csv_file_path, "w", newline="", encoding="utf-8") as csvfile:
        writer = csv.writer(csvfile)

        # Write coordination events
        writer.writerow(["Event Data"])
        writer.writerow(
            [
                "Timestamp",
                "Event Type",
                "Distance",
                "Duration",
                "Reason",
                "Drone Lat",
                "Drone Lon",
                "Car Lat",
                "Car Lon",
            ]
        )

        for event in export_data.get("coordination_events", []):
            writer.writerow(
                [
                    event["timestamp"],
                    event["event_type"],
                    event["distance"],
                    event.get("duration_seconds", ""),
                    event.get("reason", ""),
                    event["drone_position"].get("latitude", ""),
                    event["drone_position"].get("longitude", ""),
                    event["car_position"].get("latitude", ""),
                    event["car_position"].get("longitude", ""),
                ]
            )

        # Write performance metrics
        writer.writerow([])
        writer.writerow(["Performance Metrics"])
        writer.writerow(["Timestamp", "Metric Name", "Value", "Unit"])

        for metric in export_data.get("performance_metrics", []):
            writer.writerow(
                [
                    metric["timestamp"],
                    metric["metric_name"],
                    metric["value"],
                    metric["unit"],
                ]
            )

    return str(csv_file_path)
