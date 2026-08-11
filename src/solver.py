"""
Steps 3-7: the working solver.

Given a list of Availability records, operating hours, and how many
people each station needs staffed simultaneously (station_capacity),
find a schedule where every station has the right number of people
covering it every 15-minute slot, nobody is scheduled when they're
unavailable, and nobody is double-booked across two stations at once.

station_capacity example: {Station.NORTH: 2, Station.SOUTH: 2,
Station.DEANS_SUITE: 1} means North and South each need 2 people
working simultaneously, Dean's Suite needs 1.
"""

from datetime import datetime, time, timedelta
from typing import Optional

from ortools.sat.python import cp_model

from src.models import Availability, Day, Person, Shift, Station, TimeSlot

SLOT_MINUTES = 15


def _generate_slots(day: Day, start: time, end: time) -> list[TimeSlot]:
    """Builds the list of 15-min TimeSlots between start and end."""
    slots = []
    current = datetime(2000, 1, 1, start.hour, start.minute)
    end_dt = datetime(2000, 1, 1, end.hour, end.minute)

    while current < end_dt:
        slot_start = current.time()
        slot_end = (current + timedelta(minutes=SLOT_MINUTES)).time()
        slots.append(TimeSlot(day=day, start=slot_start, end=slot_end))
        current += timedelta(minutes=SLOT_MINUTES)

    return slots


def solve_day_schedule(
    availabilities: list[Availability],
    day: Day,
    operating_start: time,
    operating_end: time,
    station_capacity: dict,
) -> Optional[list[Shift]]:
    """
    Returns a list of Shifts covering every station (at its required
    headcount) for every slot in the operating window, or None if no
    valid schedule exists.

    station_capacity: dict mapping Station -> how many people that
        station needs staffed at the same time, e.g.
        {Station.NORTH: 2, Station.SOUTH: 2, Station.DEANS_SUITE: 1}
    """
    stations = list(station_capacity.keys())
    people = sorted({a.person for a in availabilities}, key=lambda p: p.name)
    slots = _generate_slots(day, operating_start, operating_end)

    # Quick lookup: is this person available at this slot's start time?
    avail_lookup = {(a.person, a.slot.start): a.is_available for a in availabilities}

    model = cp_model.CpModel()

    # One boolean variable per (person, slot, station): are they covering
    # that station during that slot?
    assign = {
        (p, s.start, station): model.NewBoolVar(
            f"assign_{p.name}_{s.start}_{station.name}"
        )
        for p in people
        for s in slots
        for station in stations
    }

    # Hard constraint: can't be assigned to any station when unavailable
    for p in people:
        for s in slots:
            if not avail_lookup.get((p, s.start), False):
                for station in stations:
                    model.Add(assign[(p, s.start, station)] == 0)

    # Hard constraint: each station is covered by exactly its required
    # headcount every slot (not always 1 -- e.g. North might need 2)
    for s in slots:
        for station in stations:
            model.Add(
                sum(assign[(p, s.start, station)] for p in people)
                == station_capacity[station]
            )

    # Hard constraint: a person can't cover two stations in the same slot
    for p in people:
        for s in slots:
            model.Add(
                sum(assign[(p, s.start, station)] for station in stations) <= 1
            )

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 30.0
    status = solver.Solve(model)

    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return None

    return _slots_to_shifts(solver, assign, people, slots, stations, day)


def _slots_to_shifts(solver, assign, people, slots, stations, day) -> list[Shift]:
    """Merges each person's consecutive assigned slots, per station, into
    single Shifts, e.g. four assigned 15-min North slots in a row become
    one 1-hour North Shift. Works the same whether a station has 1 or
    many people assigned, since each person is tracked independently."""
    shifts = []

    for p in people:
        for station in stations:
            run_start = None
            run_end = None

            for s in slots:
                is_assigned = solver.Value(assign[(p, s.start, station)]) == 1

                if is_assigned:
                    if run_start is None:
                        run_start = s.start
                    run_end = s.end
                elif run_start is not None:
                    shifts.append(
                        Shift(person=p, day=day, start=run_start, end=run_end, station=station)
                    )
                    run_start = None
                    run_end = None

            if run_start is not None:
                shifts.append(
                    Shift(person=p, day=day, start=run_start, end=run_end, station=station)
                )

    return shifts


def solve_week_schedule(
    availabilities: list[Availability],
    day_operating_hours: dict,
    station_capacity: dict,
    min_hours: float,
    max_hours: float,
    rotation_stations: Optional[list[Station]] = None,
    open_preferences: Optional[dict] = None,
    close_preferences: Optional[dict] = None,
    flexible_stations: Optional[set] = None,
    min_shift_minutes: float = 90.0,
    exact_half_or_full_days: Optional[set] = None,
    pinned_shift_blocks: Optional[dict] = None,
) -> Optional[list[Shift]]:
    """
    Steps 5/6/7: solves across an entire week at once (not one day in
    isolation), because "everyone opens at least once" and "everyone
    closes at least once" and min/max hours only make sense measured
    across the whole week.

    day_operating_hours: dict mapping Day -> (operating_start, operating_end)
        e.g. {Day.MONDAY: (time(7,30), time(17,0)), ...}

    station_capacity: dict mapping Station -> how many people that
        station needs staffed at the same time, e.g.
        {Station.NORTH: 2, Station.SOUTH: 2, Station.DEANS_SUITE: 1}

    rotation_stations: stations everyone must work at least once during
        the week (e.g. [Station.NORTH, Station.SOUTH]). Defaults to None,
        meaning no rotation requirement is enforced -- pass this in
        explicitly when you want it.

    open_preferences / close_preferences: dict mapping Person -> set of
        Days they'd prefer to open/close, e.g. {alex: {Day.MONDAY}}.
        These are SOFT -- honored when possible, but never at the cost of
        breaking a hard constraint above. Optional.

    flexible_stations: set of Stations allowed to go BELOW their listed
        capacity in a given slot when needed (e.g. Dean's Suite doesn't
        strictly need to be staffed every single moment -- it can sit
        vacant rather than force someone over max_hours or otherwise
        break a hard constraint). Stations NOT in this set are still
        held to their exact capacity every slot, no exceptions. The
        solver still tries to fully staff flexible stations whenever
        it's not costly to do so (soft preference), it's just no longer
        a hard requirement. Defaults to None (every station strict,
        matching original behavior).

    min_shift_minutes: no contiguous shift on one station can be
        shorter than this. HARD constraint -- if a block starts, it
        must run at least this long, or it can't start there at all.
        Defaults to 90 (minutes). Ignored for days listed in
        exact_half_or_full_days (see below).

    exact_half_or_full_days: set of Days (e.g. {Day.FRIDAY}) where a
        person's shift on any station must be EXACTLY the first half
        of the day, EXACTLY the second half, or the ENTIRE day -- no
        other length. Matches the real Welcome Desk rule that Friday
        shifts are always 4.5 or 9 hours, nothing in between. Requires
        that day's slot count be even (splits cleanly in half).

    pinned_shift_blocks: dict mapping Person -> {Day: "AM" | "PM" | "FULL"}
        HARD-requires that person to work at least that block pattern on
        that day (only meaningful for days in exact_half_or_full_days).
        Useful for locking in known new-hire Friday coverage ahead of
        time, e.g. {sam: {Day.FRIDAY: "AM"}}. The solver still picks
        which station -- this only pins the day/block, not the desk.

    Beyond honoring preferences, the solver also minimizes shift
    fragmentation by default (fewer, longer blocks per person per day
    rather than lots of short ones), since nobody asked for that but
    everybody wants it.

    Returns None if no schedule satisfies every hard constraint.
    """
    open_preferences = open_preferences or {}
    close_preferences = close_preferences or {}
    flexible_stations = flexible_stations or set()
    exact_half_or_full_days = exact_half_or_full_days or set()
    pinned_shift_blocks = pinned_shift_blocks or {}
    stations = list(station_capacity.keys())
    people = sorted({a.person for a in availabilities}, key=lambda p: p.name)
    days = list(day_operating_hours.keys())

    # Build slots per day, and an availability lookup keyed by (person, day, slot_start)
    slots_by_day = {
        day: _generate_slots(day, start, end)
        for day, (start, end) in day_operating_hours.items()
    }
    avail_lookup = {
        (a.person, a.slot.day, a.slot.start): a.is_available for a in availabilities
    }

    model = cp_model.CpModel()

    # One boolean variable per (person, day, slot, station)
    assign = {
        (p, day, s.start, station): model.NewBoolVar(
            f"assign_{p.name}_{day.name}_{s.start}_{station.name}"
        )
        for p in people
        for day in days
        for s in slots_by_day[day]
        for station in stations
    }

    # Hard constraint: can't be assigned when unavailable
    for p in people:
        for day in days:
            for s in slots_by_day[day]:
                if not avail_lookup.get((p, day, s.start), False):
                    for station in stations:
                        model.Add(assign[(p, day, s.start, station)] == 0)

    # Hard constraint: each station is covered by its required headcount
    # every slot -- EXACTLY, unless the station is in flexible_stations,
    # in which case it's allowed to be UNDER capacity (never over).
    for day in days:
        for s in slots_by_day[day]:
            for station in stations:
                covering = sum(assign[(p, day, s.start, station)] for p in people)
                if station in flexible_stations:
                    model.Add(covering <= station_capacity[station])
                else:
                    model.Add(covering == station_capacity[station])

    # Hard constraint: a person can't cover two stations in the same slot
    for p in people:
        for day in days:
            for s in slots_by_day[day]:
                model.Add(
                    sum(assign[(p, day, s.start, station)] for station in stations) <= 1
                )

   # Hard constraint: no shift shorter than min_shift_minutes. Applied
    # per (person, day, station) -- a contiguous run on ONE station
    # can't start unless it can run the full minimum length, whether
    # that's blocked by the person's own availability ending or by the
    # operating day ending too soon. Skipped for exact_half_or_full_days
    # -- those days get their own stricter rule below instead.
    min_shift_slots = round(min_shift_minutes / SLOT_MINUTES)
    for p in people:
        for day in days:
            if day in exact_half_or_full_days:
                continue
            slots = slots_by_day[day]
            for station in stations:
                for i, s in enumerate(slots):
                    block_start = model.NewBoolVar(
                        f"min_len_start_{p.name}_{day.name}_{s.start}_{station.name}"
                    )
                    previous = (
                        0 if i == 0 else assign[(p, day, slots[i - 1].start, station)]
                    )
                    model.Add(
                        block_start >= assign[(p, day, s.start, station)] - previous
                    )

                    if len(slots) - i < min_shift_slots:
                        # Not enough room left in the day to reach the
                        # minimum length -- a block can't start here.
                        model.Add(block_start == 0)
                    else:
                        for offset in range(1, min_shift_slots):
                            model.Add(
                                assign[(p, day, slots[i + offset].start, station)]
                                >= block_start
                            )

    # Hard constraint: on exact_half_or_full_days (e.g. Friday), a
    # person's shift on a given station must be EXACTLY the first half
    # of the day, EXACTLY the second half, or the WHOLE day. Modeled by
    # forcing every slot within each half to share one boolean value --
    # that alone only allows those three patterns (both-off, AM-only,
    # PM-only, or both-on) and rules out any partial/arbitrary block.
    works_am_by = {}  # (person, day, station) -> BoolVar
    works_pm_by = {}
    for day in exact_half_or_full_days:
        if day not in slots_by_day:
            continue
        slots = slots_by_day[day]
        midpoint = len(slots) // 2
        am_slots = slots[:midpoint]
        pm_slots = slots[midpoint:]

        for p in people:
            for station in stations:
                works_am = model.NewBoolVar(f"works_am_{p.name}_{day.name}_{station.name}")
                works_pm = model.NewBoolVar(f"works_pm_{p.name}_{day.name}_{station.name}")
                works_am_by[(p, day, station)] = works_am
                works_pm_by[(p, day, station)] = works_pm

                for s in am_slots:
                    model.Add(assign[(p, day, s.start, station)] == works_am)
                for s in pm_slots:
                    model.Add(assign[(p, day, s.start, station)] == works_pm)

    # Hard constraint: pinned_shift_blocks locks specific people into a
    # specific AM/PM/FULL pattern on a specific exact_half_or_full_day
    # (e.g. a known new hire always covering Friday mornings). The
    # solver still picks which station -- this only pins the pattern.
    for person, day_blocks in pinned_shift_blocks.items():
        for day, block in day_blocks.items():
            if day not in exact_half_or_full_days or day not in slots_by_day:
                continue
            if block in ("AM", "FULL"):
                model.Add(
                    sum(works_am_by[(person, day, station)] for station in stations) >= 1
                )
            if block in ("PM", "FULL"):
                model.Add(
                    sum(works_pm_by[(person, day, station)] for station in stations) >= 1
                )

    # Hard constraint: min/max total hours per person across the whole week
    min_slot_count = round(min_hours * (60 / SLOT_MINUTES))
    max_slot_count = round(max_hours * (60 / SLOT_MINUTES))
    for p in people:
        total_slots = sum(
            assign[(p, day, s.start, station)]
            for day in days
            for s in slots_by_day[day]
            for station in stations
        )
        model.Add(total_slots >= min_slot_count)
        model.Add(total_slots <= max_slot_count)

    # Hard constraint: everyone works each rotation station (e.g. North
    # AND South) at least once during the week
    if rotation_stations:
        for p in people:
            for station in rotation_stations:
                worked_station = sum(
                    assign[(p, day, s.start, station)]
                    for day in days
                    for s in slots_by_day[day]
                )
                model.Add(worked_station >= 1)

    # --- Soft constraints (objective function) ---
    # Everything below this line is optimized for, not required. The
    # solver will always satisfy every hard constraint above first, and
    # only then try to minimize fragmentation / maximize honored
    # preferences among the schedules that remain valid.

    FRAGMENTATION_WEIGHT = 1
    PREFERENCE_WEIGHT = 20  # heavily favor honoring requests over tidiness
    OPEN_CLOSE_WEIGHT = 15  # strongly prefer everyone opening/closing at least once, but not at the cost of feasibility
    FLEXIBLE_COVERAGE_WEIGHT = 8  # prefer fully staffing flexible stations (e.g. Dean's Suite) when it doesn't cost anything else
    CONTINUITY_WEIGHT = 3  # prefer keeping the same person on a station rather than handing off to someone else who's also available
    SAME_DAY_SWITCH_WEIGHT = 12  # prefer satisfying rotation (North AND South) across DIFFERENT days rather than switching desks within one day

    # Soft preference: minimize a person working more than one DISTINCT
    # station on the same day. The rotation requirement above only cares
    # that North and South both get worked SOMETIME during the week --
    # without this, the solver is free to satisfy it by cramming both
    # into one day (sometimes back-to-back, looking like a mid-shift
    # desk change). This nudges it toward spreading rotation across
    # different days whenever a person's availability allows it.
    same_day_switch_terms = []
    for p in people:
        for day in days:
            slots = slots_by_day[day]
            for station in stations:
                works_station_today = model.NewBoolVar(
                    f"works_today_{p.name}_{day.name}_{station.name}"
                )
                daily_total = sum(assign[(p, day, s.start, station)] for s in slots)
                model.Add(works_station_today <= daily_total)
                same_day_switch_terms.append(works_station_today)

    # Soft preference: minimize station "handoffs" -- a new person
    # taking over a station that someone else was just covering, when
    # that someone else was still available and could have kept going.
    # This is what stops a person's block from getting cut short (e.g.
    # cut off at 10:00 despite being available until 12:30) just to
    # swap in a different available person for no real reason.
    continuity_terms = []
    for day in days:
        slots = slots_by_day[day]
        for station in stations:
            for i in range(1, len(slots)):
                for p in people:
                    entered = model.NewBoolVar(
                        f"entered_{p.name}_{day.name}_{slots[i].start}_{station.name}"
                    )
                    model.Add(
                        entered
                        >= assign[(p, day, slots[i].start, station)]
                        - assign[(p, day, slots[i - 1].start, station)]
                    )
                    continuity_terms.append(entered)
    # Soft preference: fill flexible stations (e.g. Dean's Suite) up to
    # their listed capacity whenever it doesn't conflict with anything
    # else. This is what stops the solver from just always leaving them
    # empty now that they're allowed to be understaffed.
    flexible_coverage_terms = []
    for day in days:
        for s in slots_by_day[day]:
            for station in flexible_stations:
                flexible_coverage_terms.append(
                    sum(assign[(p, day, s.start, station)] for p in people)
                )

    # "Working this slot" as a single 0/1 value per (person, day, slot),
    # reusing the fact that a person covers at most one station per slot.
    working = {}
    for p in people:
        for day in days:
            for s in slots_by_day[day]:
                working[(p, day, s.start)] = sum(
                    assign[(p, day, s.start, station)] for station in stations
                )

    # A "block start" happens when someone is working a slot but wasn't
    # working the previous slot (or it's the first slot of the day).
    # Minimizing the count of these minimizes the number of separate
    # shift blocks per person per day.
    fragmentation_terms = []
    for p in people:
        for day in days:
            slots = slots_by_day[day]
            for i, s in enumerate(slots):
                block_start = model.NewBoolVar(
                    f"block_start_{p.name}_{day.name}_{s.start}"
                )
                previous_working = 0 if i == 0 else working[(p, day, slots[i - 1].start)]
                model.Add(block_start >= working[(p, day, s.start)] - previous_working)
                fragmentation_terms.append(block_start)

    # "Everyone opens/closes at least once" is IDEAL, not required --
    # someone whose availability never includes the day's first/last
    # slot simply can't, and that shouldn't make the whole week
    # infeasible. has_opened[p] is a boolean bounded above by whether p
    # actually has any opening slot assigned; the objective below
    # rewards it being 1 whenever that's achievable.
    open_close_terms = []
    for p in people:
        opens_sum = sum(
            assign[(p, day, slots_by_day[day][0].start, station)]
            for day in days
            for station in stations
        )
        has_opened = model.NewBoolVar(f"has_opened_{p.name}")
        model.Add(has_opened <= opens_sum)
        open_close_terms.append(has_opened)

        closes_sum = sum(
            assign[(p, day, slots_by_day[day][-1].start, station)]
            for day in days
            for station in stations
        )
        has_closed = model.NewBoolVar(f"has_closed_{p.name}")
        model.Add(has_closed <= closes_sum)
        open_close_terms.append(has_closed)

    # Preference bonus terms: 1 if the person opened/closed on their
    # requested day, 0 otherwise (reusing the same expressions as the
    # hard open/close constraints, just per-day instead of summed).
    preference_terms = []
    for person, preferred_days in open_preferences.items():
        for day in preferred_days:
            if day in days:
                preference_terms.append(
                    sum(
                        assign[(person, day, slots_by_day[day][0].start, station)]
                        for station in stations
                    )
                )
    for person, preferred_days in close_preferences.items():
        for day in preferred_days:
            if day in days:
                preference_terms.append(
                    sum(
                        assign[(person, day, slots_by_day[day][-1].start, station)]
                        for station in stations
                    )
                )

    model.Minimize(
        FRAGMENTATION_WEIGHT * sum(fragmentation_terms)
        - PREFERENCE_WEIGHT * sum(preference_terms)
        - OPEN_CLOSE_WEIGHT * sum(open_close_terms)
        - FLEXIBLE_COVERAGE_WEIGHT * sum(flexible_coverage_terms)
        + CONTINUITY_WEIGHT * sum(continuity_terms)
        + SAME_DAY_SWITCH_WEIGHT * sum(same_day_switch_terms)
    )

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 30.0
    status = solver.Solve(model)

    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return None

    return _week_slots_to_shifts(solver, assign, people, days, slots_by_day, stations)


def _week_slots_to_shifts(solver, assign, people, days, slots_by_day, stations) -> list[Shift]:
    """Same idea as _slots_to_shifts, but merges runs per (person, day, station)
    since shifts don't span across days."""
    shifts = []

    for p in people:
        for day in days:
            slots = slots_by_day[day]
            for station in stations:
                run_start = None
                run_end = None

                for s in slots:
                    is_assigned = solver.Value(assign[(p, day, s.start, station)]) == 1

                    if is_assigned:
                        if run_start is None:
                            run_start = s.start
                        run_end = s.end
                    elif run_start is not None:
                        shifts.append(
                            Shift(person=p, day=day, start=run_start, end=run_end, station=station)
                        )
                        run_start = None
                        run_end = None

                if run_start is not None:
                    shifts.append(
                        Shift(person=p, day=day, start=run_start, end=run_end, station=station)
                    )

    return shifts