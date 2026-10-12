# UAV SITL Test Suite
 
Automated tests for drone flight-controller software, run against a **software-in-the-loop (SITL)** simulator: the real flight-control code runs on a PC, connected to a simulated vehicle, with no hardware and no risk to an aircraft.
 
> **Status: planned.** No code has been written yet. This document describes the goal, the scope and the intended approach, so that the project can be built and judged against a clear plan. Items are marked as done only when they exist in this repository

## Why this project
Flight software is tested best where mistakes are cheap. A simulator lets me check how a flight controller reacts to normal missions and to failures (lost GPS, lost radio link, low battery) hundreds of times, repeatably, and from a script. The same thinking applies to any embedded product: define the expected behaviour, drive the system, observe it, and decide pass or fail automatically.


## Goals
- Run a flight-controller SITL simulator from a test, with a clean start and a clean stop for every test.
- Drive the vehicle over MAVLink from Python: arm, take off, change mode, fly a mission, land.
- Inject faults: GPS loss, radio-link loss, low battery, geofence breach.
- Decide pass or fail from telemetry with explicit, documented criteria.
- Keep the whole suite runnable with one command and, later, in continuous integration.
- Store logs and results for every run so that a failed test can be investigated.

## Planned scope
| Area | Example checks | Status |
|---|---|---|
| Basic flight | Arm, take off to a target altitude, hold position, land and disarm | Planned |
| Flight modes | Mode changes are accepted or rejected as expected | Planned |
| Mission execution | A waypoint mission is completed within a position and time tolerance | Planned |
| Failsafe: GPS loss | The vehicle switches to the expected safe behaviour | Planned |
| Failsafe: radio-link loss | The vehicle returns or lands according to the configured action | Planned |
| Failsafe: low battery | The configured battery action is triggered | Planned |
| Geofence | The vehicle does not leave the fence and reacts as configured | Planned |
| Parameter checks | Safety-relevant parameters keep their expected values | Planned |
 
The exact test list will be written as a test plan before the tests, and each test will state its setup, action, expected result and tolerance.


## Planned approach
- **Simulator:** an open-source flight-controller SITL (ArduPilot SITL is the first candidate; PX4 SITL is the alternative). The final choice and the reasons will be recorded in `docs/design-notes.md` when work starts.
- **Control and telemetry:** MAVLink from Python (pymavlink).
- **Test framework:** pytest, with fixtures that start and stop the simulator and open the MAVLink connection.
- **Pass or fail:** assertions on telemetry (altitude, position, mode, status messages) with explicit time limits, never fixed sleeps alone.
- **Results:** logs and a short report stored per run.
- **Automation:** a GitHub Actions workflow once the suite runs reliably locally.

## Planned repository layout
```
02-uav-sitl-tests/
├── README.md
├── docs/
│   ├── test-plan.md          what is tested, setup, expected results, tolerances
│   └── design-notes.md       why the simulator, tools and structure were chosen
├── tests/                    pytest tests, grouped by area
├── sitl/                     helpers that start, stop and configure the simulator
├── utils/                    MAVLink helpers and telemetry assertions
└── requirements.txt
```
These folders will appear as the work is done. Setup and run instructions will be added when the first test passes on a clean machine.

## Roadmap
- [ ] Decide the simulator and record the decision
- [ ] Install and run the simulator by hand, document the steps
- [ ] First test: arm, take off, land
- [ ] Reusable fixtures for starting and stopping the simulator
- [ ] Flight mode and mission tests
- [ ] Failsafe tests (GPS, radio link, battery) and geofence
- [ ] Test plan document and result reports
- [ ] Continuous integration workflow



Readme 02 · MD
# UAV SITL Test Suite
 
Automated tests for drone flight-controller software, run against a **software-in-the-loop (SITL)** simulator: the real flight-control code runs on a PC, connected to a simulated vehicle, with no hardware and no risk to an aircraft.
 
> **Status: planned.** No code has been written yet. This document describes the goal, the scope and the intended approach, so that the project can be built and judged against a clear plan. Items are marked as done only when they exist in this repository.
 
## Why this project
 
Flight software is tested best where mistakes are cheap. A simulator lets me check how a flight controller reacts to normal missions and to failures (lost GPS, lost radio link, low battery) hundreds of times, repeatably, and from a script. The same thinking applies to any embedded product: define the expected behaviour, drive the system, observe it, and decide pass or fail automatically.
 
This project is the software-side companion of the hardware work in this portfolio:
 
- [`03-pcb-test-interface-board`](../03-pcb-test-interface-board): a board that powers and observes a real device under test.
- [`01-hil-test-stand`](../01-hil-test-stand): the pytest framework that will drive that board.
- **This project:** the same style of test automation, applied to flight-controller behaviour in simulation.
## Goals
 
- Run a flight-controller SITL simulator from a test, with a clean start and a clean stop for every test.
- Drive the vehicle over MAVLink from Python: arm, take off, change mode, fly a mission, land.
- Inject faults: GPS loss, radio-link loss, low battery, geofence breach.
- Decide pass or fail from telemetry with explicit, documented criteria.
- Keep the whole suite runnable with one command and, later, in continuous integration.
- Store logs and results for every run so that a failed test can be investigated.
## Planned scope
 
| Area | Example checks | Status |
|---|---|---|
| Basic flight | Arm, take off to a target altitude, hold position, land and disarm | Planned |
| Flight modes | Mode changes are accepted or rejected as expected | Planned |
| Mission execution | A waypoint mission is completed within a position and time tolerance | Planned |
| Failsafe: GPS loss | The vehicle switches to the expected safe behaviour | Planned |
| Failsafe: radio-link loss | The vehicle returns or lands according to the configured action | Planned |
| Failsafe: low battery | The configured battery action is triggered | Planned |
| Geofence | The vehicle does not leave the fence and reacts as configured | Planned |
| Parameter checks | Safety-relevant parameters keep their expected values | Planned |
 
The exact test list will be written as a test plan before the tests, and each test will state its setup, action, expected result and tolerance.
 
## Planned approach
 
- **Simulator:** an open-source flight-controller SITL (ArduPilot SITL is the first candidate; PX4 SITL is the alternative). The final choice and the reasons will be recorded in `docs/design-notes.md` when work starts.
- **Control and telemetry:** MAVLink from Python (pymavlink).
- **Test framework:** pytest, with fixtures that start and stop the simulator and open the MAVLink connection.
- **Pass or fail:** assertions on telemetry (altitude, position, mode, status messages) with explicit time limits, never fixed sleeps alone.
- **Results:** logs and a short report stored per run.
- **Automation:** a GitHub Actions workflow once the suite runs reliably locally.
## Planned repository layout
 
```
02-uav-sitl-tests/
├── README.md
├── docs/
│   ├── test-plan.md          what is tested, setup, expected results, tolerances
│   └── design-notes.md       why the simulator, tools and structure were chosen
├── tests/                    pytest tests, grouped by area
├── sitl/                     helpers that start, stop and configure the simulator
├── utils/                    MAVLink helpers and telemetry assertions
└── requirements.txt
```
 
These folders will appear as the work is done. Setup and run instructions will be added when the first test passes on a clean machine.
 
## Roadmap
 
- [ ] Decide the simulator and record the decision
- [ ] Install and run the simulator by hand, document the steps
- [ ] First test: arm, take off, land
- [ ] Reusable fixtures for starting and stopping the simulator
- [ ] Flight mode and mission tests
- [ ] Failsafe tests (GPS, radio link, battery) and geofence
- [ ] Test plan document and result reports
- [ ] Continuous integration workflow

## Limitations 
- A simulator is not a real aircraft. Results show how the software behaves in the simulated model, not how a real vehicle flies.
- The simulated sensors and physics are simplified, so timing and tolerances measured here are not flight-qualified values.
- This is a learning and demonstration project. It is not a certified test procedure.
