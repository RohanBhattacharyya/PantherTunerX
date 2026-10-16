# Hardware acceptance checks

Physical hardware was unavailable during initial development. Do not label hardware compatibility verified until these checks are recorded with OS, server version, adapter, firmware and observed results.

1. Start with robot disabled, mechanism secured, and a known configuration backed up through official Tuner X.
2. Test remote roboRIO USB and Ethernet. Compare discovery with Tuner X: names, model variants, IDs, CAN buses, serial numbers and firmware. Test CANivore attached to roboRIO and to Linux/Windows. Test Linux SocketCAN and macOS remote access separately.
3. Unplug CAN/USB/network and power-cycle a device. Confirm no current-looking values are invented, device disappearance is shown, and reconnecting/discovering recovers reads without applying configuration.
4. Compare self-test values and faults against Tuner X, including encoder health and non-motor devices. Verify that unsupported signal/status errors are visible.
5. Compare static telemetry and known controlled sensor movement. Compare buffered timestamps, ordinals, practical record rates and CAN signal freshness. Intentionally delay fetches and overrun the ring; verify visible gap counts. Check long captures, zoom, pause gaps and CSV columns.
6. On a safe bench, change a reversible parameter through Panther, verify readback and the same value in Tuner X, then restore. Test all config groups and all device families; check enums and firmware quantization. Test external changes between refresh and apply are refused.
7. Verify file model mismatch, malformed imports, out-of-range values, cancellation and staged defaults never mutate hardware.
8. Check name, ID collision handling, duplicate IDs and blink/fault clearing. These operations need validation on physical hardware even when the simulation accepts them.
9. Trigger timeout during a write; verify that Panther reports uncertainty and does not retry. Refresh and compare actual configuration.
10. Confirm no motor activation during startup, discovery, self-test, plotting, import, defaults staging, reconnect or exit. Observe with a CAN capture and the motor secured. A different robot process can independently control the same device; Panther cannot prevent that.

11. With an independently accessible emergency stop and a secured mechanism, validate explicit Enable then Apply, each intended control mode, Stop, leaving Control, GUI/SDK termination, HTTP loss, worker stalls, and watchdog response with Driver Station enable both present and absent. Check FRC lock and non-FRC enable behavior. The software currently verifies these safeguards only in simulation.

Keep firmware updates and licensing in official CTRE software; their protocols are not implemented.
