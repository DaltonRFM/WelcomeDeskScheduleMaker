"""
Core data model for the Welcome Desk scheduler.

No solver logic here — just plain dataclasses describing the shape of the
data we're working with. Step 2 (the availability parser) will build these
objects from a CSV; Step 3+ will hand them to OR-Tools.
"""

from dataclasses import dataclass, field
from datetime import date, time
from enum import Enum


class Station(Enum):
    NORTH = "North"
    SOUTH = "South"
    DEANS_SUITE = "Dean's Suite"


class Day(Enum):
    MONDAY = "Monday"
    TUESDAY = "Tuesday"
    WEDNESDAY = "Wednesday"
    THURSDAY = "Thursday"
    FRIDAY = "Friday"


@dataclass(frozen=True)
class Person:
    """
    A student worker. Everyone is trained/eligible for all three stations,
    so there's no per-person station restriction to track right now.
    """
    name: str


@dataclass(frozen=True)
class TimeSlot:
    """
    One discrete block of time on one day, e.g. Monday 7:30-7:45.
    Shifts are built out of contiguous runs of these.
    """
    day: Day
    start: time
    end: time


@dataclass(frozen=True)
class Availability:
    """
    Whether a given person is available during a given time slot.
    is_available=False covers both class time and stated external
    conflicts (e.g. a second job) — both are hard blackout constraints,
    so we don't distinguish between them here.
    """
    person: Person
    slot: TimeSlot
    is_available: bool


@dataclass(frozen=True)
class ScheduleRequest:
    """
    A soft preference pulled from the request form, e.g. "wants to open
    Mondays". Not guaranteed to be honored — used to weight the solver's
    objective function later, not as a hard constraint.
    """
    person: Person
    description: str


@dataclass
class Shift:
    """
    An actual scheduled block: one person, one station, one contiguous
    stretch of time on one day. This is what the solver ultimately
    produces — a list of these is the finished schedule.
    """
    person: Person
    station: Station
    day: Day
    start: time
    end: time

    def duration_hours(self) -> float:
        start_minutes = self.start.hour * 60 + self.start.minute
        end_minutes = self.end.hour * 60 + self.end.minute
        return (end_minutes - start_minutes) / 60


@dataclass
class WeekSchedule:
    """
    A full week's worth of shifts, plus a convenience lookup by person
    for checking hour totals / open-close / station coverage later.
    """
    shifts: list[Shift] = field(default_factory=list)

    def shifts_for(self, person: Person) -> list[Shift]:
        return [s for s in self.shifts if s.person == person]

    def total_hours(self, person: Person) -> float:
        return sum(s.duration_hours() for s in self.shifts_for(person))