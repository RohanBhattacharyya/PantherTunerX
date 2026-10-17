"""Phoenix Diagnostics HTTP adapter, verified with CTRE Phoenix 26.3.0.

See docs/protocol.md for captures, safety rules, and compatibility limits.
"""

import copy
import math
import time

import httpx

from ..buffered import PlotCursor
from ..configuration import Configuration
from ..controls import encode_control
from ..models import Device, DeviceError, PlotBatch, Sample, Signal, TunerError
from ..protocol import checked_response, encode_payload

CONTROL_TIMEOUT = 0.5


class DiagnosticsBackend:
    def __init__(
        self,
        host: str = "172.22.11.2",
        port: int = 1250,
        timeout: float = 3,
        client: httpx.Client | None = None,
    ):
        # Accept hosts only, not arbitrary URL paths or embedded credentials.
        if not host or any(c in host for c in "/?#@"):
            raise TunerError("Enter a hostname or IP address without a URL or path")
        if not 1 <= port <= 65535:
            raise TunerError("Port must be between 1 and 65535")
        address = f"[{host}]" if ":" in host and not host.startswith("[") else host
        self.client = client or httpx.Client(
            base_url=f"http://{address}:{port}", timeout=timeout, trust_env=False, follow_redirects=False
        )
        self.version = "Disconnected"
        self.latency_ms = 0.0
        self.started = time.monotonic()
        self.simulated = False
        self.plot_cursors = {}
        self.plot_subscriptions = {}
        self.plot_capacity = 1000
        self.control_catalogs = {}
        self.latencies = []

    def request(self, action: str, device: Device | None = None, *, payload=None, **params) -> dict:
        query = {"action": action, **params}
        if device:
            query.update(model=device.model, id=device.id, canbus=device.bus)
        start = time.monotonic()
        try:
            if payload is None:
                response = self.client.get("/", params=query)
            else:
                # CTRE's actual protocol: base64 data delimited by $@$, NOT multipart JSON.
                body, headers = encode_payload(payload)
                response = self.client.post(
                    "/",
                    params=query,
                    content=body,
                    headers=headers,
                )
            response.raise_for_status()
            result = response.json()
        except (httpx.HTTPError, ValueError) as e:
            raise TunerError(f"{action}: {e}. Check target, port, and Phoenix Diagnostics Server.") from e
        self.latency_ms = (time.monotonic() - start) * 1000
        self.latencies = (self.latencies + [self.latency_ms])[-30:]
        return checked_response(action, result)

    def connect(self):
        info = self.request("getversion")
        self.version = str(info.get("Version", "Unknown"))
        return info

    def discover(self) -> list[Device]:
        result = self.request("getdevices")
        try:
            devices = [Device.from_wire(d) for d in result["DeviceArray"]]
            if any("simulated" in d.status.casefold() for d in devices):
                self.simulated = True
            return devices
        except (KeyError, ValueError, TypeError) as e:
            raise TunerError("Invalid device discovery response") from e

    def signals(self, device: Device) -> list[Signal]:
        result = self.request("getsignals", device)
        return [
            Signal(int(s["Id"]), s["Name"], s.get("Units", ""), s.get("Summary", ""))
            for s in result.get("Signals", [])
        ]

    def sample(self, device: Device, signal_ids: list[int]) -> Sample:
        if not signal_ids:
            return Sample(time.monotonic() - self.started, {})
        result = self.request("getsignalvalue", device, signals=",".join(map(str, signal_ids)))
        values = {}
        for key, value in result.get("Values", {}).items():
            if isinstance(value, (float, int)) and math.isfinite(value):
                values[int(key)] = float(value)
        return Sample(
            time.monotonic() - self.started,
            values,
            "CTRE simulation poll" if self.simulated else "diagnostics poll",
        )

    def self_test(self, device: Device) -> dict:
        values = self.request("decoratedselftest", device)["SelfTest"]
        names = {str(s.id): s.name for s in self.signals(device)}
        return {
            "device": device.name,
            "timestamp": time.time(),
            "source": "CTRE simulation" if self.simulated else "Phoenix Diagnostics",
            "signals": [
                {"id": key, "name": names.get(key, f"SPN {key}"), **value} for key, value in values.items()
            ],
        }

    def buffered_samples(self, device: Device, signal_ids: list[int]) -> PlotBatch:
        """Fetch all retained plot records, without latest-value polling or decimation.

        The server returns BEFORE updating subscriptions/capacity. Prime new selections
        to exclude stale records from a previous session, then deduplicate overlaps.
        """
        selected = tuple(sorted(set(signal_ids)))
        result = self.request(
            "plotpro", device, signals=",".join(map(str, selected)), resolution=self.plot_capacity
        )
        cursor = self.plot_cursors.setdefault(device.key, PlotCursor())
        first = device.key not in self.plot_subscriptions
        batch = cursor.decode(result, prime=first, simulated=self.simulated)
        self.plot_subscriptions[device.key] = selected
        return batch if selected else PlotBatch([])

    def stop_plot(self, device: Device):
        self.buffered_samples(device, [])
        self.plot_subscriptions.pop(device.key, None)

    def controls(self, device: Device) -> dict:
        catalog = self.request("getcontrols", device).get("Controls", {})
        if not isinstance(catalog, dict):
            raise TunerError("Invalid control request catalog")
        self.control_catalogs[device.key] = catalog
        return catalog

    def device_information(self, device: Device) -> dict:
        return self.request("deviceinformation", device).get("DeviceDetails", {})

    def control(self, device: Device, mode: str, values: dict, *, confirmed=False):
        if not confirmed:
            raise TunerError("Control output requires explicit enable and Apply")
        catalog = self.control_catalogs.get(device.key)
        if catalog is None:
            raise TunerError("Refresh the device's control requests first")
        params = encode_control(catalog, mode, values)
        return self.request("controlv2", device, controlmode=mode, controlen="true", **params)

    def control_channel(self) -> "DiagnosticsBackend":
        """A separate connection, so control requests never wait behind other I/O."""
        channel = DiagnosticsBackend(
            client=httpx.Client(
                base_url=self.client.base_url,
                timeout=CONTROL_TIMEOUT,
                trust_env=False,
                follow_redirects=False,
            )
        )
        channel.control_catalogs = dict(self.control_catalogs)
        channel.simulated = self.simulated
        return channel

    def stop_control(self, device: Device):
        return self.request("controlv2", device, controlmode="NeutralOut", controlen="false")

    def read_config(self, device: Device) -> Configuration:
        result = self.request("getconfigv2", device)
        if result.get("JsonVersion") != 2 or not isinstance(result.get("Device"), list):
            raise TunerError("Server does not support Phoenix configuration JSON version 2")
        return Configuration(device, result["Device"])

    def write_config(self, config: Configuration, *, confirmed: bool = False) -> Configuration:
        if not confirmed:
            raise TunerError("Configuration write requires explicit confirmation")
        config.validate_all()
        if not config.changes():
            return config
        self.assert_target(config.device)
        # Refresh first: never overwrite another client's intervening edits.
        current = self.read_config(config.device)
        if current.values() != config.baseline:
            raise TunerError(
                "Device configuration changed since refresh. Refresh and review your edits again."
            )
        groups = copy.deepcopy(config.groups)
        # Full schema is accepted by the server; baseline comparison protects all fields.
        self.request("setconfigv2", config.device, payload={"Device": groups, "JsonVersion": 2})
        # A successful configuration update can briefly interrupt device status.
        # Retry ONLY readback's known presence/freshness errors, with a deadline.
        # An uncertain POST, other errors, or HTTP timeouts are never repeated.
        deadline = time.monotonic() + 1
        while True:
            try:
                return self.read_config(config.device)
            except DeviceError as error:
                if error.code not in (-102, -1003) or time.monotonic() >= deadline:
                    raise
                time.sleep(0.05)

    def assert_target(self, device: Device):
        """HTTP mutations cannot uniquely address duplicate model/ID/bus tuples."""
        matches = [
            d for d in self.discover() if (d.bus, d.model, d.id) == (device.bus, device.model, device.id)
        ]
        if len(matches) != 1 or matches[0].key != device.key:
            raise TunerError(
                "Device is missing, replaced, or has a duplicate ID. Refresh discovery before writing."
            )

    def identify(self, device: Device, *, confirmed: bool = False):
        if not confirmed:
            raise TunerError("Blink also clears sticky faults; confirmation required")
        self.assert_target(device)
        return self.request("blink", device)

    def rename(self, device: Device, name: str, *, confirmed: bool = False):
        if not confirmed:
            raise TunerError("Device rename requires confirmation")
        if not name.strip() or len(name.encode("utf-8")) > 32:
            raise TunerError("Name must contain 1–32 UTF-8 bytes")
        self.assert_target(device)
        return self.request("setname", device, newname=name.strip())

    def set_id(self, device: Device, new_id: int, *, confirmed: bool = False):
        if not confirmed or type(new_id) is not int or not 0 <= new_id <= 62:
            raise TunerError("ID change requires confirmation and an integer from 0 to 62")
        self.assert_target(device)
        if any(d.bus == device.bus and d.id == new_id and d.key != device.key for d in self.discover()):
            raise TunerError("That ID is already used on this bus")
        return self.request("setid", device, newid=new_id)

    def close(self):
        self.client.close()
