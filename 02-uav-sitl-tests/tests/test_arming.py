"""Arming and disarming: commands, pre-arm refusal, auto-disarm (TC-010..TC-014)."""

import time

import pytest
from pymavlink import mavutil

from utils.commands import arm, disarm, get_param, is_armed, try_arm, wait_disarmed
from utils.constants import AUTO_DISARM_MARGIN_S, GPS_LOSS_TIMEOUT_S, POLL_INTERVAL_S
from utils.telemetry import get_gps_status

pytestmark = pytest.mark.sitl


class TestArming:
    """Who can change the ARMED state, and when."""

    def test_arm(self, vehicle_on_ground):
        """TC-010: vehicle arms in GUIDED mode on the ground."""
        arm(vehicle_on_ground)
        armed = is_armed(vehicle_on_ground)
        assert armed, f"Armed state after arm(): expected True, got {armed}"

    def test_disarm(self, vehicle_on_ground):
        """TC-011: armed vehicle on the ground disarms on command."""
        arm(vehicle_on_ground)
        armed = is_armed(vehicle_on_ground)
        assert armed, f"Armed state after arm(): expected True, got {armed}"

        disarm(vehicle_on_ground)
        armed = is_armed(vehicle_on_ground)
        assert not armed, f"Armed state after disarm(): expected False, got {armed}"

    def test_arm_refused_without_gps(self, vehicle_on_ground, param_changer):
        """TC-012: vehicle refuses to arm without a GPS 3D fix."""
        param_changer('SIM_GPS1_ENABLE', 0)
        deadline = time.monotonic() + GPS_LOSS_TIMEOUT_S
        while time.monotonic() < deadline:
            fix_type, _ = get_gps_status(vehicle_on_ground)
            if fix_type < mavutil.mavlink.GPS_FIX_TYPE_3D_FIX:
                break
            time.sleep(POLL_INTERVAL_S)
        else:
            raise TimeoutError(
                f"GPS fix did not drop within {GPS_LOSS_TIMEOUT_S} s after SIM_GPS1_ENABLE=0"
            )
        armed, reason = try_arm(vehicle_on_ground)

        assert armed is False, f"Arm without GPS fix: expected refusal, vehicle armed ({reason=})"
        assert reason is not None and "GPS" in reason, (
            f"Refusal reason: expected to mention GPS, got {reason!r}"
        )

    def test_auto_disarm_on_ground(self, vehicle_on_ground):
        """TC-013: armed vehicle on the ground disarms itself after DISARM_DELAY."""
        delay = get_param(vehicle_on_ground, "DISARM_DELAY")
        timeout = delay + AUTO_DISARM_MARGIN_S
        arm(vehicle_on_ground)
        wait_disarmed(vehicle_on_ground, timeout)
        armed = is_armed(vehicle_on_ground)
        assert not armed, f"Armed state {timeout} s after arm(): expected False, got {armed}"

    @pytest.mark.flight
    def test_disarm_in_flight_rejected(self, in_flight):
        """TC-014: vehicle refuses to disarm in flight and stays armed."""
        # ArduPilot refuses with COMMAND_ACK only, without a STATUSTEXT reason.
        with pytest.raises(RuntimeError, match="refused to disarm: rejected"):
            disarm(in_flight, timeout=3)

        armed = is_armed(in_flight)
        assert armed, f"Armed state after refused in-flight disarm: expected True, got {armed}"
