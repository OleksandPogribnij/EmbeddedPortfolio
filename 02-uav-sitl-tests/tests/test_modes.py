"""Flight modes: changes on the ground and in flight, return to launch (TC-030..TC-032)."""

import pytest

from utils.commands import get_mode, goto, is_armed, rtl, set_mode
from utils.constants import GOTO_DISTANCE_M, POSITION_TOLERANCE_M, TAKEOFF_ALT_M
from utils.geo import distance_m, offset_position
from utils.telemetry import get_position

pytestmark = pytest.mark.sitl


class TestModes:
    """Mode changes are accepted and RTL brings the vehicle home."""

    @pytest.mark.parametrize("mode", ["STABILIZE", "ALT_HOLD", "LOITER", "GUIDED"])
    def test_set_mode(self, vehicle_on_ground, mode):
        """TC-032: vehicle on the ground accepts each flight mode."""
        set_mode(vehicle_on_ground, mode)

        current = get_mode(vehicle_on_ground)
        assert current == mode, f"Mode after set_mode(): expected {mode}, got {current}"

    @pytest.mark.flight
    @pytest.mark.timeout(180)
    def test_rtl_returns_home(self, in_flight, home_position):
        """TC-031: RTL brings the vehicle back to home, where it lands and disarms."""
        target = offset_position(*home_position, GOTO_DISTANCE_M, 0)
        goto(in_flight, *target, alt=TAKEOFF_ALT_M)
        rtl(in_flight)

        lat, lon = get_position(in_flight)
        miss = distance_m(*home_position, lat, lon)
        assert miss < POSITION_TOLERANCE_M, (
            f"Distance from home after RTL: expected < {POSITION_TOLERANCE_M} m, got {miss:.2f} m"
        )
        armed = is_armed(in_flight)
        assert not armed, f"Armed state after RTL: expected False, got {armed}"

    @pytest.mark.parametrize("mode", ["LOITER", "ALT_HOLD", "GUIDED"])
    @pytest.mark.flight
    def test_mode_change_in_flight(self, in_flight, mode):
        """TC-030: vehicle accepts the mode change in flight and stays armed."""
        set_mode(in_flight, mode)

        current = get_mode(in_flight)
        assert current == mode, f"Mode in flight: expected {mode}, got {current}"
        armed = is_armed(in_flight)
        assert armed, f"Armed state after switching to {mode}: expected True, got {armed}"
