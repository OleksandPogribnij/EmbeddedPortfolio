"""Telemetry values: GPS, battery, ground speed (TC-080..TC-084)."""

import time

import pytest
from pymavlink import mavutil

from utils.commands import goto
from utils.constants import (
    BATTERY_OBSERVE_S,
    GOTO_AVG_SPEED_MIN_MPS,
    GOTO_DISTANCE_M,
    HOVER_GROUND_SPEED_MAX_MPS,
    HOVER_SETTLE_S,
    SATELLITES_MIN,
    TAKEOFF_ALT_M,
)
from utils.geo import offset_position
from utils.telemetry import get_battery, get_gps_status, get_ground_speed

pytestmark = pytest.mark.sitl


class TestTelemetry:
    """Reported telemetry is present and physically plausible."""

    def test_gps_3d_fix(self, vehicle_on_ground):
        """TC-080: vehicle on the ground has a 3D GPS fix and at least SATELLITES_MIN satellites."""
        fix_type, satellites = get_gps_status(vehicle_on_ground)
        assert fix_type >= mavutil.mavlink.GPS_FIX_TYPE_3D_FIX, (
            f"GPS fix type: expected >= {mavutil.mavlink.GPS_FIX_TYPE_3D_FIX} (3D), got {fix_type}"
        )
        assert satellites >= SATELLITES_MIN, (
            f"Visible satellites: expected >= {SATELLITES_MIN}, got {satellites}"
        )

    def test_battery_reported(self, vehicle_on_ground):
        """TC-081: battery voltage and remaining charge are reported with valid values."""
        voltage, remaining = get_battery(vehicle_on_ground)
        assert voltage > 0, f"Battery voltage: expected > 0 V, got {voltage} V"
        assert 0 <= remaining <= 100, f"Battery remaining: expected 0..100 %, got {remaining} %"

    @pytest.mark.flight
    def test_battery_does_not_increase_in_flight(self, in_flight):
        """TC-082: battery voltage does not rise in flight."""
        before, _ = get_battery(in_flight)
        time.sleep(BATTERY_OBSERVE_S)
        after, _ = get_battery(in_flight)

        assert after <= before, (
            f"Battery voltage after {BATTERY_OBSERVE_S} s of hover: "
            f"expected <= {before} V, got {after} V"
        )

    @pytest.mark.flight
    def test_hover_ground_speed_near_zero(self, in_flight):
        """TC-083: ground speed in hover stays below HOVER_GROUND_SPEED_MAX_MPS."""
        time.sleep(HOVER_SETTLE_S)
        speed = get_ground_speed(in_flight)
        assert speed < HOVER_GROUND_SPEED_MAX_MPS, (
            f"Ground speed in hover: expected < {HOVER_GROUND_SPEED_MAX_MPS} m/s, "
            f"got {speed:.2f} m/s"
        )

    @pytest.mark.flight
    def test_goto_average_speed(self, in_flight, home_position):
        """TC-084: average GUIDED flight speed is at least GOTO_AVG_SPEED_MIN_MPS."""
        lat, lon = offset_position(*home_position, GOTO_DISTANCE_M, 0)
        t0 = time.monotonic()
        goto(in_flight, lat, lon, TAKEOFF_ALT_M)
        elapsed = time.monotonic() - t0

        avg_speed = GOTO_DISTANCE_M / elapsed
        assert avg_speed > GOTO_AVG_SPEED_MIN_MPS, (
            f"Average speed over {GOTO_DISTANCE_M} m: expected > {GOTO_AVG_SPEED_MIN_MPS} m/s, "
            f"got {avg_speed:.2f} m/s ({elapsed:.1f} s)"
        )
