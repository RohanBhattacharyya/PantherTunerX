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


def test_control_editor_requires_enable_apply_and_stops_on_navigation(qtbot):
    from panther_tuner.models import Device

    w = MainWindow()
    qtbot.addWidget(w)
    calls = []

    class Backend:
        def assert_target(self, device):
            calls.append("verify")

        def control(self, device, mode, values, *, confirmed=False):
            assert confirmed
            calls.append((mode, values.copy()))
            return {}

        def stop_control(self, device):
            calls.append("stop")

        def close(self):
            pass

    w.backend = Backend()
    w.device = Device("Talon FX vers. C", 1, "", "Test", "26.3.0")
    w.discovery_timer.stop()
    w.poll_timer.stop()
    w.control_panel.set_catalog(
        {
            "DutyCycleOut": {
                "Summary": "Duty cycle",
                "ConstructorParams": [{"Name": "Output", "Type": "double", "Min": "-1", "Max": "1"}],
            }
        }
    )
    w.navigate(1)
    w.left_tabs.setCurrentIndex(1)
    w.control_panel.editors["Output"].setText("0.2")
    w.apply_control()
    assert not calls
    w.confirm = lambda *_: False
    w.arm_controls()
    assert not calls
    w.confirm = lambda *_: True
    w.arm_controls()
    qtbot.waitUntil(lambda: w.control_panel.armed)
    assert calls == ["verify"]
    w.apply_control()
    qtbot.waitUntil(lambda: any(isinstance(c, tuple) for c in calls))
    assert ("DutyCycleOut", {"Output": "0.2"}) in calls
    w.left_tabs.setCurrentIndex(2)
    qtbot.waitUntil(lambda: "stop" in calls)
    assert not w.control_panel.armed
    assert w.active_control is None
    count = len(calls)
    qtbot.wait(180)
    assert len(calls) == count
    w.close()


def test_stalled_control_request_stops_and_requires_rearming(qtbot):
    import time

    from panther_tuner.models import Device

    w = MainWindow()
    qtbot.addWidget(w)
    calls = []

    class Backend:
        def assert_target(self, device):
            pass

        def control(self, *args, **kwargs):
            calls.append("request")
            time.sleep(0.4)

        def stop_control(self, device):
            calls.append("stop")

        def close(self):
            pass

    w.backend = Backend()
    w.device = Device("Talon FX vers. C", 1, "", "Test", "26.3.0")
    w.discovery_timer.stop()
    w.poll_timer.stop()
    w.control_panel.set_catalog({"NeutralOut": {"ConstructorParams": []}})
    w.navigate(1)
    w.left_tabs.setCurrentIndex(1)
    w.confirm = lambda *_: True
    w.arm_controls()
    qtbot.waitUntil(lambda: w.control_panel.armed)
    w.apply_control()
    qtbot.waitUntil(lambda: not w.control_panel.armed)
    qtbot.waitUntil(lambda: "stop" in calls)
    qtbot.wait(200)
    assert calls == ["request", "stop"]
    assert "stalled" in w.control_panel.note.text()
    assert w.active_control is None
    w.close()


@pytest.mark.integration
def test_window_applies_and_stops_actual_vendor_simulated_output(qtbot, simulation):
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
        w.confirm = lambda *_: True
        w.arm_controls()
        qtbot.waitUntil(lambda: w.control_panel.armed)
        assert duty() == 0  # Arming alone must not activate output.
        w.apply_control()
        qtbot.waitUntil(lambda: 0.08 < duty() < 0.12, timeout=2000)
        w.control_panel.stop_requested.emit()
        qtbot.waitUntil(lambda: duty() == 0, timeout=2000)
        assert not w.control_panel.armed
    finally:
        w.stop_controls()
        simulation.enable_lease(False)
        simulation.stop_control(device)
        w.backend = None
        w.device = None
        w.close()
