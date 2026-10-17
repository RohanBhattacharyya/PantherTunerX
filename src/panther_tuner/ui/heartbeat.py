"""Control request heartbeat on its own thread and HTTP connection.

A controlv2 request outranks the robot program's control requests for only
~200 ms. Heartbeats therefore never queue behind telemetry, discovery or GUI
work; otherwise the robot program reclaims the device between requests.

Like Tuner X, control stays enabled until the user disables it. Slow or failed
requests are retried and reported rather than disabling control: when requests
stop arriving, the server's own watchdog neutralizes output.
"""

import threading
import time

from PySide6.QtCore import QThread, Signal

from ..backends.diagnostics import DiagnosticsBackend
from ..models import TunerError

PERIOD = 0.04  # Several requests per server hold window.
HOLD = 0.18  # Measured: the robot program reclaims output ~0.2 s after the last request.
GUI_STALL = 1.0  # A frozen GUI pauses requests until it responds again.
ATTEMPTS = 3  # Target verification and Stop requests.


class ControlHeartbeat(QThread):
    # (heartbeat, healthy, message): emitted only when the message changes.
    status = Signal(object, bool, str)
    ended = Signal(object, str, str)

    def __init__(self, backend, device, mode, values, renew=None, parent=None):
        super().__init__(parent)
        self.backend, self.device = backend, device
        self.request = (mode, values)
        self.renew = renew
        self.lock = threading.Lock()
        self.wake = threading.Event()
        self.active = True
        self.gui_deadline = time.monotonic() + GUI_STALL
        self.reported = None

    def update(self, mode, values):
        with self.lock:
            self.request = (mode, values)
        self.wake.set()

    def feed(self):
        self.gui_deadline = time.monotonic() + GUI_STALL

    def stop(self):
        # Under the lock, so no enable renewal can follow the revocation.
        with self.lock:
            self.active = False
            if self.renew:
                try:
                    self.renew(False)
                except TunerError:
                    pass
        self.wake.set()

    def report(self, healthy, message):
        if (healthy, message) != self.reported:
            self.reported = (healthy, message)
            self.status.emit(self, healthy, message)

    def run(self):
        channel, error, stop_error = self.backend, "", ""
        try:
            if isinstance(self.backend, DiagnosticsBackend):
                channel = self.backend.control_channel()
            # Verified on this connection, not behind queued telemetry.
            for attempt in range(ATTEMPTS):
                try:
                    channel.assert_target(self.device)
                    break
                except TunerError:
                    if attempt == ATTEMPTS - 1:
                        raise
            last_ack = None
            while True:
                with self.lock:
                    if not self.active:
                        break
                    mode, values = self.request
                sent = time.monotonic()
                if sent > self.gui_deadline:
                    self.report(False, "Paused: the application is not responding")
                else:
                    try:
                        channel.control(self.device, mode, values, confirmed=True)
                    except TunerError as e:
                        self.report(False, f"No response, retrying: {e}")
                    else:
                        now = time.monotonic()
                        with self.lock:
                            if not self.active:
                                break
                            if self.renew:
                                self.renew(True)
                        if last_ack is not None and now - last_ack > HOLD:
                            self.report(
                                True,
                                f"{mode} resumed after a {(now - last_ack) * 1000:.0f} ms gap; "
                                "the robot program may have briefly controlled the device",
                            )
                        else:
                            self.report(True, f"Sending {mode}")
                        last_ack = now
                self.wake.wait(max(0.0, sent + PERIOD - time.monotonic()))
                self.wake.clear()
        except Exception as e:
            error = str(e)
        finally:
            self.stop()
            # Sent from this thread, so it always follows the last control request.
            for _ in range(ATTEMPTS):
                try:
                    channel.stop_control(self.device)
                    stop_error = ""
                    break
                except Exception as e:
                    stop_error = str(e)
            if channel is not self.backend:
                channel.close()
            self.ended.emit(self, error, stop_error)
