# Example test run

A full run of the suite, kept as a reference. The report is a single HTML file:
open [`allure-report/index.html`](allure-report/index.html) in a browser, no server needed.

| Item | Value |
|---|---|
| Date | 2026-10-17 |
| Simulator | ArduCopter V4.8.0-dev SITL, quadcopter (`+` frame), Linux (distrobox) |
| Test runner | Windows, Python 3.14.5, pytest 9.1.1, pymavlink 2.4.50, allure-pytest 2.16.2 |
| Result | **60 passed**, 0 failed (52 SITL tests, 8 unit tests) |
| Duration | about 17.5 min |

## What the report shows

- **Behaviors** tab: tests grouped as *SITL tests* / *Unit tests*, then by area
  (arming, missions, failsafe, geofence, ...). Each test is listed under its
  TC-ID and title from [`docs/test-plan.md`](../test-plan.md).
- **Failed tests** (none in this run) carry two attachments: all STATUSTEXT
  messages received during the test and the vehicle state at the moment of failure.

## How to reproduce

1. Start a **fresh** SITL instance. Restart it before every full run: the battery
   failsafe test (TC-052/053) leaves the failsafe latched until the simulator restarts.
2. Run the suite from the project root:
   ```
   pytest
   ```
3. Build the single-file report:
   ```
   allure generate reports/allure-results --clean --single-file -o docs/results/allure-report
   ```
