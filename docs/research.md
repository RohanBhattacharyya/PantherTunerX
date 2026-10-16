# Research log and sources

Research date: **2026-10-15**. The repository was empty at the start. The implementation favors officially supported Phoenix libraries; current undocumented diagnostics wire details were checked against a real CTRE SDK simulation server before use.

## Official workflow and visual references

* [Tuner X overview](https://v6.docs.ctr-electronics.com/en/stable/docs/tuner/index.html): companion app workflow and current desktop/mobile platforms.
* [Connecting Tuner](https://v6.docs.ctr-electronics.com/en/stable/docs/tuner/connecting.html): roboRIO USB, localhost, configurable server host and port 1250.
* [Device list](https://v6.docs.ctr-electronics.com/en/stable/docs/tuner/device-list.html): card/table views, firmware-related card colors, duplicate IDs and clipboard actions. Panther avoids claiming a firmware is current without a firmware catalog.
* [Device details](https://v6.docs.ctr-electronics.com/en/stable/docs/tuner/device-details-page.html): names, IDs, firmware, blink, configuration and self-tests; IDs 0–62.
* [Configuration](https://v6.docs.ctr-electronics.com/en/stable/docs/tuner/configs.html): read, edit, backup, restore and explicit apply.
* [Self-test](https://v6.docs.ctr-electronics.com/en/stable/docs/tuner/self-test.html): snapshot tables, units, refresh, fault clearing and copying.
* [Plotter documentation](https://v6.docs.ctr-electronics.com/en/stable/docs/tuner/plotting.html): signal sidebar, tracking, pause, retained timespan, polling controls, CSV and zoom. The documentation includes animated GIF demonstrations of panning, horizontal/vertical stretch and box selection. These animations and the official [2026 plot overview screenshot](https://v6.docs.ctr-electronics.com/en/stable/_images/tuner-plot-overview.png) were used as interaction/layout references. The screenshot was downloaded and visually inspected locally.
* [Tuner evolution article](https://v6.docs.ctr-electronics.com/en/stable/docs/application-notes/tuner-evolution.html): screenshots and discussion of the redesigned shared plot/config workspace.
* [Phoenix changelog](https://api.ctr-electronics.com/changelog.html): recent reorganization of device navigation, plot signal list and lower configuration pane.

Panther reproduces the device-first workflow, left navigation and connection selector, card/table overview, signal list beside a central plot, and a persistent lower configuration pane. It uses pastel yellow/black styling and original navigation icons. No Tuner X application assets are copied; official product images from the CTRE store are bundled with source attribution. The 2026 layout is followed at the reference 1662×1114 size: 60 px title/rail, 480 px left Info/Control/Signals pane, independent Self Test/Plot tabs, per-signal left axes, and a 340 px lower-right configuration dock. Original outline icons accompany official manufacturer product images (see `src/panther_tuner/assets/devices/sources.json` and the third-party notices). Typography, native widgets, self-test rendering and unimplemented pages still differ; pixel identity is not claimed.

## APIs and communication

* [Running Diagnostics](https://v6.docs.ctr-electronics.com/en/stable/docs/troubleshooting/running-diagnostics.html): the HTTP diagnostics server is normally started by a robot program using a Phoenix device. Temporary deployment is a separate Tuner feature.
* [Hardware and platform requirements](https://v6.docs.ctr-electronics.com/en/stable/docs/installation/requirements.html): supported device families, CANivore and SocketCAN, direct hardware OS support. macOS's SDK simulation-only constraint is distinct from Tuner X's macOS GUI availability.
* [Phoenix Python API](https://api.ctr-electronics.com/phoenix6/stable/python/): configuration classes, status signals, simulation states and the supported diagnostics startup API.
* [Phoenix 6 PyPI distribution](https://pypi.org/project/phoenix6/26.3.0/): version-pinned wheels for Linux x86-64/ARM64, Windows x64, macOS universal2. Downloaded and installed locally; native shared library resources, strings and selected disassembly were inspected to resolve POST framing and signal request names.
* [CTRE public diagnostics client](https://github.com/CrossTheRoadElec/Phoenix-diagnostics-client): archived MIT reference, cloned locally. `HTTP/URI.cs`, `HTTP/WebExchange.cs`, `JSON/Serializers.cs` and `BackEnd/BackEnd.cs` establish the historical GET query interface, server response status, discovery and combined blink/fault-clearing behavior. Old model and upload formats were not assumed compatible.
* [Phoenix Tuner releases](https://github.com/CrossTheRoadElec/Phoenix-Tuner-Release): inspected latest release metadata; no need to redistribute or decompile a Tuner installer once current server behavior could be exercised directly.
* [Preparing Linux controllers](https://docs.ctre-phoenix.com/en/stable/ch06b_PrepLinuxRobot.html): server architecture and obsolete standalone-deployment caveats.
* [CTRE known issues](https://api.ctr-electronics.com/known_issues): old self-test interfaces can require Tuner X for Phoenix 6, supporting use of decorated self-test rather than assuming the v5 text action works.

Technical discussions found during research include [Chief Delphi connection failures](https://www.chiefdelphi.com/t/issues-connecting-to-phoenix-tuner/372022) and [repeated disconnects](https://www.chiefdelphi.com/t/phoenix-tuner-keeps-disconnecting-from-robot/389553). These are contextual reports about missing/incompatible diagnostics servers and network issues, not protocol specifications. Only official documentation and locally observed vendor responses were used to implement technical behavior. Official animated documentation supplied motion references; no standalone video tutorial was relied on or claimed to have been watched.

## Local verification

An isolated SDK simulation process created Talon FX, CANcoder and Pigeon 2 devices and served the real Phoenix Diagnostics API on localhost:1250. Read responses were recorded during exploration. Both invalid guessed model strings and invalid signal formats were tested, then corrected based on observed behavior. Current `$@$`/base64 POST framing was derived from native library inspection and verified by changing a simulated deadband, refreshing it, and observing actual quantized readback. The automated integration suite extends this to all seven supported model families.

This establishes software interoperability with the tested server version, not electrical CAN behavior or physical safety under every firmware version. Use the [hardware acceptance checklist](hardware-validation.md) to close that gap.

## Buffered plot and control investigation

The current native diagnostics library's `plotpro`, `getcontrols` and `controlv2` dispatch and typed query parser were inspected locally. Probes against the actual simulator verified complete overlapping record windows, server timestamps, ring capacity, delayed fetch recovery, ordinal resets and deliberate overruns. Captures are checked into the test fixtures.

[Controlling Devices](https://v6.docs.ctr-electronics.com/en/stable/docs/tuner/controlling-devices.html) and [Enabling Actuators](https://v6.docs.ctr-electronics.com/en/stable/docs/api-reference/api-usage/enabling-actuators.html) informed the explicit enable/apply workflow and independent enable lease. A successful HTTP response initially produced no motor output: the documented non-FRC enable feed was also required. With that feed, simulated voltage/duty output, explicit Stop, enable expiry and the separate request watchdog were measured. No physical motors were used. Full request details and limits are in [protocol.md](protocol.md).
