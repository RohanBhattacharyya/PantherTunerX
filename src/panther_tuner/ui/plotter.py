"""Tuner-style signal browser and multi-axis buffered plot workspace."""

import pyqtgraph as pg
from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QHBoxLayout,
    QHeaderView,
    QLineEdit,
    QSpinBox,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..models import PlotBatch, Sample
from ..telemetry import TelemetryBuffer
from .common import button, label
from .flow import FlowLayout
from .icons import icon
from .theme import ACCENT

COLORS = [ACCENT, "#a7c7e7", "#cdb4db", "#b8d8ba", "#f4c9a8", "#f2b8c6"]


class Plotter(QWidget):
    selection_changed = Signal()
    pause_changed = Signal(bool)
    export_requested = Signal()

    def __init__(self):
        super().__init__()
        self.signals = []
        self.curves = {}
        self.axes = []
        self.views = []
        self.buffer = TelemetryBuffer()
        self.paused = False
        self.resume_gap = False
        self.device_name = "Device"
        self.missing = 0
        self.signal_panel = QWidget()
        sl = QVBoxLayout(self.signal_panel)
        sl.setContentsMargins(12, 4, 12, 0)
        sl.setSpacing(5)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search signals")
        self.search.addAction(icon("search"), QLineEdit.ActionPosition.TrailingPosition)
        self.search.textChanged.connect(self.filter)
        sl.addWidget(self.search)
        self.signal_list = QTreeWidget()
        self.signal_list.setObjectName("signals")
        self.signal_list.setHeaderHidden(True)
        self.signal_list.setColumnCount(2)
        self.signal_list.setIndentation(18)
        self.signal_list.header().setStretchLastSection(False)
        self.signal_list.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.signal_list.header().setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        self.signal_list.setColumnWidth(1, 27)
        self.signal_list.itemChanged.connect(self.update_selection)
        sl.addWidget(self.signal_list)
        self.items = {}
        root = QVBoxLayout(self)
        root.setContentsMargins(5, 3, 16, 2)
        root.setSpacing(0)
        top = FlowLayout(9)
        self.pause_button = button("Ⅱ Pause", self.toggle_pause, True)
        top.addWidget(self.pause_button)
        self.follow = QCheckBox("Horizontal Tracking")
        self.follow.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        self.follow.setChecked(True)
        top.addWidget(self.follow)
        self.span = QSpinBox()
        self.span.setRange(1, 60)
        self.span.setValue(10)
        self.span.setFixedWidth(46)
        self.span.setButtonSymbols(QSpinBox.ButtonSymbols.NoButtons)
        self.interval = QSpinBox()
        self.interval.setRange(20, 2000)
        self.interval.setValue(50)
        self.interval.setFixedWidth(62)
        self.interval.setButtonSymbols(QSpinBox.ButtonSymbols.NoButtons)
        for name, spin in [("Timespan (m):", self.span), ("Update rate (ms):", self.interval)]:
            group = QWidget()
            group_layout = QHBoxLayout(group)
            group_layout.setContentsMargins(0, 0, 0, 0)
            group_layout.setSpacing(6)
            group_layout.addWidget(label(name))
            group_layout.addWidget(spin)
            top.addWidget(group)
        top.addWidget(button("Export", self.export_requested.emit, True))
        top.addStretch()
        top.addWidget(button("Clear Plot", self.clear, True))
        top.addWidget(button("Reset Zoom", self.reset_zoom, True))
        root.addLayout(top)
        pg.setConfigOptions(antialias=True, foreground="#e6e6e6")
        self.canvas = pg.GraphicsLayoutWidget()
        self.canvas.setBackground("#1c1b1f")
        self.canvas.scene().sigMouseMoved.connect(self.hover)
        self.canvas.ci.layout.setContentsMargins(0, 0, 0, 0)
        self.canvas.ci.layout.setSpacing(0)
        self.canvas.setMinimumHeight(180)
        root.addWidget(self.canvas, 1)
        self.stats = label("", "muted")
        self.stats.setVisible(False)
        self.integrity = label("Buffered acquisition · server timestamps", "integrity")
        root.addWidget(self.integrity)
        self.cursor = label("", "muted")
        self.cursor.setFixedHeight(20)
        root.addWidget(self.cursor)
        self.rebuild_axes()

    def set_signals(self, signals):
        self.signals = sorted(signals, key=lambda s: s.name.casefold())
        self.signal_list.blockSignals(True)
        self.signal_list.clear()
        self.items.clear()
        self.buffer.clear()
        self.missing = 0
        groups = {}
        defaults = {"Velocity", "StatorCurrent", "Yaw", "DistanceMeters"}
        for s in self.signals:
            name = s.name
            parent = None
            if "_" in name:
                prefix, name = name.split("_", 1)
                if prefix not in groups:
                    groups[prefix] = QTreeWidgetItem(self.signal_list, [prefix])
                parent = groups[prefix]
            item = QTreeWidgetItem(
                parent or self.signal_list, [name + ("\n" + s.units if s.units else ""), ""]
            )
            item.setData(0, Qt.ItemDataRole.UserRole, s.id)
            item.setIcon(0, icon("minus"))
            item.setToolTip(0, s.summary)
            item.setSizeHint(0, QSize(0, 44 if s.units else 34))
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(1, Qt.CheckState.Checked if s.name in defaults else Qt.CheckState.Unchecked)
            self.items[s.id] = item
        self.signal_list.blockSignals(False)
        self.update_selection()

    def selected(self):
        return [s for s in self.signals if self.items[s.id].checkState(1) == Qt.CheckState.Checked]

    def update_selection(self, *_):
        self.rebuild_axes()
        self.selection_changed.emit()

    def rebuild_axes(self):
        for view in self.views[1:]:
            self.canvas.scene().removeItem(view)
        self.canvas.clear()
        self.curves, self.axes, self.views = {}, [], []
        chosen = self.selected()
        self.plot = pg.PlotItem()
        self.plot.hideAxis("left")
        self.plot.showGrid(x=True, y=False, alpha=0.28)
        self.plot.setMenuEnabled(True)
        self.plot.getViewBox().sigRangeChangedManually.connect(lambda _: self.follow.setChecked(False))
        self.canvas.addItem(self.plot, row=0, col=len(chosen))
        for i, s in enumerate(chosen):
            color = COLORS[i % len(COLORS)]
            view = self.plot.getViewBox() if i == 0 else pg.ViewBox()
            if i:
                self.canvas.scene().addItem(view)
                view.setXLink(self.plot.getViewBox())
            axis = pg.AxisItem("left", pen="#999999", textPen="#e5e5e5")
            axis.setLabel(
                f"{self.device_name} - {s.name}", color=color, **{"font-size": "16px", "font-weight": "bold"}
            )
            axis.linkToView(view)
            axis.setWidth(72)
            axis.enableAutoSIPrefix(False)
            self.canvas.addItem(axis, row=0, col=i)
            curve = pg.PlotDataItem(pen=pg.mkPen(color, width=1.4), connect="finite", autoDownsample=True)
            view.addItem(curve)
            self.curves[s.id] = curve
            self.views.append(view)
            self.axes.append(axis)
        self.plot.getViewBox().sigResized.connect(self.sync_views)
        self.plot.getAxis("bottom").setStyle(maxTickLevel=0)
        self.sync_views()
        self.render()

    def sync_views(self):
        for view in self.views[1:]:
            view.setGeometry(self.plot.getViewBox().sceneBoundingRect())
            view.linkedViewChanged(self.plot.getViewBox(), view.XAxis)

    def filter(self, text):
        text = text.casefold()
        for s in self.signals:
            item = self.items[s.id]
            item.setHidden(text not in (s.name + " " + s.units).casefold())
            if text and not item.isHidden() and item.parent():
                item.parent().setExpanded(True)
        for i in range(self.signal_list.topLevelItemCount()):
            item = self.signal_list.topLevelItem(i)
            if item.childCount():
                item.setHidden(all(item.child(j).isHidden() for j in range(item.childCount())))

    def add_batch(self, batch: PlotBatch):
        if self.paused or not batch.samples:
            return
        samples = batch.samples
        if self.resume_gap:
            samples = [Sample(samples[0].time, {}, "intentional pause", epoch=samples[0].epoch)] + samples
            self.resume_gap = False
        self.buffer.extend(samples, self.span.value() * 60)
        self.missing += batch.missing
        if batch.reset:
            # A restarted server can have a different timestamp origin; keep all
            # epochs on disk and restart only the display window.
            self.buffer.samples.clear()
            self.buffer.samples.extend(samples)
        self.integrity.setText(
            f"Buffered · {self.buffer.total:,} records · "
            + (
                f"{self.missing:,} MISSING RECORDS — buffer overrun"
                if self.missing
                else "No sequence gaps detected"
            )
        )
        self.integrity.setProperty("error", bool(self.missing))
        self.integrity.setStyleSheet("color: #ff8d82;" if self.missing else "color: #b6b5ba;")
        self.render()

    def add_sample(self, sample):
        self.add_batch(PlotBatch([sample]))

    def render(self):
        for sid, curve in self.curves.items():
            curve.setData(*self.buffer.series(sid))
        if self.buffer.samples and self.follow.isChecked():
            latest = self.buffer.samples[-1].time
            first = max(self.buffer.samples[0].time, latest - self.span.value() * 60)
            self.plot.setXRange(first, max(first + 1, latest), padding=0.02)

    def toggle_pause(self):
        self.paused = not self.paused
        self.pause_button.setText("▶ Play" if self.paused else "Ⅱ Pause")
        if not self.paused:
            self.resume_gap = True
        self.pause_changed.emit(self.paused)

    def clear(self):
        self.buffer.clear()
        self.missing = 0
        self.render()
        self.integrity.setText("Plot cleared · buffered acquisition")

    def reset_zoom(self):
        self.follow.setChecked(True)
        for view in self.views:
            view.enableAutoRange()
        self.render()

    def hover(self, point):
        if not self.buffer.samples:
            return
        x = self.plot.getViewBox().mapSceneToView(point).x()
        sample = min(self.buffer.samples, key=lambda s: abs(s.time - x))
        self.cursor.setText(
            "  ·  ".join(
                [f"{sample.time:.6f} s"]
                + [
                    f"{s.name}: {sample.values[s.id]:.6g} {s.units}"
                    for s in self.selected()
                    if s.id in sample.values
                ]
            )
        )
