"""Simulator profile: expected parameter values and fault-injection settings.

Parameter names and the expected values below were confirmed with `param show`
in MAVProxy on the simulator used for this suite. Value meanings follow the
ArduCopter parameter documentation.
"""

# TC-070: safety-relevant configuration. The failsafe and geofence tests
# rely on these values, so a change here is caught before those tests run.
EXPECTED_SAFETY_PARAMS: dict[str, float] = {
    "DISARM_DELAY": 10,  # s; auto-disarm delay on the ground
    "ARMING_RUDDER": 2,
    "FS_OPTIONS": 16,
    "FS_THR_ENABLE": 1,  # radio failsafe: always RTL
    "FS_EKF_ACTION": 1,  # EKF failsafe: LAND
    "FS_DR_ENABLE": 2,  # dead-reckoning failsafe (GPS lost): RTL
    "FENCE_ACTION": 1,  # fence breach: RTL, or LAND if RTL is not possible
    "BATT_LOW_VOLT": 10.5,  # V; low-battery threshold
    "BATT_LOW_TIMER": 10,  # s below the threshold before the failsafe triggers
}

# Flight modes the configuration above can switch to after GPS loss
# (FS_DR_ENABLE first, FS_EKF_ACTION when dead reckoning runs out).
GPS_LOSS_FAILSAFE_MODES = {"RTL", "LAND"}

# Fault injection (SIM_* parameters exist only in SITL)
GPS_DISABLED = 0  # SIM_GPS1_ENABLE
GPS_ENABLED = 1
RC_FAIL_NO_PULSES = 1  # SIM_RC_FAIL

# Battery failsafe test settings (BATT_FS_*_ACT and BATT_CRT_VOLT are 0, i.e. off,
# by default; the test enables them only for its own duration).
BATT_ACTION_LAND = 1  # BATT_FS_*_ACT
BATT_ACTION_RTL = 2
TEST_BATT_CRT_VOLT = 9.5  # V; BATT_CRT_VOLT during the test
SIM_VOLT_BELOW_LOW = 10.2  # V; between BATT_LOW_VOLT and TEST_BATT_CRT_VOLT
SIM_VOLT_BELOW_CRITICAL = 9.0  # V; below TEST_BATT_CRT_VOLT

# Geofence test settings
FENCE_TYPE_CIRCLE = 2  # FENCE_TYPE bitmask: circle around home only
FENCE_ENABLED = 1  # FENCE_ENABLE
