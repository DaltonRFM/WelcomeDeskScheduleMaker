# Welcome Desk Scheduler

Automated shift scheduling for the Welcome Desk student worker team.

Takes weekly availability (currently tracked by hand in a Google Sheet) plus
schedule requests (collected via Google Form) and produces a shift schedule
that satisfies coverage, hour, and rotation requirements. 

The goal of this project is future WDSAM can use it to help with making a working schedule for the ~20+ welcome desk students. This currently is setup for semesterly schedules, it is not intended for small breaks, finals, or summer schedules.

## Run Tests
python -m pytest tests/ -v

## Stack (planned)
- Python 3.11+
- [OR-Tools](https://developers.google.com/optimization) (CP-SAT solver) for
  constraint satisfaction / optimization
- Google Sheets API + Google Forms API (via `gspread` / `google-api-python-client`)
  for pulling availability data and pushing the finished schedule

## Setup
```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```