from datetime import time

from src.models import Availability, Day, Person, Station, TimeSlot
from src.solver import solve_day_schedule

ALEX = Person(name="Alex")
ABBY = Person(name="Abby")
DALTON = Person(name="Dalton")
CHARLOTTE = Person(name="Charlotte")


def _avail(person, day, start, end, is_available):
    return Availability(
        person=person,
        slot=TimeSlot(day=day, start=start, end=end),
        is_available=is_available,
    )


def build_single_station_availabilities():
    """
    A tiny 1-hour test day, 7:30-8:30, in 15-min slots, for 3 people.
    Deliberately overlapping/gapped so the solver has to actually pick
    who covers what, not just assign one obvious person the whole time.
    """
    day = Day.MONDAY
    data = []

    # Alex: available 7:30-8:00 only
    data.append(_avail(ALEX, day, time(7, 30), time(7, 45), True))
    data.append(_avail(ALEX, day, time(7, 45), time(8, 0), True))
    data.append(_avail(ALEX, day, time(8, 0), time(8, 15), False))
    data.append(_avail(ALEX, day, time(8, 15), time(8, 30), False))

    # Abby: available 8:00-8:30 only
    data.append(_avail(ABBY, day, time(7, 30), time(7, 45), False))
    data.append(_avail(ABBY, day, time(7, 45), time(8, 0), False))
    data.append(_avail(ABBY, day, time(8, 0), time(8, 15), True))
    data.append(_avail(ABBY, day, time(8, 15), time(8, 30), True))

    # Dalton: available the whole hour (backup coverage)
    data.append(_avail(DALTON, day, time(7, 30), time(7, 45), True))
    data.append(_avail(DALTON, day, time(7, 45), time(8, 0), True))
    data.append(_avail(DALTON, day, time(8, 0), time(8, 15), True))
    data.append(_avail(DALTON, day, time(8, 15), time(8, 30), True))

    return data


def build_two_station_availabilities():
    """
    A 30-min test window (two 15-min slots), 4 people, needing BOTH
    North and South staffed simultaneously. Exactly 2 people are
    available in each slot, so the solver has no slack -- it must use
    both available people every slot to make it work.
    """
    day = Day.MONDAY
    data = []

    # Slot 1 (7:30-7:45): Alex + Abby available, Dalton + Charlotte not
    data.append(_avail(ALEX, day, time(7, 30), time(7, 45), True))
    data.append(_avail(ABBY, day, time(7, 30), time(7, 45), True))
    data.append(_avail(DALTON, day, time(7, 30), time(7, 45), False))
    data.append(_avail(CHARLOTTE, day, time(7, 30), time(7, 45), False))

    # Slot 2 (7:45-8:00): Dalton + Charlotte available, Alex + Abby not
    data.append(_avail(ALEX, day, time(7, 45), time(8, 0), False))
    data.append(_avail(ABBY, day, time(7, 45), time(8, 0), False))
    data.append(_avail(DALTON, day, time(7, 45), time(8, 0), True))
    data.append(_avail(CHARLOTTE, day, time(7, 45), time(8, 0), True))

    return data


def test_finds_a_valid_schedule():
    availabilities = build_single_station_availabilities()
    shifts = solve_day_schedule(
        availabilities, Day.MONDAY, time(7, 30), time(8, 30), {Station.NORTH: 1}
    )
    assert shifts is not None
    assert len(shifts) > 0


def test_nobody_scheduled_when_unavailable():
    availabilities = build_single_station_availabilities()
    shifts = solve_day_schedule(
        availabilities, Day.MONDAY, time(7, 30), time(8, 30), {Station.NORTH: 1}
    )

    for shift in shifts:
        if shift.person == ALEX:
            assert shift.start >= time(7, 30)
            assert shift.end <= time(8, 0)
        if shift.person == ABBY:
            assert shift.start >= time(8, 0)
            assert shift.end <= time(8, 30)


def test_every_slot_is_covered():
    availabilities = build_single_station_availabilities()
    shifts = solve_day_schedule(
        availabilities, Day.MONDAY, time(7, 30), time(8, 30), {Station.NORTH: 1}
    )

    total_minutes = sum(
        (s.end.hour * 60 + s.end.minute) - (s.start.hour * 60 + s.start.minute)
        for s in shifts
    )
    assert total_minutes == 60


def test_returns_none_when_impossible():
    day = Day.MONDAY
    availabilities = [
        _avail(ALEX, day, time(7, 30), time(7, 45), False),
    ]
    shifts = solve_day_schedule(
        availabilities, day, time(7, 30), time(7, 45), {Station.NORTH: 1}
    )
    assert shifts is None


def test_two_stations_covered_simultaneously():
    availabilities = build_two_station_availabilities()
    shifts = solve_day_schedule(
        availabilities,
        Day.MONDAY,
        time(7, 30),
        time(8, 0),
        {Station.NORTH: 1, Station.SOUTH: 1},
    )
    assert shifts is not None

    # Every shift must have a station assigned now
    for shift in shifts:
        assert shift.station in (Station.NORTH, Station.SOUTH)

    # In the first slot, Alex and Abby must cover North+South between them
    first_slot_people = {
        s.person for s in shifts if s.start <= time(7, 30) < s.end
    }
    assert first_slot_people == {ALEX, ABBY}


def test_nobody_double_booked_across_stations():
    availabilities = build_two_station_availabilities()
    shifts = solve_day_schedule(
        availabilities,
        Day.MONDAY,
        time(7, 30),
        time(8, 0),
        {Station.NORTH: 1, Station.SOUTH: 1},
    )
    assert shifts is not None

    # No person should have two shifts with overlapping times
    for person in {ALEX, ABBY, DALTON, CHARLOTTE}:
        person_shifts = sorted(
            (s for s in shifts if s.person == person), key=lambda s: s.start
        )
        for a, b in zip(person_shifts, person_shifts[1:]):
            assert a.end <= b.start


def test_station_needing_two_people_at_once():
    """
    4 people, all fully available for one 15-min slot. North needs 2
    people simultaneously (matches the real Welcome Desk setup where
    North and South each run 2 concurrent positions). The solver should
    assign exactly 2 different people to North for that slot.
    """
    day = Day.MONDAY
    availabilities = [
        _avail(ALEX, day, time(7, 30), time(7, 45), True),
        _avail(ABBY, day, time(7, 30), time(7, 45), True),
        _avail(DALTON, day, time(7, 30), time(7, 45), True),
        _avail(CHARLOTTE, day, time(7, 30), time(7, 45), True),
    ]

    shifts = solve_day_schedule(
        availabilities, day, time(7, 30), time(7, 45), {Station.NORTH: 2}
    )

    assert shifts is not None
    north_shifts = [s for s in shifts if s.station == Station.NORTH]
    assert len(north_shifts) == 2
    assert north_shifts[0].person != north_shifts[1].person