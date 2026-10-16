"""Isolated CTRE SDK process. Simulation physics are explicitly synthetic inputs."""

import argparse
import math
import os
import platform
import socket
import threading
import time


class EnableLease:
    """A lost/stalled GUI cannot leave the SDK feed enabled indefinitely."""

    def __init__(self):
        self.deadline = 0.0

    def read(self, stream):
        for line in stream:
            parts = line.split()
            try:
                deadline = float(parts[1]) if len(parts) == 2 and parts[0] == "enable" else 0.0
                self.deadline = min(deadline, time.monotonic() + 0.25) if math.isfinite(deadline) else 0.0
            except ValueError:
                self.deadline = 0.0
        self.deadline = 0.0

    def active(self):
        return time.monotonic() < self.deadline

    def connect_parent(self):
        port, token = os.environ.get("PANTHER_LEASE_PORT"), os.environ.get("PANTHER_LEASE_TOKEN")
        if not port or not token:
            return
        try:
            with socket.create_connection(("127.0.0.1", int(port)), timeout=3) as conn:
                conn.sendall((token + "\n").encode("ascii"))
                conn.settimeout(None)
                with conn.makefile("r", encoding="ascii") as stream:
                    self.read(stream)
        except (OSError, ValueError):
            self.deadline = 0.0


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--simulation", action="store_true")
    p.add_argument("--hardware", action="store_true")
    p.add_argument("--bus", default="can0")
    args = p.parse_args()
    os.environ["CTR_TARGET"] = "Simulation" if args.simulation else "Hardware"
    debug = os.environ.get("PANTHER_SDK_DEBUG") == "1"
    if debug:
        print(f"SDK host: {platform.platform()} Python {platform.python_version()}", flush=True)
        if os.name == "posix":
            import resource

            print(f"SDK file descriptor limits: {resource.getrlimit(resource.RLIMIT_NOFILE)}", flush=True)
    from phoenix6 import CANBus, hardware, unmanaged

    unmanaged.set_phoenix_diagnostics_start_time(0)
    unmanaged.load_phoenix()
    lease = EnableLease()
    threading.Thread(target=lease.connect_parent, daemon=True).start()
    devices = []
    if args.simulation:
        devices = [
            hardware.TalonFX(1),
            hardware.TalonFX(2),
            hardware.CANcoder(3),
            hardware.Pigeon2(4),
            hardware.CANrange(5),
            hardware.CANdi(6),
            hardware.TalonFXS(7),
            hardware.CANdle(8),
        ]
    else:
        network = CANBus(args.bus)
        network.get_status()
    start = time.monotonic()
    was_enabled = False
    iterations = 0
    last_report = start
    while True:
        t = time.monotonic() - start
        # Official non-FRC actuator enable. Never fed during discovery/plotting.
        # FRC still requires Driver Station enable; this does not bypass it.
        enabled = lease.active()
        if enabled:
            unmanaged.feed_enable(0.100)
        elif was_enabled:
            unmanaged.feed_enable(0)
        was_enabled = enabled
        for i, device in enumerate(devices):
            state = device.sim_state
            state.set_supply_voltage(12.3)
            if isinstance(device, (hardware.TalonFX, hardware.TalonFXS)):
                # Motor physics input only. No set_control(), set(), or enable calls.
                state.set_raw_rotor_position(3 * t + math.sin(t + i))
                state.set_rotor_velocity(3 + math.cos(t + i))
            elif isinstance(device, hardware.CANcoder):
                state.set_raw_position(0.25 + 0.1 * math.sin(t))
                state.set_velocity(0.1 * math.cos(t))
            elif isinstance(device, hardware.Pigeon2):
                state.set_raw_yaw(25 * math.sin(t / 3))
                state.set_pitch(4 * math.sin(t))
                state.set_roll(2 * math.cos(t))
            elif isinstance(device, hardware.CANrange):
                state.set_distance(0.5 + 0.1 * math.sin(t))
        iterations += 1
        if debug and time.monotonic() - last_report >= 2:
            print(f"SDK loop: uptime={t:.2f}s iterations={iterations} devices={len(devices)}", flush=True)
            last_report = time.monotonic()
        time.sleep(0.02)


if __name__ == "__main__":
    main()
