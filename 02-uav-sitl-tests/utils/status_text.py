"""Recorder for STATUSTEXT messages that survives buffer draining.

The helpers in this package call drain() before reading, which discards every
message already in the buffer, STATUSTEXT included. Failsafe reactions are
reported by the autopilot as status text at an arbitrary moment, so the tests
need a record that does not depend on who reads the port and when.
"""

import re
import time
from dataclasses import dataclass

from pymavlink import mavutil


@dataclass(frozen=True)
class StatusText:
    """One STATUSTEXT received from the vehicle."""

    time: float  # time.monotonic() at reception
    severity: int  # MAV_SEVERITY_*
    text: str


class StatusTextRecorder:
    """Keep every STATUSTEXT the connection receives.

    The recorder registers itself in master.message_hooks. pymavlink calls
    these hooks for each incoming message before recv_match() filters it out
    or drain() discards it, so no status text is lost.
    """

    def __init__(self, master: mavutil.mavfile) -> None:
        self._master = master
        self._messages: list[StatusText] = []
        master.message_hooks.append(self._on_message)

    def _on_message(self, _master: mavutil.mavfile,
                    msg: mavutil.mavlink.MAVLink_message) -> None:
        if msg.get_type() == "STATUSTEXT":
            self._messages.append(StatusText(time.monotonic(), msg.severity, msg.text))

    @property
    def messages(self) -> list[StatusText]:
        """All recorded status texts, oldest first."""
        return list(self._messages)

    @property
    def texts(self) -> list[str]:
        """Text of all recorded status texts, oldest first."""
        return [m.text for m in self._messages]

    def clear(self) -> None:
        """Forget everything recorded so far."""
        self._messages.clear()

    def detach(self) -> None:
        """Stop recording: remove the hook from the connection."""
        if self._on_message in self._master.message_hooks:
            self._master.message_hooks.remove(self._on_message)

    def find(self, pattern: str) -> StatusText | None:
        """First recorded status text matching the regular expression, or None."""
        regex = re.compile(pattern)
        for message in self._messages:
            if regex.search(message.text):
                return message
        return None

    def wait_for(self, pattern: str, timeout: float) -> StatusText:
        """Wait until a status text matching the regular expression is recorded.

        Hooks run only when messages are read from the port, so this method
        keeps reading while it waits.

        Raises:
            TimeoutError: no matching text within timeout seconds; the message
                lists the texts recorded so far.
        """
        deadline = time.monotonic() + timeout
        while True:
            found = self.find(pattern)
            if found is not None:
                return found
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            self._master.recv_match(blocking=True, timeout=remaining)
        raise TimeoutError(
            f"No STATUSTEXT matching {pattern!r} within {timeout} s, recorded: {self.texts}"
        )
