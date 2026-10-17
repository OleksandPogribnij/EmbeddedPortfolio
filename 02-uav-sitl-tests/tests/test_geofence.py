"""Geofence: a circular fence around home stops the vehicle and brings it back (TC-060)."""

import time

import pytest

from sitl.params import FENCE_ENABLED, FENCE_TYPE_CIRCLE
from utils.commands import send_goto, wait_disarmed, wait_for_mode
from utils.constants import (
    FAILSAFE_LANDING_TIMEOUT_S,
    FAILSAFE_REACTION_TIMEOUT_S,
    FENCE_OBSERVE_S,
    GEOFENCE_OVERSHOOT_M,
    GEOFENCE_RADIUS_M,
    STATUS_TEXT_TIMEOUT_S,
    TAKEOFF_ALT_M,
)
from utils.geo import distance_m, offset_position
from utils.telemetry import get_position

pytestmark = [pytest.mark.sitl, pytest.mark.flight]


def _max_distance_from_home(vehicle, home_position: tuple[float, float],
                            duration: float) -> float:
    """Largest distance from home seen during duration seconds."""
    deadline = time.monotonic() + duration
    max_distance = 0.0
    while time.monotonic() < deadline:
        lat, lon = get_position(vehicle)
        max_distance = max(max_distance, distance_m(*home_position, lat, lon))
    return max_distance


class TestGeofence:
    """The vehicle does not leave the fence and reacts to a breach as configured."""

    @pytest.mark.timeout(300)
    def test_geofence_breach(self, in_flight, home_position, param_changer, status_log):
        """TC-060: crossing the circular fence triggers RTL; the vehicle stays within the margin."""
        param_changer("FENCE_TYPE", FENCE_TYPE_CIRCLE)
        param_changer("FENCE_RADIUS", GEOFENCE_RADIUS_M)
        param_changer("FENCE_ENABLE", FENCE_ENABLED)

        # Target twice the radius away: the vehicle can only get there by crossing the fence.
        target = offset_position(*home_position, 2 * GEOFENCE_RADIUS_M, 0)
        send_goto(in_flight, *target, alt=TAKEOFF_ALT_M)

        wait_for_mode(in_flight, "RTL", FAILSAFE_REACTION_TIMEOUT_S)
        status_log.wait_for(r"(?i)fence", STATUS_TEXT_TIMEOUT_S)

        max_distance = _max_distance_from_home(in_flight, home_position, FENCE_OBSERVE_S)
        limit = GEOFENCE_RADIUS_M + GEOFENCE_OVERSHOOT_M
        assert max_distance <= limit, (
            f"Max distance from home after fence breach: expected <= {limit} m, "
            f"got {max_distance:.1f} m"
        )

        wait_disarmed(in_flight, FAILSAFE_LANDING_TIMEOUT_S)
