"""
Step 9 (early): writes a solved schedule out to a plain CSV file.

One row per shift: Day, Station, Person, Start, End. Sorted so the CSV
reads naturally (Monday through Friday, in time order within each day),
not in whatever order the solver happened to return shifts in.
"""

import csv
from datetime import datetime

from src.models import Day, Person, Shift, Station

DAY_ORDER = {day: i for i, day in enumerate(Day)}
DAY_BY_NAME = {d.value: d for d in Day}
STATION_BY_NAME = {s.value: s for s in Station}


def write_schedule_csv(shifts: list[Shift], filepath: str) -> None:
    sorted_shifts = sorted(
        shifts,
        key=lambda s: (
            DAY_ORDER[s.day],
            s.start,
            s.station.value if s.station else "",
        ),
    )

    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Day", "Station", "Person", "Start", "End", "Hours"])

        for s in sorted_shifts:
            writer.writerow(
                [
                    s.day.value,
                    s.station.value if s.station else "",
                    s.person.name,
                    s.start.strftime("%I:%M %p").lstrip("0"),
                    s.end.strftime("%I:%M %p").lstrip("0"),
                    s.duration_hours(),
                ]
            )


def read_schedule_csv(filepath: str) -> list[Shift]:
    """
    Reverses write_schedule_csv -- reads an already-generated schedule
    CSV back into Shift objects. Used so downstream outputs (like the
    xlsx writer) can reuse an already-solved schedule instead of
    re-running the solver and risking a different (still valid, but
    different) result.
    """
    shifts = []
    with open(filepath, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            shifts.append(
                Shift(
                    person=Person(name=row["Person"]),
                    day=DAY_BY_NAME[row["Day"]],
                    start=datetime.strptime(row["Start"].strip(), "%I:%M %p").time(),
                    end=datetime.strptime(row["End"].strip(), "%I:%M %p").time(),
                    station=STATION_BY_NAME[row["Station"]] if row["Station"] else None,
                )
            )
    return shifts