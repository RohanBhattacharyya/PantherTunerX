import csv
import math

from panther_tuner.models import Sample, Signal
from panther_tuner.telemetry import TelemetryBuffer


def test_retention_gaps_and_csv(tmp_path):
    b = TelemetryBuffer(max_samples=3)
    for t in range(10):
        b.append(Sample(t, {1: t} if t != 8 else {}), timespan=2)
    assert [s.time for s in b.samples] == [7, 8, 9]
    assert math.isnan(b.series(1)[1][1])
    path = tmp_path / "trace.csv"
    b.export(str(path), [Signal(1, "Velocity", "rps")])
    with path.open() as f:
        rows = list(csv.reader(f))
    assert rows[0] == ["server_timestamp_s", "acquisition", "ordinal", "epoch", "Velocity [rps] (SPN 1)"]
    assert len(rows) == 11  # All records survive display-window eviction.
    assert rows[9][4] == ""
    assert rows[1][4] == "0"
    b.close()


def test_csv_preserves_earlier_signal_selections_and_epochs(tmp_path):
    b = TelemetryBuffer(max_samples=2)
    b.extend([Sample(0.1, {1: 1}, ordinal=10), Sample(0.2, {1: 2}, ordinal=11)], 1)
    b.extend([Sample(0.3, {}, "server stream reset", epoch=1), Sample(0.3, {2: 42}, ordinal=0, epoch=1)], 1)
    path = tmp_path / "all.csv"
    # Even an omitted catalog entry is exported, with an honest SPN fallback label.
    b.export(str(path), [Signal(2, "Voltage", "V")])
    with path.open() as f:
        rows = list(csv.reader(f))
    assert len(rows) == 5
    assert "SPN 1" in rows[0][4]
    assert rows[1][4:] == ["1", ""]
    assert rows[-1][2:] == ["0", "1", "", "42"]
    b.close()
