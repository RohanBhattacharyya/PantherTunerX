"""Archive desktop bundles without losing Unix executable bits or framework links."""

import argparse
import platform
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def archive_bundle(dist: Path, system: str, machine: str):
    root = dist / ("PantherTunerX.app" if system == "darwin" else "PantherTunerX")
    if not root.is_dir():
        raise ValueError(f"Desktop bundle does not exist: {root}")
    system_name = {"linux": "linux", "darwin": "macos", "win32": "windows"}[system]
    architecture = {"amd64": "x86_64", "aarch64": "arm64"}.get(machine.lower(), machine.lower())
    name = dist / f"PantherTunerX-{system_name}-{architecture}"
    return Path(
        shutil.make_archive(
            str(name), "zip" if system == "win32" else "gztar", root_dir=dist, base_dir=root.name
        )
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dist", type=Path, default=ROOT / "dist")
    args = parser.parse_args()
    print(archive_bundle(args.dist, sys.platform, platform.machine()))


if __name__ == "__main__":
    main()
