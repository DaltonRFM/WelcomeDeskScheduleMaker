# Welcome Desk Scheduler

Automated shift scheduling for the Welcome Desk student worker team.

Takes weekly availability (currently tracked by hand in a Google Sheet) plus
schedule requests (collected via Google Form) and produces a shift schedule
that satisfies coverage, hour, and rotation requirements.

The goal of this project is future WDSAM can use it to help with making a working schedule for the ~20+ welcome desk students. This currently is setup for semesterly schedules, it is not intended for small breaks, finals, or summer schedules.

## Stack
- Python 3.9+
- [OR-Tools](https://developers.google.com/optimization) (CP-SAT solver) for
  constraint satisfaction / optimization
- `openpyxl` for the colored spreadsheet output
- (Planned) Google Sheets API for pulling availability live instead of via
  manual CSV export -- see docs/ROADMAP.md Step 8 stretch goal

## Setup
```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## How to generate a schedule (full workflow)

This is the process end-to-end, from the color-coded availability sheet to
a finished, colored schedule file. Do this once per semester/term.

### 1. Convert the colored availability sheet to plain Y/N data

The master availability sheet uses cell background color (green =
available, red = busy) to track availability, but the scheduler needs plain
text data to read. A Google Apps Script handles this conversion:

1. Open the master availability Google Sheet.
2. Go to **Extensions > Apps Script**.
3. Paste in the script from `tools/apps_script_color_to_yn.gs` (or it may
   already be saved there from a previous run -- check first).
4. At the top of the script, update the `CONFIG` object if your sheet's
   layout has changed (which row has names, which row/column data starts
   at, etc.) -- comments in the script explain each field.
5. Save (disk icon), then from the function dropdown near "Run", select
   `runAllDays` (converts all 5 weekday tabs in one go, if they share the
   same layout) and click **Run**.
6. First run will prompt you to authorize the script -- this is normal,
   click through it (Review permissions > your account > Advanced > Go to
   [project name] (unsafe) > Allow). It only touches this spreadsheet.
7. You'll get 5 new tabs: `Monday_YN`, `Tuesday_YN`, etc.

### 2. Export each day as CSV

For each `_YN` tab: **File > Download > Comma Separated Values (.csv)**.
You should end up with 5 files (one per weekday).

### 3. Add the CSVs to this project

Move the downloaded CSVs into `data/`, named clearly, e.g.:
`monday_availability.csv`, `tuesday_availability.csv`, etc.

**Important:** the two manager accounts (Dalton and Grayson, or whoever is
making the schedule) don't fill out the availability form and won't appear
in these CSVs. If they need to be included in the schedule, their
availability needs to be added to the CSVs by hand before running the
solver.

### 4. Point the pipeline at the real files

In `src/main.py`, update `CSV_FILES` to point at your 5 real files instead
of the sample data:
```python
CSV_FILES = {
    Day.MONDAY: "data/monday_availability.csv",
    Day.TUESDAY: "data/tuesday_availability.csv",
    Day.WEDNESDAY: "data/wednesday_availability.csv",
    Day.THURSDAY: "data/thursday_availability.csv",
    Day.FRIDAY: "data/friday_availability.csv",
}
```

Also double check the business-rule constants near the top of `main.py`
still match reality for this semester (operating hours, station capacity,
min/max hours, etc.) -- these change occasionally and are worth a quick
review each term.

### 5. Run the solver

```bash
python -m src.main
```

This writes a plain CSV to `data/generated_schedule.csv`. If it says **"No
valid schedule found"**, don't panic -- see Troubleshooting below.

### 6. Generate the colored spreadsheet

```bash
python -m src.xlsx_writer
```

This writes `data/generated_schedule.xlsx` -- a colored, merged-cell
spreadsheet matching the original hand-built layout (Day > Station columns
across the top, time down the side, one color per person). Open it
directly in Excel/Numbers, or upload it to Google Drive and open with
Sheets (no Google API setup needed for this step).

### Troubleshooting: "No valid schedule found"

This means the constraints as configured can't all be satisfied
simultaneously -- it's telling you something real, not a bug. Two tools
help figure out why:

```bash
python -m src.diagnostics
```
Checks for basic issues: not enough people available at some time slot, or
not enough total availability for everyone to hit their minimum hours.

```bash
python -m src.bisect_infeasibility
```
If diagnostics comes back clean but it's still infeasible, this re-runs
the real data with different constraints relaxed one at a time (no
rotation requirement, wider hour bounds, etc.) to isolate which specific
rule is the actual conflict. Can take a while to run -- each attempt has
up to a 30-second solve limit.

Common fixes: widen `MIN_HOURS`/`MAX_HOURS` in `main.py`, double check
`STATION_CAPACITY` matches reality, or confirm the CSVs actually loaded
(a typo'd file path silently produces an empty availability set).

## Run Tests
python -m pytest tests/ -v
