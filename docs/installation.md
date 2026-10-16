# Installation and packaging

## Supported platforms

| Platform | Network diagnostics | Local simulation | Direct CAN hardware |
|---|---|---|---|
| Linux x86-64 / ARM64 | Yes | Yes | SocketCAN / CANivore, with CTRE runtime and drivers |
| Windows 10/11 x64 | Yes | Yes | CANivore, with CTRE runtime and drivers |
| macOS 13+ | Yes | Yes | Not supported by CTRE |

Hardware behavior remains unverified. Application tests use the official Phoenix 26.3.0 simulator. Source installs require Python 3.10–3.13; **3.12.14 is the packaged runtime**. The current Phoenix dependency cannot run on Python 3.14. Native Linux packages include their own Python/Qt runtime and do not install Python packages into the distribution's environment.

## Arch Linux: makepkg

```sh
sudo pacman -S --needed base-devel git uv desktop-file-utils
git clone https://github.com/RohanBhattacharyya/PantherTunerX.git
cd PantherTunerX
makepkg -si
```

Run `makepkg` as your ordinary user. `-s` asks pacman to install missing build/runtime dependencies; `-i` installs the completed package using pacman. The result is `panther-tuner-x-git-<version>-<architecture>.pkg.tar.zst`.

The root [PKGBUILD](../PKGBUILD) follows `main` and calculates a VCS package version. Preparation downloads Python 3.12.14 and dependencies verified against `uv.lock` into the makepkg source directory. The build then runs offline and creates a frozen application; `check()` runs tests that need neither hardware nor port 1250. Allow roughly 2 GB of working space plus the compressed package. There is no download, pip invocation, or SDK server startup during package installation.

The resulting package installs:

- `/usr/bin/panther-tuner`: launcher, preserving command-line arguments.
- `/usr/share/applications/panther-tuner-x.desktop`: application menu entry and Simulation action.
- `/opt/panther-tuner-x/`: private runtime, application, SDK, and offline device imagery.
- `/usr/share/licenses/panther-tuner-x/`: application, vendor, dependency, and image notices.
- `/usr/share/doc/panther-tuner-x/`: usage, installation, protocol, and hardware guidance.

Update:

```sh
git pull
makepkg -si
```

Remove:

```sh
sudo pacman -Rns panther-tuner-x-git
```

This is a repository-provided recipe, not an AUR or official repository publication. AUR helpers cannot install it by name until someone publishes and maintains an AUR package. For an already downloaded Arch package, use `sudo pacman -U ./panther-tuner-x-git-*.pkg.tar.zst`.

## Ubuntu / Debian: APT

Download the Linux packages artifact from a completed [CI run](https://github.com/RohanBhattacharyya/PantherTunerX/actions/workflows/ci.yml) and extract it. Use the `.deb` matching your architecture (`amd64` or `arm64`):

```sh
sudo apt install ./panther-tuner-x_*.deb
panther-tuner
```

Keep only the desired package version in the directory when using a wildcard. APT resolves the declared system libraries. Install a newer `.deb` with the same command to upgrade. Remove with `sudo apt remove panther-tuner-x`.

CI builds on Ubuntu 22.04 for a glibc 2.35 baseline. Packages built on a newer distribution can require a newer glibc; the builder scans bundled ELF files and records the higher requirement. Do not copy a package built on a rolling distribution to an older Debian/Ubuntu system. Use the baseline container described below instead.

These are local packages; no hosted APT repository, automatic update channel, or signing key is provided.

## Fedora: DNF

Download and extract the Linux packages artifact, then install the `.rpm` matching your architecture (`x86_64` or `aarch64`):

```sh
sudo dnf install ./panther-tuner-x-*.rpm
panther-tuner
```

DNF resolves the system libraries. Install a newer package to upgrade; remove with `sudo dnf remove panther-tuner-x`. Packages are unsigned local builds, not a configured DNF repository. SDK/Qt libraries stay private to the application instead of advertising system-wide library provides.

## Source installs

Install [uv](https://docs.astral.sh/uv/getting-started/installation/), clone the repository, and run:

```sh
uv sync --frozen --python 3.12.14
uv run panther-tuner
uv run panther-tuner --simulate
```

The default launch is disconnected. Only `--simulate` creates isolated simulated devices. Existing network servers can be accessed with `--host <hostname-or-IP>`.

### Linux runtime libraries

Ubuntu 22.04+:

```sh
sudo apt install libegl1 libopengl0 libgl1 libxcb-cursor0 libxkbcommon-x11-0 \
  libxcb-icccm4 libxcb-image0 libxcb-keysyms1 libxcb-render-util0 \
  libfontconfig1 libfreetype6 libdbus-1-3 libusb-1.0-0
```

Arch native package dependencies are declared in the PKGBUILD. For other distributions use the corresponding Qt/XCB/OpenGL runtime libraries. Linux wheels require glibc 2.35 or later; musl-based distributions such as Alpine are not supported by the vendor SDK.

For direct CAN, configure SocketCAN or install CTRE's CANivore runtime/drivers according to [CTRE's official instructions](https://v6.docs.ctr-electronics.com/en/stable/docs/installation/installation-nonfrc.html). Package installation does not configure CAN interfaces, change bitrates, or create privileged services.

### Windows and macOS

Use the same source commands with uv. Windows local hardware requires the CTRE CANivore runtime. macOS supports local simulation and remote diagnostics. CI builds unsigned platform bundles; macOS builds are not notarized.

## Building native packages

All packaging runs as an ordinary user into staging directories. The package manager is only needed to install the finished files.

### Build on your Linux distribution

```sh
uv sync --frozen --python 3.12.14
uv run python tools/build.py
```

Build a Debian package where `dpkg-deb` is available:

```sh
uv run python tools/package_linux.py --format deb
```

Build an RPM where `rpmbuild` is available (Fedora: `sudo dnf install rpm-build`):

```sh
uv run python tools/package_linux.py --format rpm
```

Packages are written to `dist/packages/`. Architecture comes from the actual ELF executable; only Linux x86-64 and ARM64 are accepted. To use an existing bundle, pass `--bundle /path/to/PantherTunerX`. These tools package a bundle; they do not cross-compile it or turn a Windows/macOS build into a Linux package.

For another package manager, stage the common filesystem layout:

```sh
uv run python tools/package_linux.py --format stage --destdir /tmp/panther-package-root
```

The destination must be empty. Nothing is installed into the live filesystem. Runtime library links are preserved, file permissions are normalized, and vendor notices are required.

### Build against the Ubuntu 22.04 baseline

A container avoids accidentally bundling libraries that require a rolling host's newer glibc. Docker is optional; native Arch `makepkg` does not require it.

```sh
docker build -t panther-linux-builder -f packaging/linux/Dockerfile .
docker run --rm --user "$(id -u):$(id -g)" -v "$PWD:/work" panther-linux-builder \
  bash -c 'uv sync --frozen --python 3.12.14 && uv run python tools/build.py && uv run python tools/package_linux.py --format deb && uv run python tools/package_linux.py --format rpm'
```

The image contains native Debian and RPM tooling. Source stays in your checkout; temporary Python/dependency caches live inside the disposable container. Output is written to `dist/` as your user. Allow network access during dependency synchronization.

### Portable desktop bundles

```sh
uv run python tools/build.py
```

Linux and Windows produce `dist/PantherTunerX/`; macOS also produces an app bundle. Keep the executable with its accompanying directory. Bundles include Python, Qt, the SDK, images, and license notices. Packaging does not imply that redistribution rights for third-party components have changed; preserve [third-party notices](../THIRD_PARTY_NOTICES.md).

CI builds desktop bundles on Linux, Windows, and macOS, creates `.deb`/`.rpm` artifacts on Linux, and builds the Arch recipe separately. Pinned dependencies and the lockfile make inputs repeatable; byte-for-byte reproducible or signed packages are not claimed.

## Troubleshooting

- **No menu entry:** log out/in or refresh your desktop's application cache. `panther-tuner` should also work from a terminal.
- **Qt platform plugin errors:** install the runtime libraries above; use `QT_DEBUG_PLUGINS=1 panther-tuner` to identify a missing library.
- **Python 3.14 errors:** use the native package or explicitly select Python 3.12.14 with uv.
- **Port 1250 already in use:** stop the other local server or choose Network diagnostics to connect to it. Simulation never silently attaches to an existing server.
- **No CAN devices:** check power, bus configuration, termination, drivers, and the Diagnostics Server. Network connections need a running robot/controller program.

Headless tests use `QT_QPA_PLATFORM=offscreen`; this renders the actual Qt widget tree but does not validate a physical desktop/window system. See [validation](validation.md) and [hardware checks](hardware-validation.md) for the remaining limits.
