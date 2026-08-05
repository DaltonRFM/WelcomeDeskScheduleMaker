# Planning: Requirements & Constraints

## Inputs
1. **Availability data** — currently a manually-colored Google Sheet
   (green = available, red = busy/in class), 15-min granularity, one column
   per person, one row per time slot, split by day.
2. **Schedule request form** (Google Form, "Fall '26 Semester Schedule")
   collects per person:
   - Class schedule upload (source of the green/red availability, ideally
     with class *locations* — not used for scheduling logic yet, but
     collected)
   - Whether their schedule is likely to change before the semester starts
   - Free-text: non-class time conflicts during working hours (e.g. a second
     job at specific times) — **treat as hard blackout constraint**, same
     as class time
   - Free-text: schedule requests, e.g. "I want to open Mondays" — **treat
     as soft/preferred constraint**, no guarantee

## Business rules (hard constraints)
- Operating hours: Mon–Thu 7:30 AM–5:00 PM, Fri 8:00 AM–5:00 PM
- Three stations per (non-Friday) shift block: North, South, Dean's Suite
  - Friday: North, South, Dean's Suite (per screenshot — confirm exact
    Friday station list/hours before building the Friday logic)
- A person can never be scheduled during a time they marked unavailable
  (class) or during a stated external conflict (e.g. second job)
- No person double-booked across two stations in overlapping time
- Every person must work **both** North and South at some point during the
  week (not necessarily every day)
- Every person must open (be on the first shift of a day) **at least once**
  during the week
- Every person must close (be on the last shift of a day) **at least once**
  during the week
- Minimum total weekly hours per person: **10**
- Maximum total weekly hours per person: **12.5**

## Soft constraints / preferences (optimize for, not guaranteed)
- Honor specific requests from the form where possible (e.g. "prefer to
  open Mondays")
- Minimize shift fragmentation (prefer fewer, longer blocks per person per
  day over many short ones)
- Balance hours reasonably across the team within the 10–12.5 band

## Output (MVP → stretch)
- **MVP:** structured output (CSV or plain table) listing person, day,
  station, start time, end time
- **Stretch goal:** auto-generate a Google Sheet formatted like the current
  hand-built schedule (colored blocks per person, station columns, day
  sections) via the Sheets API

## Open questions to confirm before building the solver
- Exact Friday station/hour breakdown (screenshot shows North/South/Dean's,
  shifts roughly 8–12:30 / 12:30–5 / full day — confirm exact rules)
- Is "must work both North and South" weekly, or is it OK to skip a desk in
  a given week if unavoidable?
- How to weight honoring a request vs. other soft goals (fragmentation,
  hour balance) if they conflict
- Minimum shift length allowed (avoid something like a 15–30 min shift)