"""Test profile: flight parameters, pass/fail thresholds and timeouts (SI units)."""

# Flight profile
WAYPOINT_OFFSET_M = 30
GOTO_DISTANCE_M = 50
TAKEOFF_ALT_M = 10

# Pass/fail thresholds
HOVER_GROUND_SPEED_MAX_MPS = 0.5
MOVING_SPEED_MIN_MPS = 1  # the vehicle counts as moving above this ground speed
LAND_DETECT_ALT_M = 0.3
LANDED_ALT_MAX_M = 0.5
ALT_TOLERANCE_M = 1
MISSION_ALT_TOLERANCE_M = 2
GOTO_AVG_SPEED_MIN_MPS = 1
POSITION_TOLERANCE_M = 3
SATELLITES_MIN = 6

# Geofence test
GEOFENCE_RADIUS_M = 60
GEOFENCE_OVERSHOOT_M = 30  # braking after the breach; ~22 m measured in SITL at default speed

# Helper acceptance criteria
WAYPOINT_REACHED_M = 2  # goto() treats the target as reached within this distance

# Timeouts
TAKEOFF_TIMEOUT_S = 60
GOTO_TIMEOUT_S = 60
LAND_DESCENT_TIMEOUT_S = 60
RTL_TIMEOUT_S = 180
MISSION_TIMEOUT_S = 120
STOP_TIMEOUT_S = 15
FAILSAFE_REACTION_TIMEOUT_S = 30
FAILSAFE_LANDING_TIMEOUT_S = 120
STATUS_TEXT_TIMEOUT_S = 5
DISARM_AFTER_LANDING_TIMEOUT_S = 20
TELEMETRY_TIMEOUT_S = 10
GPS_LOSS_TIMEOUT_S = 30
AUTO_DISARM_MARGIN_S = 5
POLL_INTERVAL_S = 0.5
STATE_READ_TIMEOUT_S = 2  # per-value timeout when reading the vehicle state for a report

# Observation windows
ALT_HOLD_DURATION_S = 10
BATTERY_OBSERVE_S = 20
HOVER_SETTLE_S = 3
FENCE_OBSERVE_S = 10  # how long to track the distance from home after a fence breach
