# Validation record

Environment: Linux x86-64, Python 3.12.14, PySide6 6.10.2, pyqtgraph 0.14.0, Phoenix 26.3.0. Date: 2026-10-16.

Current source validation: **74 tests passed**, including the real vendor simulation integration suite; Ruff lint and formatting checks passed.

The automated suite exercises the real CTRE SDK with `CTR_TARGET=Simulation`. No physical CAN interfaces or CANivore USB adapter were present on the development machine. No physical motor behavior has been validated.

## Vendor integration results

| Reported model | Config parameters | Self-test signals | Read / write / readback |
|---|---:|---:|---|
| Talon FX vers. C | 100 | 167 | Passed |
| Talon FXS | 113 | 185 | Passed |
| CANCoder vers. H | 5 | 47 | Passed |
| CANrange | 11 | 49 | Passed |
| CANdi | 14 | 56 | Passed |
| Pigeon 2 | 11 | 84 | Passed |
| CANdle | 8 | 78 | Passed |

Write tests change and restore a custom parameter on each device family, passing the complete metadata schema through the real configuration endpoint. A separate Talon FX test changes and restores duty-cycle deadband and verifies sensor telemetry changes over time. These are interoperability tests, not proof that every field's electrical behavior is correct.

Blink / clear sticky faults and device rename succeeded in simulation. CAN ID changes were rejected by the simulator with vendor error -109; the app surfaces this error and does not claim the ID changed.

Buffered integration checks confirm delayed fetches retain intermediate records, overlapping fetches do not duplicate ordinals, and deliberate ring overruns produce missing-record counts/gaps. Control integration checks confirm actual simulated duty output, explicit Stop, enable lease expiry and HTTP request heartbeat expiry while global enable continues. UI tests verify editing and cancelled Enable send no requests, and leaving Control stops an applied request, stalled requests disarm without automatic resume, and expired IPC messages cannot reenable output. An additional Qt integration test exercises the actual editor-to-local-SDK path: arm produces no output, Apply produces approximately 10% simulated duty cycle, and Stop returns output to zero. These checks do not validate every control mode or physical firmware.

Other automated checks cover malformed server responses, HTTP-success/device-error handling, missing readings, timeouts without write retries, bounded readback recovery after acknowledged writes, explicit mutation confirmation, duplicate/replaced/missing target rejection, concurrent external configuration edits, invalid and cross-model imports, validation of finite values and ranges, telemetry retention and CSV gaps, and Qt startup/device/configuration/plot/self-test/disconnect workflows.

## Desktop and packaging

The actual Qt UI was rendered with Qt's offscreen platform against the vendor simulation. Screenshots in [images](images/) show live simulation data from the app, not mockups.

`tools/build.py` successfully produced the Linux onedir bundle. `tools/smoke_bundle.py` launched the frozen GUI with `--simulate`, confirmed that its bundled SDK subprocess enumerated eight simulated devices, and read configuration, self-test and control metadata, and acquired buffered plot records through that subprocess. The source GUI and frozen GUI were both exercised.

The bundle smoke test uses a short 500 ms request timeout only while probing startup, then restores the application's normal 3 s timeout for device transactions. Previously the short probe timeout also applied to configuration reads, causing intermittent macOS bundle failures after source tests passed. Regression checks verify timeout restoration on discovery success, startup deadline expiry, and process exit. The smoke test prints captured GUI output on failure; device transactions are not automatically retried.

GitHub Actions verified source tests and desktop builds on Windows and macOS 14 (Apple Silicon), plus Linux and an Arch makepkg job. macOS CI now pins the supported Python 3.12.14 runtime. Its control watchdog test reads a single status signal rather than a slow full self-test, waits for asynchronous telemetry within a deadline, and keeps enable feeds active when verifying independent request expiry and Stop. No macOS simulation tests are disabled. SDK process/loop diagnostics are attached to failed integration tests. Linux builds report optional pyqtgraph OpenGL and TIFF image-plugin dependency warnings; the app uses a 2D plot and SVG/PNG assets. Those optional features are not used.

## Native Linux installation checks

- Built the actual Arch PKGBUILD with `makepkg` on x86-64; pacman successfully inspected the resulting `.pkg.tar.zst`. The same recipe also passed in CI's official Arch container.
- Built the frozen application in the Ubuntu 22.04 baseline container and confirmed its bundled glibc requirement is 2.35.
- Built `.deb` and `.rpm` packages using native dpkg-deb and rpmbuild tooling.
- Installed with APT in a clean Ubuntu 22.04 container and DNF in a clean Fedora 44 container. In both, the installed command ran, the frozen GUI/SDK smoke test enumerated eight simulated devices and read configuration/self-test/control metadata/buffered records, and package-manager removal removed the launcher.
- Unit checks cover ELF architecture detection, staging/permission rules, preserved library links, mandatory notices, non-overwriting behavior, glibc requirement detection, and portable archives preserving Unix executable bits/macOS framework links. Desktop entries and shell recipes were validated.

ARM64 native package builds remain unverified. These container checks use the offscreen Qt platform and simulation; no physical CAN devices or live desktop sessions are tested.

## Reproduce

```sh
uv sync --frozen
uv run ruff check .
uv run ruff format --check .
QT_QPA_PLATFORM=offscreen uv run pytest -q
uv run python tools/build.py
uv run python tools/smoke_bundle.py dist/PantherTunerX/PantherTunerX
QT_QPA_PLATFORM=offscreen uv run python tools/preview.py
```

Tests, preview and bundle smoke each need exclusive access to port 1250; run those three operations sequentially. `tools/probe.py` can collect read-only responses from a specified hardware server for future validation. Use the separate [hardware acceptance checks](hardware-validation.md) before declaring physical hardware support verified.
