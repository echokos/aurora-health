#!/usr/bin/env python3
"""Generate cron-events.json from multiple sources:
- health-monitor-config.json (system cron jobs)
- ~/.openclaw/cron/jobs.json (OpenClaw scheduled tasks)
- systemd user timers
"""

import json
from datetime import datetime, timedelta
from pathlib import Path
import re
import subprocess

CONFIG_PATH = Path.home() / "aurora" / "health-monitor-config.json"
OPENCLAW_CRON_PATH = Path.home() / ".openclaw" / "cron" / "jobs.json"
OUTPUT_PATH = Path.home() / "projects" / "aurora-health" / "dist" / "cron-events.json"

def parse_cron_expression(cron_expr: str) -> dict:
    """Convert cron expression (e.g., '*/30 * * * *') to schedule format."""
    parts = cron_expr.split()
    if len(parts) != 5:
        return {"display": cron_expr, "frequency": "unknown", "times": []}
    
    minute, hour, day, month, weekday = parts
    
    # Check for every-X-minute patterns
    if minute.startswith("*/"):
        interval = minute[2:]
        return {
            "display": f"every {interval} min",
            "frequency": f"every-{interval}-min",
            "times": ["recurring"]
        }
    
    # Hourly pattern (specific minute each hour)
    if hour == "*" and day == "*" and month == "*" and weekday == "*":
        return {
            "display": f"hourly :{minute.zfill(2)}",
            "frequency": "hourly",
            "times": [f":{minute.zfill(2)}"]
        }
    
    # Daily pattern (specific time each day)
    if day == "*" and month == "*" and weekday == "*":
        h = int(hour) if hour != "*" else 0
        m = int(minute) if minute != "*" else 0
        time_str = f"{h:02d}:{m:02d}"
        am_pm = "am" if h < 12 else "pm"
        display_h = h if h <= 12 else h - 12
        if display_h == 0:
            display_h = 12
        return {
            "display": f"daily {display_h}:{m:02d}{am_pm}",
            "frequency": "daily",
            "times": [time_str]
        }
    
    # Default fallback
    return {
        "display": cron_expr,
        "frequency": "custom",
        "times": []
    }

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

def load_openclaw_jobs():
    """Load OpenClaw scheduled jobs."""
    jobs = []
    try:
        if OPENCLAW_CRON_PATH.exists():
            with open(OPENCLAW_CRON_PATH) as f:
                data = json.load(f)
                for job in data.get("jobs", []):
                    if not job.get("enabled", True):
                        continue
                    
                    schedule_data = job.get("schedule", {})
                    if schedule_data.get("kind") == "cron":
                        cron_expr = schedule_data.get("expr", "")
                        jobs.append({
                            "id": f"openclaw-{job['id'][:8]}",
                            "name": job.get("name", "Unknown OpenClaw Job"),
                            "schedule": parse_cron_expression(cron_expr),
                            "source": "OpenClaw Scheduler",
                            "description": job.get("description", "")
                        })
    except Exception as e:
        print(f"Warning: Failed to load OpenClaw jobs: {e}")
    
    return jobs

def load_systemd_timers():
    """Load systemd user timers."""
    timers = []
    try:
        result = subprocess.run(
            ["systemctl", "--user", "list-timers", "--all", "--no-pager"],
            capture_output=True,
            text=True,
            timeout=5
        )
        
        if result.returncode == 0:
            lines = result.stdout.strip().split("\n")
            # Skip header and footer
            for line in lines[1:-2]:
                if not line.strip():
                    continue
                
                parts = line.split()
                if len(parts) < 5:
                    continue
                
                # Extract timer name (usually second to last column)
                timer_name = parts[-2] if parts[-2].endswith(".timer") else None
                if not timer_name:
                    continue
                
                # Skip snap timers (system-level)
                if timer_name.startswith("snap."):
                    continue
                
                timers.append({
                    "id": f"timer-{timer_name.replace('.timer', '')}",
                    "name": timer_name.replace(".timer", "").replace("-", " ").title(),
                    "schedule": {
                        "display": "systemd timer",
                        "frequency": "timer",
                        "times": []
                    },
                    "source": "systemd timer"
                })
    except Exception as e:
        print(f"Warning: Failed to load systemd timers: {e}")
    
    return timers

def generate_events():
    """Generate cron events JSON from all sources."""
    events = []
    
    # 1. Load from health-monitor-config.json (system cron)
    try:
        with open(CONFIG_PATH) as f:
            config = json.load(f)
        
        # Extract scheduled jobs from config
        scheduled = config.get("groups", {}).get("scheduled-jobs", {})
        for component in scheduled.get("components", []):
            if "schedule" in component:
                events.append({
                    "id": component["id"],
                    "name": component["name"],
                    "schedule": parse_schedule(component["schedule"]),
                    "logfile": component.get("logfile", ""),
                    "script": component.get("script", ""),
                    "source": "system cron"
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
                        "script": component.get("script", ""),
                        "source": "system cron"
                    })
    except Exception as e:
        print(f"Warning: Failed to load system cron jobs: {e}")
    
    # 2. Load OpenClaw scheduled jobs
    openclaw_jobs = load_openclaw_jobs()
    events.extend(openclaw_jobs)
    
    # 3. Load systemd timers
    systemd_timers = load_systemd_timers()
    events.extend(systemd_timers)
    
    output = {
        "generated": datetime.now().isoformat(),
        "sources": {
            "system_cron": len([e for e in events if e.get("source") == "system cron"]),
            "openclaw": len(openclaw_jobs),
            "systemd": len(systemd_timers),
            "total": len(events)
        },
        "events": events
    }
    
    with open(OUTPUT_PATH, "w") as f:
        json.dump(output, f, indent=2)
    
    print(f"Generated {len(events)} events to {OUTPUT_PATH}")
    print(f"  - System cron: {output['sources']['system_cron']}")
    print(f"  - OpenClaw: {output['sources']['openclaw']}")
    print(f"  - systemd: {output['sources']['systemd']}")

if __name__ == "__main__":
    generate_events()
