"""
Step 8: the real end-to-end pipeline.

Reads one availability CSV per weekday (exported from the Apps Script
Y/N conversion -- see tools/apps_script_color_to_yn.gs), runs the
solver, and writes the finished schedule out to a CSV.

This still isn't pulling live from Google Sheets (that's a later step --
auth setup is its own chunk of work). For now, you export each day's
"_YN" tab as a CSV into data/, named to match CSV_FILES below, and run
this script.

Usage:
    python -m src.main
"""

from datetime import time

from src.availability_parser import parse_availability_csv
from src.models import Day, Person, Station
from src.output_writer import write_schedule_csv
from src.solver import solve_week_schedule

# Update these paths once you've exported real Y/N CSVs from the Apps
# Script for each day. Days you don't have a file for yet can just be
# omitted from this dict -- the pipeline will only schedule the days
# present here.
CSV_FILES = {
    Day.MONDAY: "data/monday_availability.csv",
    Day.TUESDAY: "data/tuesday_availability.csv",
    Day.WEDNESDAY: "data/wednesday_availability.csv",
    Day.THURSDAY: "data/thursday_availability.csv",
    Day.FRIDAY: "data/friday_availability.csv",
}

# Business rules from docs/PLANNING.md
DAY_OPERATING_HOURS = {
    Day.MONDAY: (time(7, 30), time(17, 0)),
    Day.TUESDAY: (time(7, 30), time(17, 0)),
    Day.WEDNESDAY: (time(7, 30), time(17, 0)),
    Day.THURSDAY: (time(7, 30), time(17, 0)),
    Day.FRIDAY: (time(8, 0), time(17, 0)),
}

STATION_CAPACITY = {
    Station.NORTH: 2,
    Station.SOUTH: 2,
    Station.DEANS_SUITE: 1,
}
FLEXIBLE_STATIONS = {Station.DEANS_SUITE}
ROTATION_STATIONS = [Station.NORTH, Station.SOUTH]
MIN_HOURS = 9.0
MAX_HOURS = 13.0
EXACT_HALF_OR_FULL_DAYS = {Day.FRIDAY}

# Lock specific people into specific Friday blocks -- e.g. new hires who
# always cover a known Friday shift. Values are "AM" (first half),
# "PM" (second half), or "FULL" (whole day). Add entries here as needed;
# leave empty ({}) if nobody needs to be pinned this semester.
#
# Example:
#     from src.models import Person
#     PINNED_SHIFT_BLOCKS = {
#         Person(name="Sam"): {Day.FRIDAY: "AM"},
#         Person(name="Jordan"): {Day.FRIDAY: "FULL"},
#     }
PINNED_SHIFT_BLOCKS = {
    Person(name='Caroline S'): {Day.FRIDAY: 'AM'},
    Person(name='Charlie'): {Day.FRIDAY: 'FULL'},
    Person(name='Mia'): {Day.FRIDAY: 'AM'},
    Person(name='Abby'): {Day.FRIDAY: 'AM'},
    Person(name='Keira'): {Day.FRIDAY: 'PM'},
    Person(name='Naisha'): {Day.FRIDAY: 'PM'},
    Person(name='Alex'): {Day.FRIDAY: 'PM'},
    Person(name='Reese'): {Day.FRIDAY: 'PM'}
}

OUTPUT_PATH = "data/generated_schedule.csv"


def main():
    all_availabilities = []
    for day, filepath in CSV_FILES.items():
        all_availabilities.extend(parse_availability_csv(filepath, day))

    active_day_hours = {
        day: hours for day, hours in DAY_OPERATING_HOURS.items() if day in CSV_FILES
    }

    shifts = solve_week_schedule(
        availabilities=all_availabilities,
        day_operating_hours=active_day_hours,
        station_capacity=STATION_CAPACITY,
        min_hours=MIN_HOURS,
        max_hours=MAX_HOURS,
        rotation_stations=ROTATION_STATIONS,
        flexible_stations=FLEXIBLE_STATIONS,
        exact_half_or_full_days=EXACT_HALF_OR_FULL_DAYS,
        pinned_shift_blocks=PINNED_SHIFT_BLOCKS
    )

    if shifts is None:
        print("No valid schedule found -- constraints are too tight to satisfy.")
        print("Try loosening min/max hours, or double-check availability data.")
        return

    write_schedule_csv(shifts, OUTPUT_PATH)
    print(f"Schedule written to {OUTPUT_PATH} ({len(shifts)} shifts).")


if __name__ == "__main__":
    main()