from datetime import time

from src.models import Day, Person, Shift, Station, WeekSchedule


def test_shift_duration_hours():
    dalton = Person(name="Dalton")
    shift = Shift(
        person=dalton,
        day=Day.MONDAY,
        start=time(7, 30),
        end=time(9, 30),
        station=Station.NORTH,
    )
    assert shift.duration_hours() == 2.0


def test_week_schedule_total_hours():
    dalton = Person(name="Dalton")
    week = WeekSchedule(
        shifts=[
            Shift(dalton, Day.MONDAY, time(7, 30), time(9, 30), Station.NORTH),
            Shift(dalton, Day.TUESDAY, time(12, 30), time(17, 0), Station.SOUTH),
        ]
    )
    assert week.total_hours(dalton) == 6.5
    assert len(week.shifts_for(dalton)) == 2