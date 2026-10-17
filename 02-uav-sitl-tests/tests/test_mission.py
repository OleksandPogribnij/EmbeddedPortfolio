"""Waypoint missions: upload, download, clear, overwrite, execution (TC-040..TC-046)."""

import pytest
from pymavlink import mavutil

from utils.commands import arm, get_mode, set_mode
from utils.constants import (
    HOVER_GROUND_SPEED_MAX_MPS,
    MISSION_ALT_TOLERANCE_M,
    MOVING_SPEED_MIN_MPS,
    POSITION_TOLERANCE_M,
    STOP_TIMEOUT_S,
    TAKEOFF_ALT_M,
    WAYPOINT_OFFSET_M,
)
from utils.geo import distance_m, offset_position
from utils.mission import (
    MissionItem,
    clear_mission,
    download_mission,
    make_takeoff_item,
    make_waypoint,
    record_mission_progress,
    start_mission,
    upload_mission,
    wait_mission_item_reached,
)
from utils.telemetry import (
    get_position,
    get_relative_altitude,
    wait_ground_speed_above,
    wait_ground_speed_below,
)

pytestmark = pytest.mark.sitl

FIRST_WAYPOINT_SEQ = 2  # seq 0 is home, seq 1 is the take-off item


def _square_mission(
        home_position: tuple[float, float],
) -> tuple[list[MissionItem], list[tuple[float, float]]]:
    """Take-off plus a square of WAYPOINT_OFFSET_M sides that starts and ends over home.

    Returns:
        Tuple (mission items, waypoint coordinates).
    """
    side = WAYPOINT_OFFSET_M
    # Square corners relative to home (north_m, east_m); the last one closes the square.
    corners = [(side, 0), (side, side), (0, side), (0, 0)]
    waypoints = [offset_position(*home_position, north, east) for north, east in corners]
    items = [make_takeoff_item(TAKEOFF_ALT_M)]
    items += [make_waypoint(*wp, TAKEOFF_ALT_M) for wp in waypoints]
    return items, waypoints


class TestMission:
    """Mission protocol and AUTO-mode flight."""

    def test_mission_roundtrip(self, clean_mission, home_position):
        """TC-043: uploaded mission is downloaded back unchanged."""
        waypoint = offset_position(*home_position, WAYPOINT_OFFSET_M, 0)
        items = [make_takeoff_item(20), make_waypoint(*waypoint, 20)]
        upload_mission(clean_mission, items)
        got = download_mission(clean_mission)

        assert len(got) == len(items) + 1, (
            f"Mission size (home + items): expected {len(items) + 1}, got {len(got)}"
        )
        assert got[1]["command"] == mavutil.mavlink.MAV_CMD_NAV_TAKEOFF, (
            f"Item 1 command: expected MAV_CMD_NAV_TAKEOFF, got {got[1]['command']}"
        )
        assert got[2]["lat"] == pytest.approx(items[1]["lat"], abs=1e-6), (
            f"Item 2 latitude: expected {items[1]['lat']}, got {got[2]['lat']}"
        )

    def test_mission_clear(self, clean_mission, home_position):
        """TC-044: no mission items remain on the vehicle after clearing."""
        waypoint = offset_position(*home_position, WAYPOINT_OFFSET_M, 0)
        items = [make_takeoff_item(20), make_waypoint(*waypoint, 20)]
        upload_mission(clean_mission, items)
        clear_mission(clean_mission)
        got = download_mission(clean_mission)

        assert len(got) == 0, f"Mission size after clear: expected 0, got {len(got)}"

    @pytest.mark.timeout(300)
    @pytest.mark.flight
    def test_mission_execute(self, clean_mission, vehicle_on_ground, home_position):
        """TC-040: vehicle flies the mission to the last waypoint."""
        items, waypoints = _square_mission(home_position)

        upload_mission(vehicle_on_ground, items)
        arm(vehicle_on_ground)
        start_mission(vehicle_on_ground)
        # seq 0 is home, so the uploaded items have seq 1..len(items).
        for seq in range(1, len(items) + 1):
            wait_mission_item_reached(vehicle_on_ground, seq)

        alt = get_relative_altitude(vehicle_on_ground)
        assert alt == pytest.approx(TAKEOFF_ALT_M, abs=MISSION_ALT_TOLERANCE_M), (
            f"Altitude at last waypoint: expected {TAKEOFF_ALT_M} +/- "
            f"{MISSION_ALT_TOLERANCE_M} m, got {alt:.2f} m"
        )

        lat, lon = get_position(vehicle_on_ground)
        miss = distance_m(*waypoints[-1], lat, lon)
        assert miss < POSITION_TOLERANCE_M, (
            f"Distance to last waypoint: expected < {POSITION_TOLERANCE_M} m, got {miss:.2f} m"
        )

    @pytest.mark.timeout(300)
    @pytest.mark.flight
    def test_mission_progress(self, clean_mission, vehicle_on_ground, home_position):
        """TC-041: current mission item never goes back and reaches the last item."""
        items, _ = _square_mission(home_position)
        upload_mission(vehicle_on_ground, items)
        arm(vehicle_on_ground)
        start_mission(vehicle_on_ground)

        progress = record_mission_progress(vehicle_on_ground, last_seq=len(items))

        assert progress == sorted(progress), (
            f"Current mission item: expected a non-decreasing sequence, got {progress}"
        )
        assert progress[-1] == len(items), (
            f"Last current mission item: expected {len(items)}, got {progress[-1]}"
        )

    @pytest.mark.timeout(300)
    @pytest.mark.flight
    def test_mission_interrupted_by_loiter(self, clean_mission, vehicle_on_ground,
                                           home_position):
        """TC-042: switching to LOITER during a mission stops the vehicle."""
        items, _ = _square_mission(home_position)
        upload_mission(vehicle_on_ground, items)
        arm(vehicle_on_ground)
        start_mission(vehicle_on_ground)

        # Interrupt between the first and the second corner, while the vehicle is moving.
        wait_mission_item_reached(vehicle_on_ground, FIRST_WAYPOINT_SEQ)
        wait_ground_speed_above(vehicle_on_ground, MOVING_SPEED_MIN_MPS, timeout=STOP_TIMEOUT_S)

        set_mode(vehicle_on_ground, "LOITER")
        speed = wait_ground_speed_below(
            vehicle_on_ground, HOVER_GROUND_SPEED_MAX_MPS, timeout=STOP_TIMEOUT_S
        )

        mode = get_mode(vehicle_on_ground)
        assert mode == "LOITER", f"Mode after interrupting the mission: expected LOITER, got {mode}"
        assert speed < HOVER_GROUND_SPEED_MAX_MPS, (
            f"Ground speed in LOITER: expected < {HOVER_GROUND_SPEED_MAX_MPS} m/s, "
            f"got {speed:.2f} m/s"
        )

    def test_mission_unsupported_frame_rejected(self, clean_mission, home_position):
        """TC-045: vehicle rejects a mission item with an unknown frame."""
        bad = make_waypoint(*offset_position(*home_position, WAYPOINT_OFFSET_M, 0), 20)
        bad["frame"] = 99
        with pytest.raises(RuntimeError, match="UNSUPPORTED_FRAME"):
            upload_mission(clean_mission, [bad])

    def test_mission_overwrite(self, clean_mission, home_position):
        """TC-046: a new mission fully replaces the previous one."""
        north = offset_position(*home_position, WAYPOINT_OFFSET_M, 0)
        east = offset_position(*home_position, 0, WAYPOINT_OFFSET_M)
        first = [make_takeoff_item(TAKEOFF_ALT_M), make_waypoint(*north, TAKEOFF_ALT_M)]
        second = [make_waypoint(*east, 15)]  # different altitude on purpose

        upload_mission(clean_mission, first)
        upload_mission(clean_mission, second)
        got = download_mission(clean_mission)

        assert len(got) == 2, f"Mission size (home + 1 item): expected 2, got {len(got)}"
        assert got[1]["command"] == mavutil.mavlink.MAV_CMD_NAV_WAYPOINT, (
            f"Item 1 command: expected MAV_CMD_NAV_WAYPOINT, got {got[1]['command']}"
        )
        assert got[1]["alt"] == pytest.approx(15), (
            f"Item 1 altitude: expected 15 m (second mission), got {got[1]['alt']} m"
        )
        assert got[1]["lon"] == pytest.approx(second[0]["lon"], abs=1e-6), (
            f"Item 1 longitude: expected {second[0]['lon']}, got {got[1]['lon']}"
        )
