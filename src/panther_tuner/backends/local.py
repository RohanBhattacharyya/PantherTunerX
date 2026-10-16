"""Own the SDK in a child process so simulation can never attach to real CAN.

The child hosts CTRE's diagnostics server; communication uses the same adapter
as a roboRIO. Enable feeds require an explicitly armed, renewable control lease.
"""

import os
import secrets
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from ..models import TunerError
from .diagnostics import DiagnosticsBackend


class LocalBackend(DiagnosticsBackend):
    def __init__(self, simulation: bool, bus: str = "can0", **kwargs):
        super().__init__("127.0.0.1", **kwargs)
        if not simulation and sys.platform == "darwin":
            raise TunerError("CTRE does not support direct CAN hardware on macOS. Use a network server.")
        self.simulated = simulation
        self.bus = bus
        self.process = None
        self.log = None
        self.lease_socket = None

    def connect(self):
        # Do not silently attach to an existing server: it might be real hardware.
        with socket.socket() as sock:
            if sock.connect_ex(("127.0.0.1", 1250)) == 0:
                raise TunerError("Port 1250 is already in use. Stop the existing server or use Network mode.")
        self.log = tempfile.TemporaryFile(mode="w+b")
        env = dict(os.environ, CTR_TARGET="Simulation" if self.simulated else "Hardware")
        listener = socket.socket()
        listener.bind(("127.0.0.1", 0))
        listener.listen(1)
        listener.settimeout(5)
        token = secrets.token_hex(32)
        env["PANTHER_LEASE_PORT"] = str(listener.getsockname()[1])
        env["PANTHER_LEASE_TOKEN"] = token
        args = [sys.executable]
        if getattr(sys, "frozen", False):
            args += ["--sdk-host"]
        else:
            args += ["-m", "panther_tuner.sdk_host"]
        args += ["--simulation" if self.simulated else "--hardware", "--bus", self.bus]
        # Separate writable cwd contains any native SDK logs and simulation files.
        self.workdir = tempfile.TemporaryDirectory(prefix="panther-sdk-")
        env["PYTHONPATH"] = os.pathsep.join(
            [str(Path(__file__).resolve().parents[2]), env.get("PYTHONPATH", "")]
        )
        try:
            self.process = subprocess.Popen(
                args, env=env, stdout=self.log, stderr=self.log, cwd=self.workdir.name
            )
            self.lease_socket, _ = listener.accept()
            self.lease_socket.settimeout(0.2)
            # Handshake works in Windows --windowed bundles with no sys.stdin.
            received = b""
            while b"\n" not in received and len(received) < 128:
                part = self.lease_socket.recv(128)
                if not part:
                    break
                received += part
            if received.strip().decode("ascii") != token:
                raise TunerError("SDK control watchdog handshake failed")
        except (OSError, UnicodeError) as e:
            raise TunerError(f"SDK control watchdog could not start: {e}") from e
        finally:
            listener.close()
        deadline = time.monotonic() + 8
        original_timeout = self.client.timeout
        self.client.timeout = 0.25
        while time.monotonic() < deadline:
            if self.process.poll() is not None:
                self.log.seek(0)
                raise TunerError(
                    "Phoenix SDK failed to start: " + self.log.read().decode(errors="replace")[-2000:]
                )
            try:
                result = super().connect()
                self.client.timeout = original_timeout
                return result
            except TunerError:
                time.sleep(0.1)
        raise TunerError("Phoenix SDK server did not start within 8 seconds")

    def enable_lease(self, enabled):
        if self.process and self.process.poll() is None and self.lease_socket:
            try:
                command = f"enable {time.monotonic() + 0.25:.9f}\n" if enabled else "disable\n"
                self.lease_socket.sendall(command.encode("ascii"))
            except (BrokenPipeError, OSError):
                if enabled:
                    raise TunerError("SDK control watchdog is unavailable")
        elif enabled:
            raise TunerError("SDK control watchdog is unavailable")

    def close(self):
        self.enable_lease(False)
        super().close()
        if self.process and self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait()
        if self.lease_socket:
            self.lease_socket.close()
            self.lease_socket = None
        if self.log:
            self.log.close()
        if hasattr(self, "workdir"):
            self.workdir.cleanup()
