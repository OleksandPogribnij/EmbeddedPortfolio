# UAV SITL Test Suite

[![UAV SITL tests](https://github.com/OleksandPogribnij/EmbeddedPortfolio/actions/workflows/sitl-tests.yml/badge.svg)](https://github.com/OleksandPogribnij/EmbeddedPortfolio/actions/workflows/sitl-tests.yml)
[![Allure report](https://img.shields.io/badge/report-Allure-orange)](https://oleksandpogribnij.github.io/EmbeddedPortfolio/)

Automated tests for drone flight-controller software. The suite drives
**ArduCopter** running in the ArduPilot **SITL (software-in-the-loop)**
simulator over **MAVLink**, injects faults (GPS loss, radio-link loss, low
battery, geofence breach) and decides pass or fail from telemetry. The real
flight code runs on a PC, so failures are cheap and every run is repeatable.

**Status: complete.** 60 tests pass (52 SITL, 8 unit) against ArduCopter
V4.8.0-dev. Reference report: [`docs/results`](docs/results/README.md).

## What is tested

| Area | Test cases | Examples |
|---|---|---|
| Connection | TC-001..003 | Heartbeat, telemetry streams, initial state |
| Arming | TC-010..014 | Arm, disarm, arm refused without GPS (with reason), auto-disarm, disarm refused in flight |
| Take-off and landing | TC-020..024 | Target altitude ± 1 m, altitude hold, landing with auto-disarm, take-off refused while disarmed |
| Flight modes | TC-030..032 | Mode changes on the ground and in flight, RTL lands within 3 m of home |
| Missions | TC-040..046 | Square mission in AUTO, progress, interruption by LOITER, upload/download, clear, overwrite, invalid item |
| Failsafe | TC-050..053 | GPS loss → RTL/LAND, radio loss → RTL home, low battery → RTL then critical → LAND |
| Geofence | TC-060 | Breach of a 60 m circular fence → RTL, overshoot ≤ 30 m |
| Parameters | TC-070..072 | Safety configuration the failsafe tests rely on, write/read-back, unknown name |
| Telemetry | TC-080..084 | GPS fix, battery, hover drift, flight speed |
| Helpers (unit) | UT-001..008 | Geodesic distance, STATUSTEXT recorder |

Every test case has a setup, steps, expected result and tolerance in the
[test plan](docs/test-plan.md); the ID in the plan, in the code and in the
report is the same.

## How it works

```
 Linux: ArduCopter SITL ── MAVProxy ──UDP 14550──▶ Windows: pytest + pymavlink
                                                         │
          (CI: SITL on the same runner, TCP 5760) ◀──────┘
                                                         ▼
                                                   Allure report
```

- **Fixtures as vehicle states.** `vehicle_on_ground`, `in_flight`,
  `clean_mission`, `param_changer` put the vehicle into a known state and
  restore it after the test, whatever the test did.
- **Faults over MAVLink.** GPS, RC link and battery faults are injected
  with SITL `SIM_*` parameters, the same way a ground station would set
  any parameter. All names and values were confirmed with `param show`
  and live in [`sitl/params.py`](sitl/params.py).
- **Every reaction is explained.** A recorder hooked into pymavlink keeps
  every STATUSTEXT, so a failsafe test checks both *what* the autopilot did
  (mode, landing, position) and that it *reported* it. A failed test
  carries the status texts and the vehicle state in the Allure report.
- **No magic numbers.** Thresholds and timeouts are named constants with
  units (`utils/constants.py`); helpers raise errors that say what was
  expected and what was last seen.

The reasoning behind each decision and what was learned about ArduCopter
along the way (latched battery failsafe, geofence braking distance, why
`drain()` loses status texts, …) is in the
[design notes](docs/design-notes.md).

## Quick start

```bash
# Linux: simulator (see docs/setup.md for the ArduPilot build)
sim_vehicle.py -v ArduCopter --model + --out 127.0.0.1:14550

# test runner
cd 02-uav-sitl-tests
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
pytest                         # full suite, about 17.5 min
pytest -m "not sitl"           # unit tests only, no simulator
allure serve reports/allure-results
```

Restart SITL before every full run. Full instructions, including running
the simulator and the tests on different machines: [docs/setup.md](docs/setup.md).

## Continuous integration

[`.github/workflows/sitl-tests.yml`](../.github/workflows/sitl-tests.yml):

1. **Lint and unit tests**: ruff and the unit tests, no simulator.
2. **SITL tests**: builds ArduCopter SITL (cached per ArduPilot commit),
   starts it on the runner and runs the SITL suite against it.
3. **Allure report**: merges the results and publishes the report to
   GitHub Pages, also when tests fail.

## Repository layout

```
02-uav-sitl-tests/
├── README.md
├── pytest.ini              markers, timeouts, Allure output
├── pyproject.toml          ruff configuration
├── requirements.txt        test dependencies
├── requirements-dev.txt    + ruff
├── docs/
│   ├── test-plan.md        every test case: setup, steps, expected result, tolerance
│   ├── design-notes.md     decisions and ArduCopter findings
│   ├── setup.md            simulator and test runner setup
│   └── results/            reference run with a single-file Allure report
├── sitl/
│   └── params.py           expected parameters and fault-injection values
├── utils/
│   ├── connection.py       connect, heartbeat, drain
│   ├── commands.py         arm, disarm, modes, take-off, land, RTL, goto, parameters
│   ├── telemetry.py        altitude, position, GPS, battery, ground speed
│   ├── mission.py          mission upload, download, clear, start, progress
│   ├── status_text.py      STATUSTEXT recorder
│   ├── geo.py              distance and offset on the Earth's surface
│   └── constants.py        thresholds, timeouts, flight profile
└── tests/
    ├── conftest.py         fixtures, run order, Allure labels and failure attachments
    └── test_*.py           one file per area
```

## Tools

Python 3.14 · pytest · pymavlink · ArduPilot SITL · MAVProxy · Allure ·
ruff · GitHub Actions

## Limitations

- Simulated physics are simplified: the tolerances are criteria for the
  simulator, not flight-qualified values.
- The battery failsafe stays latched until SITL restarts, so the battery
  test runs last and a full run needs a fresh simulator.
- The STATUSTEXT checks match keywords, not the exact wording of the
  autopilot messages.
