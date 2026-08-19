"""
Step 8: the real end-to-end pipeline.

Reads one availability CSV per weekday (exported from the Apps Script
Y/N conversion -- see tools/apps_script_color_to_yn.gs), runs the
solver, and writes the finished schedule out to a CSV.

This still isn't pulling live from Google Sheets (that's a later step --
auth setup is its own chunk of work). For now, you export each day's
"_YN" tab as a CSV into data/, named to match CSV_FILES below, and run
this script.

Fully run the program to generate a new excel spreadsheet using these two commands:
    python -m src.main
    python -m src.xlsx_writer
"""

from datetime import time

from src.availability_parser import apply_blackouts, parse_availability_csv
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

# Hours are from 7:30am to 5pm then Friday 8-5pm
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
MAX_SHIFT_MINUTES = 480.0  # 8 hours -- ignored on Friday (governed by the AM/PM/FULL rule instead)
EXACT_HALF_OR_FULL_DAYS = {Day.FRIDAY}

# Lock specific people into specific Friday blocks
# leave empty ({}) if nobody needs to be pinned this semester.
#
PINNED_SHIFT_BLOCKS = {
    Person(name='Caroline S'): {Day.FRIDAY: 'AM'},
    Person(name='Charlie'): {Day.FRIDAY: 'FULL'},
    Person(name='Olivia D'): {Day.FRIDAY: 'AM'},
    Person(name='Mia'): {Day.FRIDAY: 'AM'},
    Person(name='Abby'): {Day.FRIDAY: 'AM'},
    Person(name='Keira'): {Day.FRIDAY: 'PM'},
    Person(name='Naisha'): {Day.FRIDAY: 'PM'},
    Person(name='Alex'): {Day.FRIDAY: 'PM'},
    Person(name='Reese'): {Day.FRIDAY: 'PM'}
}

# Individual shift requests -- ex: "Dalton wants 7:30-12:30 Monday".
# SOFT: the solver tries hard to honor these but will never let a
# request break a hard rule or block the schedule from solving. After
# solving, a report prints showing exactly how well each request was
# honored (fully / partially / not at all) -- see diagnostics.py.
#
# Example:
#     from src.models import Person
#     SHIFT_REQUESTS = {
#     Person(name="Dalton"): [(Day.MONDAY, time(7, 30), time(12, 30))],
#     Person(name="Ivanna"): [ (This is how you do multiple requests for the same person)
#         (Day.MONDAY, time(7, 30), time(12, 30)),
#         (Day.TUESDAY, time(14, 0), time(17, 0)),
#     ],
# }
# It's in military time for the hours! 

SHIFT_REQUESTS = {
    Person(name="Ivanna"): [
        (Day.MONDAY, time(7, 30), time(12, 30)),
        (Day.TUESDAY, time(14, 0), time(17, 0)),
    ],
     Person(name="Grace"): [(Day.MONDAY, time(7, 30), time(12, 30))]

}

# Personal "I don't want to work X" preferences -- treated as a HARD
# blackout (same weight as being in class), not a soft ask. Each
# person's list can mix whole-day entries and partial-window entries.
#
# Example:
#     from src.models import Person
#     BLACKOUTS = {
#         Person(name="Laila"): [Day.MONDAY],  # whole day off
#         Person(name="Sam"): [(Day.TUESDAY, time(14, 0), time(17, 0))],  # just Tue afternoons
#     }
BLACKOUTS = {
    Person(name="Laila"): [Day.MONDAY]
}

OUTPUT_PATH = "data/generated_schedule.csv"


def main():
    all_availabilities = []
    for day, filepath in CSV_FILES.items():
        all_availabilities.extend(parse_availability_csv(filepath, day))

    all_availabilities = apply_blackouts(all_availabilities, BLACKOUTS)

    active_day_hours = {
        day: hours for day, hours in DAY_OPERATING_HOURS.items() if day in CSV_FILES
    }

    shifts = solve_week_schedule(
        availabilities=all_availabilities,
        day_operating_hours=active_day_hours,
        station_capacity=STATION_CAPACITY,
        min_hours=MIN_HOURS,
        max_hours=MAX_HOURS,
        max_shift_minutes=MAX_SHIFT_MINUTES,
        rotation_stations=ROTATION_STATIONS,
        flexible_stations=FLEXIBLE_STATIONS,
        exact_half_or_full_days=EXACT_HALF_OR_FULL_DAYS,
        pinned_shift_blocks=PINNED_SHIFT_BLOCKS,
        shift_requests=SHIFT_REQUESTS
    )

    if shifts is None:
        print("No valid schedule found -- constraints are too tight to satisfy.")
        print("Try loosening min/max hours, or double-check availability data.")
        return

    write_schedule_csv(shifts, OUTPUT_PATH)
    print(f"Schedule written to {OUTPUT_PATH} ({len(shifts)} shifts).")

    from src.diagnostics import print_request_report
    print_request_report(shifts, SHIFT_REQUESTS)


if __name__ == "__main__":
    main()