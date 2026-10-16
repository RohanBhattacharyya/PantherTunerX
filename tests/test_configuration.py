import copy
import json

import pytest

from panther_tuner.configuration import Configuration
from panther_tuner.models import Device, TunerError


@pytest.fixture
def config(capture):
    return Configuration(
        Device.from_wire(capture("getdevices")["DeviceArray"][0]), capture("getconfigv2")["Device"]
    )


def test_config_covers_captured_fields_and_changes(config):
    assert len(config.values()) == 100
    assert config.changes() == []
    config.set(1905, 0.02)
    assert config.changes() == [("Motor Output / Duty Cycle Neutral Deadband", 0, 0.02)]
    config.validate_all()  # default timesync 0 is outside nominal 50–500 range


@pytest.mark.parametrize("value", [float("nan"), float("inf"), -0.01, 0.26, "2"])
def test_bad_values_leave_original(config, value):
    with pytest.raises(TunerError):
        config.set(1905, value)
    assert not config.changes()


def test_enum_rejects_unknown(config):
    with pytest.raises(TunerError):
        config.set(1901, 100)


def test_import_is_atomic_and_model_bound(config, tmp_path):
    path = tmp_path / "config.json"
    config.save(str(path))
    doc = json.loads(path.read_text())
    doc["values"]["1905"] = 0.02
    doc["values"]["1901"] = 50
    path.write_text(json.dumps(doc))
    with pytest.raises(TunerError):
        config.load(str(path))
    assert not config.changes()
    doc["model"] = "other"
    path.write_text(json.dumps(doc))
    with pytest.raises(TunerError, match="selected device"):
        config.load(str(path))


def test_import_and_defaults_only_stage(config, tmp_path):
    original = copy.deepcopy(config.baseline)
    config.set(1905, 0.02)
    path = tmp_path / "config.json"
    config.save(str(path))
    config.defaults()
    assert config.values() == {int(f["SignalId"]): f["DefaultValue"] for _, f in config.fields()}
    config.load(str(path))
    assert config.values()[1905] == 0.02
    assert config.baseline == original
