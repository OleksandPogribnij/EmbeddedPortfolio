"""Take-off, altitude hold and landing in GUIDED mode (TC-020..TC-024)."""

import time

import pytest

from utils.commands import arm, is_armed, land, takeoff
from utils.constants import (
    ALT_HOLD_DURATION_S,
    ALT_TOLERANCE_M,
    LANDED_ALT_MAX_M,
    TAKEOFF_ALT_M,
)
from utils.telemetry import get_relative_altitude

pytestmark = pytest.mark.sitl


class TestTakeoffLanding:
    """Vertical flight: reaching, holding and leaving the target altitude."""

    @pytest.mark.timeout(90)
    @pytest.mark.flight
    def test_takeoff_reaches_target_altitude(self, vehicle_on_ground):
        """TC-020: vehicle takes off to TAKEOFF_ALT_M within ALT_TOLERANCE_M."""
        arm(vehicle_on_ground)
        takeoff(vehicle_on_ground, TAKEOFF_ALT_M, tolerance=ALT_TOLERANCE_M)

        alt = get_relative_altitude(vehicle_on_ground)
        assert alt == pytest.approx(TAKEOFF_ALT_M, abs=ALT_TOLERANCE_M), (
            f"Altitude after take-off: expected {TAKEOFF_ALT_M} +/- {ALT_TOLERANCE_M} m, "
            f"got {alt:.2f} m"
        )

    @pytest.mark.timeout(150)
    @pytest.mark.flight
    def test_landing(self, vehicle_on_ground):
        """TC-022: vehicle lands and disarms itself."""
        arm(vehicle_on_ground)
        takeoff(vehicle_on_ground, TAKEOFF_ALT_M, tolerance=ALT_TOLERANCE_M)
        alt = get_relative_altitude(vehicle_on_ground)
        assert alt == pytest.approx(TAKEOFF_ALT_M, abs=ALT_TOLERANCE_M), (
            f"Altitude before landing: expected {TAKEOFF_ALT_M} +/- {ALT_TOLERANCE_M} m, "
            f"got {alt:.2f} m"
        )

        land(vehicle_on_ground)

        armed = is_armed(vehicle_on_ground)
        assert not armed, f"Armed state after landing: expected False, got {armed}"
        alt = get_relative_altitude(vehicle_on_ground)
        assert alt < LANDED_ALT_MAX_M, (
            f"Altitude after landing: expected < {LANDED_ALT_MAX_M} m, got {alt:.2f} m"
        )

    @pytest.mark.timeout(90)
    @pytest.mark.flight
    def test_altitude_hold(self, vehicle_on_ground):
        """TC-021: vehicle holds the target altitude within ALT_TOLERANCE_M."""
        arm(vehicle_on_ground)
        takeoff(vehicle_on_ground, TAKEOFF_ALT_M, tolerance=ALT_TOLERANCE_M)

        start = time.monotonic()
        deadline = start + ALT_HOLD_DURATION_S
        while time.monotonic() < deadline:
            alt = get_relative_altitude(vehicle_on_ground)
            elapsed = time.monotonic() - start
            assert alt == pytest.approx(TAKEOFF_ALT_M, abs=ALT_TOLERANCE_M), (
                f"Altitude at {elapsed:.1f} s of hold: expected {TAKEOFF_ALT_M} +/- "
                f"{ALT_TOLERANCE_M} m, got {alt:.2f} m"
            )

    @pytest.mark.timeout(90)
    @pytest.mark.parametrize("target_alt", [5, 10, 20])
    @pytest.mark.flight
    def test_takeoff_to_various_altitudes(self, vehicle_on_ground, target_alt):
        """TC-023: take-off reaches each target altitude within ALT_TOLERANCE_M."""
        arm(vehicle_on_ground)
        takeoff(vehicle_on_ground, target_alt, tolerance=ALT_TOLERANCE_M)

        alt = get_relative_altitude(vehicle_on_ground)
        assert alt == pytest.approx(target_alt, abs=ALT_TOLERANCE_M), (
            f"Altitude after take-off: expected {target_alt} +/- {ALT_TOLERANCE_M} m, "
            f"got {alt:.2f} m"
        )

    def test_takeoff_without_arm_rejected(self, vehicle_on_ground):
        """TC-024: take-off command is rejected while disarmed; vehicle stays on the ground."""
        with pytest.raises(RuntimeError, match="must be armed"):
            takeoff(vehicle_on_ground, TAKEOFF_ALT_M, timeout=5)

        alt = get_relative_altitude(vehicle_on_ground)
        assert alt < LANDED_ALT_MAX_M, (
            f"Altitude after rejected take-off: expected < {LANDED_ALT_MAX_M} m, got {alt:.2f} m"
        )
