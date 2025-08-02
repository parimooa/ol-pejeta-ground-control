import asyncio
import json
from collections import defaultdict
from pathlib import Path
from typing import List, Tuple

from backend.config import CONFIG
from backend.schemas.survey import GroupedSurveyLog, SurveyInstance


class SurveyLogService:
    """
    A service to read, parse, and group survey data from JSON log files.
    """

    def __init__(self):
        self.surveys_dir = Path(CONFIG.directories.SURVEYED_AREA)
        self.surveys_dir.mkdir(exist_ok=True)

    async def get_grouped_logs_paginated(
        self, page: int, limit: int
    ) -> Tuple[List[GroupedSurveyLog], int]:
        """
        Reads all survey JSON files, groups them by mission waypoint,
        and returns a paginated list.
        """
        all_records = []
        # Use asyncio.to_thread to run sync file I/O without blocking the event loop
        file_paths = await asyncio.to_thread(
            lambda: list(self.surveys_dir.glob("*.json"))
        )

        for file_path in file_paths:
            try:
                content = await asyncio.to_thread(file_path.read_text)
                data = json.loads(content)
                if isinstance(data, list):
                    all_records.extend(data)
                elif isinstance(data, dict):
                    all_records.append(data)
            except (json.JSONDecodeError, IOError) as e:
                print(f"Warning: Could not read or parse survey file {file_path}: {e}")
                continue

        # Group records by mission_waypoint_id
        grouped_data = defaultdict(list)
        for record in all_records:
            # Ensure the record has a mission_waypoint_id to be included
            if record.get("mission_waypoint_id") is not None:
                grouped_data[record["mission_waypoint_id"]].append(record)

        # Process the grouped data into the final format
        processed_logs = []
        for waypoint_id, instances in grouped_data.items():
            # Sort instances by date to find the most recent one
            instances.sort(key=lambda x: x.get("completed_at", ""), reverse=True)

            processed_logs.append(
                GroupedSurveyLog(
                    mission_waypoint_id=waypoint_id,
                    survey_count=len(instances),
                    last_surveyed_at=instances[0].get("completed_at"),
                    instances=[
                        SurveyInstance(
                            id=inst.get("id"),
                            completed_at=inst.get("completed_at"),
                            duration_formatted=inst.get("duration_formatted", "N/A"),
                            survey_abandoned=inst.get("survey_abandoned", False),
                            waypoint_count=len(inst.get("waypoints", [])),
                        )
                        for inst in instances
                    ],
                )
            )

        # Sort the final grouped logs by the most recent survey time
        processed_logs.sort(key=lambda x: x.last_surveyed_at, reverse=True)

        total_count = len(processed_logs)
        start_index = (page - 1) * limit
        end_index = start_index + limit

        return processed_logs[start_index:end_index], total_count


# Singleton instance for easy use across the application
survey_log_service = SurveyLogService()
