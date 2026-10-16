"""Control request heartbeat on its own thread and HTTP connection.

A controlv2 request outranks the robot program's control requests for only
~200 ms. Heartbeats therefore never queue behind telemetry, discovery or GUI
work; otherwise the robot program reclaims the device between requests.
"""

import threading
import time

from PySide6.QtCore import QThread, Signal

from ..backends.diagnostics import DiagnosticsBackend
from ..models import TunerError

PERIOD = 0.04  # Several requests per server hold window.
HOLD = 0.18  # Measured: the robot program reclaims output ~0.2 s after the last request.
STALL = 0.3  # No acknowledgment or GUI feed for this long ends the session.


class ControlHeartbeat(QThread):
    acknowledged = Signal(object, str)
    lapsed = Signal(object, float)
    ended = Signal(object, str, str)

    def __init__(self, backend, device, mode, values, renew=None, parent=None):
        super().__init__(parent)
        self.backend, self.device = backend, device
        self.request = (mode, values)
        self.renew = renew
        self.lock = threading.Lock()
        self.wake = threading.Event()
        self.active = True
        self.gui_deadline = time.monotonic() + STALL

    def update(self, mode, values):
        with self.lock:
            self.request = (mode, values)
        self.wake.set()

    def feed(self):
        self.gui_deadline = time.monotonic() + STALL

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

    def run(self):
        channel, error, stop_error = self.backend, "", ""
        try:
            if isinstance(self.backend, DiagnosticsBackend):
                channel = self.backend.control_channel()
            last_ack, reported = time.monotonic(), None
            while True:
                with self.lock:
                    if not self.active:
                        break
                    request = self.request
                if time.monotonic() > self.gui_deadline:
                    raise TunerError(
                        "GUI heartbeat stalled; explicit Enable and Apply are required to resume"
                    )
                sent = time.monotonic()
                channel.control(self.device, *request, confirmed=True)
                now = time.monotonic()
                if now - last_ack > STALL:
                    raise TunerError(
                        "Control heartbeat stalled; explicit Enable and Apply are required to resume"
                    )
                with self.lock:
                    if not self.active:
                        break
                    if self.renew:
                        self.renew(True)
                if now - last_ack > HOLD:
                    self.lapsed.emit(self, now - last_ack)
                last_ack = now
                if request is not reported:
                    reported = request
                    self.acknowledged.emit(self, request[0])
                self.wake.wait(max(0.0, sent + PERIOD - time.monotonic()))
                self.wake.clear()
        except Exception as e:
            error = str(e)
        finally:
            self.stop()
            # Sent from this thread, so it always follows the last control request.
            try:
                channel.stop_control(self.device)
            except Exception as e:
                stop_error = str(e)
            if channel is not self.backend:
                channel.close()
            self.ended.emit(self, error, stop_error)
