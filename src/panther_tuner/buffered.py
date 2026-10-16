"""Sequence-aware decoder for Phoenix's overlapping plotpro ring-buffer responses."""

import math

from .models import PlotBatch, Sample, TunerError


class PlotCursor:
    def __init__(self):
        self.ordinal = None
        self.timestamp = None
        self.epoch = 0

    def decode(self, response: dict, *, prime=False, simulated=False) -> PlotBatch:
        points = response.get("Points")
        if not isinstance(points, list) or response.get("Count") != len(points):
            raise TunerError("Invalid buffered plot response: point count does not match payload")
        decoded = []
        try:
            for point in points:
                ordinal, timestamp = point["Ordinal"], point["Timestamp"]
                if type(ordinal) is not int or ordinal < 0 or not math.isfinite(timestamp):
                    raise ValueError("invalid ordinal or timestamp")
                values = {}
                for key, value in point["Signals"].items():
                    if value is None:
                        continue
                    if not isinstance(value, (int, float)) or not math.isfinite(value):
                        raise ValueError("invalid signal value")
                    values[int(key)] = float(value)
                decoded.append((ordinal, float(timestamp), values))
            if any(b[0] <= a[0] or b[1] < a[1] for a, b in zip(decoded, decoded[1:])):
                raise ValueError("nonmonotonic point sequence")
        except (KeyError, ValueError, TypeError, AttributeError) as e:
            raise TunerError(f"Invalid buffered plot record: {e}") from e
        if not decoded:
            if prime:
                self.ordinal, self.timestamp = -1, None
                self.epoch += 1
            return PlotBatch([])
        if prime:
            self.ordinal, self.timestamp = decoded[-1][:2]
            self.epoch += 1
            return PlotBatch([])
        reset = (
            self.ordinal is not None and decoded[-1][0] <= self.ordinal and decoded[-1][1] > self.timestamp
        )
        # A server restart can also reset its timestamp origin.
        reset = reset or (self.timestamp is not None and decoded[-1][1] < self.timestamp)
        # A new stream can already have passed the old ordinal before our next
        # fetch. An overlapping ordinal with a new timestamp identifies reuse.
        reset = reset or (
            self.timestamp is not None
            and any(
                number == self.ordinal and timestamp != self.timestamp for number, timestamp, _ in decoded
            )
        )
        ordinal = None if reset else self.ordinal
        epoch = self.epoch + int(reset)
        missing = 0
        samples = []
        for number, timestamp, values in decoded:
            if ordinal is not None and number <= ordinal:
                continue
            if ordinal is not None and number != ordinal + 1:
                missing += number - ordinal - 1
                samples.append(Sample(timestamp, {}, "server buffer overrun", epoch=epoch))
            elif reset and not samples:
                samples.append(Sample(timestamp, {}, "server stream reset", epoch=epoch))
            samples.append(
                Sample(
                    timestamp,
                    values,
                    "CTRE simulation buffered" if simulated else "Phoenix buffered",
                    number,
                    epoch,
                )
            )
            ordinal = number
        if samples:
            self.ordinal, self.timestamp, self.epoch = ordinal, decoded[-1][1], epoch
        return PlotBatch(samples, missing, reset)
