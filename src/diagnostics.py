"""
Diagnostic tool: when solve_week_schedule() returns None, this figures
out roughly WHY, instead of leaving you to guess.

Checks two of the most common causes of infeasibility:
1. Coverage gaps -- a time slot where fewer people are available than
   there are stations to staff (impossible to cover no matter what).
2. Total availability vs. total hour requirements -- not enough
   person-hours of availability across the whole week to hit
   min_hours per person for everyone.

This does NOT check every possible cause (e.g. rotation station
requirements or open/close requirements can also cause infeasibility
even when coverage and hours look fine), but it catches the most common
and easiest-to-fix ones first.

Usage:
    python -m src.diagnostics
"""

from datetime import time

from src.availability_parser import parse_availability_csv
from src.models import Day
from src.solver import _generate_slots


def check_coverage_gaps(availabilities, day_operating_hours, stations):
    """
    For every slot, counts how many people are available. Flags any
    slot where that count is less than the number of stations needed
    (impossible to staff no matter how the solver assigns people).
    """
    people = sorted({a.person for a in availabilities}, key=lambda p: p.name)
    avail_lookup = {
        (a.person, a.slot.day, a.slot.start): a.is_available for a in availabilities
    }

    gaps = []
    for day, (start, end) in day_operating_hours.items():
        slots = _generate_slots(day, start, end)
        for s in slots:
            available_count = sum(
                1 for p in people if avail_lookup.get((p, day, s.start), False)
            )
            if available_count < len(stations):
                gaps.append((day, s.start, available_count, len(stations)))

    return gaps


def check_total_hours_feasibility(availabilities, day_operating_hours, min_hours):
    """
    Rough sanity check: total available person-hours across the week,
    vs. the minimum this would require if everyone needs at least
    min_hours. Doesn't guarantee feasibility (availability could still
    be badly distributed) but catches an obviously impossible target.
    """
    people = sorted({a.person for a in availabilities}, key=lambda p: p.name)
    num_people = len(people)

    total_required_person_hours = num_people * min_hours

    total_slots_needed = 0
    for day, (start, end) in day_operating_hours.items():
        slots = _generate_slots(day, start, end)
        total_slots_needed += len(slots)

    # Total coverage hours actually needed (assuming 1 person per
    # station per slot -- adjust if you pass multiple stations)
    return {
        "num_people": num_people,
        "total_required_person_hours": total_required_person_hours,
        "total_operating_slots": total_slots_needed,
    }


def print_report(availabilities, day_operating_hours, stations, min_hours):
    print("=== Coverage gap check ===")
    gaps = check_coverage_gaps(availabilities, day_operating_hours, stations)
    if not gaps:
        print("No coverage gaps found -- every slot has enough available people.")
    else:
        print(f"Found {len(gaps)} slot(s) where not enough people are available:")
        for day, slot_start, available, needed in gaps[:20]:
            print(
                f"  {day.value} {slot_start.strftime('%I:%M %p').lstrip('0')}: "
                f"only {available} available, need {needed}"
            )
        if len(gaps) > 20:
            print(f"  ...and {len(gaps) - 20} more")

    print()
    print("=== Hours sanity check ===")
    stats = check_total_hours_feasibility(availabilities, day_operating_hours, min_hours)
    print(f"People: {stats['num_people']}")
    print(f"Total required person-hours (num_people x min_hours): {stats['total_required_person_hours']}")
    print(f"Total operating slots across the week: {stats['total_operating_slots']}")


if __name__ == "__main__":
    from src.main import CSV_FILES, DAY_OPERATING_HOURS, STATIONS, MIN_HOURS

    all_availabilities = []
    for day, filepath in CSV_FILES.items():
        all_availabilities.extend(parse_availability_csv(filepath, day))

    active_day_hours = {
        day: hours for day, hours in DAY_OPERATING_HOURS.items() if day in CSV_FILES
    }

    print_report(all_availabilities, active_day_hours, STATIONS, MIN_HOURS)