"""Render actual Qt screens backed by CTRE simulation (no fixture readings)."""

import argparse
import os
import time
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication

from panther_tuner.ui.theme import STYLE
from panther_tuner.ui.window import MainWindow


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path("docs/images"))
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    QSettings.setDefaultFormat(QSettings.Format.IniFormat)
    QSettings.setPath(QSettings.Format.IniFormat, QSettings.Scope.UserScope, "/tmp/panther-preview-settings")
    app = QApplication([])
    app.setStyle("Fusion")
    app.setStyleSheet(STYLE)
    window = MainWindow()
    window.show()

    def until(condition, seconds=20):
        deadline = time.monotonic() + seconds
        while not condition():
            if time.monotonic() > deadline:
                raise RuntimeError("Timed out rendering preview")
            app.processEvents()
            time.sleep(0.01)

    try:
        window.connection_mode.setCurrentIndex(2)
        window.toggle_connection()
        until(lambda: len(window.devices) == 8)
        app.processEvents()
        window.grab().save(str(args.output / "devices.png"))
        window.open_device(next(d for d in window.devices if d.id == 1))
        until(lambda: len(window.plotter.buffer.samples) > 70)
        window.grab().save(str(args.output / "workspace.png"))
        window.left_tabs.setCurrentIndex(1)
        app.processEvents()
        window.grab().save(str(args.output / "control.png"))
        window.left_tabs.setCurrentIndex(0)
        window.tabs.setCurrentIndex(0)
        window.self_test()
        until(lambda: window.test_result is not None)
        window.grab().save(str(args.output / "self-test.png"))
        window.left_tabs.setCurrentIndex(2)
        window.tabs.setCurrentIndex(1)
        window.resize(1040, 720)
        app.processEvents()
        window.grab().save(str(args.output / "compact.png"))
    finally:
        window.close()


if __name__ == "__main__":
    main()
