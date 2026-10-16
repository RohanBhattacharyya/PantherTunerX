"""Build on the target OS. Libraries remain dynamically linked in an onedir bundle."""

import importlib.metadata
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    command = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--windowed",
        "--name",
        "PantherTunerX",
        "--paths",
        str(ROOT / "src"),
        "--collect-all",
        "phoenix6",
        "--copy-metadata",
        "phoenix6",
        "--hidden-import",
        "panther_tuner.sdk_host",
        "--add-data",
        str(ROOT / "src" / "panther_tuner" / "assets") + ":panther_tuner/assets",
        "--exclude-module",
        "PySide6.QtWebEngineCore",
        "--exclude-module",
        "PySide6.QtWebEngineWidgets",
        str(ROOT / "tools" / "launcher.py"),
    ]
    subprocess.run(command, cwd=ROOT, check=True)
    notices = ROOT / "dist" / "PantherTunerX" / "licenses"
    notices.mkdir(exist_ok=True, parents=True)
    for name in ["LICENSE", "THIRD_PARTY_NOTICES.md"]:
        shutil.copy2(ROOT / name, notices / name)
    shutil.copy2(ROOT / "docs" / "licenses" / "CTRE_LICENSE.txt", notices / "CTRE_LICENSE.txt")
    for package in [
        "phoenix6",
        "PySide6",
        "shiboken6",
        "numpy",
        "pyqtgraph",
        "httpx",
        "httpcore",
        "certifi",
        "anyio",
        "idna",
    ]:
        dist = importlib.metadata.distribution(package)
        destination = notices / package
        destination.mkdir(exist_ok=True)
        for file in dist.files or []:
            if "license" in str(file).lower() or "copying" in str(file).lower():
                source = Path(dist.locate_file(file))
                if source.is_file():
                    relative = Path(str(file).replace("..", "parent"))
                    target = destination / relative
                    target.parent.mkdir(exist_ok=True, parents=True)
                    shutil.copy2(source, target)
    app_resources = ROOT / "dist" / "PantherTunerX.app" / "Contents" / "Resources"
    if app_resources.exists():
        shutil.copytree(notices, app_resources / "licenses", dirs_exist_ok=True)
    print("Bundle created in dist/PantherTunerX. Review licenses before distributing.")


if __name__ == "__main__":
    main()
