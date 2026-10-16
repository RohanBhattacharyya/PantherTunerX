import json
import os
import time
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture(scope="session", autouse=True)
def isolated_settings(tmp_path_factory):
    from PySide6.QtCore import QSettings

    QSettings.setDefaultFormat(QSettings.Format.IniFormat)
    QSettings.setPath(
        QSettings.Format.IniFormat, QSettings.Scope.UserScope, str(tmp_path_factory.mktemp("qt-settings"))
    )


@pytest.fixture
def capture():
    def read(action):
        return json.loads((Path(__file__).parent / "fixtures" / (action + ".json")).read_text())

    return read


@pytest.fixture(scope="session")
def simulation():
    from panther_tuner.backends.local import LocalBackend

    backend = LocalBackend(True)
    try:
        backend.connect()
        for _ in range(100):
            devices = backend.discover()
            if len(devices) == 8:
                break
            if backend.process.poll() is not None:
                backend.log.seek(0)
                pytest.fail(backend.log.read().decode())
            time.sleep(0.1)
        assert len(devices) == 8, "Vendor simulation did not enumerate eight devices"
        yield backend
    finally:
        backend.close()
