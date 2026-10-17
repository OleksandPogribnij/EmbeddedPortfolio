# Design Notes

Why the suite is built the way it is, and what was learned about ArduCopter
while building it. Each finding below was observed on ArduCopter V4.8.0-dev
SITL and is reflected in the code; the file and function names show where.

## 1. Decisions

### 1.1 Simulator: ArduPilot SITL

ArduPilot SITL runs the real ArduCopter flight code against a simulated
vehicle, speaks MAVLink like real hardware, and exposes fault injection
through `SIM_*` parameters (GPS, RC link, battery voltage). That covers
every failure this suite needs without touching simulator code. PX4 SITL
was the alternative; ArduPilot was chosen for its parameter-based fault
injection and because one autopilot is enough to show the method.

### 1.2 Control library: pymavlink

pymavlink gives direct access to every MAVLink message: COMMAND_ACK
results, STATUSTEXT reasons, mission protocol handshakes. Higher-level
libraries hide exactly the details a test has to check, such as *why* an
arm command was refused. The cost is more code in `utils/`; that code is
small, typed and documented.

### 1.3 Simulator lifecycle is outside the suite

The first plan had a `sitl/manager.py` that would start and stop SITL for
every test. It was dropped:

- Locally, SITL runs on another machine (a Linux laptop) than the tests
  (a Windows PC), so the test process cannot start it.
- Starting SITL per test would add start-up and EKF/GPS settling time to
  every test and make the run several times longer.

Instead, test isolation comes from fixtures (section 2) that put the
vehicle into a known state before each test and back on the ground after
it. The simulator is started once per run: by hand locally, by the
workflow in CI. The one state that fixtures cannot reset — a latched
battery failsafe — is handled by test ordering (section 3.9).

### 1.4 One connection per session

The `vehicle` fixture opens one MAVLink connection for the whole run.
Reconnecting per test costs time and, over UDP, one port can have only one
listener anyway. If the simulator is unreachable, the run stops at once
with exit code 2 and a message that names the endpoint, instead of
producing 52 identical failures.

### 1.5 Helpers raise, tests assert

Helpers in `utils/` (`arm`, `takeoff`, `goto`, `wait_for_mode`, …) wait
with their own timeouts and raise `TimeoutError` or `RuntimeError` with
what was expected and what was last seen ("Altitude 10 m not reached
within 60 s, last: 7.4 m"). Tests contain only the checks of the test case,
each with a message in the form *"<what>: expected X, got Y"*. A failure
can be understood from the message without rerunning the test.

### 1.6 Configuration as data

- `utils/constants.py`: every threshold, timeout and observation window,
  with its unit in the name (`_M`, `_S`, `_MPS`). No magic numbers in tests.
- `sitl/params.py`: expected parameter values and fault-injection values.
  All names and values were confirmed with `param show` on the simulator,
  not taken from memory. TC-070 checks the values the failsafe tests depend
  on, so a changed configuration fails one clear test instead of making a
  failsafe test fail for an unrelated-looking reason.

### 1.7 Test IDs live in docstrings

The first line of each test's docstring starts with its ID
(`"TC-012: vehicle refuses to arm without a GPS 3D fix."`). A hook in
`conftest.py` reads it and sets the Allure ID, title and tags; the module
docstring gives the Allure feature. The test plan, the code and the report
use the same ID, and there is no second copy in decorators to keep in sync.

### 1.8 Unit tests for the test helpers

The non-trivial helpers that do not need a simulator are unit-tested:
the haversine distance (UT-001..003) and the STATUSTEXT recorder
(UT-004..008, with a fake connection that runs message hooks like
pymavlink). These run in CI on every push in seconds.

## 2. Fixtures as vehicle states

Fixtures describe the state the vehicle is in when the test starts, and
each one cleans up after itself:

```
vehicle                 one connection, STATUSTEXT recorder attached
└── vehicle_on_ground   landed, disarmed, GUIDED        → land after the test
    ├── home_position   position read on the ground
    └── in_flight       armed, hovering at 10 m         → land after the test
clean_mission           no mission before and after
param_changer           changed parameters restored after the test
status_log              STATUSTEXT recorder emptied for this test
```

`in_flight` depends on `home_position` without using it: this forces the
home point to be read on the ground, before take-off.

## 3. ArduCopter findings

### 3.1 STATUSTEXT is lost by `drain()`

Most helpers call `drain()` before reading, so they see fresh values and
not a stale buffer. But the autopilot reports *why* something happened
(failsafe triggered, arming refused) as STATUSTEXT, at a moment the test
does not control, and `drain()` throws those messages away.

Solution: `utils/status_text.py`. `StatusTextRecorder` registers a function
in pymavlink's `message_hooks`. pymavlink calls these hooks for every
received message *before* `recv_match()` filters it or `drain()` discards
it, so every status text is kept with its time and severity. `wait_for()`
keeps reading the port while it waits, because hooks run only when
something reads. The same recorder feeds the failure report (section 4).

### 3.2 Arm refusals: read COMMAND_ACK and STATUSTEXT together

When arming is refused, ArduCopter sends a STATUSTEXT with the reason
(e.g. `Arm: GPS 1: Bad fix`) and a COMMAND_ACK with a failure result.
`_send_arm_disarm()` reads HEARTBEAT, STATUSTEXT and COMMAND_ACK in one
loop and, after a refusal, waits one more second for the reason text.
`arm()` retries, because pre-arm checks fail for a while after SITL start.

### 3.3 In-flight disarm is refused without a reason text

A disarm command in flight is refused with COMMAND_ACK only; no
STATUSTEXT is sent. The helper reports this as `"rejected"`, and TC-014
checks for exactly that. `disarm()` does not retry: waiting does not make
an in-flight disarm possible.

### 3.4 Automatic disarm

The vehicle disarms itself in two situations: after a touchdown in LAND or
RTL, and when it is armed on the ground without taking off (after
`DISARM_DELAY` = 10 s). `land()` and `rtl()` therefore wait for touchdown
and then for the automatic disarm, instead of sending a disarm command.
TC-013 checks the on-ground delay; tests that arm on the ground must take
off within those 10 s.

### 3.5 AUTO on the ground needs `MAV_CMD_MISSION_START`

Switching to AUTO on the ground does not start the mission. The vehicle
takes off only after `MAV_CMD_MISSION_START`. `start_mission()` sends it
and checks its COMMAND_ACK.

### 3.6 Mission numbering and clearing

- seq 0 of an uploaded mission is home. `upload_mission()` sends the
  current position as seq 0, so the test's items are seq 1…n, and a
  downloaded mission has one item more than was uploaded.
- After `MISSION_CLEAR_ALL` the vehicle reports 0 items (not even home).
- After the last waypoint the copter hovers, it does not land. The
  `vehicle_on_ground` teardown lands it.
- `MISSION_CLEAR_ALL` is rejected while a mission is running. The
  `clean_mission` fixture must therefore be torn down *after* the vehicle
  has landed: it is listed before `vehicle_on_ground` in the test arguments,
  and pytest tears fixtures down in reverse order.

### 3.7 Ground-station HEARTBEATs

MAVProxy sends its own HEARTBEAT (`MAV_TYPE_GCS`) on the same link.
`wait_vehicle_heartbeat()` and the arm/disarm loop skip it; otherwise the
mode and armed state would sometimes be read from the ground station.

### 3.8 Geofence overshoot

After a circular fence breach the vehicle needs distance to brake before
RTL turns it around. At the default GUIDED speed, about 22 m beyond the
60 m radius was measured. The test allows 30 m (`GEOFENCE_OVERSHOOT_M`).
The first attempt allowed 15 m and failed: braking distance grows with
the square of speed, so a tight margin would make the test fail for
physical, not functional, reasons.

### 3.9 Battery failsafe stays latched

Once the battery failsafe has triggered, restoring `SIM_BATT_VOLTAGE` does
not clear it; every later arm attempt fails with `Arm: Battery failsafe`
until SITL restarts. The battery test is marked `last`, and
`pytest_collection_modifyitems` moves it to the end of the run. The
simulator must be restarted before every full run.

### 3.10 Low and critical battery in one flight

TC-052 and TC-053 are one test. The vehicle first flies 50 m away, so
the low-battery RTL is still in the air when the voltage drops to the
critical level; then the switch from RTL to LAND can be observed, as it
would happen in a real flight. Two separate tests would need two
simulator restarts because of the latch (3.9).

### 3.11 GPS loss: RTL or LAND

With `FS_DR_ENABLE` = 2 the vehicle starts RTL on dead reckoning after the
GPS is lost; when dead reckoning can no longer be trusted, the EKF
failsafe (`FS_EKF_ACTION` = 1) switches to LAND. Which mode the test sees
first depends on timing, so TC-050 accepts either and checks the outcome
that matters: the vehicle lands and disarms. GPS is restored inside the
test, because the next test needs a position to enter GUIDED.

### 3.12 pytest-timeout on Windows

On Windows, pytest-timeout uses its thread method, and a timeout ends
the *whole* run, not only the test. That is why every helper has its own,
shorter timeout that raises a normal test failure, and pytest-timeout
(120 s default, 300 s for long flights) is only a last-resort guard.

### 3.13 pymavlink `recv_match` arguments

The first positional parameter of `recv_match()` is `condition`, not the
message type. `recv_match("HEARTBEAT")` silently does the wrong thing;
the code always uses `type=...`.

## 4. Reporting

- Allure labels every test from its docstrings (section 1.7) and groups
  tests as *SITL tests* / *Unit tests* → feature (module).
- The title is set in the `pytest_runtest_call` hook: a title set in a
  fixture is overwritten by allure-pytest.
- When a SITL test fails, `pytest_runtest_makereport` attaches:
  - **STATUSTEXT during the test**: every status text since the test
    started, with time offset and severity;
  - **Vehicle state at failure**: mode, armed state, altitude, position,
    battery and GPS, read before teardown lands the vehicle. A value that
    cannot be read is reported as unavailable instead of raising, so the
    report never hides the original failure.
- A reference report of a full run is kept in [`results/`](results/README.md).
  CI publishes the report of every run on `main` to GitHub Pages.

## 5. Continuous integration

`.github/workflows/sitl-tests.yml` (at the repository root) has three jobs:

1. **lint-and-unit**: ruff and the unit tests; fast, no simulator.
2. **sitl-tests**: builds ArduCopter SITL (cached by ArduPilot commit),
   starts it in the background and runs `pytest -m sitl` against
   `tcp:127.0.0.1:5760`. SITL runs in the same job as the tests because
   each job is a separate virtual machine.
3. **report**: merges the Allure results of both jobs, generates the
   report and deploys it to GitHub Pages, also when tests failed.

In CI the tests connect to SITL directly, without MAVProxy. The code does
not change: only `SITL_CONNECTION` differs.
