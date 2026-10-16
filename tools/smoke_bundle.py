"""Launch the frozen GUI in simulation and verify its bundled SDK child works."""

import argparse
import os
import signal
import socket
import subprocess
import tempfile
import time
from pathlib import Path

import httpx

from panther_tuner.backends.diagnostics import DiagnosticsBackend
from panther_tuner.models import TunerError


def wait_for_devices(backend, process, *, timeout=25):
    """Probe startup quickly without shortening subsequent device transactions."""
    original_timeout = backend.client.timeout
    backend.client.timeout = httpx.Timeout(0.5)
    deadline = time.monotonic() + timeout
    last_error = "No devices discovered"
    try:
        while time.monotonic() < deadline:
            if process.poll() is not None:
                raise RuntimeError(f"Frozen GUI exited with status {process.returncode}")
            try:
                backend.connect()
                devices = backend.discover()
                if len(devices) == 8:
                    return devices
                last_error = f"Discovered {len(devices)} of 8 devices"
            except TunerError as error:
                last_error = str(error)
            time.sleep(0.1)
        raise RuntimeError(f"Frozen GUI did not start eight simulated devices: {last_error}")
    finally:
        backend.client.timeout = original_timeout


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("executable", type=Path)
    args = p.parse_args()
    with socket.socket() as sock:
        if sock.connect_ex(("127.0.0.1", 1250)) == 0:
            raise RuntimeError("Port 1250 must be free for isolated bundle smoke test")
    backend = DiagnosticsBackend("127.0.0.1")
    with tempfile.TemporaryFile() as log:
        process = subprocess.Popen(
            [str(args.executable.resolve()), "--simulate"],
            env=dict(os.environ, QT_QPA_PLATFORM="offscreen"),
            stdout=log,
            stderr=log,
            start_new_session=os.name != "nt",
        )
        try:
            devices = wait_for_devices(backend, process)
            device = next(d for d in devices if d.id == 1)
            assert "Simulated" in device.status
            assert len(backend.read_config(device).values()) == 100
            assert backend.self_test(device)["signals"]
            assert "DutyCycleOut" in backend.controls(device)
            assert backend.device_information(device)["Frc Lock"] is False
            sid = next(s.id for s in backend.signals(device) if s.name == "Velocity")
            backend.buffered_samples(device, [sid])
            time.sleep(0.25)
            assert len(backend.buffered_samples(device, [sid]).samples) >= 10
            backend.stop_plot(device)
            print(
                "Frozen GUI + SDK smoke passed: 8 devices, configuration, self-test, control catalog and buffered records."
            )
        except Exception:
            log.seek(0)
            print("Frozen GUI output:\n" + log.read().decode(errors="replace"), flush=True)
            raise
        finally:
            backend.close()
            if os.name == "nt":
                subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"], check=False)
            else:
                try:
                    os.killpg(process.pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass
            process.wait(timeout=5)


if __name__ == "__main__":
    main()
