"""Bounded display window plus a complete, transactional on-disk capture."""

import csv
import json
import math
import sqlite3
import tempfile
from collections import deque
from pathlib import Path

from .models import Sample, Signal, TunerError


class TelemetryBuffer:
    def __init__(self, max_samples: int = 60000):
        self.samples: deque[Sample] = deque(maxlen=max_samples)
        self.directory = tempfile.TemporaryDirectory(prefix="panther-capture-")
        self.path = Path(self.directory.name) / "capture.sqlite3"
        self.connection = sqlite3.connect(self.path)
        self.connection.execute(
            "CREATE TABLE samples (time REAL, source TEXT, ordinal INTEGER, epoch INTEGER, vals TEXT)"
        )
        self.total = 0
        self.captured_ids = set()

    def append(self, sample: Sample, timespan: float):
        self.extend([sample], timespan)

    def extend(self, samples: list[Sample], timespan: float):
        if not samples:
            return
        try:
            with self.connection:
                self.connection.executemany(
                    "INSERT INTO samples VALUES (?, ?, ?, ?, ?)",
                    [
                        (s.time, s.source, s.ordinal, s.epoch, json.dumps(s.values, allow_nan=False))
                        for s in samples
                    ],
                )
        except (sqlite3.Error, OSError) as e:
            raise TunerError(f"Capture could not be saved; acquisition paused: {e}") from e
        self.total += len(samples)
        self.captured_ids.update(sid for s in samples for sid in s.values)
        self.samples.extend(samples)
        while self.samples and self.samples[0].time < samples[-1].time - timespan:
            self.samples.popleft()

    def series(self, signal_id: int):
        return ([s.time for s in self.samples], [s.values.get(signal_id, math.nan) for s in self.samples])

    def clear(self):
        with self.connection:
            self.connection.execute("DELETE FROM samples")
        self.samples.clear()
        self.total = 0
        self.captured_ids.clear()

    def export(self, path: str, signals: list[Signal]):
        catalog = {s.id: s for s in signals}
        signals = (
            [catalog.get(sid, Signal(sid, f"SPN {sid}")) for sid in sorted(self.captured_ids)]
            if self.captured_ids
            else signals
        )
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(
                ["server_timestamp_s", "acquisition", "ordinal", "epoch"]
                + [f"{s.name} [{s.units}] (SPN {s.id})" for s in signals]
            )
            for timestamp, source, ordinal, epoch, raw in self.connection.execute(
                "SELECT * FROM samples ORDER BY rowid"
            ):
                values = json.loads(raw)
                writer.writerow(
                    [timestamp, source, ordinal, epoch] + [values.get(str(s.id), "") for s in signals]
                )

    def close(self):
        self.connection.close()
        self.directory.cleanup()
