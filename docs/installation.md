# Installation and packaging

Use Python 3.12 and the committed uv lockfile on each platform:

```sh
uv sync --frozen
uv run panther-tuner
```

Linux: Ubuntu 22.04+ / compatible glibc 2.35+, x86-64 or ARM64 vendor wheel. Install Qt runtime libraries listed in README. Configure SocketCAN or install CTRE's CANivore driver/runtime using their official instructions. Driver installation and CAN bitrate setup are intentionally outside the GUI: the app does not change your OS network configuration.

Windows: Windows 10/11 x64 with a supported CTRE CANivore runtime for local hardware. Network diagnostics needs no local CAN adapter.

macOS: vendor universal2 SDK requires macOS 13+; local simulation or remote diagnostics. CTRE's SDK does not support local hardware on macOS. The application is not codesigned or notarized.

Build a directory bundle on the platform where it will run:

```sh
uv sync --frozen
uv run python tools/build.py
```

Linux/Windows: run the executable inside `dist/PantherTunerX`. macOS also produces an app bundle. Do not move the executable out of its accompanying directory. Bundles contain Python, Qt, pyqtgraph, and the installed CTRE native libraries. Review THIRD_PARTY_NOTICES before distribution. CI uploads bundles as artifacts; it does not publish releases, install system packages outside its runner, or claim signed installers.

For development use `QT_QPA_PLATFORM=offscreen` on headless Linux. Qt's offscreen plugin renders the actual widget tree; it is not a substitute for testing window-system integration on a physical desktop.
