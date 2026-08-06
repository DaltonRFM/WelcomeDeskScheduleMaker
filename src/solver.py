"""
Step 3: the first working solver.

Given a list of Availability records for a single day, and the day's
operating hours, find a schedule where exactly one person covers every
15-minute slot, and nobody is scheduled when they're unavailable.

No stations yet (Step 4), no min/max hours or open/close rules yet
(Step 5), no soft preferences yet (Step 7). This step only proves the
solver can find ANY valid schedule against real availability constraints.
"""

from datetime import datetime, time, timedelta

from ortools.sat.python import cp_model

from src.models import Availability, Day, Person, Shift, TimeSlot

from typing import Optional

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
) -> Optional[list[Shift]]:
    """
    Returns a list of Shifts covering every slot in the operating window,
    or None if no valid schedule exists (e.g. nobody's available during
    some slot).
    """
    people = sorted({a.person for a in availabilities}, key=lambda p: p.name)
    slots = _generate_slots(day, operating_start, operating_end)

    # Quick lookup: is this person available at this slot's start time?
    avail_lookup = {(a.person, a.slot.start): a.is_available for a in availabilities}

    model = cp_model.CpModel()

    # One boolean variable per (person, slot): are they covering it?
    assign = {
        (p, s.start): model.NewBoolVar(f"assign_{p.name}_{s.start}")
        for p in people
        for s in slots
    }

    # Hard constraint: can't be assigned when unavailable
    for p in people:
        for s in slots:
            if not avail_lookup.get((p, s.start), False):
                model.Add(assign[(p, s.start)] == 0)

    # Hard constraint: exactly one person covers each slot
    for s in slots:
        model.Add(sum(assign[(p, s.start)] for p in people) == 1)

    solver = cp_model.CpSolver()
    status = solver.Solve(model)

    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return None

    return _slots_to_shifts(solver, assign, people, slots, day)


def _slots_to_shifts(solver, assign, people, slots, day) -> list[Shift]:
    """Merges each person's consecutive assigned slots into single Shifts,
    e.g. four assigned 15-min slots in a row become one 1-hour Shift."""
    shifts = []

    for p in people:
        run_start = None
        run_end = None

        for s in slots:
            is_assigned = solver.Value(assign[(p, s.start)]) == 1

            if is_assigned:
                if run_start is None:
                    run_start = s.start
                run_end = s.end
            elif run_start is not None:
                shifts.append(Shift(person=p, day=day, start=run_start, end=run_end))
                run_start = None
                run_end = None

        if run_start is not None:
            shifts.append(Shift(person=p, day=day, start=run_start, end=run_end))

    return shifts