import base64
import copy
import json

import httpx
import pytest

from panther_tuner.backends.diagnostics import DiagnosticsBackend
from panther_tuner.models import Device, TunerError


def backend_with(handler):
    return DiagnosticsBackend(
        client=httpx.Client(base_url="http://robot:1250", transport=httpx.MockTransport(handler))
    )


def test_current_protocol_model_and_signal_query(capture):
    device = Device.from_wire(capture("getdevices")["DeviceArray"][0])

    def handler(request):
        assert request.url.params["model"] == "Talon FX vers. C"
        assert request.url.params["signals"] == "1781,1782"
        return httpx.Response(200, json={"GeneralReturn": {"Error": 0}, "Values": {"1781": 12.2}})

    with backend_with(handler).client as client:
        b = DiagnosticsBackend(client=client)
        result = b.sample(device, [1781, 1782])
        assert result.values == {1781: 12.2}  # absent value is not fabricated


@pytest.mark.parametrize(
    "response",
    [
        {"GeneralReturn": {"Error": -120, "ErrorMessage": "Device not found"}},
        {},
        [],
    ],
)
def test_http_success_is_not_device_success(response):
    b = backend_with(lambda _: httpx.Response(200, json=response))
    with pytest.raises(TunerError):
        b.connect()
    b.close()


def test_timeout_is_reported_without_retry():
    calls = []

    def handler(request):
        calls.append(request)
        raise httpx.ReadTimeout("timed out", request=request)

    b = backend_with(handler)
    with pytest.raises(TunerError, match="timed out"):
        b.connect()
    assert len(calls) == 1
    b.close()


def test_custom_post_framing_and_confirmation(capture):
    config_doc = capture("getconfigv2")
    device = Device.from_wire(capture("getdevices")["DeviceArray"][0])
    seen = []

    def handler(request):
        seen.append(request)
        if request.url.params["action"] == "getdevices":
            return httpx.Response(200, json=capture("getdevices"))
        if request.method == "POST":
            assert request.content.startswith(b"$@$") and request.content.endswith(b"$@$")
            raw = base64.b64decode(request.content[3:-3])
            assert int(request.headers["X-Decoded-Size"]) == len(raw)
            payload = json.loads(raw)
            assert payload["Device"][0]["Configs"][2]["Value"] == 0.02
            config_doc["Device"] = payload["Device"]
        return httpx.Response(200, json=config_doc)

    b = backend_with(handler)
    config = b.read_config(device)
    config.set(1905, 0.02)
    with pytest.raises(TunerError, match="confirmation"):
        b.write_config(config)
    assert len(seen) == 1
    result = b.write_config(config, confirmed=True)
    assert result.values()[1905] == 0.02
    assert len([r for r in seen if r.method == "POST"]) == 1
    b.close()


def test_concurrent_external_edit_blocks_write(capture):
    doc = capture("getconfigv2")
    device = Device.from_wire(capture("getdevices")["DeviceArray"][0])
    posts = []

    def handler(request):
        if request.url.params["action"] == "getdevices":
            return httpx.Response(200, json=capture("getdevices"))
        if request.method == "POST":
            posts.append(request)
        return httpx.Response(200, json=copy.deepcopy(doc))

    b = backend_with(handler)
    config = b.read_config(device)
    config.set(1905, 0.02)
    doc["Device"][0]["Configs"][2]["Value"] = 0.03
    with pytest.raises(TunerError, match="changed since refresh"):
        b.write_config(config, confirmed=True)
    assert not posts
    b.close()


def test_admin_mutations_require_confirmation(capture):
    device = Device.from_wire(capture("getdevices")["DeviceArray"][0])
    calls = []
    b = backend_with(lambda r: calls.append(r))
    for operation in [
        lambda: b.identify(device),
        lambda: b.rename(device, "name"),
        lambda: b.set_id(device, 2),
    ]:
        with pytest.raises(TunerError):
            operation()
    assert not calls
    b.close()


@pytest.mark.parametrize("case", ["duplicate", "replaced", "missing"])
def test_ambiguous_or_replaced_device_cannot_be_mutated(capture, case):
    doc = capture("getdevices")
    device = Device.from_wire(doc["DeviceArray"][0])
    if case == "duplicate":
        clone = copy.deepcopy(doc["DeviceArray"][0])
        clone["SerialNo"] = "different device"
        doc["DeviceArray"].append(clone)
    elif case == "replaced":
        doc["DeviceArray"][0]["SerialNo"] = "different device"
    else:
        doc["DeviceArray"].clear()
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(200, json=doc)

    b = backend_with(handler)
    with pytest.raises(TunerError, match="missing, replaced, or has a duplicate"):
        b.identify(device, confirmed=True)
    assert all(r.url.params["action"] == "getdevices" for r in requests)
    b.close()


def test_write_timeout_is_not_retried(capture):
    device = Device.from_wire(capture("getdevices")["DeviceArray"][0])
    posts = []

    def handler(request):
        if request.method == "POST":
            posts.append(request)
            raise httpx.ReadTimeout("uncertain write", request=request)
        action = request.url.params["action"]
        return httpx.Response(200, json=capture(action))

    b = backend_with(handler)
    config = b.read_config(device)
    config.set(1905, 0.02)
    with pytest.raises(TunerError, match="uncertain write"):
        b.write_config(config, confirmed=True)
    assert len(posts) == 1
    b.close()


@pytest.mark.parametrize("code", [-102, -1003])
def test_successful_write_tolerates_transient_readback_without_rewriting(capture, code):
    doc = capture("getconfigv2")
    device = Device.from_wire(capture("getdevices")["DeviceArray"][0])
    posts = []
    readbacks = []

    def handler(request):
        if request.url.params["action"] == "getdevices":
            return httpx.Response(200, json=capture("getdevices"))
        if request.method == "POST":
            posts.append(request)
            doc["Device"] = json.loads(base64.b64decode(request.content[3:-3]))["Device"]
        elif posts:
            readbacks.append(request)
            if len(readbacks) == 1:
                return httpx.Response(
                    200, json={"GeneralReturn": {"Error": code, "ErrorMessage": "Temporarily unavailable"}}
                )
        return httpx.Response(200, json=doc)

    b = backend_with(handler)
    try:
        config = b.read_config(device)
        config.set(1905, 0.02)
        assert b.write_config(config, confirmed=True).values()[1905] == 0.02
        assert len(posts) == 1
        assert len(readbacks) == 2
    finally:
        b.close()


@pytest.mark.parametrize("failure", ["permanent", "timeout", "persistent-unavailable"])
def test_readback_failures_are_bounded_and_never_repeat_write(capture, failure):
    doc = capture("getconfigv2")
    device = Device.from_wire(capture("getdevices")["DeviceArray"][0])
    posts, readbacks = [], []

    def handler(request):
        if request.url.params["action"] == "getdevices":
            return httpx.Response(200, json=capture("getdevices"))
        if request.method == "POST":
            posts.append(request)
        elif posts:
            readbacks.append(request)
            if failure == "timeout":
                raise httpx.ReadTimeout("readback timed out", request=request)
            return httpx.Response(
                200,
                json={
                    "GeneralReturn": {
                        "Error": -102 if failure == "persistent-unavailable" else -120,
                        "ErrorMessage": "Readback failed",
                    }
                },
            )
        return httpx.Response(200, json=doc)

    b = backend_with(handler)
    try:
        config = b.read_config(device)
        config.set(1905, 0.02)
        with pytest.raises(TunerError):
            b.write_config(config, confirmed=True)
        assert len(posts) == 1
        assert len(readbacks) > 1 if failure == "persistent-unavailable" else len(readbacks) == 1
    finally:
        b.close()
