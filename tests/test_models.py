from datetime import time

from src.models import Day, Person, Shift, Station, WeekSchedule


def test_shift_duration_hours():
    dalton = Person(name="Dalton")
    shift = Shift(
        person=dalton,
        station=Station.NORTH,
        day=Day.MONDAY,
        start=time(7, 30),
        end=time(9, 30),
    )
    assert shift.duration_hours() == 2.0


def test_week_schedule_total_hours():
    dalton = Person(name="Dalton")
    week = WeekSchedule(
        shifts=[
            Shift(dalton, Station.NORTH, Day.MONDAY, time(7, 30), time(9, 30)),
            Shift(dalton, Station.SOUTH, Day.TUESDAY, time(12, 30), time(17, 0)),
        ]
    )
    assert week.total_hours(dalton) == 6.5
    assert len(week.shifts_for(dalton)) == 2