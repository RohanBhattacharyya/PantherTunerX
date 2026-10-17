import pytest
from PySide6.QtWidgets import QLineEdit

from panther_tuner.configuration import Configuration
from panther_tuner.models import Device
from panther_tuner.ui.config_editor import ConfigEditor
from panther_tuner.ui.window import MainWindow


def test_startup_is_disconnected(qtbot):
    w = MainWindow()
    qtbot.addWidget(w)
    assert w.backend is None
    assert w.device is None
    assert w.mode_badge.text() == "DISCONNECTED"
    w.close()


def test_config_editor_stages_only_and_validates(qtbot, capture):
    config = Configuration(
        Device.from_wire(capture("getdevices")["DeviceArray"][0]), capture("getconfigv2")["Device"]
    )
    w = ConfigEditor()
    qtbot.addWidget(w)
    w.set_config(config)
    row = next(
        r for r in range(w.fields.rowCount()) if "Duty Cycle Neutral Deadband" in w.fields.item(r, 0).text()
    )
    editor = w.fields.cellWidget(row, 1)
    assert isinstance(editor, QLineEdit)
    editor.setText("0.02")
    editor.editingFinished.emit()
    assert w.apply_button.isEnabled()
    assert config.changes()
    editor.setText("nan")
    editor.editingFinished.emit()
    assert not w.apply_button.isEnabled()
    # Editing another valid field must not hide the invalid field or enable Apply.
    another = w.fields.cellWidget(
        next(r for r in range(w.fields.rowCount()) if "Peak Forward" in w.fields.item(r, 0).text()), 1
    )
    another.setText("0.5")
    another.editingFinished.emit()
    assert not w.apply_button.isEnabled()
    w.groups.setCurrentRow(1)
    w.groups.setCurrentRow(0)
    assert w.fields.cellWidget(row, 1).text() == "nan"
    assert not w.apply_button.isEnabled()


def test_cancel_apply_makes_no_device_request(qtbot, capture):
    w = MainWindow()
    qtbot.addWidget(w)
    config = Configuration(
        Device.from_wire(capture("getdevices")["DeviceArray"][0]), capture("getconfigv2")["Device"]
    )

    class NoCalls:
        def write_config(self, *_args, **_kwargs):
            raise AssertionError("Cancelled apply must not write")

        def close(self):
            pass

    w.backend = NoCalls()
    w.device = config.device
    w.config_editor.set_config(config)
    config.set(1905, 0.02)
    w.confirm = lambda *_: False
    w.apply_config()
    assert not w.operation
    config.defaults()
    w.config_editor.config = None
    w.close()


@pytest.mark.integration
def test_window_simulation_workflow(qtbot, simulation, tmp_path):
    # The window attaches to this test's already isolated vendor server as a network client.
    w = MainWindow()
    qtbot.addWidget(w)
    w.target.setCurrentText("127.0.0.1")
    w.toggle_connection()
    qtbot.waitUntil(lambda: w.backend is not None, timeout=10000)
    assert len(w.devices) == 8
    w.open_device(next(d for d in w.devices if d.id == 1))
    qtbot.waitUntil(lambda: w.config_editor.config is not None, timeout=10000)
    qtbot.waitUntil(lambda: len(w.plotter.buffer.samples) >= 2, timeout=10000)
    assert w.config_editor.groups.count() == 18
    w.self_test()
    qtbot.waitUntil(lambda: w.test_result is not None, timeout=10000)
    assert w.test_table.rowCount() > 40
    path = tmp_path / "data.csv"
    w.plotter.buffer.export(str(path), w.plotter.selected())
    assert path.stat().st_size > 50
    w.disconnect()
    assert w.backend is None
    w.close()


class RecordingControlBackend:
    """Records control traffic with arrival times; no HTTP channel of its own."""

    def __init__(self):
        import threading

        self.calls = []
        self.lock = threading.Lock()

    def record(self, kind, values=None):
        import time

        with self.lock:
            self.calls.append((time.monotonic(), kind, dict(values or {})))

    def kinds(self):
        with self.lock:
            return [kind for _, kind, _ in self.calls]

    def assert_target(self, device):
        self.record("verify")

    def control(self, device, mode, values, *, confirmed=False):
        assert confirmed
        self.record(mode, values)

    def stop_control(self, device):
        self.record("stop")

    def close(self):
        pass


def control_window(qtbot, backend):
    from panther_tuner.models import Device

    w = MainWindow()
    qtbot.addWidget(w)
    w.backend = backend
    w.device = Device("Talon FX vers. C", 1, "", "Test", "26.3.0")
    w.discovery_timer.stop()
    w.poll_timer.stop()
    w.control_panel.set_catalog(
        {
            "DutyCycleOut": {
                "ConstructorParams": [{"Name": "Output", "Type": "double", "Min": "-1", "Max": "1"}]
            }
        }
    )
    w.navigate(1)
    w.left_tabs.setCurrentIndex(1)
    w.control_panel.editors["Output"].setText("0.2")
    return w


def enabled_window(qtbot, backend):
    w = control_window(qtbot, backend)
    w.control_panel.enable_button.click()
    qtbot.waitUntil(lambda: "DutyCycleOut" in backend.kinds())
    return w


def test_enable_toggle_sends_continuously_applies_edits_live_and_disables(qtbot):
    backend = RecordingControlBackend()
    w = control_window(qtbot, backend)
    panel = w.control_panel
    assert panel.enable_button.text() == "DISABLED"
    assert panel.enable_button.objectName() == "disabled"
    panel.editors["Output"].setText("0.3")
    panel.editors["Output"].editingFinished.emit()
    qtbot.wait(100)
    assert not backend.calls  # Editing while disabled sends nothing.
    panel.enable_button.click()
    assert panel.output_enabled
    assert panel.enable_button.text() == "ENABLED"
    assert panel.enable_button.objectName() == "enabled"
    qtbot.waitUntil(lambda: backend.kinds().count("DutyCycleOut") >= 5)
    assert backend.kinds()[0] == "verify"
    assert backend.calls[1][2] == {"Output": "0.3"}
    panel.editors["Output"].setText("-0.4")
    panel.editors["Output"].editingFinished.emit()
    qtbot.waitUntil(lambda: backend.calls[-1][2] == {"Output": "-0.4"})
    # Selecting plot signals keeps control enabled, unlike leaving the device.
    w.left_tabs.setCurrentIndex(2)
    qtbot.wait(150)
    assert panel.output_enabled
    panel.enable_button.click()
    assert not panel.output_enabled
    assert panel.enable_button.text() == "DISABLED"
    qtbot.waitUntil(lambda: not w.heartbeats)
    count = len(backend.calls)
    qtbot.wait(150)
    assert len(backend.calls) == count
    assert backend.kinds()[-1] == "stop"
    assert backend.kinds().count("stop") == 1
    w.close()


def test_leaving_the_device_disables_control(qtbot):
    backend = RecordingControlBackend()
    w = enabled_window(qtbot, backend)
    w.navigate(0)
    assert not w.control_panel.output_enabled
    assert w.active_control is None
    qtbot.waitUntil(lambda: backend.kinds()[-1] == "stop")
    w.close()


def test_slow_and_failed_requests_retry_without_disabling(qtbot):
    import time

    from panther_tuner.models import TunerError

    class FlakyBackend(RecordingControlBackend):
        def control(self, *args, **kwargs):
            attempt = self.kinds().count("attempt")
            self.record("attempt")
            if attempt == 1:
                time.sleep(0.4)
            elif attempt in (2, 3, 4):
                raise TunerError("controlv2: timed out")
            super().control(*args, **kwargs)

    backend = FlakyBackend()
    w = enabled_window(qtbot, backend)
    qtbot.waitUntil(lambda: "retrying" in w.control_panel.note.text())
    assert w.control_panel.output_enabled
    qtbot.waitUntil(lambda: w.control_panel.note.text() == "Sending DutyCycleOut")
    assert "resumed after" in w.log.toPlainText()
    assert w.control_panel.output_enabled
    w.close()
    assert backend.kinds()[-1] == "stop"


def test_control_heartbeat_does_not_wait_behind_other_io(qtbot):
    """The server holds a request over the robot program's for only ~200 ms."""
    import time

    from panther_tuner.ui.heartbeat import HOLD

    backend = RecordingControlBackend()
    w = enabled_window(qtbot, backend)
    # A slow telemetry/discovery request occupies the ordered I/O worker.
    w.worker.submit(lambda: time.sleep(0.8), lambda *_: None)
    qtbot.wait(800)
    assert w.control_panel.output_enabled
    times = [t for t, kind, _ in backend.calls if kind == "DutyCycleOut"]
    assert len(times) >= 12
    assert max(b - a for a, b in zip(times, times[1:])) < HOLD
    w.close()


def test_gui_stall_pauses_requests_until_the_gui_responds(qtbot):
    backend = RecordingControlBackend()
    w = enabled_window(qtbot, backend)
    w.control_timer.stop()  # The GUI stops feeding its liveness deadline.
    qtbot.waitUntil(lambda: "not responding" in w.control_panel.note.text(), timeout=3000)
    count = backend.kinds().count("DutyCycleOut")
    qtbot.wait(200)
    assert backend.kinds().count("DutyCycleOut") == count
    assert w.control_panel.output_enabled
    w.control_timer.start()
    qtbot.waitUntil(lambda: backend.kinds().count("DutyCycleOut") > count + 3)
    w.close()


def test_missing_target_cannot_be_enabled(qtbot):
    from panther_tuner.models import TunerError

    class MissingBackend(RecordingControlBackend):
        def assert_target(self, device):
            raise TunerError("Device is missing, replaced, or has a duplicate ID")

    backend = MissingBackend()
    w = control_window(qtbot, backend)
    w.control_panel.enable_button.click()
    qtbot.waitUntil(lambda: not w.control_panel.output_enabled)
    assert "missing" in w.control_panel.note.text()
    assert "DutyCycleOut" not in backend.kinds()
    w.close()


def test_control_lapse_is_reported(qtbot):
    import time

    class SlowBackend(RecordingControlBackend):
        def control(self, *args, **kwargs):
            super().control(*args, **kwargs)
            if self.kinds().count("DutyCycleOut") == 2:
                time.sleep(0.22)

    backend = SlowBackend()
    w = enabled_window(qtbot, backend)
    qtbot.waitUntil(lambda: "gap" in w.log.toPlainText())
    assert w.control_panel.output_enabled
    w.close()
    assert backend.kinds()[-1] == "stop"


@pytest.mark.integration
def test_window_enables_edits_and_disables_actual_vendor_simulated_output(qtbot, simulation):
    w = MainWindow()
    qtbot.addWidget(w)
    device = next(d for d in simulation.discover() if d.id == 1)
    assert device.status == "Simulated Device."
    # Reuse the isolated session host; the window must not own its cleanup.
    w.backend = simulation
    w.discovery_timer.stop()
    try:
        w.open_device(device)
        qtbot.waitUntil(lambda: "DutyCycleOut" in w.control_panel.catalog, timeout=10000)
        w.plotter.toggle_pause()
        w.left_tabs.setCurrentIndex(1)
        w.control_panel.mode.setCurrentText("DutyCycleOut")
        w.control_panel.editors["Output"].setText("0.1")
        w.control_panel.editors["EnableFOC"].setChecked(False)
        duty_id = next(s.id for s in w.plotter.signals if s.name == "DutyCycle")

        def duty():
            return simulation.sample(device, [duty_id]).values[duty_id]

        assert duty() == 0
        w.control_panel.enable_button.click()
        qtbot.waitUntil(lambda: 0.08 < duty() < 0.12, timeout=2000)
        w.control_panel.editors["Output"].setText("0.2")
        w.control_panel.editors["Output"].editingFinished.emit()
        qtbot.waitUntil(lambda: 0.18 < duty() < 0.22, timeout=2000)
        w.control_panel.enable_button.click()
        qtbot.waitUntil(lambda: duty() == 0, timeout=2000)
        assert not w.control_panel.output_enabled
    finally:
        w.stop_controls()
        simulation.enable_lease(False)
        simulation.stop_control(device)
        w.backend = None
        w.device = None
        w.close()
