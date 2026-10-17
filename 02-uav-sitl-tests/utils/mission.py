"""Mission protocol helpers: build, upload, download, clear and run waypoint missions."""

import time

from pymavlink import mavutil

from utils.commands import set_mode
from utils.connection import drain
from utils.constants import MISSION_TIMEOUT_S
from utils.telemetry import get_position

MissionItem = dict[str, float]


def make_waypoint(lat: float, lon: float, alt: float, hold_s: float = 0) -> MissionItem:
    """NAV_WAYPOINT item at (lat, lon), alt metres above home, holding hold_s seconds."""
    return {
        "command": mavutil.mavlink.MAV_CMD_NAV_WAYPOINT,
        "frame": mavutil.mavlink.MAV_FRAME_GLOBAL_RELATIVE_ALT_INT,
        "lat": lat,
        "lon": lon,
        "alt": alt,
        "param1": hold_s,
        "param2": 0,
        "param3": 0,
        "param4": 0,
    }


def make_takeoff_item(alt: float) -> MissionItem:
    """NAV_TAKEOFF item to alt metres above home at the current position."""
    return {
        "command": mavutil.mavlink.MAV_CMD_NAV_TAKEOFF,
        "frame": mavutil.mavlink.MAV_FRAME_GLOBAL_RELATIVE_ALT_INT,
        "lat": 0,
        "lon": 0,
        "alt": alt,
        "param1": 0,
        "param2": 0,
        "param3": 0,
        "param4": 0,
    }


def upload_mission(master: mavutil.mavfile, items: list[MissionItem],
                   timeout: float = 10) -> None:
    """Upload a mission; the current position is sent as seq 0 (home).

    Raises:
        RuntimeError: the vehicle rejected the mission; the message holds
            the MAV_MISSION_RESULT name.
        TimeoutError: the upload did not finish within timeout seconds.
    """
    cur_lat, cur_lon = get_position(master)
    home = make_waypoint(cur_lat, cur_lon, 0)
    full = [home] + items

    drain(master)
    master.mav.mission_count_send(master.target_system, master.target_component, len(full))

    last_seq = None
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        msg = master.recv_match(
            type=["MISSION_REQUEST_INT", "MISSION_REQUEST", "MISSION_ACK"],
            blocking=True,
            timeout=deadline - time.monotonic(),
        )
        if msg is None:
            continue

        kind = msg.get_type()
        if kind in ("MISSION_REQUEST_INT", "MISSION_REQUEST"):
            last_seq = msg.seq
            item = full[msg.seq]
            master.mav.mission_item_int_send(
                master.target_system,
                master.target_component,
                msg.seq,
                item["frame"],
                item["command"],
                0,  # current
                1,  # autocontinue
                item["param1"], item["param2"], item["param3"], item["param4"],
                int(item["lat"] * 1e7),
                int(item["lon"] * 1e7),
                item["alt"],
            )
        elif kind == "MISSION_ACK":
            if msg.type == mavutil.mavlink.MAV_MISSION_ACCEPTED:
                return
            name = mavutil.mavlink.enums["MAV_MISSION_RESULT"][msg.type].name
            raise RuntimeError(f"Mission upload rejected: {name}")

    raise TimeoutError(f"Mission upload timed out, last requested seq={last_seq}")


def clear_mission(master: mavutil.mavfile, timeout: float = 10) -> None:
    """Delete the mission stored on the vehicle.

    Raises:
        RuntimeError: the vehicle rejected the request (e.g. a mission is running).
        TimeoutError: no MISSION_ACK within timeout seconds.
    """
    drain(master)
    master.mav.mission_clear_all_send(master.target_system, master.target_component)
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        remaining = deadline - time.monotonic()
        msg = master.recv_match(type="MISSION_ACK", blocking=True, timeout=remaining)
        if msg is None:
            continue
        if msg.type == mavutil.mavlink.MAV_MISSION_ACCEPTED:
            return
        name = mavutil.mavlink.enums["MAV_MISSION_RESULT"][msg.type].name
        raise RuntimeError(f"Mission clear rejected: {name}")
    raise TimeoutError("Mission clear timed out")


def download_mission(master: mavutil.mavfile, timeout: float = 10) -> list[MissionItem]:
    """Read the mission stored on the vehicle, including home at seq 0.

    Raises:
        TimeoutError: the download did not finish within timeout seconds.
    """
    drain(master)
    deadline = time.monotonic() + timeout

    master.mav.mission_request_list_send(master.target_system, master.target_component)
    count = None
    while count is None:
        if time.monotonic() >= deadline:
            raise TimeoutError("Mission download: no MISSION_COUNT received")
        msg = master.recv_match(type="MISSION_COUNT", blocking=True,
                                timeout=deadline - time.monotonic())
        if msg is not None:
            count = msg.count

    items = []
    for seq in range(count):
        master.mav.mission_request_int_send(master.target_system, master.target_component, seq)
        item = None
        while item is None:
            if time.monotonic() >= deadline:
                raise TimeoutError(f"Mission download: timeout on item seq={seq} of {count}")
            msg = master.recv_match(type="MISSION_ITEM_INT", blocking=True,
                                    timeout=deadline - time.monotonic())
            if msg is not None and msg.seq == seq:
                item = {
                    "command": msg.command,
                    "frame": msg.frame,
                    "lat": msg.x / 1e7,
                    "lon": msg.y / 1e7,
                    "alt": msg.z,
                    "param1": msg.param1,
                    "param2": msg.param2,
                    "param3": msg.param3,
                    "param4": msg.param4,
                }
        items.append(item)

    master.mav.mission_ack_send(master.target_system, master.target_component,
                                mavutil.mavlink.MAV_MISSION_ACCEPTED)
    return items


def start_mission(master: mavutil.mavfile, first_seq: int = 1, timeout: float = 10) -> None:
    """Switch to AUTO and start the uploaded mission from first_seq.

    In ArduCopter, AUTO mode on the ground does not take off by itself;
    MAV_CMD_MISSION_START is required.

    Raises:
        RuntimeError: the vehicle rejected MAV_CMD_MISSION_START.
        TimeoutError: no COMMAND_ACK for MAV_CMD_MISSION_START within timeout seconds.
    """
    master.mav.mission_set_current_send(master.target_system, master.target_component, first_seq)
    set_mode(master, "AUTO")
    master.mav.command_long_send(
        master.target_system, master.target_component,
        mavutil.mavlink.MAV_CMD_MISSION_START,
        0,  # confirmation
        0, 0, 0, 0, 0, 0, 0)  # param1..param7

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        remaining = deadline - time.monotonic()
        msg = master.recv_match(type="COMMAND_ACK", blocking=True, timeout=remaining)
        if msg is None or msg.command != mavutil.mavlink.MAV_CMD_MISSION_START:
            continue
        if msg.result == mavutil.mavlink.MAV_RESULT_ACCEPTED:
            return
        name = mavutil.mavlink.enums["MAV_RESULT"][msg.result].name
        raise RuntimeError(f"Mission start rejected: {name}")
    raise TimeoutError(f"No COMMAND_ACK for MAV_CMD_MISSION_START within {timeout} s")


def wait_mission_item_reached(master: mavutil.mavfile, seq: int, timeout: float = 60) -> None:
    """Wait for MISSION_ITEM_REACHED with the given seq.

    Raises:
        TimeoutError: item seq was not reached within timeout seconds;
            the message holds the last reached seq.
    """
    # No drain() here: it would discard the MISSION_ITEM_REACHED we are waiting for.
    deadline = time.monotonic() + timeout
    last_reached = None
    while time.monotonic() < deadline:
        msg = master.recv_match(type="MISSION_ITEM_REACHED", blocking=True,
                                timeout=deadline - time.monotonic())
        if msg is None:
            continue
        last_reached = msg.seq
        if msg.seq == seq:
            return
    raise TimeoutError(f"Mission item {seq} not reached in {timeout}s, last reached={last_reached}")


def record_mission_progress(master: mavutil.mavfile, last_seq: int,
                            timeout: float = MISSION_TIMEOUT_S) -> list[int]:
    """Record MISSION_CURRENT changes until the vehicle heads for last_seq.

    Returns:
        Distinct seq values in the order they were reported.

    Raises:
        TimeoutError: last_seq was not reported within timeout seconds;
            the message holds the sequence recorded so far.
    """
    # No drain() here: it would discard MISSION_CURRENT values we need to record.
    deadline = time.monotonic() + timeout
    progress: list[int] = []
    while time.monotonic() < deadline:
        msg = master.recv_match(type="MISSION_CURRENT", blocking=True,
                                timeout=deadline - time.monotonic())
        if msg is None:
            continue
        if not progress or progress[-1] != msg.seq:
            progress.append(msg.seq)
        if msg.seq == last_seq:
            return progress
    raise TimeoutError(f"Mission item {last_seq} not current within {timeout} s, seen: {progress}")
