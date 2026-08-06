from datetime import time

from src.models import Availability, Day, Person, TimeSlot
from src.solver import solve_day_schedule

ALEX = Person(name="Alex")
ABBY = Person(name="Abby")
DALTON = Person(name="Dalton")


def _avail(person, day, start, end, is_available):
    return Availability(
        person=person,
        slot=TimeSlot(day=day, start=start, end=end),
        is_available=is_available,
    )


def build_fake_availabilities():
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


def test_finds_a_valid_schedule():
    availabilities = build_fake_availabilities()
    shifts = solve_day_schedule(
        availabilities, Day.MONDAY, time(7, 30), time(8, 30)
    )
    assert shifts is not None
    assert len(shifts) > 0


def test_nobody_scheduled_when_unavailable():
    availabilities = build_fake_availabilities()
    shifts = solve_day_schedule(
        availabilities, Day.MONDAY, time(7, 30), time(8, 30)
    )

    for shift in shifts:
        if shift.person == ALEX:
            # Alex was only available 7:30-8:00
            assert shift.start >= time(7, 30)
            assert shift.end <= time(8, 0)
        if shift.person == ABBY:
            # Abby was only available 8:00-8:30
            assert shift.start >= time(8, 0)
            assert shift.end <= time(8, 30)


def test_every_slot_is_covered():
    availabilities = build_fake_availabilities()
    shifts = solve_day_schedule(
        availabilities, Day.MONDAY, time(7, 30), time(8, 30)
    )

    # Total covered minutes across all shifts should equal the full hour
    total_minutes = sum(
        (s.end.hour * 60 + s.end.minute) - (s.start.hour * 60 + s.start.minute)
        for s in shifts
    )
    assert total_minutes == 60


def test_returns_none_when_impossible():
    # A slot nobody is available for -> no valid schedule exists
    day = Day.MONDAY
    availabilities = [
        _avail(ALEX, day, time(7, 30), time(7, 45), False),
    ]
    shifts = solve_day_schedule(
        availabilities, day, time(7, 30), time(7, 45)
    )
    assert shifts is None