import time

import pytest

from panther_tuner.backends.local import LocalBackend
from panther_tuner.models import TunerError

pytestmark = pytest.mark.integration


def test_all_vendor_simulated_models(simulation):
    devices = simulation.discover()
    assert len(devices) == 8
    for device in devices:
        assert device.status == "Simulated Device."
        assert device.firmware.startswith("26.3")
        assert simulation.signals(device)
        assert simulation.read_config(device).values()
        result = simulation.self_test(device)
        assert result["signals"]
        assert result["source"] == "CTRE simulation"


def test_actual_write_readback_telemetry_and_restore(simulation, tmp_path):
    device = next(d for d in simulation.discover() if d.id == 1)
    original = simulation.read_config(device)
    config = simulation.read_config(device)
    old = config.values()[1905]
    config.set(1905, 0.02 if old != 0.02 else 0.04)
    try:
        result = simulation.write_config(config, confirmed=True)
        assert result.values()[1905] != old
        result.save(str(tmp_path / "readback.json"))
        assert simulation.read_config(device).values() == result.values()
        signals = simulation.signals(device)
        position = next(s for s in signals if s.name == "Position")
        a = simulation.sample(device, [position.id])
        time.sleep(0.15)
        b = simulation.sample(device, [position.id])
        assert a.values[position.id] != b.values[position.id]
    finally:
        restore = simulation.read_config(device)
        for sid, value in original.values().items():
            restore.set(sid, value)
        simulation.write_config(restore, confirmed=True)


def test_simulation_refuses_existing_server(simulation):
    another = LocalBackend(True)
    try:
        with pytest.raises(TunerError, match="already in use"):
            another.connect()
    finally:
        another.close()


def test_vendor_admin(simulation):
    device = next(d for d in simulation.discover() if d.id == 2)
    simulation.identify(device, confirmed=True)
    simulation.rename(device, "Panther simulation", confirmed=True)
    renamed = next(d for d in simulation.discover() if d.id == 2)
    assert renamed.name == "Panther simulation"
    with pytest.raises(TunerError, match="already used"):
        simulation.set_id(renamed, 1, confirmed=True)


def test_vendor_simulation_reports_id_change_unsupported(simulation):
    device = next(d for d in simulation.discover() if d.id == 7)
    with pytest.raises(TunerError, match="Unable to set ID"):
        simulation.set_id(device, 9, confirmed=True)
    assert any(d.key == device.key for d in simulation.discover())


def test_configuration_write_roundtrip_each_device_family(simulation):
    tested = set()
    for device in simulation.discover():
        if device.model in tested:
            continue
        tested.add(device.model)
        config = simulation.read_config(device)
        group = next(g for g in config.groups if g["Name"] == "Custom Params")
        field = group["Configs"][0]
        sid, original = int(field["SignalId"]), field["Value"]
        config.set(sid, original + 1)
        try:
            result = simulation.write_config(config, confirmed=True)
            assert result.values()[sid] == original + 1
        finally:
            restore = simulation.read_config(device)
            restore.set(sid, original)
            assert simulation.write_config(restore, confirmed=True).values()[sid] == original
    assert len(tested) == 7


def test_vendor_buffer_retains_delayed_samples_and_deduplicates(simulation):
    device = next(d for d in simulation.discover() if d.id == 1)
    position = next(s.id for s in simulation.signals(device) if s.name == "Position")
    simulation.stop_plot(device)
    time.sleep(0.15)
    simulation.plot_cursors.pop(device.key, None)
    simulation.plot_subscriptions.pop(device.key, None)
    simulation.buffered_samples(device, [position])
    try:
        time.sleep(0.25)
        a = simulation.buffered_samples(device, [position])
        assert len(a.samples) >= 15, "Delayed fetch must retain intermediate server records"
        time.sleep(0.12)
        b = simulation.buffered_samples(device, [position])
        assert b.samples
        assert a.samples[-1].ordinal < b.samples[0].ordinal
        records = a.samples + b.samples
        assert len({s.ordinal for s in records}) == len(records)
        assert all(s.source == "CTRE simulation buffered" for s in records)
        assert all(position in s.values for s in records)
        assert not (a.missing or b.missing)
        # Intentionally shrink the native buffer, then prove lost ordinals are visible.
        simulation.plot_capacity = 10
        simulation.buffered_samples(device, [position])
        time.sleep(0.4)
        overflow = simulation.buffered_samples(device, [position])
        assert overflow.missing > 0
        assert any(not s.values for s in overflow.samples)
    finally:
        simulation.plot_capacity = 1000
        simulation.stop_plot(device)


def test_vendor_control_output_and_two_independent_watchdogs(simulation):
    device = next(d for d in simulation.discover() if d.id == 1)
    assert device.status == "Simulated Device."
    catalog = simulation.controls(device)
    assert "DutyCycleOut" in catalog
    assert simulation.device_information(device)["Frc Lock"] is False
    params = {
        f["Name"]: False if f["Type"] == "bool" else 0.1 for f in catalog["DutyCycleOut"]["ConstructorParams"]
    }
    duty_id = next(s.id for s in simulation.signals(device) if s.name == "DutyCycle")

    def duty():
        # A full self-test can take longer than the 250 ms enable lease on macOS.
        # Read just this signal so the assertion doesn't itself expire the
        # watchdog being tested; the GUI uses the same point-read path in tests.
        return simulation.sample(device, [duty_id]).values[duty_id]

    try:
        with pytest.raises(TunerError, match="explicit"):
            simulation.control(device, "DutyCycleOut", params)
        assert duty() == 0
        for _ in range(5):
            simulation.control(device, "DutyCycleOut", params, confirmed=True)
            simulation.enable_lease(True)
            time.sleep(0.06)
        assert 0.08 < duty() < 0.12
        # Lose the GUI enable lease, despite the last request being acknowledged.
        time.sleep(0.5)
        assert duty() == 0
        # Independently lose control HTTP heartbeats while continuing global enable.
        simulation.control(device, "DutyCycleOut", params, confirmed=True)
        for _ in range(20):
            simulation.enable_lease(True)
            time.sleep(0.05)
        assert duty() == 0
        # Explicit Stop must also neutralize output while enable continues.
        for _ in range(3):
            simulation.control(device, "DutyCycleOut", params, confirmed=True)
            simulation.enable_lease(True)
            time.sleep(0.05)
        assert duty() > 0.08
        simulation.stop_control(device)
        time.sleep(0.1)
        assert duty() == 0
    finally:
        simulation.enable_lease(False)
        simulation.stop_control(device)
