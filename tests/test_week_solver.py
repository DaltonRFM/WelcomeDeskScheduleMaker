from datetime import time

from src.models import Availability, Day, Person, Station, TimeSlot
from src.solver import solve_week_schedule

ALEX = Person(name="Alex")
BOB = Person(name="Bob")


def _avail(person, day, start, end, is_available):
    return Availability(
        person=person,
        slot=TimeSlot(day=day, start=start, end=end),
        is_available=is_available,
    )


def build_two_day_availabilities():
    """
    2 days (Monday, Tuesday), 2 slots each (7:30-7:45, 7:45-8:00), single
    station, 2 people both fully available the whole time. Small enough
    that we can reason about exactly what a valid schedule looks like.
    """
    data = []
    for day in (Day.MONDAY, Day.TUESDAY):
        for person in (ALEX, BOB):
            data.append(_avail(person, day, time(7, 30), time(7, 45), True))
            data.append(_avail(person, day, time(7, 45), time(8, 0), True))
    return data


def test_finds_a_valid_week_schedule():
    availabilities = build_two_day_availabilities()
    day_hours = {
        Day.MONDAY: (time(7, 30), time(8, 0)),
        Day.TUESDAY: (time(7, 30), time(8, 0)),
    }
    shifts = solve_week_schedule(
        availabilities, day_hours, {Station.NORTH: 1},
        min_hours=0.5, max_hours=1.0, min_shift_minutes=0,
    )
    assert shifts is not None
    assert len(shifts) > 0


def test_everyone_meets_min_and_max_hours():
    availabilities = build_two_day_availabilities()
    day_hours = {
        Day.MONDAY: (time(7, 30), time(8, 0)),
        Day.TUESDAY: (time(7, 30), time(8, 0)),
    }
    shifts = solve_week_schedule(
        availabilities, day_hours, {Station.NORTH: 1},
        min_hours=0.5, max_hours=1.0, min_shift_minutes=0,
    )

    for person in (ALEX, BOB):
        total_hours = sum(
            s.duration_hours() for s in shifts if s.person == person
        )
        assert 0.5 <= total_hours <= 1.0


def test_everyone_opens_at_least_once():
    availabilities = build_two_day_availabilities()
    day_hours = {
        Day.MONDAY: (time(7, 30), time(8, 0)),
        Day.TUESDAY: (time(7, 30), time(8, 0)),
    }
    shifts = solve_week_schedule(
        availabilities, day_hours, {Station.NORTH: 1},
        min_hours=0.5, max_hours=1.0, min_shift_minutes=0,
    )

    openers = {s.person for s in shifts if s.start == time(7, 30)}
    assert openers == {ALEX, BOB}


def test_everyone_closes_at_least_once():
    availabilities = build_two_day_availabilities()
    day_hours = {
        Day.MONDAY: (time(7, 30), time(8, 0)),
        Day.TUESDAY: (time(7, 30), time(8, 0)),
    }
    shifts = solve_week_schedule(
        availabilities, day_hours, {Station.NORTH: 1},
        min_hours=0.5, max_hours=1.0, min_shift_minutes=0,
    )

    closers = {s.person for s in shifts if s.end == time(8, 0)}
    assert closers == {ALEX, BOB}


def test_returns_none_when_hours_impossible():
    # Only 2 total slots exist across the week (one day, one slot each
    # for 2 people can't both hit a 2-hour minimum)
    availabilities = [
        _avail(ALEX, Day.MONDAY, time(7, 30), time(7, 45), True),
        _avail(BOB, Day.MONDAY, time(7, 30), time(7, 45), True),
    ]
    day_hours = {Day.MONDAY: (time(7, 30), time(7, 45))}
    shifts = solve_week_schedule(
        availabilities, day_hours, {Station.NORTH: 1},
        min_hours=2.0, max_hours=5.0, min_shift_minutes=0,
    )
    assert shifts is None


def build_two_station_two_day_availabilities():
    """
    2 days, 2 slots each, 2 stations (North, South), 2 people both fully
    available everywhere. With 2 people and 2 stations needed every slot,
    both people work every slot -- giving the solver room to rotate them
    through both stations across the week.
    """
    data = []
    for day in (Day.MONDAY, Day.TUESDAY):
        for person in (ALEX, BOB):
            data.append(_avail(person, day, time(7, 30), time(7, 45), True))
            data.append(_avail(person, day, time(7, 45), time(8, 0), True))
    return data


def test_everyone_works_every_rotation_station_at_least_once():
    availabilities = build_two_station_two_day_availabilities()
    day_hours = {
        Day.MONDAY: (time(7, 30), time(8, 0)),
        Day.TUESDAY: (time(7, 30), time(8, 0)),
    }
    shifts = solve_week_schedule(
        availabilities,
        day_hours,
        {Station.NORTH: 1, Station.SOUTH: 1},
        min_hours=0.5,
        max_hours=1.0,
        rotation_stations=[Station.NORTH, Station.SOUTH],
        min_shift_minutes=0,
    )
    assert shifts is not None

    for person in (ALEX, BOB):
        stations_worked = {s.station for s in shifts if s.person == person}
        assert Station.NORTH in stations_worked
        assert Station.SOUTH in stations_worked


def test_rotation_not_enforced_when_not_requested():
    # Same dataset, but rotation_stations omitted -- solver shouldn't be
    # forced to rotate anyone, just needs to remain valid/feasible.
    availabilities = build_two_station_two_day_availabilities()
    day_hours = {
        Day.MONDAY: (time(7, 30), time(8, 0)),
        Day.TUESDAY: (time(7, 30), time(8, 0)),
    }
    shifts = solve_week_schedule(
        availabilities,
        day_hours,
        {Station.NORTH: 1, Station.SOUTH: 1},
        min_hours=0.5,
        max_hours=1.0,
        min_shift_minutes=0,
    )
    assert shifts is not None


def test_fragmentation_is_minimized():
    """
    Monday has 4 slots, single station, both people fully available the
    whole time -- lots of feasible ways to split it, some fragmented
    (checkerboard: A,B,A,B), some clean (A,A,B,B). Tuesday is a small
    2-slot day (same shape as build_two_day_availabilities) just so the
    hard "everyone opens/closes once" rule from Step 5 has somewhere for
    the other person to satisfy it -- Monday alone can't, since only one
    person can ever occupy Monday's single first/last slot.

    On Monday specifically, fragmentation minimization should still give
    each person at most one contiguous block.
    """
    day_hours = {
        Day.MONDAY: (time(7, 30), time(8, 30)),
        Day.TUESDAY: (time(7, 30), time(8, 0)),
    }

    availabilities = []
    for start, end in [
        (time(7, 30), time(7, 45)),
        (time(7, 45), time(8, 0)),
        (time(8, 0), time(8, 15)),
        (time(8, 15), time(8, 30)),
    ]:
        availabilities.append(_avail(ALEX, Day.MONDAY, start, end, True))
        availabilities.append(_avail(BOB, Day.MONDAY, start, end, True))
    availabilities.append(_avail(ALEX, Day.TUESDAY, time(7, 30), time(7, 45), True))
    availabilities.append(_avail(ALEX, Day.TUESDAY, time(7, 45), time(8, 0), True))
    availabilities.append(_avail(BOB, Day.TUESDAY, time(7, 30), time(7, 45), True))
    availabilities.append(_avail(BOB, Day.TUESDAY, time(7, 45), time(8, 0), True))

    shifts = solve_week_schedule(
        availabilities, day_hours, {Station.NORTH: 1},
        min_hours=0.5, max_hours=1.5, min_shift_minutes=0,
    )

    assert shifts is not None
    for person in (ALEX, BOB):
        monday_shifts = [s for s in shifts if s.person == person and s.day == Day.MONDAY]
        # Fragmentation minimized -> at most one contiguous block on Monday
        assert len(monday_shifts) <= 1


def test_open_preference_is_honored_when_feasible():
    """
    2 days, single station, 2 people fully available both days. The
    hard "everyone opens once" rule forces exactly one of them to open
    Monday and the other Tuesday -- without a preference, either
    assignment is equally valid. With Alex's open preference for
    Monday, the solver should specifically pick Alex to open Monday.
    """
    availabilities = build_two_day_availabilities()
    day_hours = {
        Day.MONDAY: (time(7, 30), time(8, 0)),
        Day.TUESDAY: (time(7, 30), time(8, 0)),
    }
    shifts = solve_week_schedule(
        availabilities,
        day_hours,
        {Station.NORTH: 1},
        min_hours=0.5,
        max_hours=1.0,
        open_preferences={ALEX: {Day.MONDAY}},
        min_shift_minutes=0,
    )

    assert shifts is not None
    monday_opener = next(
        s.person for s in shifts if s.day == Day.MONDAY and s.start == time(7, 30)
    )
    assert monday_opener == ALEX


def test_schedule_still_solves_when_someone_cant_open_or_close():
    """
    Bob is only ever available for the two MIDDLE slots of a 4-slot day
    -- never the first (open) or last (close) slot. Under the old hard
    "everyone opens/closes at least once" rule this made the whole week
    infeasible. Now that it's a soft preference, the solver should still
    find a valid schedule; Bob just won't open or close, and that's fine.
    """
    day_hours = {Day.MONDAY: (time(7, 30), time(8, 30))}
    availabilities = [
        _avail(ALEX, Day.MONDAY, time(7, 30), time(7, 45), True),
        _avail(ALEX, Day.MONDAY, time(7, 45), time(8, 0), True),
        _avail(ALEX, Day.MONDAY, time(8, 0), time(8, 15), True),
        _avail(ALEX, Day.MONDAY, time(8, 15), time(8, 30), True),
        _avail(BOB, Day.MONDAY, time(7, 30), time(7, 45), False),
        _avail(BOB, Day.MONDAY, time(7, 45), time(8, 0), True),
        _avail(BOB, Day.MONDAY, time(8, 0), time(8, 15), True),
        _avail(BOB, Day.MONDAY, time(8, 15), time(8, 30), False),
    ]

    shifts = solve_week_schedule(
        availabilities, day_hours, {Station.NORTH: 1},
        min_hours=0.25, max_hours=1.0, min_shift_minutes=0,
    )

    assert shifts is not None
    bob_opened = any(s.person == BOB and s.start == time(7, 30) for s in shifts)
    bob_closed = any(s.person == BOB and s.end == time(8, 30) for s in shifts)
    assert not bob_opened
    assert not bob_closed


def test_flexible_station_resolves_otherwise_infeasible_schedule():
    """
    Only Alex is ever available -- nobody else. A second station
    (South) needs 1 person too, but with only 1 person total, both
    North and South can never be simultaneously staffed at capacity 1
    each. If South is flexible, the solver should still find a valid
    schedule (Alex covers North, South just goes unstaffed). If South
    were NOT flexible, this would be infeasible.
    """
    day_hours = {Day.MONDAY: (time(7, 30), time(7, 45))}
    availabilities = [
        _avail(ALEX, Day.MONDAY, time(7, 30), time(7, 45), True),
    ]

    shifts = solve_week_schedule(
        availabilities,
        day_hours,
        {Station.NORTH: 1, Station.SOUTH: 1},
        min_hours=0.25,
        max_hours=0.25,
        flexible_stations={Station.SOUTH},
        min_shift_minutes=0,
    )

    assert shifts is not None
    assert any(s.station == Station.NORTH for s in shifts)
    assert not any(s.station == Station.SOUTH for s in shifts)


def test_flexible_station_still_fully_staffed_when_free_to_do_so():
    """
    2 people, both fully available. South is flexible, but with enough
    people around to cover it at no cost to anything else, the solver
    should still fill it -- flexible doesn't mean "leave it empty by
    default," it means "allowed to be empty when something else needs
    priority."
    """
    day_hours = {Day.MONDAY: (time(7, 30), time(7, 45))}
    availabilities = [
        _avail(ALEX, Day.MONDAY, time(7, 30), time(7, 45), True),
        _avail(BOB, Day.MONDAY, time(7, 30), time(7, 45), True),
    ]

    shifts = solve_week_schedule(
        availabilities,
        day_hours,
        {Station.NORTH: 1, Station.SOUTH: 1},
        min_hours=0.25,
        max_hours=0.25,
        flexible_stations={Station.SOUTH},
        min_shift_minutes=0,
    )

    assert shifts is not None
    stations_covered = {s.station for s in shifts}
    assert Station.NORTH in stations_covered
    assert Station.SOUTH in stations_covered


def test_no_shift_shorter_than_minimum():
    """
    A full 3-hour Monday (12 slots), single station, 2 people both fully
    available the entire time. With the default 90-min (6-slot) minimum,
    every resulting shift should be at least 90 minutes -- no 15 or
    30-min slivers, even though nothing else here forces long shifts.
    """
    day_hours = {Day.MONDAY: (time(7, 30), time(10, 30))}
    availabilities = []
    h, m = 7, 30
    slots = []
    for _ in range(12):
        start = time(h, m)
        m += 15
        if m >= 60:
            m -= 60
            h += 1
        end = time(h, m)
        slots.append((start, end))

    for start, end in slots:
        availabilities.append(_avail(ALEX, Day.MONDAY, start, end, True))
        availabilities.append(_avail(BOB, Day.MONDAY, start, end, True))

    shifts = solve_week_schedule(
        availabilities, day_hours, {Station.NORTH: 1},
        min_hours=0.25, max_hours=3.0,
    )  # min_shift_minutes uses the 90-min default here

    assert shifts is not None
    for shift in shifts:
        assert shift.duration_hours() >= 1.5


def test_min_shift_length_can_be_disabled():
    # Same tiny 15-min window used throughout other tests -- only
    # feasible at all because min_shift_minutes=0 turns the rule off.
    availabilities = [
        _avail(ALEX, Day.MONDAY, time(7, 30), time(7, 45), True),
    ]
    day_hours = {Day.MONDAY: (time(7, 30), time(7, 45))}
    shifts = solve_week_schedule(
        availabilities, day_hours, {Station.NORTH: 1},
        min_hours=0.25, max_hours=0.25, min_shift_minutes=0,
    )
    assert shifts is not None

def build_friday_availabilities():
    """
    A mini 'Friday' (2 hours, 8 slots of 15 min -- scaled down from the
    real 9-hour Friday for a fast test, but the same halves logic
    applies). 2 people, both fully available the whole time.
    """
    day = Day.FRIDAY
    data = []
    h, m = 8, 0
    for _ in range(8):
        start = time(h, m)
        m += 15
        if m >= 60:
            m -= 60
            h += 1
        end = time(h, m)
        data.append(_avail(ALEX, day, start, end, True))
        data.append(_avail(BOB, day, start, end, True))
    return data


def test_friday_shifts_are_exactly_half_or_full_day():
    """
    Mini 2-hour Friday, single station, 2 people fully available. Valid
    per-person patterns on that station are ONLY: not working, exactly
    the first hour (half), exactly the second hour (half), or the full
    2 hours -- nothing in between (e.g. 45 min or 1.5 hours).
    """
    availabilities = build_friday_availabilities()
    day_hours = {Day.FRIDAY: (time(8, 0), time(10, 0))}

    shifts = solve_week_schedule(
        availabilities, day_hours, {Station.NORTH: 1},
        min_hours=0.5, max_hours=2.0,
        exact_half_or_full_days={Day.FRIDAY},
    )

    assert shifts is not None
    for shift in shifts:
        assert shift.duration_hours() in (1.0, 2.0)


def test_non_exact_days_unaffected_by_friday_rule():
    # Monday isn't in exact_half_or_full_days -- normal min-length rule
    # (90 min default) should still be the only length constraint.
    availabilities = build_two_day_availabilities()
    day_hours = {
        Day.MONDAY: (time(7, 30), time(8, 0)),
        Day.TUESDAY: (time(7, 30), time(8, 0)),
    }
    shifts = solve_week_schedule(
        availabilities, day_hours, {Station.NORTH: 1},
        min_hours=0.5, max_hours=1.0, min_shift_minutes=0,
        exact_half_or_full_days={Day.FRIDAY},  # Friday isn't even in this dataset
    )
    assert shifts is not None


def test_continuity_prefers_keeping_same_person_over_handoff():
    """
    3-hour single-station day (12 slots), 2 people BOTH available the
    entire time. With no other constraint favoring a split, the solver
    should keep ONE person on the station the whole time rather than
    handing off to the other partway through for no reason -- exactly
    the "Grace cut off early, Alex takes over" problem this fixes.
    """
    day_hours = {Day.MONDAY: (time(7, 30), time(10, 30))}
    availabilities = []
    h, m = 7, 30
    for _ in range(12):
        start = time(h, m)
        m += 15
        if m >= 60:
            m -= 60
            h += 1
        end = time(h, m)
        availabilities.append(_avail(ALEX, Day.MONDAY, start, end, True))
        availabilities.append(_avail(BOB, Day.MONDAY, start, end, True))

    shifts = solve_week_schedule(
        availabilities, day_hours, {Station.NORTH: 1},
        min_hours=0, max_hours=3.0, min_shift_minutes=0,
    )

    assert shifts is not None
    # Only one shift should exist for this single station/day -- one
    # person covering the whole thing, not two people splitting it
    north_shifts = [s for s in shifts if s.station == Station.NORTH]
    assert len(north_shifts) == 1
    assert north_shifts[0].duration_hours() == 3.0

def test_rotation_prefers_different_days_over_same_day_switch():
    """
    2 people, both available Monday AND Tuesday, both stations, both
    days. Rotation requires each person work North AND South at some
    point. With multiple days open and nothing forcing a same-day
    switch, the solver should satisfy rotation using DIFFERENT days per
    person rather than cramming both stations into one day -- exactly
    the Laila-style same-day desk switch this fixes.
    """
    day_hours = {
        Day.MONDAY: (time(7, 30), time(9, 0)),
        Day.TUESDAY: (time(7, 30), time(9, 0)),
    }
    availabilities = []
    for day in (Day.MONDAY, Day.TUESDAY):
        h, m = 7, 30
        for _ in range(6):
            start = time(h, m)
            m += 15
            if m >= 60:
                m -= 60
                h += 1
            end = time(h, m)
            availabilities.append(_avail(ALEX, day, start, end, True))
            availabilities.append(_avail(BOB, day, start, end, True))

    shifts = solve_week_schedule(
        availabilities,
        day_hours,
        {Station.NORTH: 1, Station.SOUTH: 1},
        min_hours=0,
        max_hours=3.0,
        min_shift_minutes=0,
        rotation_stations=[Station.NORTH, Station.SOUTH],
    )

    assert shifts is not None
    for person in (ALEX, BOB):
        stations_by_day = {}
        for s in shifts:
            if s.person == person:
                stations_by_day.setdefault(s.day, set()).add(s.station)
        # Nobody should work 2 distinct stations on the SAME day
        for day, stations_worked in stations_by_day.items():
            assert len(stations_worked) == 1


def test_pinned_friday_block_is_honored():
    """
    A "new hire" (Alex) is pinned to work the AM half of Friday.
    Regardless of what else the solver would otherwise choose, Alex
    must end up covering some station for the first half of Friday.
    """
    availabilities = build_friday_availabilities()  # Alex + Bob, both fully available
    day_hours = {Day.FRIDAY: (time(8, 0), time(10, 0))}

    shifts = solve_week_schedule(
        availabilities, day_hours, {Station.NORTH: 1},
        min_hours=0, max_hours=2.0,
        exact_half_or_full_days={Day.FRIDAY},
        pinned_shift_blocks={ALEX: {Day.FRIDAY: "AM"}},
    )

    assert shifts is not None
    alex_am_shift = [
        s for s in shifts
        if s.person == ALEX and s.start == time(8, 0) and s.duration_hours() >= 1.0
    ]
    assert len(alex_am_shift) == 1


def test_pinned_friday_full_day_is_honored():
    availabilities = build_friday_availabilities()
    day_hours = {Day.FRIDAY: (time(8, 0), time(10, 0))}

    shifts = solve_week_schedule(
        availabilities, day_hours, {Station.NORTH: 1},
        min_hours=0, max_hours=2.0,
        exact_half_or_full_days={Day.FRIDAY},
        pinned_shift_blocks={ALEX: {Day.FRIDAY: "FULL"}},
    )

    assert shifts is not None
    alex_shifts = [s for s in shifts if s.person == ALEX]
    assert len(alex_shifts) == 1
    assert alex_shifts[0].start == time(8, 0)
    assert alex_shifts[0].end == time(10, 0)