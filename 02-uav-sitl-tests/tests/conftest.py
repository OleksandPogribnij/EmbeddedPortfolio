"""Shared pytest fixtures: SITL connection, vehicle states, parameters and missions."""

import os
import re
import time
from collections.abc import Callable, Iterator

import allure
import pytest
from pymavlink import mavutil

from utils.commands import (
    arm,
    get_mode,
    get_param,
    is_armed,
    land,
    set_mode,
    set_param,
    takeoff,
)
from utils.connection import connect
from utils.constants import STATE_READ_TIMEOUT_S, TAKEOFF_ALT_M
from utils.mission import clear_mission
from utils.status_text import StatusTextRecorder
from utils.telemetry import get_battery, get_gps_status, get_position, get_relative_altitude

DEFAULT_CONNECTION = "udp:0.0.0.0:14550"

# First docstring line of a test: "TC-012: ..." or "TC-052, TC-053: ...".
TEST_ID_PATTERN = re.compile(r"^((?:TC|UT)-\d+(?:,\s*(?:TC|UT)-\d+)*):")

STATUS_RECORDER_KEY = pytest.StashKey[StatusTextRecorder]()
TEST_START_KEY = pytest.StashKey[float]()


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """Move tests marked 'last' to the end of the run (stable order otherwise)."""
    items.sort(key=lambda item: item.get_closest_marker("last") is not None)


@pytest.hookimpl(tryfirst=True)
def pytest_runtest_setup(item: pytest.Item) -> None:
    """Remember when the test started, to select its STATUSTEXT messages later."""
    item.stash[TEST_START_KEY] = time.monotonic()


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item: pytest.Item,
                              call: pytest.CallInfo[None]) -> Iterator[None]:
    """On a failed SITL test, attach status texts and the vehicle state to the Allure report.

    The state is read before teardown, so it shows the vehicle as the test left it.
    """
    outcome = yield
    report = outcome.get_result()
    if report.when != "call" or not report.failed:
        return
    vehicle = item.funcargs.get("vehicle")
    if vehicle is None:  # unit test: no simulator connection
        return
    allure.attach(_status_texts_report(item), name="STATUSTEXT during the test",
                  attachment_type=allure.attachment_type.TEXT)
    allure.attach(_vehicle_state_report(vehicle), name="Vehicle state at failure",
                  attachment_type=allure.attachment_type.TEXT)


def _status_texts_report(item: pytest.Item) -> str:
    """Status texts received since the test started, one per line with time and severity."""
    recorder = item.config.stash.get(STATUS_RECORDER_KEY, None)
    if recorder is None:
        return "(STATUSTEXT recorder not active)"
    start = item.stash.get(TEST_START_KEY, 0.0)
    severities = mavutil.mavlink.enums["MAV_SEVERITY"]
    lines = []
    for message in recorder.messages:
        if message.time < start:
            continue
        severity = severities[message.severity].name.removeprefix("MAV_SEVERITY_") \
            if message.severity in severities else str(message.severity)
        lines.append(f"{message.time - start:7.1f} s  [{severity}] {message.text}")
    return "\n".join(lines) or "(no STATUSTEXT during the test)"


def _vehicle_state_report(vehicle: mavutil.mavfile) -> str:
    """Mode, armed state, altitude, position, battery and GPS, one value per line.

    A value that cannot be read (vehicle silent) is reported instead of raising,
    so the report never hides the original failure.
    """
    timeout = STATE_READ_TIMEOUT_S
    readers: dict[str, Callable[[], object]] = {
        "mode": lambda: get_mode(vehicle, timeout=timeout),
        "armed": lambda: is_armed(vehicle, timeout=timeout),
        "relative altitude, m": lambda: round(get_relative_altitude(vehicle, timeout), 2),
        "position (lat, lon)": lambda: get_position(vehicle, timeout),
        "battery (V, %)": lambda: get_battery(vehicle, timeout),
        "GPS (fix type, satellites)": lambda: get_gps_status(vehicle, timeout),
    }
    lines = []
    for name, read in readers.items():
        try:
            value = read()
        except TimeoutError as error:
            value = f"unavailable ({error})"
        lines.append(f"{name}: {value}")
    return "\n".join(lines)


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_call(item: pytest.Item) -> Iterator[None]:
    """Label every test in the Allure report from its docstrings.

    The test docstring gives the TC-ID and the title, the module docstring
    gives the feature, the sitl marker gives the epic. The docstrings stay
    the single source of truth; nothing is duplicated in decorators.
    Runs in the call phase: a title set earlier is overwritten by allure-pytest.
    """
    function = getattr(item, "function", None)
    test_doc = (getattr(function, "__doc__", None) or "").strip()
    first_line = test_doc.splitlines()[0] if test_doc else ""
    match = TEST_ID_PATTERN.match(first_line)
    if match:
        ids = [test_id.strip() for test_id in match.group(1).split(",")]
        allure.dynamic.id(ids[0])
        for test_id in ids:
            allure.dynamic.tag(test_id)
        allure.dynamic.title(first_line.rstrip("."))

    module = getattr(item, "module", None)
    module_doc = (getattr(module, "__doc__", None) or "").strip()
    if module_doc:
        # Feature name: the module summary up to the first ':', ';' or '('.
        feature = re.split(r"[:;(]", module_doc.splitlines()[0])[0].strip()
        allure.dynamic.feature(feature)

    is_sitl = item.get_closest_marker("sitl") is not None
    allure.dynamic.epic("SITL tests" if is_sitl else "Unit tests")
    yield


@pytest.fixture(scope="session")
def connection_string() -> str:
    """MAVLink endpoint from SITL_CONNECTION, or the default UDP port.

    Returns:
        Connection string for pymavlink, e.g. "udp:0.0.0.0:14550".
    """
    return os.environ.get("SITL_CONNECTION", DEFAULT_CONNECTION)


@pytest.fixture(scope="session")
def vehicle(request: pytest.FixtureRequest,
            connection_string: str) -> Iterator[mavutil.mavfile]:
    """One MAVLink connection to SITL for the whole test session.

    Stops the entire run with exit code 2 if the simulator is not reachable.
    Starts a session-wide STATUSTEXT recorder, used by status_log and by
    the failure report.

    Yields:
        pymavlink connection; closed after the last test.
    """
    try:
        master, _ = connect(connection_string, timeout=20)
    except TimeoutError as error:
        pytest.exit(f"SITL not reachable on {connection_string}. {error}\n"
                    "Check that the simulator is running and MAVProxy forwards MAVLink to this PC",
                    returncode=2,
                    )
    recorder = StatusTextRecorder(master)
    request.config.stash[STATUS_RECORDER_KEY] = recorder
    yield master
    recorder.detach()
    master.close()


@pytest.fixture
def vehicle_on_ground(vehicle: mavutil.mavfile) -> Iterator[mavutil.mavfile]:
    """Vehicle on the ground in GUIDED mode, ready to arm.

    After the test the vehicle is landed and disarmed, whatever state
    the test left it in.

    Yields:
        pymavlink connection.
    """
    land(vehicle)
    set_mode(vehicle, "GUIDED")

    yield vehicle
    land(vehicle)


@pytest.fixture
def param_changer(
        vehicle: mavutil.mavfile,
) -> Iterator[Callable[[str, float], float]]:
    """Change autopilot parameters for the duration of one test.

    The original value of each parameter is saved before its first change
    and restored after the test, even if the test fails.

    Yields:
        Function change(name, value) that sets a parameter and returns
        the value confirmed by the vehicle.
    """
    original: dict[str, float] = {}

    def change(name: str, value: float) -> float:
        if name not in original:
            original[name] = get_param(vehicle, name)
        return set_param(vehicle, name, value)

    yield change

    for name, old_value in original.items():
        set_param(vehicle, name, old_value)


@pytest.fixture
def home_position(vehicle_on_ground: mavutil.mavfile) -> tuple[float, float]:
    """Vehicle position on the ground before the test (the home point).

    Returns:
        Tuple (lat, lon) in degrees.
    """
    return get_position(vehicle_on_ground)


@pytest.fixture
def in_flight(
        vehicle_on_ground: mavutil.mavfile,
        home_position: tuple[float, float],
) -> Iterator[mavutil.mavfile]:
    """Armed vehicle hovering at TAKEOFF_ALT_M in GUIDED mode; landed after the test.

    Depends on home_position without using it, so that the home point is
    read on the ground before takeoff, not in the air.

    Yields:
        pymavlink connection.
    """
    arm(vehicle_on_ground)
    takeoff(vehicle_on_ground, TAKEOFF_ALT_M)

    yield vehicle_on_ground
    land(vehicle_on_ground)


@pytest.fixture
def clean_mission(vehicle: mavutil.mavfile) -> Iterator[mavutil.mavfile]:
    """Empty mission on the autopilot before and after the test.

    List it before vehicle_on_ground in the test arguments: teardowns run
    in reverse order, so the vehicle lands first and the mission is cleared
    after that. ArduPilot rejects MISSION_CLEAR_ALL while a mission is running.

    Yields:
        pymavlink connection.
    """
    clear_mission(vehicle)
    yield vehicle
    clear_mission(vehicle)


@pytest.fixture(scope="session")
def status_recorder(request: pytest.FixtureRequest,
                    vehicle: mavutil.mavfile) -> StatusTextRecorder:
    """Session-wide STATUSTEXT recorder started together with the vehicle connection.

    Returns:
        StatusTextRecorder attached to the session connection.
    """
    return request.config.stash[STATUS_RECORDER_KEY]


@pytest.fixture
def status_log(status_recorder: StatusTextRecorder) -> StatusTextRecorder:
    """STATUSTEXT recorder emptied at the start of the test.

    Use it in tests that check the autopilot's reason for a reaction
    (failsafe, refusals): only texts sent during this test are kept.

    Returns:
        The session StatusTextRecorder, cleared.
    """
    status_recorder.clear()
    return status_recorder
