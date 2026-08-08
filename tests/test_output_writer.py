import csv
from datetime import time

from src.models import Day, Person, Shift, Station
from src.output_writer import write_schedule_csv

ALEX = Person(name="Alex")
BOB = Person(name="Bob")


def test_writes_expected_rows(tmp_path):
    shifts = [
        Shift(ALEX, Day.MONDAY, time(7, 30), time(9, 30), Station.NORTH),
        Shift(BOB, Day.MONDAY, time(9, 30), time(11, 0), Station.SOUTH),
    ]
    output_path = tmp_path / "schedule.csv"

    write_schedule_csv(shifts, str(output_path))

    with open(output_path, newline="", encoding="utf-8") as f:
        rows = list(csv.reader(f))

    assert rows[0] == ["Day", "Station", "Person", "Start", "End", "Hours"]
    assert len(rows) == 3  # header + 2 shifts
    assert rows[1][0] == "Monday"
    assert rows[1][2] == "Alex"


def test_rows_sorted_by_day_then_time(tmp_path):
    # Deliberately out of order going in
    shifts = [
        Shift(BOB, Day.TUESDAY, time(7, 30), time(9, 0), Station.NORTH),
        Shift(ALEX, Day.MONDAY, time(9, 0), time(11, 0), Station.NORTH),
        Shift(ALEX, Day.MONDAY, time(7, 30), time(9, 0), Station.NORTH),
    ]
    output_path = tmp_path / "schedule.csv"

    write_schedule_csv(shifts, str(output_path))

    with open(output_path, newline="", encoding="utf-8") as f:
        rows = list(csv.reader(f))

    data_rows = rows[1:]
    # Monday's 7:30 shift first, then Monday's 9:00 shift, then Tuesday
    assert data_rows[0][0] == "Monday"
    assert data_rows[0][3] == "7:30 AM"
    assert data_rows[1][0] == "Monday"
    assert data_rows[1][3] == "9:00 AM"
    assert data_rows[2][0] == "Tuesday"