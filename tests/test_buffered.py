import math

import pytest

from panther_tuner.buffered import PlotCursor
from panther_tuner.models import TunerError


def wire(start, end, offset=0):
    points = [
        {"Ordinal": n, "Timestamp": offset + n / 100, "Signals": {"1789": n / 10, "1790": None}}
        for n in range(start, end)
    ]
    return {"Count": len(points), "Points": points}


def test_overlapping_buffers_preserve_each_record_once():
    c = PlotCursor()
    c.decode(wire(0, 0), prime=True)
    batches = [c.decode(wire(0, 20)), c.decode(wire(0, 40)), c.decode(wire(20, 60))]
    records = [s for b in batches for s in b.samples]
    assert [s.ordinal for s in records] == list(range(60))
    assert records[-1].time == 0.59
    assert records[-1].values == {1789: 5.9}
    assert not c.decode(wire(20, 60)).samples
    assert all(b.missing == 0 for b in batches)


def test_overrun_is_counted_and_breaks_curve():
    c = PlotCursor()
    c.decode(wire(0, 5))
    b = c.decode(wire(10, 20))
    assert b.missing == 5
    assert b.samples[0].values == {}
    assert b.samples[1].ordinal == 10


def test_server_restart_starts_new_epoch():
    c = PlotCursor()
    c.decode(wire(0, 100, offset=10))
    b = c.decode(wire(0, 10))
    assert b.reset
    assert b.missing == 0
    assert b.samples[0].source == "server stream reset"
    assert b.samples[-1].epoch == 1


def test_new_subscription_excludes_previous_session():
    c = PlotCursor()
    assert not c.decode(wire(50, 100), prime=True).samples
    b = c.decode(wire(50, 110))
    assert [s.ordinal for s in b.samples] == list(range(100, 110))


@pytest.mark.parametrize("malform", ["count", "order", "value", "timestamp"])
def test_corrupt_response_never_advances_cursor(malform):
    c = PlotCursor()
    c.decode(wire(0, 5))
    w = wire(0, 10)
    if malform == "count":
        w["Count"] = 3
    elif malform == "order":
        w["Points"].reverse()
    elif malform == "value":
        w["Points"][-1]["Signals"]["1789"] = math.nan
    else:
        w["Points"][-1]["Timestamp"] = math.inf
    with pytest.raises(TunerError):
        c.decode(w)
    assert c.ordinal == 4


def test_captured_vendor_buffer(capture):
    response = capture("plotpro")
    result = PlotCursor().decode(response)
    assert len(result.samples) == response["Count"] == 50
    assert [s.ordinal for s in result.samples] == list(range(290, 340))
    assert result.samples[0].values[1789] == response["Points"][0]["Signals"]["1789"]


def test_restart_detected_even_if_new_stream_passed_old_ordinal():
    c = PlotCursor()
    c.decode(wire(0, 5, offset=10))
    b = c.decode(wire(0, 10))
    assert b.reset
    assert [s.ordinal for s in b.samples if s.values] == list(range(10))
    # A subscription reset can preserve the clock while restarting ordinals.
    b = c.decode(wire(0, 20, offset=30))
    assert b.reset
    assert len([s for s in b.samples if s.values]) == 20
