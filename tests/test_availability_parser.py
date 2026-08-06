from datetime import time

from src.availability_parser import parse_availability_csv
from src.models import Day, Person


def test_parses_all_rows_for_all_people():
    results = parse_availability_csv("data/sample_monday.csv", Day.MONDAY)
    # 4 time rows x 3 people = 12 Availability records
    assert len(results) == 12


def test_correct_availability_values():
    results = parse_availability_csv("data/sample_monday.csv", Day.MONDAY)

    dalton_730 = next(
        r for r in results
        if r.person == Person(name="Dalton") and r.slot.start == time(7, 30)
    )
    assert dalton_730.is_available is True

    abby_730 = next(
        r for r in results
        if r.person == Person(name="Abby") and r.slot.start == time(7, 30)
    )
    assert abby_730.is_available is False


def test_slot_end_is_15_minutes_after_start():
    results = parse_availability_csv("data/sample_monday.csv", Day.MONDAY)
    first = results[0]
    assert first.slot.start == time(7, 30)
    assert first.slot.end == time(7, 45)