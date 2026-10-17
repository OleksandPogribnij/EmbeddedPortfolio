"""MAVLink connection to the SITL vehicle and HEARTBEAT handling."""

import time

from pymavlink import mavutil

STREAM_RATE_HZ = 4  # rate requested for all telemetry streams


def connect(connection_string: str,
            timeout: float = 30) -> tuple[mavutil.mavfile, mavutil.mavlink.MAVLink_message]:
    """Open a MAVLink connection, wait for the vehicle and request telemetry streams.

    Args:
        connection_string: pymavlink endpoint, e.g. "udp:0.0.0.0:14550".
        timeout: seconds to wait for the first vehicle HEARTBEAT.

    Returns:
        Tuple (connection, first vehicle HEARTBEAT).

    Raises:
        TimeoutError: no HEARTBEAT from the vehicle within timeout seconds.
    """
    master = mavutil.mavlink_connection(connection_string)

    msg = wait_vehicle_heartbeat(master, timeout)

    master.mav.request_data_stream_send(
        master.target_system,
        master.target_component,
        mavutil.mavlink.MAV_DATA_STREAM_ALL,
        STREAM_RATE_HZ,
        1,  # start sending
    )

    return master, msg


def wait_vehicle_heartbeat(master: mavutil.mavfile,
                           timeout: float = 30) -> mavutil.mavlink.MAVLink_message:
    """Wait for the next HEARTBEAT sent by the vehicle.

    The buffer is drained first, so the result reflects the current state.
    HEARTBEATs from ground stations (MAV_TYPE_GCS, e.g. MAVProxy) are skipped.

    Returns:
        The vehicle HEARTBEAT message.

    Raises:
        TimeoutError: no vehicle HEARTBEAT within timeout seconds.
    """
    drain(master)
    deadline = time.monotonic() + timeout
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            break
        msg = master.recv_match(type='HEARTBEAT', blocking=True, timeout=remaining)
        if msg is None:
            continue
        if msg.type == mavutil.mavlink.MAV_TYPE_GCS:
            continue
        return msg
    raise TimeoutError(f"No heartbeat from the vehicle within {timeout} s")


def drain(master: mavutil.mavfile) -> None:
    """Discard all messages already waiting in the receive buffer.

    Makes the next read return a fresh message. Side effect: everything in
    the buffer is lost, including STATUSTEXT messages with autopilot reasons.
    """
    while master.recv_match(blocking=False) is not None:
        pass
