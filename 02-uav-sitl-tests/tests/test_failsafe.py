"""Failsafe reactions in flight: GPS, radio link, low/critical battery (TC-050..TC-053).

Faults are injected through SITL-only SIM_* parameters. The expected reactions
follow the failsafe configuration checked in TC-070 (sitl/params.py).
"""

import time

import pytest
from pymavlink import mavutil

from sitl.params import (
    BATT_ACTION_LAND,
    BATT_ACTION_RTL,
    GPS_DISABLED,
    GPS_ENABLED,
    GPS_LOSS_FAILSAFE_MODES,
    RC_FAIL_NO_PULSES,
    SIM_VOLT_BELOW_CRITICAL,
    SIM_VOLT_BELOW_LOW,
    TEST_BATT_CRT_VOLT,
)
from utils.commands import goto, is_armed, wait_disarmed, wait_for_any_mode, wait_for_mode
from utils.constants import (
    FAILSAFE_LANDING_TIMEOUT_S,
    FAILSAFE_REACTION_TIMEOUT_S,
    GOTO_DISTANCE_M,
    GPS_LOSS_TIMEOUT_S,
    LANDED_ALT_MAX_M,
    POLL_INTERVAL_S,
    POSITION_TOLERANCE_M,
    STATUS_TEXT_TIMEOUT_S,
    TAKEOFF_ALT_M,
)
from utils.geo import distance_m, offset_position
from utils.telemetry import get_gps_status, get_position, get_relative_altitude

pytestmark = [pytest.mark.sitl, pytest.mark.flight]


def _wait_gps_fix(vehicle, timeout: float) -> None:
    """Wait until the simulated GPS reports a 3D fix again."""
    deadline = time.monotonic() + timeout
    fix_type = None
    while time.monotonic() < deadline:
        fix_type, _ = get_gps_status(vehicle)
        if fix_type >= mavutil.mavlink.GPS_FIX_TYPE_3D_FIX:
            return
        time.sleep(POLL_INTERVAL_S)
    raise TimeoutError(f"GPS fix not restored within {timeout} s, last fix type: {fix_type}")


def _assert_landed_and_disarmed(vehicle, context: str) -> None:
    """Wait for the failsafe landing to finish and check the final state."""
    wait_disarmed(vehicle, FAILSAFE_LANDING_TIMEOUT_S)
    armed = is_armed(vehicle)
    assert not armed, f"Armed state after {context}: expected False, got {armed}"
    alt = get_relative_altitude(vehicle)
    assert alt < LANDED_ALT_MAX_M, (
        f"Altitude after {context}: expected < {LANDED_ALT_MAX_M} m, got {alt:.2f} m"
    )


class TestFailsafe:
    """The autopilot detects the fault, reports it and brings the vehicle down safely."""

    @pytest.mark.timeout(300)
    def test_gps_loss_in_flight(self, in_flight, param_changer, status_log):
        """TC-050: GPS loss in flight triggers a failsafe; the vehicle lands and disarms."""
        param_changer("SIM_GPS1_ENABLE", GPS_DISABLED)

        mode = wait_for_any_mode(in_flight, GPS_LOSS_FAILSAFE_MODES, FAILSAFE_REACTION_TIMEOUT_S)
        assert mode in GPS_LOSS_FAILSAFE_MODES, (
            f"Mode after GPS loss: expected one of {sorted(GPS_LOSS_FAILSAFE_MODES)}, got {mode}"
        )
        status_log.wait_for(r"(?i)failsafe|gps|ekf|dead reckon", STATUS_TEXT_TIMEOUT_S)

        _assert_landed_and_disarmed(in_flight, "GPS-loss failsafe")

        # Restore GPS inside the test: the next test needs a position fix to enter GUIDED.
        param_changer("SIM_GPS1_ENABLE", GPS_ENABLED)
        _wait_gps_fix(in_flight, GPS_LOSS_TIMEOUT_S)

    @pytest.mark.timeout(300)
    def test_radio_link_loss(self, in_flight, home_position, param_changer, status_log):
        """TC-051: radio link loss triggers RTL; the vehicle lands at home and disarms."""
        target = offset_position(*home_position, GOTO_DISTANCE_M, 0)
        goto(in_flight, *target, alt=TAKEOFF_ALT_M)

        param_changer("SIM_RC_FAIL", RC_FAIL_NO_PULSES)

        wait_for_mode(in_flight, "RTL", FAILSAFE_REACTION_TIMEOUT_S)
        status_log.wait_for(r"(?i)failsafe", STATUS_TEXT_TIMEOUT_S)

        _assert_landed_and_disarmed(in_flight, "radio failsafe RTL")
        lat, lon = get_position(in_flight)
        miss = distance_m(*home_position, lat, lon)
        assert miss < POSITION_TOLERANCE_M, (
            f"Distance from home after radio failsafe RTL: "
            f"expected < {POSITION_TOLERANCE_M} m, got {miss:.2f} m"
        )

    @pytest.mark.last
    @pytest.mark.timeout(300)
    def test_battery_failsafe_escalation(self, in_flight, home_position, param_changer,
                                         status_log):
        """TC-052, TC-053: low battery triggers RTL; critical battery then switches to LAND.

        One flight covers both levels, as in a real flight where the battery keeps
        draining. Marked 'last': a battery failsafe may stay latched until SITL restarts.
        """
        param_changer("BATT_FS_LOW_ACT", BATT_ACTION_RTL)
        param_changer("BATT_CRT_VOLT", TEST_BATT_CRT_VOLT)
        param_changer("BATT_FS_CRT_ACT", BATT_ACTION_LAND)

        # Fly away first, so the low-battery RTL is still in the air when the
        # critical level is reached.
        target = offset_position(*home_position, GOTO_DISTANCE_M, 0)
        goto(in_flight, *target, alt=TAKEOFF_ALT_M)

        param_changer("SIM_BATT_VOLTAGE", SIM_VOLT_BELOW_LOW)
        wait_for_mode(in_flight, "RTL", FAILSAFE_REACTION_TIMEOUT_S)
        status_log.wait_for(r"(?i)battery.*low|low.*battery", STATUS_TEXT_TIMEOUT_S)

        param_changer("SIM_BATT_VOLTAGE", SIM_VOLT_BELOW_CRITICAL)
        wait_for_mode(in_flight, "LAND", FAILSAFE_REACTION_TIMEOUT_S)
        status_log.wait_for(r"(?i)critical", STATUS_TEXT_TIMEOUT_S)

        _assert_landed_and_disarmed(in_flight, "critical-battery LAND")
