"""
Parses a per-day availability CSV into Person/Availability objects.

Expected CSV format (one file per day):
    - Column A: time slot start, e.g. "7:30 AM" (15-min increments)
    - Header row: person names across the remaining columns
    - Cell values: "Y" (available) or "N" (busy/unavailable) — blank is
      treated as "N" so a half-filled sheet doesn't accidentally mark
      people available.

This assumes the master color-coded sheet has been (or will be) converted
to text values. See docs/PLANNING.md for why we're not reading cell
background colors directly yet.
"""

import csv
from datetime import datetime, time, timedelta

from src.models import Availability, Day, Person, TimeSlot

SLOT_MINUTES = 15


def _parse_time(raw: str) -> time:
    """Turns '7:30 AM' into a datetime.time. Adjust the format string here
    if your sheet exports times differently."""
    return datetime.strptime(raw.strip(), "%I:%M %p").time()


def _slot_end(start: time) -> time:
    dummy_date = datetime(2000, 1, 1, start.hour, start.minute)
    return (dummy_date + timedelta(minutes=SLOT_MINUTES)).time()


def parse_availability_csv(filepath: str, day: Day) -> list[Availability]:
    """
    Reads one day's availability CSV and returns a flat list of
    Availability objects — one per (person, time slot) combination found
    in the file.
    """
    availabilities: list[Availability] = []

    with open(filepath, newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        rows = list(reader)

    if not rows:
        return availabilities

    header = rows[0]
    people = [Person(name=name.strip()) for name in header[1:] if name.strip()]

    for row in rows[1:]:
        if not row or not row[0].strip():
            continue

        start = _parse_time(row[0])
        end = _slot_end(start)
        slot = TimeSlot(day=day, start=start, end=end)

        for person, cell in zip(people, row[1:]):
            is_available = cell.strip().upper() == "Y"
            availabilities.append(
                Availability(person=person, slot=slot, is_available=is_available)
            )

    return availabilities