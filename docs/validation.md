# Validation record

Environment: Linux x86-64, Python 3.12.14, PySide6 6.10.2, pyqtgraph 0.14.0, Phoenix 26.3.0. Date: 2026-10-16.

Current source validation: **57 tests passed**, including the real vendor simulation integration suite; Ruff lint and formatting checks passed.

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

Other automated checks cover malformed server responses, HTTP-success/device-error handling, missing readings, timeouts without write retries, explicit mutation confirmation, duplicate/replaced/missing target rejection, concurrent external configuration edits, invalid and cross-model imports, validation of finite values and ranges, telemetry retention and CSV gaps, and Qt startup/device/configuration/plot/self-test/disconnect workflows.

## Desktop and packaging

The actual Qt UI was rendered with Qt's offscreen platform against the vendor simulation. Screenshots in [images](images/) show live simulation data from the app, not mockups.

`tools/build.py` successfully produced the Linux onedir bundle. `tools/smoke_bundle.py` launched the frozen GUI with `--simulate`, confirmed that its bundled SDK subprocess enumerated eight simulated devices, and read configuration, self-test and control metadata, and acquired buffered plot records through that subprocess. The source GUI and frozen GUI were both exercised.

Windows and macOS build/test jobs are configured in CI but were **not run from this Linux environment**. Linux builds report optional pyqtgraph OpenGL and TIFF image-plugin dependency warnings; the app uses a 2D plot and SVG/PNG assets. Those optional features are not used.

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
