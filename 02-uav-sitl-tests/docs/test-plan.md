# Test Plan: UAV SITL Test Suite

## 1. Introduction

### 1.1 Purpose

This document defines what is tested in the UAV SITL test suite, how each
test is set up and executed, what result is expected, and within which
tolerances a test passes. It was written before the tests and has been
updated to match the implemented suite: every test case below exists in
`tests/` and every number comes from `utils/constants.py` or `sitl/params.py`.

### 1.2 System under test

The system under test is the **ArduCopter** flight-controller software,
version **V4.8.0-dev**, running in the ArduPilot **SITL (software in the
loop)** simulator as a quadcopter in `+` frame. In SITL the real
flight-control code runs on a PC against a simulated multicopter, so no
hardware is needed and no real aircraft is at risk.

### 1.3 Test approach

- **Language and framework:** Python and **pytest**.
- **Vehicle control and telemetry:** **MAVLink** through the **pymavlink**
  library. The tests arm the vehicle, change flight modes, command take-off,
  upload missions, change parameters and read telemetry. They never touch
  the simulator internals; faults are injected only through the SITL-only
  `SIM_*` parameters, over MAVLink, the same way a ground station would.
- **Pass or fail:** every test asserts on telemetry (altitude, position,
  mode, armed state, status messages) within an explicit timeout. Fixed
  sleeps are used only as observation windows (for example "hover for 3 s,
  then measure"), never as a pass criterion on their own.
- **Connection:** the simulator and the test runner can run on different
  machines. The MAVLink endpoint is set in the `SITL_CONNECTION`
  environment variable (default `udp:0.0.0.0:14550`).
- **Reporting:** Allure. Each test is labelled in the report with its ID
  and title from this plan; a failed SITL test carries the STATUSTEXT
  messages received during the test and the vehicle state at failure.

### 1.4 Scope

In scope: connection, arming, take-off and landing, flight modes,
waypoint missions, failsafe behaviour (GPS, radio link, battery),
geofence, safety-relevant parameters, telemetry plausibility, and unit
tests of the test helpers themselves.

Out of scope: real hardware, flight-dynamics accuracy, and any
certification claim. The simulated physics are simplified, so the
tolerances in this plan are test criteria for the simulated model, not
flight-qualified values.

### 1.5 Document status

| Item | Value |
|---|---|
| Version | 1.0 |
| Date | 2026-10-17 |
| Status | Implemented. All 60 tests pass (52 SITL, 8 unit), see [`results/`](results/README.md). |
| Author | Oleksandr Pohribnyi |

## 2. Test environment

| Item | Value |
|---|---|
| Simulator | ArduCopter V4.8.0-dev SITL, quadcopter, `+` frame |
| Simulator host | Linux laptop (Fedora), ArduPilot built inside an Ubuntu 22.04 container (distrobox), started with `sim_vehicle.py` and MAVProxy |
| Test runner host | Windows PC, Python 3.14 |
| Python packages | pymavlink 2.4.50, pytest 9.1.1, pytest-timeout 2.4.0, allure-pytest 2.16.2 (`requirements.txt`) |
| Telemetry link | MAVLink over UDP, port 14550, forwarded by MAVProxy |
| Connection setting | Environment variable `SITL_CONNECTION` |
| CI | GitHub Actions, Ubuntu runner, SITL started directly (no MAVProxy), `SITL_CONNECTION=tcp:127.0.0.1:5760` |

Setup instructions: [`setup.md`](setup.md).

## 3. Conventions

### 3.1 Common preconditions (fixtures)

The preconditions below are provided by pytest fixtures in
`tests/conftest.py`. A test case that says "Common" uses `vehicle_on_ground`.

| Fixture | State before the test | Cleanup after the test |
|---|---|---|
| `vehicle` | One MAVLink connection for the whole session; telemetry streams requested at 4 Hz. The run stops with exit code 2 if no HEARTBEAT arrives within 20 s. | Connection closed after the last test. |
| `vehicle_on_ground` | Landed, disarmed, mode GUIDED. | Landed and disarmed, whatever state the test left. |
| `home_position` | Position read on the ground before take-off. | — |
| `in_flight` | Armed, hovering at 10 m (`TAKEOFF_ALT_M`) in GUIDED. | Landed and disarmed. |
| `clean_mission` | No mission on the vehicle. | Mission cleared (after landing). |
| `param_changer` | — | Every changed parameter is restored to its original value, also when the test fails. |
| `status_log` | STATUSTEXT recorder emptied; records every status text of the test. | — |

### 3.2 Pass/fail criteria and timeouts

All thresholds are named constants with their unit in the name
(`utils/constants.py`). The main ones:

| Constant | Value | Used for |
|---|---|---|
| `TAKEOFF_ALT_M` | 10 m | Default flight altitude |
| `ALT_TOLERANCE_M` | 1 m | Take-off and altitude hold |
| `MISSION_ALT_TOLERANCE_M` | 2 m | Altitude at the end of a mission |
| `POSITION_TOLERANCE_M` | 3 m | Final position: at home after RTL, at the last mission waypoint |
| `LANDED_ALT_MAX_M` | 0.5 m | "On the ground" |
| `HOVER_GROUND_SPEED_MAX_MPS` | 0.5 m/s | "Stopped" |
| `GEOFENCE_RADIUS_M` / `GEOFENCE_OVERSHOOT_M` | 60 m / 30 m | Geofence test |
| `FAILSAFE_REACTION_TIMEOUT_S` | 30 s | Time for a failsafe to change the mode |
| `FAILSAFE_LANDING_TIMEOUT_S` | 120 s | Time for a failsafe landing to end in disarm |
| `STATUS_TEXT_TIMEOUT_S` | 5 s | Time for the autopilot's status text after a reaction |

Every helper has its own timeout and raises an exception that names what
was expected and what was last seen. pytest-timeout (120 s by default,
up to 300 s for long flights) is only a safety net.

### 3.3 Fault injection

Faults are injected with SITL-only parameters. Names and values were
confirmed with `param show` on the simulator; they are kept in
`sitl/params.py`.

| Fault | Parameter | Value |
|---|---|---|
| GPS loss | `SIM_GPS1_ENABLE` | 0 (restored to 1) |
| Radio link loss | `SIM_RC_FAIL` | 1 (no pulses) |
| Low battery | `SIM_BATT_VOLTAGE` | 10.2 V (below `BATT_LOW_VOLT` = 10.5 V) |
| Critical battery | `SIM_BATT_VOLTAGE` | 9.0 V (below the test's `BATT_CRT_VOLT` = 9.5 V) |

### 3.4 Run order and simulator state

- Tests marked `last` run after all others (`pytest_collection_modifyitems`).
  TC-052/053 is marked `last` because a battery failsafe stays latched
  until the simulator restarts; any later test would fail to arm.
- The simulator must be **restarted before every full run**.
- Markers: `sitl` (needs the simulator), `flight` (the vehicle takes off,
  slow), `last`. Example: `pytest -m "sitl and not flight"` runs the fast
  SITL checks only.

### 3.5 Test IDs

`TC-xxx` are SITL test cases, `UT-xxx` are unit tests of the helpers. The
ID is the first word of the test's docstring; the Allure report reads it
from there, so the plan, the code and the report always use the same ID.
A parametrized test is one test case with several runs.

## 4. Test case summary

| ID | Test | Title | Priority | Runs | Status |
|---|---|---|---|---|---|
| TC-001 | `TestConnection::test_vehicle_sends_heartbeat` | Heartbeat | High | 1 | Passed |
| TC-002 | `TestConnection::test_telemetry_streams` | Telemetry streams | High | 3 | Passed |
| TC-003 | `TestConnection::test_initial_state_disarmed_on_ground` | Initial state | Medium | 1 | Passed |
| TC-010 | `TestArming::test_arm` | Arm in GUIDED | High | 1 | Passed |
| TC-011 | `TestArming::test_disarm` | Disarm on the ground | High | 1 | Passed |
| TC-012 | `TestArming::test_arm_refused_without_gps` | Arm refused without GPS (negative) | High | 1 | Passed |
| TC-013 | `TestArming::test_auto_disarm_on_ground` | Auto-disarm on the ground | Medium | 1 | Passed |
| TC-014 | `TestArming::test_disarm_in_flight_rejected` | Disarm refused in flight (negative) | High | 1 | Passed |
| TC-020 | `TestTakeoffLanding::test_takeoff_reaches_target_altitude` | Take-off | High | 1 | Passed |
| TC-021 | `TestTakeoffLanding::test_altitude_hold` | Altitude hold | Medium | 1 | Passed |
| TC-022 | `TestTakeoffLanding::test_landing` | Landing | High | 1 | Passed |
| TC-023 | `TestTakeoffLanding::test_takeoff_to_various_altitudes` | Take-off to several altitudes | Medium | 3 | Passed |
| TC-024 | `TestTakeoffLanding::test_takeoff_without_arm_rejected` | Take-off refused while disarmed (negative) | High | 1 | Passed |
| TC-030 | `TestModes::test_mode_change_in_flight` | Mode changes in flight | High | 3 | Passed |
| TC-031 | `TestModes::test_rtl_returns_home` | Return to launch | High | 1 | Passed |
| TC-032 | `TestModes::test_set_mode` | Mode changes on the ground | Medium | 4 | Passed |
| TC-040 | `TestMission::test_mission_execute` | Square mission | High | 1 | Passed |
| TC-041 | `TestMission::test_mission_progress` | Mission progress | Medium | 1 | Passed |
| TC-042 | `TestMission::test_mission_interrupted_by_loiter` | Mission interrupted by LOITER | Medium | 1 | Passed |
| TC-043 | `TestMission::test_mission_roundtrip` | Mission upload and download | High | 1 | Passed |
| TC-044 | `TestMission::test_mission_clear` | Mission clear | Medium | 1 | Passed |
| TC-045 | `TestMission::test_mission_unsupported_frame_rejected` | Invalid mission item rejected (negative) | Medium | 1 | Passed |
| TC-046 | `TestMission::test_mission_overwrite` | Mission overwrite | Medium | 1 | Passed |
| TC-050 | `TestFailsafe::test_gps_loss_in_flight` | GPS loss in flight | High | 1 | Passed |
| TC-051 | `TestFailsafe::test_radio_link_loss` | Radio link loss | High | 1 | Passed |
| TC-052, TC-053 | `TestFailsafe::test_battery_failsafe_escalation` | Low battery, then critical battery | High | 1 | Passed |
| TC-060 | `TestGeofence::test_geofence_breach` | Geofence breach | High | 1 | Passed |
| TC-070 | `TestParameters::test_safety_params` | Safety-relevant parameters | High | 9 | Passed |
| TC-071 | `TestParameters::test_param_write_read_back` | Parameter write and read-back | Low | 1 | Passed |
| TC-072 | `TestParameters::test_param_unknown_name` | Unknown parameter (negative) | Low | 1 | Passed |
| TC-080 | `TestTelemetry::test_gps_3d_fix` | GPS fix on the ground | Medium | 1 | Passed |
| TC-081 | `TestTelemetry::test_battery_reported` | Battery reported | Medium | 1 | Passed |
| TC-082 | `TestTelemetry::test_battery_does_not_increase_in_flight` | Battery voltage does not rise in flight | Low | 1 | Passed |
| TC-083 | `TestTelemetry::test_hover_ground_speed_near_zero` | Ground speed in hover | Medium | 1 | Passed |
| TC-084 | `TestTelemetry::test_goto_average_speed` | Average GUIDED flight speed | Low | 1 | Passed |
| UT-001…UT-008 | `test_geo.py`, `test_status_text.py` | Unit tests of the helpers, see section 6 | — | 8 | Passed |

Total: 35 SITL test cases in 52 runs, plus 8 unit tests.
Status as of the reference run on 2026-10-17.

## 5. SITL test cases

### Connection (`tests/test_connection.py`)

#### TC-001 Heartbeat

- Priority: High
- Goal: The simulator is reachable and identifies itself as a multicopter.
- Preconditions: Simulator running, `SITL_CONNECTION` set.
- Steps:
  1. Wait for a HEARTBEAT from the vehicle (ground-station HEARTBEATs are skipped).
- Expected result: The HEARTBEAT type is `MAV_TYPE_QUADROTOR`.
- Tolerance / timeout: 10 s.
- Status: Passed

#### TC-002 Telemetry streams

- Priority: High
- Goal: The telemetry needed by the other tests is streamed.
- Preconditions: Connection open, streams requested.
- Steps (one run per message type):
  1. Wait for `GLOBAL_POSITION_INT`, `ATTITUDE` or `SYS_STATUS`.
- Expected result: Each message type is received.
- Tolerance / timeout: 10 s per message type.
- Status: Passed

#### TC-003 Initial state

- Priority: Medium
- Goal: The vehicle starts disarmed on the ground.
- Preconditions: Connection open; no test has flown yet.
- Steps:
  1. Read a HEARTBEAT.
  2. Read the relative altitude from `GLOBAL_POSITION_INT`.
- Expected result: Disarmed; relative altitude below 0.5 m.
- Tolerance / timeout: 10 s per read.
- Status: Passed

### Arming (`tests/test_arming.py`)

#### TC-010 Arm in GUIDED

- Priority: High
- Goal: The vehicle can be armed in GUIDED mode.
- Preconditions: Common.
- Steps:
  1. Send the arm command, repeating it until pre-arm checks pass.
  2. Read the armed state from the HEARTBEAT.
- Expected result: The vehicle reports armed.
- Tolerance / timeout: 120 s (pre-arm checks need time after the simulator starts).
- Status: Passed

#### TC-011 Disarm on the ground

- Priority: High
- Goal: An armed vehicle on the ground disarms on command.
- Preconditions: Common; vehicle armed.
- Steps:
  1. Send the disarm command.
  2. Read the armed state.
- Expected result: The vehicle reports disarmed.
- Tolerance / timeout: 10 s.
- Status: Passed

#### TC-012 Arm refused without GPS (negative)

- Priority: High
- Goal: The vehicle refuses to arm without a position source and says why.
- Preconditions: Common.
- Steps:
  1. Set `SIM_GPS1_ENABLE` = 0.
  2. Wait until `GPS_RAW_INT` reports less than a 3D fix.
  3. Send one arm command and collect COMMAND_ACK and STATUSTEXT.
- Expected result: Arming is refused, and the refusal reason mentions GPS
  (observed: `Arm: GPS 1: Bad fix`). `SIM_GPS1_ENABLE` is restored after the test.
- Tolerance / timeout: 30 s for the fix to drop; 10 s for the arm answer.
- Status: Passed

#### TC-013 Auto-disarm on the ground

- Priority: Medium
- Goal: An armed vehicle that does not take off disarms itself.
- Preconditions: Common.
- Steps:
  1. Read `DISARM_DELAY` (10 s).
  2. Arm, do not take off.
  3. Wait for the disarmed state.
- Expected result: The vehicle disarms by itself.
- Tolerance / timeout: `DISARM_DELAY` + 5 s.
- Status: Passed

#### TC-014 Disarm refused in flight (negative)

- Priority: High
- Goal: A disarm command in flight is refused, so the motors keep running.
- Preconditions: `in_flight` (10 m, GUIDED).
- Steps:
  1. Send the disarm command.
  2. Read the armed state.
- Expected result: The command is rejected (COMMAND_ACK only; ArduPilot sends
  no STATUSTEXT for this refusal) and the vehicle stays armed.
- Tolerance / timeout: 3 s for the answer.
- Status: Passed

### Take-off and landing (`tests/test_takeoff_landing.py`)

#### TC-020 Take-off

- Priority: High
- Goal: The vehicle takes off and reaches the commanded altitude.
- Preconditions: Common.
- Steps:
  1. Arm, command take-off to 10 m.
  2. Wait for the relative altitude to reach the target.
- Expected result: Relative altitude is 10 m ± 1 m.
- Tolerance / timeout: ± 1 m, 60 s.
- Status: Passed

#### TC-021 Altitude hold

- Priority: Medium
- Goal: The vehicle holds the target altitude in GUIDED.
- Preconditions: Common; vehicle taken off to 10 m.
- Steps:
  1. Sample the relative altitude continuously for 10 s.
- Expected result: Every sample is within 10 m ± 1 m.
- Tolerance / timeout: ± 1 m for 10 s.
- Status: Passed

#### TC-022 Landing

- Priority: High
- Goal: The vehicle lands and disarms by itself.
- Preconditions: Common; vehicle taken off to 10 m.
- Steps:
  1. Switch to LAND.
  2. Wait until the relative altitude is below 0.3 m.
  3. Wait for the automatic disarm.
- Expected result: Disarmed; relative altitude below 0.5 m.
- Tolerance / timeout: 60 s descent, then 20 s to disarm.
- Status: Passed

#### TC-023 Take-off to several altitudes

- Priority: Medium
- Goal: Take-off works for different target altitudes.
- Preconditions: Common. Parametrized over 5 m, 10 m and 20 m.
- Steps:
  1. Arm, command take-off to the target altitude.
- Expected result: Relative altitude is target ± 1 m in each run.
- Tolerance / timeout: ± 1 m, 60 s per run.
- Status: Passed

#### TC-024 Take-off refused while disarmed (negative)

- Priority: High
- Goal: A take-off command is not executed while the vehicle is disarmed.
- Preconditions: Common; vehicle disarmed.
- Steps:
  1. Request take-off to 10 m.
  2. Read the relative altitude.
- Expected result: The take-off helper refuses with "must be armed" before
  sending the command; the vehicle stays below 0.5 m.
- Tolerance / timeout: immediate refusal; altitude below 0.5 m.
- Status: Passed

### Flight modes (`tests/test_modes.py`)

#### TC-030 Mode changes in flight

- Priority: High
- Goal: The vehicle accepts flight-mode changes in flight and stays armed.
- Preconditions: `in_flight`. Parametrized over LOITER, ALT_HOLD and GUIDED.
- Steps:
  1. Request the mode.
  2. Wait for a HEARTBEAT with that mode.
- Expected result: The reported mode equals the requested mode; the vehicle is still armed.
- Tolerance / timeout: 10 s per mode.
- Status: Passed

#### TC-031 Return to launch

- Priority: High
- Goal: RTL brings the vehicle back to the launch point and lands it.
- Preconditions: `in_flight`; home position read on the ground.
- Steps:
  1. Fly 50 m north in GUIDED.
  2. Switch to RTL.
  3. Wait for touchdown and disarm.
  4. Compare the final position with home.
- Expected result: Disarmed within 3 m of home.
- Tolerance / timeout: 3 m; 180 s for RTL.
- Status: Passed

#### TC-032 Mode changes on the ground

- Priority: Medium
- Goal: The vehicle on the ground accepts each basic flight mode.
- Preconditions: Common. Parametrized over STABILIZE, ALT_HOLD, LOITER and GUIDED.
- Steps:
  1. Request the mode and wait for a HEARTBEAT with it.
- Expected result: The reported mode equals the requested mode.
- Tolerance / timeout: 10 s per mode.
- Status: Passed

### Missions (`tests/test_mission.py`)

The flight tests use one mission: a NAV_TAKEOFF to 10 m and a square of
four waypoints with 30 m sides at 10 m that starts north of home and ends
over home. On the vehicle, seq 0 is home, seq 1 is the take-off, seq 2–5
are the waypoints. AUTO is started with `MAV_CMD_MISSION_START`, because
ArduCopter does not take off in AUTO by itself.

#### TC-040 Square mission

- Priority: High
- Goal: A waypoint mission is flown to completion.
- Preconditions: `clean_mission`, Common.
- Steps:
  1. Upload the mission.
  2. Arm, switch to AUTO, start the mission.
  3. Wait for `MISSION_ITEM_REACHED` for each item, seq 1 to 5.
  4. Read altitude and position.
- Expected result: All items are reached; the vehicle is within 3 m of the
  last waypoint at 10 m ± 2 m.
- Tolerance / timeout: 60 s per item; 300 s for the test.
- Status: Passed

#### TC-041 Mission progress

- Priority: Medium
- Goal: The mission sequence only moves forward and reaches the last item.
- Preconditions: As TC-040.
- Steps:
  1. Start the mission.
  2. Record every change of `MISSION_CURRENT` until it reports the last item.
- Expected result: The recorded sequence never decreases and ends at seq 5.
- Tolerance / timeout: 120 s.
- Status: Passed

#### TC-042 Mission interrupted by LOITER

- Priority: Medium
- Goal: A mode change stops the vehicle in the middle of a mission.
- Preconditions: As TC-040.
- Steps:
  1. Start the mission; wait until the first waypoint (seq 2) is reached.
  2. Wait until the ground speed is above 1 m/s (on the way to the next corner).
  3. Switch to LOITER.
  4. Wait for the ground speed to drop.
- Expected result: Mode is LOITER; ground speed below 0.5 m/s.
- Tolerance / timeout: 15 s to start moving, 15 s to stop.
- Status: Passed

#### TC-043 Mission upload and download

- Priority: High
- Goal: A mission is stored on the vehicle unchanged.
- Preconditions: `clean_mission`, Common.
- Steps:
  1. Upload a take-off item and one waypoint (20 m).
  2. Download the mission.
- Expected result: 3 items (home + 2); item 1 is `MAV_CMD_NAV_TAKEOFF`;
  the latitude of item 2 matches the uploaded one.
- Tolerance / timeout: 1e-6 deg; 10 s per transfer.
- Status: Passed

#### TC-044 Mission clear

- Priority: Medium
- Goal: Clearing removes the mission.
- Preconditions: `clean_mission`, Common.
- Steps:
  1. Upload a two-item mission.
  2. Clear it (`MISSION_CLEAR_ALL`).
  3. Download the mission.
- Expected result: 0 items (home is not reported after a clear).
- Tolerance / timeout: 10 s per transfer.
- Status: Passed

#### TC-045 Invalid mission item rejected (negative)

- Priority: Medium
- Goal: The vehicle rejects a mission item it cannot interpret.
- Preconditions: `clean_mission`, Common.
- Steps:
  1. Upload one waypoint with frame = 99.
- Expected result: The upload fails with `MAV_MISSION_UNSUPPORTED_FRAME`.
- Tolerance / timeout: 10 s.
- Status: Passed

#### TC-046 Mission overwrite

- Priority: Medium
- Goal: A new upload fully replaces the previous mission.
- Preconditions: `clean_mission`, Common.
- Steps:
  1. Upload a take-off and a waypoint 30 m north.
  2. Upload one waypoint 30 m east at 15 m.
  3. Download the mission.
- Expected result: 2 items (home + 1); item 1 is `MAV_CMD_NAV_WAYPOINT`
  at 15 m with the longitude of the second mission.
- Tolerance / timeout: 1e-6 deg; 10 s per transfer.
- Status: Passed

### Failsafe (`tests/test_failsafe.py`)

The expected reactions follow the failsafe configuration checked in TC-070.
Each test also waits for the autopilot's STATUSTEXT about the reaction; the
patterns are deliberately broad (case-insensitive keywords).

#### TC-050 GPS loss in flight

- Priority: High
- Goal: Loss of GPS in flight triggers a failsafe that brings the vehicle down.
- Preconditions: `in_flight`; `FS_DR_ENABLE` = 2 (RTL), `FS_EKF_ACTION` = 1 (LAND).
- Steps:
  1. Set `SIM_GPS1_ENABLE` = 0.
  2. Wait for the failsafe mode.
  3. Wait for a status text matching `failsafe|gps|ekf|dead reckon`.
  4. Wait for touchdown and disarm.
  5. Restore GPS and wait for a 3D fix (the next test needs a position).
- Expected result: Mode becomes RTL or LAND (which one depends on how long
  dead reckoning lasts); the vehicle lands and disarms below 0.5 m.
- Tolerance / timeout: 30 s to react, 5 s for the text, 120 s to disarm, 30 s for the fix.
- Status: Passed

#### TC-051 Radio link loss

- Priority: High
- Goal: Loss of the RC link triggers RTL, and the vehicle lands at home.
- Preconditions: `in_flight`; `FS_THR_ENABLE` = 1 (RTL).
- Steps:
  1. Fly 50 m north, so that RTL has to travel.
  2. Set `SIM_RC_FAIL` = 1 (no pulses).
  3. Wait for RTL and a status text matching `failsafe`.
  4. Wait for touchdown and disarm; compare position with home.
- Expected result: RTL; disarmed below 0.5 m, within 3 m of home.
- Tolerance / timeout: 30 s to react, 5 s for the text, 120 s to disarm.
- Status: Passed

#### TC-052, TC-053 Low battery, then critical battery

- Priority: High
- Goal: The battery failsafe escalates from RTL at low voltage to LAND at
  critical voltage, as in a real flight where the battery keeps draining.
  Both levels are checked in one flight.
- Preconditions: `in_flight`; `BATT_LOW_VOLT` = 10.5 V, `BATT_LOW_TIMER` = 10 s.
  For this test only: `BATT_FS_LOW_ACT` = 2 (RTL), `BATT_CRT_VOLT` = 9.5 V,
  `BATT_FS_CRT_ACT` = 1 (LAND); all restored afterwards. Marked `last`.
- Steps:
  1. Fly 50 m north, so that the RTL is still in the air when the critical level comes.
  2. TC-052: set `SIM_BATT_VOLTAGE` = 10.2 V; wait for RTL and a text matching `battery … low`.
  3. TC-053: set `SIM_BATT_VOLTAGE` = 9.0 V; wait for LAND and a text matching `critical`.
  4. Wait for touchdown and disarm.
- Expected result: RTL, then LAND; disarmed below 0.5 m.
- Tolerance / timeout: 30 s per reaction (includes the 10 s low-voltage timer),
  5 s per text, 120 s to disarm.
- Note: the failsafe stays latched until SITL restarts (`Arm: Battery failsafe`).
- Status: Passed

### Geofence (`tests/test_geofence.py`)

#### TC-060 Geofence breach

- Priority: High
- Goal: Crossing the fence triggers RTL and the vehicle does not go far beyond it.
- Preconditions: `in_flight`; `FENCE_ACTION` = 1 (RTL). For this test only:
  `FENCE_TYPE` = 2 (circle), `FENCE_RADIUS` = 60 m, `FENCE_ENABLE` = 1; all restored afterwards.
- Steps:
  1. Send a GUIDED target 120 m north (twice the radius), without waiting.
  2. Wait for RTL and a status text matching `fence`.
  3. Track the maximum distance from home for 10 s.
  4. Wait for the RTL to end in disarm.
- Expected result: RTL; maximum distance ≤ 90 m (radius + 30 m braking margin).
- Tolerance / timeout: 30 s to react, 5 s for the text, 120 s to disarm.
  The overshoot measured in SITL at default speed is about 22 m.
- Status: Passed

### Parameters (`tests/test_parameters.py`)

#### TC-070 Safety-relevant parameters

- Priority: High
- Goal: Detect changes to the configuration that the failsafe and geofence tests rely on.
- Preconditions: Connection open.
- Steps (one run per parameter):
  1. Read the parameter.
- Expected result: Each value equals the expected value in `sitl/params.py`:

  | Parameter | Expected | Meaning |
  |---|---|---|
  | `DISARM_DELAY` | 10 | Auto-disarm after 10 s on the ground |
  | `ARMING_RUDDER` | 2 | Arm/disarm with rudder allowed |
  | `FS_OPTIONS` | 16 | Failsafe options bitmask |
  | `FS_THR_ENABLE` | 1 | Radio failsafe: RTL |
  | `FS_EKF_ACTION` | 1 | EKF failsafe: LAND |
  | `FS_DR_ENABLE` | 2 | Dead-reckoning failsafe: RTL |
  | `FENCE_ACTION` | 1 | Fence breach: RTL (or LAND) |
  | `BATT_LOW_VOLT` | 10.5 | Low-battery threshold, V |
  | `BATT_LOW_TIMER` | 10 | Seconds below the threshold before the failsafe |

- Tolerance / timeout: equal within 1e-6 relative (pytest.approx); 5 s per parameter.
- Status: Passed

#### TC-071 Parameter write and read-back

- Priority: Low
- Goal: A written parameter value is stored and read back unchanged.
- Preconditions: Connection open.
- Steps:
  1. Write `DISARM_DELAY` = 5.
  2. Read it back.
- Expected result: 5. The original value is restored after the test.
- Tolerance / timeout: 5 s per operation.
- Status: Passed

#### TC-072 Unknown parameter (negative)

- Priority: Low
- Goal: A request for a parameter that does not exist gets no value.
- Preconditions: Connection open.
- Steps:
  1. Request `PARAM_UNKNOWN`.
- Expected result: No `PARAM_VALUE` arrives; the helper raises a timeout
  naming the parameter.
- Tolerance / timeout: 3 s.
- Status: Passed

### Telemetry (`tests/test_telemetry.py`)

#### TC-080 GPS fix on the ground

- Priority: Medium
- Goal: The vehicle has a usable GPS solution.
- Preconditions: Common.
- Steps:
  1. Read `GPS_RAW_INT`.
- Expected result: Fix type ≥ 3D; at least 6 satellites.
- Tolerance / timeout: 5 s.
- Status: Passed

#### TC-081 Battery reported

- Priority: Medium
- Goal: Battery telemetry is present and in range.
- Preconditions: Common.
- Steps:
  1. Read `SYS_STATUS`.
- Expected result: Voltage > 0 V; remaining charge 0–100 %.
- Tolerance / timeout: 5 s.
- Status: Passed

#### TC-082 Battery voltage does not rise in flight

- Priority: Low
- Goal: The battery model behaves plausibly under load.
- Preconditions: `in_flight`.
- Steps:
  1. Read the voltage, hover 20 s, read it again.
- Expected result: The second value is not higher than the first.
- Tolerance / timeout: 20 s observation.
- Status: Passed

#### TC-083 Ground speed in hover

- Priority: Medium
- Goal: The vehicle holds position in hover.
- Preconditions: `in_flight`.
- Steps:
  1. Wait 3 s for the hover to settle.
  2. Read the ground speed from `VFR_HUD`.
- Expected result: Below 0.5 m/s.
- Tolerance / timeout: 3 s settle, 5 s read.
- Status: Passed

#### TC-084 Average GUIDED flight speed

- Priority: Low
- Goal: The vehicle moves at a plausible speed in GUIDED.
- Preconditions: `in_flight`.
- Steps:
  1. Fly 50 m north and measure the time.
- Expected result: Average speed above 1 m/s.
- Tolerance / timeout: 60 s for the flight (target reached within 2 m).
- Status: Passed

## 6. Unit tests

Unit tests check the test helpers without a simulator. They run in CI on
every push.

| ID | Test | What is checked | Status |
|---|---|---|---|
| UT-001 | `TestGeo::test_same_point` | Distance between identical points is 0 m | Passed |
| UT-002 | `TestGeo::test_distance_along_latitude` | 0.001° of latitude ≈ 111 m (± 1 m) | Passed |
| UT-003 | `TestGeo::test_distance_along_longitude` | 0.001° of longitude at 49° N ≈ 73 m (± 1 m) | Passed |
| UT-004 | `TestStatusTextRecorder::test_records_only_status_text` | Only STATUSTEXT is recorded | Passed |
| UT-005 | `TestStatusTextRecorder::test_status_text_survives_drain` | A status text discarded by `drain()` is still recorded | Passed |
| UT-006 | `TestStatusTextRecorder::test_wait_for_reads_until_match` | `wait_for()` keeps reading until a matching text arrives | Passed |
| UT-007 | `TestStatusTextRecorder::test_wait_for_timeout_lists_recorded_texts` | The timeout error lists the texts seen | Passed |
| UT-008 | `TestStatusTextRecorder::test_clear_and_detach` | `clear()` forgets, `detach()` stops recording | Passed |

## 7. Known limitations

- The STATUSTEXT patterns in the failsafe and geofence tests are broad
  keywords; they confirm that the autopilot reported the reaction, not
  the exact wording.
- TC-050 accepts RTL or LAND. Which mode the vehicle enters depends on
  how long dead reckoning keeps a usable position.
- The battery failsafe cannot be reset without restarting SITL, so the
  suite needs a fresh simulator for every full run.
- Tolerances are tuned for the simulator at real-time speed (`--speedup 1`).
