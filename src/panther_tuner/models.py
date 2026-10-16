"""Transport-independent domain objects. Missing data is never replaced with zero."""

from dataclasses import dataclass, field
from typing import Any


class TunerError(Exception):
    """A communication, capability or validation error suitable for presentation."""


@dataclass(frozen=True)
class Device:
    model: str
    id: int
    bus: str
    name: str
    firmware: str
    serial: str = ""
    status: str = ""
    raw: dict[str, Any] = field(default_factory=dict, compare=False)

    @property
    def key(self) -> str:
        return f"{self.bus}/{self.model}/{self.id}/{self.serial}"

    @classmethod
    def from_wire(cls, d: dict) -> "Device":
        return cls(
            str(d["Model"]),
            int(d["ID"]),
            str(d.get("CANbus", "")),
            str(d.get("Name") or d["Model"]),
            str(d.get("CurrentVers", "Unknown")),
            str(d.get("SerialNo", "")),
            str(d.get("SoftStatus", "Unknown")),
            d,
        )


@dataclass(frozen=True)
class Signal:
    id: int
    name: str
    units: str = ""
    summary: str = ""


@dataclass(frozen=True)
class Sample:
    time: float
    values: dict[int, float]
    source: str = "poll"
    ordinal: int | None = None
    epoch: int = 0


@dataclass(frozen=True)
class PlotBatch:
    samples: list[Sample]
    missing: int = 0
    reset: bool = False
