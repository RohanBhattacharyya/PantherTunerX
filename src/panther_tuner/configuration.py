"""Configuration documents, validation and review; independent of Qt and transport."""

import copy
import json
import math
from datetime import datetime, timezone
from pathlib import Path

from .models import Device, TunerError


class Configuration:
    def __init__(self, device: Device, groups: list[dict]):
        self.device = device
        self.groups = copy.deepcopy(groups)
        self.baseline = self.values()

    def fields(self):
        for group in self.groups:
            for field in group["Configs"]:
                yield group, field

    def values(self) -> dict[int, float]:
        return {int(f["SignalId"]): f["Value"] for _, f in self.fields()}

    def set(self, signal_id: int, value):
        for _, f in self.fields():
            if int(f["SignalId"]) == signal_id:
                self.validate(f, value)
                f["Value"] = value
                return
        raise TunerError(f"Unknown configuration signal {signal_id}")

    @staticmethod
    def validate(f: dict, value):
        if isinstance(value, bool):
            value = int(value)
        if not isinstance(value, (int, float)) or not math.isfinite(value):
            raise TunerError(f"{f['Name']}: enter a finite number")
        enums = f.get("EnumValues", [])
        if enums and value not in [x["Value"] for x in enums]:
            raise TunerError(f"{f['Name']}: select a supported enum value")
        if f.get("Type", "").lower() in ("bool", "boolean") and value not in (0, 1):
            raise TunerError(f"{f['Name']}: expected true or false")
        if f.get("Type", "").lower() in ("int", "int32", "uint32", "integer") and value != int(value):
            raise TunerError(f"{f['Name']}: expected an integer")
        # CTRE metadata contains defaults outside nominal ranges (e.g. 0 disables timesync).
        if value != f.get("DefaultValue") and not enums:
            if not f.get("MinValue", -math.inf) <= value <= f.get("MaxValue", math.inf):
                raise TunerError(f"{f['Name']}: expected {f.get('MinValue')} to {f.get('MaxValue')}")

    def changes(self) -> list[tuple[str, float, float]]:
        return [
            (f"{g['Name']} / {f['Name']}", self.baseline[int(f["SignalId"])], f["Value"])
            for g, f in self.fields()
            if self.baseline[int(f["SignalId"])] != f["Value"]
        ]

    def defaults(self):
        for _, f in self.fields():
            self.set(int(f["SignalId"]), f["DefaultValue"])

    def validate_all(self):
        for _, f in self.fields():
            self.validate(f, f["Value"])

    def save(self, path: str):
        Path(path).write_text(
            json.dumps(
                {
                    "format": "panther-tuner-config",
                    "version": 1,
                    "model": self.device.model,
                    "firmware": self.device.firmware,
                    "created": datetime.now(timezone.utc).isoformat(),
                    "values": {str(k): v for k, v in self.values().items()},
                },
                indent=2,
                allow_nan=False,
            ),
            encoding="utf-8",
        )

    def load(self, path: str):
        doc = json.loads(Path(path).read_text(encoding="utf-8"))
        if doc.get("format") != "panther-tuner-config" or doc.get("version") != 1:
            raise TunerError("Unsupported configuration file format")
        if doc.get("model") != self.device.model:
            raise TunerError(f"File is for {doc.get('model')}, selected device is {self.device.model}")
        candidate = copy.deepcopy(self)
        for key, value in doc["values"].items():
            candidate.set(int(key), value)
        self.groups = candidate.groups
