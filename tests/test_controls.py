import pytest

from panther_tuner.controls import encode_control
from panther_tuner.models import TunerError

CATALOG = {
    "DutyCycleOut": {
        "ConstructorParams": [
            {"Name": "Output", "Type": "double", "Min": "-1", "Max": "1"},
            {"Name": "EnableFOC", "Type": "bool"},
            {"Name": "Slot", "Type": "int", "Min": "0", "Max": "2"},
        ]
    }
}


def test_typed_request_encoding():
    assert encode_control(CATALOG, "DutyCycleOut", {"Output": 0.125, "EnableFOC": False, "Slot": 1}) == {
        "Output": "f_0.125",
        "EnableFOC": "b_False",
        "Slot": "i_1",
    }


@pytest.mark.parametrize(
    "field,value",
    [("Output", 1.1), ("Output", "nan"), ("Output", "inf"), ("Slot", 1.5), ("EnableFOC", "False")],
)
def test_invalid_request_rejected(field, value):
    values = {"Output": 0.1, "EnableFOC": False, "Slot": 1}
    values[field] = value
    with pytest.raises(TunerError):
        encode_control(CATALOG, "DutyCycleOut", values)


def test_unadvertised_modes_and_missing_fields_rejected():
    with pytest.raises(TunerError):
        encode_control(CATALOG, "Unknown", {})
    with pytest.raises(TunerError):
        encode_control(CATALOG, "DutyCycleOut", {"Output": 0.1})


def test_all_advertised_vendor_request_schemas_encode(capture):
    catalog = capture("getcontrols")["Controls"]
    assert len(catalog) == 44
    for mode, spec in catalog.items():
        values = {}
        for field in spec["ConstructorParams"]:
            kind = field["Type"]
            if kind == "bool":
                value = field.get("Default", "false") == "true"
            elif field.get("EnumValues"):
                value = field["EnumValues"][0]["Value"]
            else:
                value = field.get("Default", field.get("TunerMin", field.get("Min", 0)))
            values[field["Name"]] = value
        assert set(encode_control(catalog, mode, values)) == set(values)


def test_delayed_ipc_lease_message_cannot_reenable_after_stall():
    import time

    from panther_tuner.sdk_host import EnableLease

    lease = EnableLease()
    observed = []

    def stream():
        yield f"enable {time.monotonic() - 1}\n"
        observed.append(lease.active())
        yield f"enable {time.monotonic() + 0.25}\n"
        observed.append(lease.active())
        yield "disable\n"
        observed.append(lease.active())

    lease.read(stream())
    assert observed == [False, True, False]
    assert not lease.active()
