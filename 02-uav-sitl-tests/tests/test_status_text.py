"""Unit tests for StatusTextRecorder; no simulator needed (fake MAVLink connection)."""

from collections import deque

import pytest

from utils.connection import drain
from utils.status_text import StatusTextRecorder


class FakeMessage:
    """Minimal stand-in for a pymavlink message."""

    def __init__(self, msg_type: str, text: str = "", severity: int = 6) -> None:
        self._type = msg_type
        self.text = text
        self.severity = severity

    def get_type(self) -> str:
        return self._type


class FakeConnection:
    """Stand-in for mavutil.mavfile: queued messages pass through message_hooks when read."""

    def __init__(self, *messages: FakeMessage) -> None:
        self.message_hooks = []
        self._queue = deque(messages)

    def recv_match(self, blocking: bool = False, timeout: float | None = None):
        if not self._queue:
            return None
        msg = self._queue.popleft()
        for hook in self.message_hooks:
            hook(self, msg)
        return msg


class TestStatusTextRecorder:
    """STATUSTEXT recording through pymavlink message hooks."""

    def test_records_only_status_text(self):
        """UT-004: only STATUSTEXT messages are recorded, other types are ignored."""
        conn = FakeConnection(
            FakeMessage("HEARTBEAT"),
            FakeMessage("STATUSTEXT", "GPS Glitch"),
            FakeMessage("GLOBAL_POSITION_INT"),
        )
        recorder = StatusTextRecorder(conn)
        while conn.recv_match() is not None:
            pass

        assert recorder.texts == ["GPS Glitch"], (
            f"Recorded texts: expected ['GPS Glitch'], got {recorder.texts}"
        )

    def test_status_text_survives_drain(self):
        """UT-005: status text discarded by drain() is still recorded."""
        conn = FakeConnection(FakeMessage("STATUSTEXT", "Battery failsafe"))
        recorder = StatusTextRecorder(conn)

        drain(conn)

        assert recorder.find("failsafe") is not None, (
            f"Text after drain(): expected 'Battery failsafe', got {recorder.texts}"
        )

    def test_wait_for_reads_until_match(self):
        """UT-006: wait_for() keeps reading the port until a matching text arrives."""
        conn = FakeConnection(
            FakeMessage("HEARTBEAT"),
            FakeMessage("STATUSTEXT", "EKF variance"),
            FakeMessage("STATUSTEXT", "Failsafe: LAND"),
        )
        recorder = StatusTextRecorder(conn)

        found = recorder.wait_for(r"Failsafe.*LAND", timeout=1)

        assert found.text == "Failsafe: LAND", (
            f"Matched text: expected 'Failsafe: LAND', got {found.text!r}"
        )

    def test_wait_for_timeout_lists_recorded_texts(self):
        """UT-007: wait_for() raises TimeoutError that lists the texts seen so far."""
        conn = FakeConnection(FakeMessage("STATUSTEXT", "EKF variance"))
        recorder = StatusTextRecorder(conn)

        with pytest.raises(TimeoutError, match="EKF variance"):
            recorder.wait_for("GPS", timeout=0.1)

    def test_clear_and_detach(self):
        """UT-008: clear() forgets old texts; detach() stops recording."""
        conn = FakeConnection(
            FakeMessage("STATUSTEXT", "old"),
            FakeMessage("STATUSTEXT", "after detach"),
        )
        recorder = StatusTextRecorder(conn)
        conn.recv_match()
        recorder.clear()
        recorder.detach()
        conn.recv_match()

        assert recorder.texts == [], f"Recorded texts: expected [], got {recorder.texts}"
