"""Vehicle commands over MAVLink: arming, flight modes, take-off, landing, parameters, goto."""

import math
import time

from pymavlink import mavutil

from utils.connection import drain, wait_vehicle_heartbeat
from utils.constants import (
    ALT_TOLERANCE_M,
    DISARM_AFTER_LANDING_TIMEOUT_S,
    GOTO_TIMEOUT_S,
    LAND_DESCENT_TIMEOUT_S,
    LAND_DETECT_ALT_M,
    POLL_INTERVAL_S,
    RTL_TIMEOUT_S,
    TAKEOFF_TIMEOUT_S,
    WAYPOINT_REACHED_M,
)
from utils.geo import distance_m
from utils.telemetry import get_position, get_relative_altitude

# SET_POSITION_TARGET_GLOBAL_INT type_mask: use the position fields only,
# ignore velocity, acceleration, yaw and yaw rate.
POSITION_ONLY_TYPE_MASK = 3576
# Parameters travel as float32, so a read-back value may differ in the last digits.
PARAM_ABS_TOLERANCE = 1e-4
NO_RESPONSE = "no response"


def is_armed(master: mavutil.mavfile, timeout: float = 5) -> bool:
    """Return True if the next vehicle HEARTBEAT reports the armed state."""
    heartbeat = wait_vehicle_heartbeat(master, timeout=timeout)
    return (heartbeat.base_mode & mavutil.mavlink.MAV_MODE_FLAG_SAFETY_ARMED) != 0


def get_mode(master: mavutil.mavfile, timeout: float = 10) -> str:
    """Return the current flight mode name from the next vehicle HEARTBEAT."""
    heartbeat = wait_vehicle_heartbeat(master, timeout=timeout)
    return mavutil.mode_string_v10(heartbeat)


def wait_for_any_mode(master: mavutil.mavfile, modes: set[str], timeout: float) -> str:
    """Wait until the vehicle reports one of the given flight modes.

    Used for mode changes made by the autopilot itself (failsafe RTL/LAND),
    where more than one reaction can be correct.

    Returns:
        The mode that was reported.

    Raises:
        ValueError: a mode name is unknown for this vehicle.
        TimeoutError: none of the modes was reported within timeout seconds;
            the message holds the last mode seen.
    """
    unknown = modes - set(master.mode_mapping())
    if unknown:
        raise ValueError(f"Invalid mode(s) {sorted(unknown)}")
    deadline = time.monotonic() + timeout
    cur_mode = None
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            break
        try:
            cur_mode = get_mode(master, timeout=remaining)
        except TimeoutError:
            break
        if cur_mode in modes:
            return cur_mode
    raise TimeoutError(
        f"Mode {sorted(modes)} not reached within {timeout} s, last seen: {cur_mode}"
    )


def wait_for_mode(master: mavutil.mavfile, mode: str, timeout: float = 30) -> None:
    """Wait until the vehicle reports the given flight mode.

    Raises:
        ValueError: the mode name is unknown for this vehicle.
        TimeoutError: the mode was not reported within timeout seconds.
    """
    wait_for_any_mode(master, {mode}, timeout)


def set_mode(master: mavutil.mavfile, mode: str, timeout: float = 10) -> None:
    """Request a flight mode and wait until the vehicle reports it."""
    if mode not in master.mode_mapping():
        raise ValueError(f"Invalid mode {mode}")
    master.set_mode(master.mode_mapping()[mode])
    wait_for_mode(master, mode, timeout)


def _send_arm_disarm(master: mavutil.mavfile, want_armed: bool,
                     timeout: float) -> tuple[bool, str | None]:
    """Send MAV_CMD_COMPONENT_ARM_DISARM and wait for the result.

    HEARTBEAT, STATUSTEXT and COMMAND_ACK are read in one loop, so the
    refusal reason sent by the autopilot is not lost.

    Returns:
        (success, reason): reason is None on success; otherwise the last
        STATUSTEXT, "rejected" (refusal without text) or NO_RESPONSE.
    """
    drain(master)
    master.mav.command_long_send(
        master.target_system,
        master.target_component,
        mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM,
        0,
        1 if want_armed else 0, 0, 0, 0, 0, 0, 0
    )

    last_text = None
    refused = False
    deadline = time.monotonic() + timeout

    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            break
        msg = master.recv_match(
            type=["HEARTBEAT", "STATUSTEXT", "COMMAND_ACK"],
            blocking=True,
            timeout=remaining,
        )
        if msg is None:
            continue

        kind = msg.get_type()

        if kind == "STATUSTEXT":
            last_text = msg.text

        elif kind == "HEARTBEAT":
            if msg.type == mavutil.mavlink.MAV_TYPE_GCS:
                continue
            armed = bool(msg.base_mode & mavutil.mavlink.MAV_MODE_FLAG_SAFETY_ARMED)
            if armed == want_armed:
                return True, None

        elif kind == "COMMAND_ACK":
            is_arm_ack = msg.command == mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM
            is_ok = msg.result in (mavutil.mavlink.MAV_RESULT_ACCEPTED,
                                   mavutil.mavlink.MAV_RESULT_IN_PROGRESS)
            if is_arm_ack and not is_ok:
                refused = True
                # Give the autopilot one more second to send the STATUSTEXT reason.
                deadline = min(deadline, time.monotonic() + 1)

    return False, last_text or ("rejected" if refused else NO_RESPONSE)


def try_arm(master: mavutil.mavfile, timeout: float = 10) -> tuple[bool, str | None]:
    """Send one ARM command. Returns (armed, reason)."""
    return _send_arm_disarm(master, want_armed=True, timeout=timeout)


def try_disarm(master: mavutil.mavfile, timeout: float = 10) -> tuple[bool, str | None]:
    """Send one DISARM command. Returns (disarmed, reason)."""
    return _send_arm_disarm(master, want_armed=False, timeout=timeout)


def arm(master: mavutil.mavfile, timeout: float = 120,
        attempt_timeout: float = 5, retry_interval: float = 1) -> None:
    """Arm the vehicle, retrying until pre-arm checks pass or the timeout expires.

    Raises:
        TimeoutError: the vehicle did not arm in time; the message holds
            the last refusal reason reported by the autopilot.
    """
    deadline = time.monotonic() + timeout
    last_reason = None
    attempts = 0

    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            break

        armed, reason = try_arm(master, timeout=min(attempt_timeout, remaining))
        attempts += 1
        if armed:
            return
        last_reason = reason

        remaining = deadline - time.monotonic()
        if remaining <= 0:
            break
        time.sleep(min(retry_interval, remaining))

    raise TimeoutError(
        f"Vehicle did not arm within {timeout} s after {attempts} attempt(s), "
        f"last reason: {last_reason}"
    )


def disarm(master: mavutil.mavfile, timeout: float = 10) -> None:
    """Disarm the vehicle. Does nothing if it is already disarmed.

    No retries: unlike arming, a refused disarm (e.g. in flight) does not
    become possible by waiting.

    Raises:
        RuntimeError: the autopilot refused to disarm; the message holds its reason.
        TimeoutError: no answer from the autopilot within timeout seconds.
    """
    if not is_armed(master):
        return
    disarmed, reason = try_disarm(master, timeout)
    if disarmed:
        return
    if reason == NO_RESPONSE:
        raise TimeoutError(f"No answer to DISARM within {timeout} s")
    raise RuntimeError(f"Vehicle refused to disarm: {reason}")


def takeoff(master: mavutil.mavfile, altitude: float,
            timeout: float = TAKEOFF_TIMEOUT_S,
            tolerance: float = ALT_TOLERANCE_M) -> None:
    """Take off in GUIDED mode and wait until altitude +/- tolerance is reached.

    Raises:
        RuntimeError: the vehicle is not armed or not in GUIDED mode.
        TimeoutError: the target altitude was not reached within timeout seconds.
    """
    if not is_armed(master):
        raise RuntimeError("Vehicle must be armed")

    cur_mode = get_mode(master)
    if cur_mode != "GUIDED":
        raise RuntimeError(f"Mode is {cur_mode}, expected GUIDED")

    master.mav.command_long_send(
        master.target_system,
        master.target_component,
        mavutil.mavlink.MAV_CMD_NAV_TAKEOFF,
        0,
        0,
        0, 0, 0, 0, 0, altitude
    )
    deadline = time.monotonic() + timeout
    relative_alt = None
    while time.monotonic() < deadline:
        relative_alt = get_relative_altitude(master, timeout=2)
        if abs(relative_alt - altitude) <= tolerance:
            return
    raise TimeoutError(
        f"Altitude {altitude} m not reached within {timeout} s, last: {relative_alt} m"
    )


def wait_altitude_below(master: mavutil.mavfile, alt_m: float, timeout: float) -> None:
    """Wait until the relative altitude drops to alt_m or lower.

    Raises:
        TimeoutError: the vehicle is still above alt_m after timeout seconds;
            the message holds the last measured altitude.
    """
    deadline = time.monotonic() + timeout
    cur_alt = None
    while time.monotonic() < deadline:
        cur_alt = get_relative_altitude(master, timeout=3)
        if cur_alt <= alt_m:
            return
    raise TimeoutError(
        f"Altitude did not drop to {alt_m} m within {timeout} s, last: {cur_alt} m"
    )


def wait_disarmed(master: mavutil.mavfile, timeout: float = 120) -> None:
    """Wait until the vehicle reports the disarmed state.

    Raises:
        TimeoutError: the vehicle is still armed after timeout seconds.
    """
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if not is_armed(master):
            return
        time.sleep(POLL_INTERVAL_S)
    raise TimeoutError(f"Vehicle still armed after {timeout} s")


def _descend_and_disarm(master: mavutil.mavfile, mode: str, alt_m: float,
                        descent_timeout: float, disarm_timeout: float) -> None:
    """Switch to a landing mode, wait for touchdown, then wait for auto-disarm.

    Does nothing if the vehicle is already disarmed.
    """
    if not is_armed(master):
        return
    set_mode(master, mode)
    wait_altitude_below(master, alt_m, descent_timeout)
    wait_disarmed(master, disarm_timeout)


def land(master: mavutil.mavfile, alt_m: float = LAND_DETECT_ALT_M,
         descent_timeout: float = LAND_DESCENT_TIMEOUT_S,
         disarm_timeout: float = DISARM_AFTER_LANDING_TIMEOUT_S) -> None:
    """Land at the current position and wait until the vehicle disarms."""
    _descend_and_disarm(master, "LAND", alt_m, descent_timeout, disarm_timeout)


def rtl(master: mavutil.mavfile, alt_m: float = LAND_DETECT_ALT_M,
        descent_timeout: float = RTL_TIMEOUT_S,
        disarm_timeout: float = DISARM_AFTER_LANDING_TIMEOUT_S) -> None:
    """Return to launch, land there and wait until the vehicle disarms."""
    _descend_and_disarm(master, "RTL", alt_m, descent_timeout, disarm_timeout)


def get_param(master: mavutil.mavfile, name: str, timeout: float = 5) -> float:
    """Read one autopilot parameter.

    Raises:
        TimeoutError: no PARAM_VALUE for name within timeout seconds
            (ArduPilot does not answer requests for unknown parameters).
    """
    drain(master)
    master.param_fetch_one(name)
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        remaining = deadline - time.monotonic()
        msg = master.recv_match(type="PARAM_VALUE", blocking=True, timeout=remaining)
        if msg is None:
            continue
        if msg.param_id == name:
            return msg.param_value
    raise TimeoutError(f"Timed out waiting for {name}")


def set_param(master: mavutil.mavfile, name: str, value: float, timeout: float = 5) -> float:
    """Write one autopilot parameter and wait for the vehicle to confirm it.

    Returns:
        The value confirmed by the vehicle.

    Raises:
        ValueError: the vehicle confirmed a different value.
        TimeoutError: no confirmation within timeout seconds.
    """
    drain(master)
    master.mav.param_set_send(
        master.target_system,
        master.target_component,
        name.encode(),
        value,
        mavutil.mavlink.MAV_PARAM_TYPE_REAL32
    )
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        remaining = deadline - time.monotonic()
        msg = master.recv_match(type="PARAM_VALUE", blocking=True, timeout=remaining)
        if msg is None:
            continue
        if msg.param_id != name:
            continue
        if not math.isclose(msg.param_value, value, abs_tol=PARAM_ABS_TOLERANCE):
            raise ValueError(
                f"Param {name}: requested {value}, vehicle returned {msg.param_value}"
            )
        return msg.param_value
    raise TimeoutError(f"Timed out waiting for confirmation of {name}")


def send_goto(master: mavutil.mavfile, lat: float, lon: float, alt: float) -> None:
    """Send a GUIDED position target without waiting for the vehicle to get there."""
    master.mav.set_position_target_global_int_send(
        0,
        master.target_system,
        master.target_component,
        mavutil.mavlink.MAV_FRAME_GLOBAL_RELATIVE_ALT_INT,
        POSITION_ONLY_TYPE_MASK,
        int(lat * 1e7),
        int(lon * 1e7),
        alt,
        0, 0, 0,
        0, 0, 0,
        0, 0
    )


def goto(master: mavutil.mavfile, lat: float, lon: float, alt: float,
         timeout: float = GOTO_TIMEOUT_S,
         tolerance: float = WAYPOINT_REACHED_M) -> None:
    """Fly to (lat, lon) at alt metres above home in GUIDED mode and wait until reached.

    Raises:
        RuntimeError: the vehicle is not armed or not in GUIDED mode.
        TimeoutError: the target was not reached within timeout seconds.
    """
    if not is_armed(master):
        raise RuntimeError("Vehicle must be armed")
    cur_mode = get_mode(master)
    if cur_mode != "GUIDED":
        raise RuntimeError(f"Mode is {cur_mode}, expected GUIDED")

    send_goto(master, lat, lon, alt)

    deadline = time.monotonic() + timeout
    remaining_m = None
    while time.monotonic() < deadline:
        cur_lat, cur_lon = get_position(master)
        remaining_m = distance_m(cur_lat, cur_lon, lat, lon)
        if remaining_m < tolerance:
            return
    raise TimeoutError(
        f"Target not reached within {timeout} s, last distance: {remaining_m} m"
    )
