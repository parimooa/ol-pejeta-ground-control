#!/usr/bin/env python3
"""
Script to force persistence of current analytics data
"""

from backend.services.analytics_service import analytics_service

def force_persist():
    """Force persistence of current analytics data"""
    print("Forcing persistence of analytics data...")
    analytics_service.force_persist()
    
    print(f"Persisted {len(analytics_service.coordination_events)} coordination events")
    print(f"Persisted {len(analytics_service.performance_metrics)} performance metrics")
    print(f"Persisted {len(analytics_service.system_health)} system health records")
    print("Analytics data has been saved to persistent files!")

if __name__ == "__main__":
    force_persist()