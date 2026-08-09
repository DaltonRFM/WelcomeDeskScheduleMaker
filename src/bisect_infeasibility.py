"""
When aggregate checks (diagnostics.py) all look fine but the solver
still reports infeasible, the cause is usually constraints fighting
each other in combination -- not something a simple total-hours or
coverage-gap check can catch.

This script re-runs the real dataset against solve_week_schedule
several times, relaxing one constraint at a time, to isolate which one
is actually causing the conflict.

Usage:
    python -m src.bisect_infeasibility
"""

from src.availability_parser import parse_availability_csv
from src.solver import solve_week_schedule


def try_config(label, availabilities, day_hours, **kwargs):
    result = solve_week_schedule(availabilities, day_hours, **kwargs)
    status = "FEASIBLE" if result is not None else "infeasible"
    print(f"{status:12} -- {label}")
    return result is not None


def main():
    from src.main import CSV_FILES, DAY_OPERATING_HOURS, STATION_CAPACITY, MIN_HOURS, MAX_HOURS, ROTATION_STATIONS

    all_availabilities = []
    for day, filepath in CSV_FILES.items():
        all_availabilities.extend(parse_availability_csv(filepath, day))

    active_day_hours = {
        day: hours for day, hours in DAY_OPERATING_HOURS.items() if day in CSV_FILES
    }

    print("Testing combinations against your real data...\n")

    # Baseline: everything as configured in main.py
    try_config(
        "full config (as in main.py)",
        all_availabilities,
        active_day_hours,
        station_capacity=STATION_CAPACITY,
        min_hours=MIN_HOURS,
        max_hours=MAX_HOURS,
        rotation_stations=ROTATION_STATIONS,
    )

    # Without rotation requirement
    try_config(
        "WITHOUT rotation_stations",
        all_availabilities,
        active_day_hours,
        station_capacity=STATION_CAPACITY,
        min_hours=MIN_HOURS,
        max_hours=MAX_HOURS,
        rotation_stations=None,
    )

    # With a much wider hour band (basically no hour constraint)
    try_config(
        "with min_hours=0, max_hours=40 (hours effectively unconstrained)",
        all_availabilities,
        active_day_hours,
        station_capacity=STATION_CAPACITY,
        min_hours=0,
        max_hours=40,
        rotation_stations=ROTATION_STATIONS,
    )

    # With both relaxed
    try_config(
        "WITHOUT rotation AND hours effectively unconstrained",
        all_availabilities,
        active_day_hours,
        station_capacity=STATION_CAPACITY,
        min_hours=0,
        max_hours=40,
        rotation_stations=None,
    )

    # Slightly wider max_hours only (in case 12.5 is just a bit too tight)
    try_config(
        "with max_hours=15 (min_hours unchanged)",
        all_availabilities,
        active_day_hours,
        station_capacity=STATION_CAPACITY,
        min_hours=MIN_HOURS,
        max_hours=15,
        rotation_stations=ROTATION_STATIONS,
    )

    # Slightly lower min_hours only
    try_config(
        "with min_hours=8 (max_hours unchanged)",
        all_availabilities,
        active_day_hours,
        station_capacity=STATION_CAPACITY,
        min_hours=8,
        max_hours=MAX_HOURS,
        rotation_stations=ROTATION_STATIONS,
    )


if __name__ == "__main__":
    main()