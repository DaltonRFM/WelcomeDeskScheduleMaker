# Roadmap (small, incremental steps)

Each step should be small enough to finish and test in one sitting.

- [x] **Step 0** — Repo scaffold
- [ ] **Step 1** — Define the core data model (Person, TimeSlot, Availability,
      Shift, Station) as plain Python classes/dataclasses, no solver yet
- [ ] **Step 2** — Write a parser that turns an exported availability sheet
      (CSV) into the data model — no Google API auth yet, just local files
- [ ] **Step 3** — Hard-code a tiny fake dataset (3–4 people, 1 day) and get
      OR-Tools CP-SAT producing *any* valid schedule respecting availability
      + operating hours
- [ ] **Step 4** — Add station coverage requirements (North/South/Dean's
      staffed correctly)
- [ ] **Step 5** — Add open/close-at-least-once and min/max weekly hours
      constraints
- [ ] **Step 6** — Add the "must work North and South at some point" rule
- [ ] **Step 7** — Add soft constraints: honor requests, minimize
      fragmentation, balance hours (objective function + weights)
- [ ] **Step 8** — Swap the fake dataset for real data pulled from the
      actual Google Sheet (Sheets API auth)
- [ ] **Step 9** — Output formatting: clean CSV/table export
- [ ] **Step 10 (stretch)** — Auto-generate the colored Google Sheet output
- [ ] **Step 11 (stretch)** — Pull request-form free text answers in and
      parse/apply them (starts manual/simple, could later use light NLP)