import importlib.util
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest

from panther_tuner.backends.diagnostics import DiagnosticsBackend

_spec = importlib.util.spec_from_file_location(
    "smoke_bundle", Path(__file__).parents[1] / "tools/smoke_bundle.py"
)
smoke = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(smoke)


def test_startup_probe_restores_normal_device_request_timeout(capture):
    observed = []

    def respond(request):
        action = request.url.params["action"]
        observed.append((action, request.extensions["timeout"]["read"]))
        payload = capture(action)
        if action == "getdevices":
            # The recorded fixture predates the eight-device simulation fleet.
            device = payload["DeviceArray"][0]
            payload["DeviceArray"] = [dict(device, ID=i) for i in range(1, 9)]
        return httpx.Response(200, json=payload)

    client = httpx.Client(base_url="http://localhost:1250", transport=httpx.MockTransport(respond), timeout=3)
    backend = DiagnosticsBackend(client=client)
    process = SimpleNamespace(poll=lambda: None)
    try:
        devices = smoke.wait_for_devices(backend, process)
        backend.read_config(devices[0])
        assert observed == [("getversion", 0.5), ("getdevices", 0.5), ("getconfigv2", 3)]
    finally:
        backend.close()


@pytest.mark.parametrize("exited", [False, True])
def test_failed_startup_restores_timeout(exited):
    backend = DiagnosticsBackend()
    original_timeout = backend.client.timeout
    process = SimpleNamespace(poll=lambda: 1 if exited else None, returncode=1)
    try:
        with pytest.raises(RuntimeError, match="exited with status 1" if exited else "did not start"):
            smoke.wait_for_devices(backend, process, timeout=1 if exited else 0)
        assert backend.client.timeout == original_timeout
    finally:
        backend.close()
