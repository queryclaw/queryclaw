"""Schedule parser for at/every/cron expressions."""

from __future__ import annotations

import re
from typing import Any

from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger


def parse_schedule(schedule: str) -> Any:
    """Parse schedule string into APScheduler trigger.

    Supports:
    - "at HH:MM" — daily at given time (e.g. "at 09:00")
    - "every Nm" / "every Nh" — interval (e.g. "every 30m", "every 1h")
    - "cron min hour day month weekday" — 5-field cron (e.g. "cron 0 9 * * 1" = Mon 9am)

    Returns:
        APScheduler trigger (CronTrigger or IntervalTrigger).
    Raises:
        ValueError: If schedule format is invalid.
    """
    s = schedule.strip().lower()

    # at HH:MM — daily
    m = re.match(r"at\s+(\d{1,2}):(\d{2})$", s)
    if m:
        hour, minute = int(m.group(1)), int(m.group(2))
        if 0 <= hour <= 23 and 0 <= minute <= 59:
            return CronTrigger(hour=hour, minute=minute)
        raise ValueError(f"Invalid time: {schedule}")

    # every Nm / every Nh
    m = re.match(r"every\s+(\d+)\s*(m|min|minute|minutes|h|hour|hours)$", s)
    if m:
        n = int(m.group(1))
        unit = m.group(2).lower()
        if n <= 0:
            raise ValueError(f"Interval must be positive: {schedule}")
        if unit.startswith("m"):
            return IntervalTrigger(minutes=n)
        return IntervalTrigger(hours=n)

    # cron min hour day month weekday (5 fields)
    m = re.match(r"cron\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)$", s)
    if m:
        fields = m.group(1), m.group(2), m.group(3), m.group(4), m.group(5)
        return CronTrigger(
            minute=fields[0],
            hour=fields[1],
            day=fields[2],
            month=fields[3],
            day_of_week=fields[4],
        )

    raise ValueError(f"Unknown schedule format: {schedule}")
