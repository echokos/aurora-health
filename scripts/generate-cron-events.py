#!/usr/bin/env python3
"""Generate cron-events.json from health-monitor-config.json"""

import json
from datetime import datetime, timedelta
from pathlib import Path
import re

CONFIG_PATH = Path.home() / "aurora" / "health-monitor-config.json"
OUTPUT_PATH = Path.home() / "projects" / "aurora-health" / "dist" / "cron-events.json"

def parse_schedule(schedule_str: str) -> dict:
    """Convert human-readable schedule to structured format."""
    schedule = {
        "display": schedule_str,
        "frequency": "unknown",
        "times": []
    }
    
    s = schedule_str.lower()
    
    if "every 5 min" in s:
        schedule["frequency"] = "every-5-min"
        schedule["times"] = ["recurring"]
    elif "every 10 min" in s:
        schedule["frequency"] = "every-10-min"
        schedule["times"] = ["recurring"]
    elif "every 15 min" in s:
        schedule["frequency"] = "every-15-min"
        schedule["times"] = ["recurring"]
    elif "hourly" in s:
        schedule["frequency"] = "hourly"
        match = re.search(r':(\d+)', s)
        schedule["times"] = [f":{match.group(1)}" if match else ":00"]
    elif "daily" in s:
        schedule["frequency"] = "daily"
        # Try to match time with minutes first (e.g., "3:30am")
        match = re.search(r'(\d+):(\d+)(am|pm)', s)
        if match:
            hour = int(match.group(1))
            minute = match.group(2)
            if match.group(3) == "pm" and hour != 12:
                hour += 12
            elif match.group(3) == "am" and hour == 12:
                hour = 0
            schedule["times"] = [f"{hour:02d}:{minute}"]
        else:
            # Try to match time without minutes (e.g., "4am")
            match = re.search(r'(\d+)(am|pm)', s)
            if match:
                hour = int(match.group(1))
                if match.group(2) == "pm" and hour != 12:
                    hour += 12
                elif match.group(2) == "am" and hour == 12:
                    hour = 0
                schedule["times"] = [f"{hour:02d}:00"]
    elif "weekly" in s:
        schedule["frequency"] = "weekly"
        # Try to match day + time with minutes
        match = re.search(r'(\w+)\s+(\d+):(\d+)(am|pm)', s)
        if match:
            hour = int(match.group(2))
            minute = match.group(3)
            if match.group(4) == "pm" and hour != 12:
                hour += 12
            elif match.group(4) == "am" and hour == 12:
                hour = 0
            schedule["day"] = match.group(1).capitalize()
            schedule["times"] = [f"{hour:02d}:{minute}"]
        else:
            # Try to match day + time without minutes
            match = re.search(r'(\w+)\s+(\d+)(am|pm)', s)
            if match:
                hour = int(match.group(2))
                if match.group(3) == "pm" and hour != 12:
                    hour += 12
                elif match.group(3) == "am" and hour == 12:
                    hour = 0
                schedule["day"] = match.group(1).capitalize()
                schedule["times"] = [f"{hour:02d}:00"]
    elif "monthly" in s:
        schedule["frequency"] = "monthly"
        # Try to match time with minutes
        match = re.search(r'(\d+):(\d+)(am|pm)', s)
        if match:
            hour = int(match.group(1))
            minute = match.group(2)
            if match.group(3) == "pm" and hour != 12:
                hour += 12
            elif match.group(3) == "am" and hour == 12:
                hour = 0
            schedule["times"] = [f"{hour:02d}:{minute}"]
        else:
            # Try to match time without minutes
            match = re.search(r'(\d+)(am|pm)', s)
            if match:
                hour = int(match.group(1))
                if match.group(2) == "pm" and hour != 12:
                    hour += 12
                elif match.group(2) == "am" and hour == 12:
                    hour = 0
                schedule["times"] = [f"{hour:02d}:00"]
    
    return schedule

def generate_events():
    """Generate cron events JSON."""
    with open(CONFIG_PATH) as f:
        config = json.load(f)
    
    events = []
    
    # Extract scheduled jobs from config
    scheduled = config.get("groups", {}).get("scheduled-jobs", {})
    for component in scheduled.get("components", []):
        if "schedule" in component:
            events.append({
                "id": component["id"],
                "name": component["name"],
                "schedule": parse_schedule(component["schedule"]),
                "logfile": component.get("logfile", ""),
                "script": component.get("script", "")
            })
    
    # Also check other groups for cron-type components
    for group_id, group in config.get("groups", {}).items():
        if group_id == "scheduled-jobs":
            continue
        for component in group.get("components", []):
            if component.get("type") == "system_cron" and "schedule" in component:
                events.append({
                    "id": component["id"],
                    "name": component["name"],
                    "schedule": parse_schedule(component["schedule"]),
                    "logfile": component.get("logfile", ""),
                    "script": component.get("script", "")
                })
    
    output = {
        "generated": datetime.now().isoformat(),
        "events": events
    }
    
    with open(OUTPUT_PATH, "w") as f:
        json.dump(output, f, indent=2)
    
    print(f"Generated {len(events)} events to {OUTPUT_PATH}")

if __name__ == "__main__":
    generate_events()
