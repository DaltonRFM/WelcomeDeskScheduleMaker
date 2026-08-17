"""
Diagnostic tool: when solve_week_schedule() returns None, this figures
out roughly WHY, instead of leaving you to guess.

Checks two of the most common causes of infeasibility:
1. Coverage gaps -- a time slot where fewer people are available than
   the total station_capacity needed (impossible to cover no matter
   what).
2. Total availability vs. total hour requirements -- not enough
   coverage-hours across the whole week to hit min_hours per person
   for everyone.

This does NOT check every possible cause (e.g. rotation station
requirements or open/close requirements can also cause infeasibility
even when coverage and hours look fine), but it catches the most common
and easiest-to-fix ones first.

Usage:
    python -m src.diagnostics
"""

from src.availability_parser import parse_availability_csv
from src.models import Day
from src.solver import _generate_slots


def check_coverage_gaps(availabilities, day_operating_hours, station_capacity):
    """
    For every slot, counts how many people are available. Flags any
    slot where that count is less than the TOTAL capacity needed across
    all stations (impossible to staff no matter how the solver assigns
    people).
    """
    people = sorted({a.person for a in availabilities}, key=lambda p: p.name)
    avail_lookup = {
        (a.person, a.slot.day, a.slot.start): a.is_available for a in availabilities
    }
    total_capacity_needed = sum(station_capacity.values())

    gaps = []
    for day, (start, end) in day_operating_hours.items():
        slots = _generate_slots(day, start, end)
        for s in slots:
            available_count = sum(
                1 for p in people if avail_lookup.get((p, day, s.start), False)
            )
            if available_count < total_capacity_needed:
                gaps.append((day, s.start, available_count, total_capacity_needed))

    return gaps


def check_total_hours_feasibility(availabilities, day_operating_hours, station_capacity, min_hours):
    """
    Rough sanity check: total coverage-hours actually available across
    the week (operating hours x total station capacity needed per
    slot), vs. the minimum this would require if everyone needs at
    least min_hours. Doesn't guarantee feasibility (availability could
    still be badly distributed) but catches an obviously impossible
    target -- e.g. too many people for too few total shift-hours.
    """
    people = sorted({a.person for a in availabilities}, key=lambda p: p.name)
    num_people = len(people)

    total_required_person_hours = num_people * min_hours

    total_slots = 0
    for day, (start, end) in day_operating_hours.items():
        slots = _generate_slots(day, start, end)
        total_slots += len(slots)

    total_operating_hours = total_slots * (15 / 60)
    total_capacity_needed = sum(station_capacity.values())
    total_coverage_hours = total_operating_hours * total_capacity_needed

    return {
        "num_people": num_people,
        "total_required_person_hours": total_required_person_hours,
        "total_operating_hours": total_operating_hours,
        "total_capacity_needed": total_capacity_needed,
        "total_coverage_hours": total_coverage_hours,
    }

def check_per_person_availability(availabilities, day_operating_hours, min_hours):
    """
    For each person, sums up how many hours they're even AVAILABLE for
    across the week (not how many they're scheduled -- just how much
    green exists on their row). If that's less than min_hours, no
    schedule can ever give them their minimum, no matter how the solver
    assigns anyone else.
    """
    from src.solver import _generate_slots

    people = sorted({a.person for a in availabilities}, key=lambda p: p.name)
    avail_lookup = {
        (a.person, a.slot.day, a.slot.start): a.is_available for a in availabilities
    }

    shortfalls = []
    for p in people:
        available_slots = 0
        for day, (start, end) in day_operating_hours.items():
            slots = _generate_slots(day, start, end)
            for s in slots:
                if avail_lookup.get((p, day, s.start), False):
                    available_slots += 1
        available_hours = available_slots * (15 / 60)
        if available_hours < min_hours:
            shortfalls.append((p, available_hours))

    return shortfalls

def check_request_fulfillment(shifts, shift_requests):
    """
    After solving, checks how much of each requested (Day, start, end)
    window was actually covered by that person's assigned shifts.
    Requests are soft (see solve_week_schedule's shift_requests param),
    so this is how you find out which ones didn't get (fully) honored
    instead of the solver silently ignoring them.

    Returns a list of dicts, one per request:
        {person, day, requested_start, requested_end,
         requested_hours, fulfilled_hours, pct_fulfilled}
    """
    from datetime import datetime

    results = []
    for person, requests in shift_requests.items():
        person_shifts = [s for s in shifts if s.person == person]

        for day, req_start, req_end in requests:
            requested_minutes = (
                datetime(2000, 1, 1, req_end.hour, req_end.minute)
                - datetime(2000, 1, 1, req_start.hour, req_start.minute)
            ).seconds / 60

            fulfilled_minutes = 0
            for s in person_shifts:
                if s.day != day:
                    continue
                overlap_start = max(s.start, req_start)
                overlap_end = min(s.end, req_end)
                if overlap_end > overlap_start:
                    fulfilled_minutes += (
                        datetime(2000, 1, 1, overlap_end.hour, overlap_end.minute)
                        - datetime(2000, 1, 1, overlap_start.hour, overlap_start.minute)
                    ).seconds / 60

            pct = (fulfilled_minutes / requested_minutes * 100) if requested_minutes else 0
            results.append({
                "person": person,
                "day": day,
                "requested_start": req_start,
                "requested_end": req_end,
                "requested_hours": requested_minutes / 60,
                "fulfilled_hours": fulfilled_minutes / 60,
                "pct_fulfilled": pct,
            })

    return results


def print_request_report(shifts, shift_requests):
    if not shift_requests:
        return

    print()
    print("=== Shift request fulfillment ===")
    results = check_request_fulfillment(shifts, shift_requests)
    for r in results:
        status = "✅ fully honored" if r["pct_fulfilled"] >= 99.9 else (
            "⚠ partially honored" if r["pct_fulfilled"] > 0 else "❌ NOT honored"
        )
        start_str = r["requested_start"].strftime("%I:%M %p").lstrip("0")
        end_str = r["requested_end"].strftime("%I:%M %p").lstrip("0")
        print(
            f"  {r['person'].name} -- {r['day'].value} {start_str}-{end_str}: "
            f"{status} ({r['fulfilled_hours']:.2f}/{r['requested_hours']:.2f} hours)"
        )


def print_report(availabilities, day_operating_hours, station_capacity, min_hours):
    print("=== Coverage gap check ===")
    gaps = check_coverage_gaps(availabilities, day_operating_hours, station_capacity)
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
    stats = check_total_hours_feasibility(availabilities, day_operating_hours, station_capacity, min_hours)
    print(f"People: {stats['num_people']}")
    print(f"Total station capacity needed per slot: {stats['total_capacity_needed']}")
    print(f"Total operating hours/week: {stats['total_operating_hours']:.1f}")
    print(f"Total coverage-hours available/week (operating hours x capacity): {stats['total_coverage_hours']:.1f}")
    print(f"Total required person-hours (num_people x min_hours): {stats['total_required_person_hours']:.1f}")

    deficit = stats["total_required_person_hours"] - stats["total_coverage_hours"]
    if deficit > 0:
        print()
        print(
            f"⚠ SHORTFALL: {deficit:.1f} hours short. There isn't enough total "
            f"coverage-work across the week to give every person {min_hours} hours "
            f"minimum. Either lower min_hours (max possible avg is "
            f"{stats['total_coverage_hours'] / stats['num_people']:.1f} hours/person), "
            f"increase station capacity at some times, or reduce headcount."
        )
    else:
        print("Total coverage-hours comfortably covers everyone's minimum.")
        print()
        print("=== Per-person availability check ===")
        shortfalls = check_per_person_availability(availabilities, day_operating_hours, min_hours)
        if not shortfalls:
            print(f"Everyone has at least {min_hours} hours of availability individually.")
        else:
            print(f"{len(shortfalls)} person/people don't have enough TOTAL availability to hit {min_hours} hours:")
            for person, available_hours in shortfalls:
                print(f"  {person.name}: only {available_hours:.2f} hours available all week")


if __name__ == "__main__":
    from src.main import CSV_FILES, DAY_OPERATING_HOURS, STATION_CAPACITY, MIN_HOURS

    all_availabilities = []
    for day, filepath in CSV_FILES.items():
        all_availabilities.extend(parse_availability_csv(filepath, day))

    active_day_hours = {
        day: hours for day, hours in DAY_OPERATING_HOURS.items() if day in CSV_FILES
    }

    print_report(all_availabilities, active_day_hours, STATION_CAPACITY, MIN_HOURS)