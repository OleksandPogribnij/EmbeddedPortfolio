"""Telemetry readers: altitude, position, GPS, battery and ground speed."""

import time
from collections.abc import Callable

from pymavlink import mavutil

from utils.connection import drain


def get_relative_altitude(master: mavutil.mavfile, timeout: float = 5) -> float:
    """Altitude above home in metres, from GLOBAL_POSITION_INT."""
    alt_mm = _read_message(master, 'GLOBAL_POSITION_INT', timeout).relative_alt
    return alt_mm / 1000


def get_position(master: mavutil.mavfile, timeout: float = 5) -> tuple[float, float]:
    """Current position as (lat, lon) in degrees, from GLOBAL_POSITION_INT."""
    msg = _read_message(master, 'GLOBAL_POSITION_INT', timeout)
    return msg.lat / 1e7, msg.lon / 1e7


def get_gps_status(master: mavutil.mavfile, timeout: float = 5) -> tuple[int, int]:
    """GPS state as (fix_type, satellites_visible), from GPS_RAW_INT."""
    msg = _read_message(master, 'GPS_RAW_INT', timeout)
    return msg.fix_type, msg.satellites_visible


def get_battery(master: mavutil.mavfile, timeout: float = 5) -> tuple[float, int]:
    """Battery state as (voltage in V, remaining charge in %), from SYS_STATUS."""
    msg = _read_message(master, 'SYS_STATUS', timeout)
    return msg.voltage_battery / 1000, msg.battery_remaining


def get_ground_speed(master: mavutil.mavfile, timeout: float = 5) -> float:
    """Ground speed in m/s, from VFR_HUD."""
    msg = _read_message(master, 'VFR_HUD', timeout)
    return msg.groundspeed


def wait_ground_speed_above(master: mavutil.mavfile, mps: float, timeout: float) -> float:
    """Wait until the ground speed is above mps; returns the measured speed.

    Raises:
        TimeoutError: the speed stayed at or below mps for timeout seconds.
    """
    return _wait_ground_speed(master, lambda speed: speed > mps, f"above {mps} m/s", timeout)


def wait_ground_speed_below(master: mavutil.mavfile, mps: float, timeout: float) -> float:
    """Wait until the ground speed is below mps; returns the measured speed.

    Raises:
        TimeoutError: the speed stayed at or above mps for timeout seconds.
    """
    return _wait_ground_speed(master, lambda speed: speed < mps, f"below {mps} m/s", timeout)


def _wait_ground_speed(master: mavutil.mavfile, condition: Callable[[float], bool],
                       description: str, timeout: float) -> float:
    """Poll VFR_HUD ground speed until condition(speed) is true."""
    deadline = time.monotonic() + timeout
    speed = None
    while time.monotonic() < deadline:
        speed = get_ground_speed(master)
        if condition(speed):
            return speed
    raise TimeoutError(f"Ground speed not {description} within {timeout} s, last: {speed} m/s")


def _read_message(master: mavutil.mavfile, msg_type: str,
                  timeout: float) -> mavutil.mavlink.MAVLink_message:
    """Drain the buffer and return the next fresh message of msg_type.

    Raises:
        TimeoutError: no msg_type message within timeout seconds.
    """
    drain(master)
    msg = master.recv_match(type=msg_type, blocking=True, timeout=timeout)
    if msg is not None:
        return msg
    raise TimeoutError(f"No {msg_type} from the vehicle within {timeout} s")
