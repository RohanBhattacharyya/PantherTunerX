"""Stage the frozen Linux application or build native .deb/.rpm packages.

Uses native package builders, never installs into the running system, and keeps
all private Python/Qt/SDK dependencies inside /opt/panther-tuner-x.
"""

import argparse
import os
import platform
import re
import shutil
import struct
import subprocess
import sys
import tempfile
from pathlib import Path

import tomllib

ROOT = Path(__file__).resolve().parents[1]
NAME = "panther-tuner-x"
ARCHITECTURES = {62: ("amd64", "x86_64"), 183: ("arm64", "aarch64")}
DEB_DEPENDS = (
    "libc6 (>= 2.35), libstdc++6, libgl1, libegl1, libx11-6, libxext6, libxrender1, "
    "libxcb1, libxkbcommon-x11-0, libxcb-cursor0, libxcb-icccm4, libxcb-image0, "
    "libxcb-keysyms1, libxcb-render-util0, libfontconfig1, libfreetype6, libdbus-1-3, "
    "zlib1g, libusb-1.0-0"
)


def bundle_architecture(bundle: Path):
    binary = bundle / "PantherTunerX"
    if not binary.is_file() or not os.access(binary, os.X_OK) or not (bundle / "_internal").is_dir():
        raise ValueError("Build the complete Linux bundle first: uv run python tools/build.py")
    with binary.open("rb") as f:
        header = f.read(20)
    if len(header) != 20 or header[:6] != b"\x7fELF\x02\x01":
        raise ValueError("Expected a 64-bit little-endian Linux ELF executable")
    machine = struct.unpack_from("<H", header, 18)[0]
    if machine not in ARCHITECTURES:
        raise ValueError(f"Unsupported ELF architecture: {machine}")
    return ARCHITECTURES[machine]


def glibc_floor(bundle: Path):
    """Never advertise an older libc than the bundled host libraries require."""
    versions = {(2, 35)}
    for path in bundle.rglob("*"):
        if path.is_symlink() or not path.is_file():
            continue
        with path.open("rb") as stream:
            if stream.read(4) != b"\x7fELF":
                continue
            stream.seek(0)
            versions.update(tuple(map(int, v)) for v in re.findall(rb"GLIBC_(\d+)\.(\d+)", stream.read()))
    return ".".join(map(str, max(versions)))


def stage(bundle: Path, destdir: Path):
    bundle = bundle.resolve()
    destdir = destdir.resolve()
    bundle_architecture(bundle)
    if destdir == Path("/") or destdir.is_relative_to(bundle) or bundle.is_relative_to(destdir):
        raise ValueError("Choose a separate, empty staging directory")
    if destdir.exists() and any(destdir.iterdir()):
        raise ValueError("Staging directory must be empty; existing files will not be overwritten")
    if not (bundle / "licenses" / "CTRE_LICENSE.txt").is_file():
        raise ValueError("Bundle is missing vendor license notices; rebuild with tools/build.py")
    application = destdir / "opt" / NAME
    shutil.copytree(bundle, application, symlinks=True)
    launcher = destdir / "usr/bin/panther-tuner"
    launcher.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(ROOT / "packaging/linux/panther-tuner", launcher)
    desktop = destdir / "usr/share/applications/panther-tuner-x.desktop"
    desktop.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(ROOT / "packaging/linux/panther-tuner-x.desktop", desktop)
    licenses = destdir / "usr/share/licenses" / NAME
    shutil.copytree(bundle / "licenses", licenses)
    image_notices = ROOT / "src/panther_tuner/assets/devices"
    for name in ("README.md", "sources.json"):
        shutil.copyfile(image_notices / name, licenses / ("device-images-" + name))
    docs = destdir / "usr/share/doc" / NAME
    docs.mkdir(parents=True)
    shutil.copyfile(ROOT / "README.md", docs / "README.md")
    for name in ("installation.md", "hardware-validation.md", "protocol.md"):
        shutil.copyfile(ROOT / "docs" / name, docs / name)
    for path in [destdir, *destdir.rglob("*")]:
        if path.is_symlink():
            continue
        path.chmod(0o755 if path.is_dir() or path.stat().st_mode & 0o111 else 0o644)
    launcher.chmod(0o755)


def build_deb(bundle: Path, output: Path, version: str):
    builder = shutil.which("dpkg-deb")
    if not builder:
        raise RuntimeError("Building .deb packages requires dpkg-deb (Debian/Ubuntu: sudo apt install dpkg)")
    arch, _ = bundle_architecture(bundle)
    with tempfile.TemporaryDirectory(prefix="panther-deb-") as temp:
        root = Path(temp) / "root"
        stage(bundle, root)
        control = root / "DEBIAN"
        control.mkdir()
        size = sum(p.stat().st_size for p in root.rglob("*") if p.is_file() and not p.is_symlink())
        (control / "control").write_text(
            f"Package: {NAME}\nVersion: {version}\nArchitecture: {arch}\n"
            "Maintainer: Rohan Bhattacharyya <73246001+RohanBhattacharyya@users.noreply.github.com>\n"
            f"Installed-Size: {(size + 1023) // 1024}\nSection: electronics\nPriority: optional\n"
            f"Depends: {DEB_DEPENDS.replace('2.35', glibc_floor(bundle))}\n"
            "Homepage: https://github.com/RohanBhattacharyya/PantherTunerX\n"
            "Description: Desktop workbench for CTRE Phoenix 6 devices\n"
            " Discover, configure, diagnose, plot and explicitly control Phoenix devices.\n"
            " Includes private Python/Qt runtimes and isolated vendor simulation.\n"
        )
        target = output / f"{NAME}_{version}_{arch}.deb"
        subprocess.run([builder, "--root-owner-group", "-Zxz", "--build", str(root), str(target)], check=True)
        return target


def build_rpm(bundle: Path, output: Path, version: str):
    builder = shutil.which("rpmbuild")
    if not builder:
        raise RuntimeError("Building .rpm packages requires rpmbuild (Fedora: sudo dnf install rpm-build)")
    _, arch = bundle_architecture(bundle)
    with tempfile.TemporaryDirectory(prefix="panther-rpm-") as temp:
        top = Path(temp)
        for name in ("BUILD", "BUILDROOT", "RPMS", "SOURCES", "SPECS", "SRPMS"):
            (top / name).mkdir()
        stage(bundle, top / "SOURCES/root")
        template = (ROOT / "packaging/rpm/panther-tuner-x.spec.in").read_text()
        spec = top / "SPECS/panther-tuner-x.spec"
        spec.write_text(
            template.replace("@VERSION@", version)
            .replace("@ARCH@", arch)
            .replace("@GLIBC@", glibc_floor(bundle))
        )
        subprocess.run(
            [builder, "-bb", "--define", f"_topdir {top}", "--target", arch, str(spec)], check=True
        )
        packages = list((top / "RPMS").rglob("*.rpm"))
        if len(packages) != 1:
            raise RuntimeError("RPM builder did not produce exactly one application package")
        target = output / packages[0].name
        shutil.copyfile(packages[0], target)
        return target


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--format", choices=("stage", "deb", "rpm"), required=True)
    parser.add_argument("--bundle", type=Path, default=ROOT / "dist/PantherTunerX")
    parser.add_argument("--output", type=Path, default=ROOT / "dist/packages")
    parser.add_argument("--destdir", type=Path, help="Empty staging directory; required with --format stage")
    args = parser.parse_args()
    if sys.platform != "linux":
        parser.error("Build Linux packages on Linux")
    try:
        if args.format == "stage":
            if args.destdir is None:
                parser.error("--format stage requires --destdir")
            stage(args.bundle, args.destdir)
            print(f"Staged {NAME} in {args.destdir}")
        else:
            if args.destdir is not None:
                parser.error("--destdir is only valid with --format stage")
            version = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]["version"]
            if not re.fullmatch(r"\d+(?:\.\d+)*", version):
                raise ValueError("Native packaging currently requires a numeric release version")
            args.output.mkdir(parents=True, exist_ok=True)
            build = build_deb if args.format == "deb" else build_rpm
            print(f"Built {build(args.bundle, args.output.resolve(), version)} ({platform.machine()})")
    except (OSError, ValueError, RuntimeError, subprocess.CalledProcessError) as e:
        parser.exit(1, f"Packaging failed: {e}\n")


if __name__ == "__main__":
    main()
