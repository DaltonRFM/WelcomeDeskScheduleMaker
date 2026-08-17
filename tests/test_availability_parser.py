from datetime import time

from src.availability_parser import apply_blackouts, parse_availability_csv
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

def test_blackout_whole_day():
    results = parse_availability_csv("data/sample_monday.csv", Day.MONDAY)
    dalton = Person(name="Dalton")

    blacked_out = apply_blackouts(results, {dalton: [Day.MONDAY]})

    for r in blacked_out:
        if r.person == dalton:
            assert r.is_available is False
    # Other people's availability untouched
    abby_730 = next(
        r for r in blacked_out
        if r.person == Person(name="Abby") and r.slot.start == time(7, 30)
    )
    assert abby_730.is_available is False  # unchanged from original data (was already N)


def test_blackout_partial_window():
    results = parse_availability_csv("data/sample_monday.csv", Day.MONDAY)
    dalton = Person(name="Dalton")

    # Dalton was Y at 7:30 and 7:45 in the sample data -- blackout just 7:30-7:45
    blacked_out = apply_blackouts(
        results, {dalton: [(Day.MONDAY, time(7, 30), time(7, 45))]}
    )

    dalton_730 = next(
        r for r in blacked_out if r.person == dalton and r.slot.start == time(7, 30)
    )
    dalton_800 = next(
        r for r in blacked_out if r.person == dalton and r.slot.start == time(8, 0)
    )
    assert dalton_730.is_available is False  # blacked out
    assert dalton_800.is_available is True   # untouched, still available


def test_blackout_does_not_mutate_input():
    results = parse_availability_csv("data/sample_monday.csv", Day.MONDAY)
    dalton = Person(name="Dalton")
    original_snapshot = [r.is_available for r in results]

    apply_blackouts(results, {dalton: [Day.MONDAY]})

    assert [r.is_available for r in results] == original_snapshot