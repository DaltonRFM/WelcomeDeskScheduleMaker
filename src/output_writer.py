"""
Step 9 (early): writes a solved schedule out to a plain CSV file.

One row per shift: Day, Station, Person, Start, End. Sorted so the CSV
reads naturally (Monday through Friday, in time order within each day),
not in whatever order the solver happened to return shifts in.
"""

import csv

from src.models import Day, Shift

DAY_ORDER = {day: i for i, day in enumerate(Day)}


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