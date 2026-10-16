"""Staged control request editor. Editing never sends an actuator command."""

import math

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QLineEdit,
    QScrollArea,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from ..controls import encode_control
from .common import button, label


class ControlPanel(QWidget):
    arm_requested = Signal()
    apply_requested = Signal()
    stop_requested = Signal()

    def __init__(self):
        super().__init__()
        self.catalog = {}
        self.editors = {}
        self.armed = False
        root = QVBoxLayout(self)
        root.setContentsMargins(14, 16, 14, 10)
        top = QHBoxLayout()
        self.mode = QComboBox()
        self.mode.currentTextChanged.connect(self.show_mode)
        self.enable_button = button("DISABLED", self.toggle_arm)
        self.enable_button.setObjectName("danger")
        top.addWidget(self.enable_button, 1)
        root.addLayout(top)
        self.frc_status = label("FRC lock: unknown", "muted")
        root.addWidget(self.frc_status)
        root.addWidget(self.mode)
        self.summary = label("Select a device to read its supported control requests.", "callout", True)
        self.summary.setMargin(12)
        root.addWidget(self.summary)
        self.note = label("Output is disabled. Editing parameters only stages a request.", "muted", True)
        root.addWidget(self.note)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.form_widget = QWidget()
        self.form = QFormLayout(self.form_widget)
        self.form.setContentsMargins(0, 8, 0, 8)
        self.form.setSpacing(12)
        self.scroll.setWidget(self.form_widget)
        root.addWidget(self.scroll, 1)
        actions = QHBoxLayout()
        self.apply_button = button("Apply control request", self.apply_requested.emit, True)
        self.apply_button.setEnabled(False)
        actions.addWidget(self.apply_button)
        self.stop_button = button("■ Stop", self.stop_requested.emit)
        self.stop_button.setObjectName("danger")
        actions.addWidget(self.stop_button)
        root.addLayout(actions)

    def toggle_arm(self):
        (self.stop_requested if self.armed else self.arm_requested).emit()

    def set_armed(self, armed):
        self.armed = armed
        self.enable_button.setText("ENABLED · Stop" if armed else "DISABLED")
        self.apply_button.setEnabled(armed and bool(self.catalog))
        self.mode.setEnabled(not armed)
        self.note.setText(
            "Armed. Press Apply to send the staged request. Stop neutralizes output."
            if armed
            else "Output is disabled. Editing parameters only stages a request."
        )

    def set_catalog(self, catalog):
        self.set_armed(False)
        self.catalog = catalog
        self.mode.clear()
        self.mode.addItems(sorted(catalog))
        if "DutyCycleOut" in catalog:
            self.mode.setCurrentText("DutyCycleOut")
        self.enable_button.setEnabled(bool(catalog))
        if not catalog:
            self.summary.setText("This device/server does not advertise control requests.")

    def show_mode(self, mode):
        while self.form.rowCount():
            self.form.removeRow(0)
        self.editors.clear()
        entry = self.catalog.get(mode, {})
        self.summary.setText(entry.get("Summary", "") or "")
        requirements = []
        if entry.get("RequiresPro"):
            requirements.append("Requires Phoenix Pro")
        if entry.get("RequiresCANivore"):
            requirements.append("Requires CANivore")
        if requirements:
            self.summary.setText(self.summary.text() + "\n" + " · ".join(requirements))
        self.summary.setToolTip(entry.get("Description", "") or "")
        for f in entry.get("ConstructorParams", []):
            kind = f["Type"]
            if kind == "bool":
                editor = QCheckBox()
                editor.setChecked(str(f.get("Default", "false")).lower() == "true")
            elif f.get("EnumValues"):
                editor = QComboBox()
                for item in f["EnumValues"]:
                    editor.addItem(item["Name"], item["Value"])
            else:
                editor = QLineEdit(str(f.get("Default", "0")))
            editor.setToolTip(
                (f.get("Description") or "")
                + f"\nRange: {f.get('TunerMin', f.get('Min', 'unspecified'))} to "
                + str(f.get("TunerMax", f.get("Max", "unspecified")))
            )
            name = label(f["Name"] + ("\n" + f["Units"] if f.get("Units") else ""))
            name.setToolTip(editor.toolTip())
            self.form.addRow(name, editor)
            self.editors[f["Name"]] = editor
            if f["Name"] == "Output" and kind == "double" and "Min" in f and "Max" in f:
                lo, hi = float(f.get("TunerMin", f["Min"])), float(f.get("TunerMax", f["Max"]))
                slider = QSlider(Qt.Orientation.Horizontal)
                slider.setRange(0, 1000)
                slider.setValue(round((float(editor.text()) - lo) * 1000 / (hi - lo)))

                def slide(value, line=editor, low=lo, high=hi):
                    line.setText(f"{low + value / 1000 * (high - low):.6g}")

                slider.valueChanged.connect(slide)

                def synchronize(text, target=slider, low=lo, high=hi):
                    try:
                        value = float(text)
                        if math.isfinite(value):
                            previous = target.blockSignals(True)
                            target.setValue(round((value - low) * 1000 / (high - low)))
                            target.blockSignals(previous)
                    except ValueError:
                        pass

                editor.textChanged.connect(synchronize)
                self.form.addRow(slider)

    def set_device_information(self, info):
        lock = info.get("Frc Lock")
        self.frc_status.setText(
            "FRC locked · Driver Station enable required"
            if lock is True
            else "FRC lock: clear · Phoenix enable is still required"
            if lock is False
            else "FRC lock: unknown · check the target's enable requirements"
        )

    def staged(self):
        mode = self.mode.currentText()
        values = {}
        for name, editor in self.editors.items():
            values[name] = (
                editor.isChecked()
                if isinstance(editor, QCheckBox)
                else editor.currentData()
                if isinstance(editor, QComboBox)
                else editor.text()
            )
        encode_control(self.catalog, mode, values)
        return mode, values
