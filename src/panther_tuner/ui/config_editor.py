"""Metadata-driven editor covering every parameter returned by Phoenix."""

from html import escape

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QHeaderView,
    QLineEdit,
    QListWidget,
    QMenu,
    QSizePolicy,
    QSplitter,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..configuration import Configuration
from ..models import TunerError
from .common import label, table
from .icons import icon, tool


class ConfigEditor(QWidget):
    apply_requested = Signal()
    refresh_requested = Signal()
    save_requested = Signal()
    load_requested = Signal()
    defaults_requested = Signal()

    def __init__(self):
        super().__init__()
        self.config: Configuration | None = None
        self.loading = False
        self.invalid = {}
        root = QHBoxLayout(self)
        root.setContentsMargins(15, 7, 14, 3)
        root.setSpacing(16)
        split = QSplitter()
        left = QWidget()
        ll = QVBoxLayout(left)
        ll.setContentsMargins(0, 0, 0, 0)
        ll.setSpacing(4)
        toolbar = QHBoxLayout()
        toolbar.setSpacing(2)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search configs")
        self.search.addAction(icon("search"), QLineEdit.ActionPosition.TrailingPosition)
        self.search.textChanged.connect(self.filter)
        toolbar.addWidget(self.search, 1)
        self.apply_button = tool("download", self.apply_requested.emit, "Review and apply staged changes", 28)
        self.apply_button.setEnabled(False)
        toolbar.addWidget(self.apply_button)
        toolbar.addWidget(tool("refresh", self.refresh_requested.emit, "Refresh configuration", 28))
        menu_button = tool("more", lambda: None, "Configuration actions", 28)
        menu = QMenu(menu_button)
        for text, signal in [
            ("Import configuration…", self.load_requested),
            ("Export configuration…", self.save_requested),
            ("Stage factory defaults…", self.defaults_requested),
        ]:
            menu.addAction(text, signal.emit)
        menu_button.setMenu(menu)
        toolbar.addWidget(menu_button)
        ll.addLayout(toolbar)
        self.groups = QListWidget()
        self.groups.currentRowChanged.connect(self.show_group)
        ll.addWidget(self.groups)
        split.addWidget(left)
        right = QWidget()
        layout = QVBoxLayout(right)
        layout.setContentsMargins(14, 0, 0, 0)
        layout.setSpacing(5)
        self.heading = label("Configuration", "configHeading")
        self.heading.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        layout.addWidget(self.heading)
        self.description = label("", "muted", True)
        self.description.hide()
        self.fields = table(["PARAMETER", "STAGED VALUE", "UNIT", "DEVICE VALUE"])
        self.fields.horizontalHeader().hide()
        self.fields.setShowGrid(False)
        self.fields.setAlternatingRowColors(False)
        self.fields.setColumnHidden(2, True)
        self.fields.setColumnHidden(3, True)
        self.fields.horizontalHeader().setStretchLastSection(False)
        self.fields.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        self.fields.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.fields.setColumnWidth(0, 195)
        self.fields.verticalHeader().setDefaultSectionSize(45)
        layout.addWidget(self.fields)
        self.notice = label("Refresh to read configuration. Writes require review.", "muted")
        self.notice.setStyleSheet("font-size: 12px;")
        layout.addWidget(self.notice)
        split.addWidget(right)
        split.setHandleWidth(1)
        split.setSizes([290, 730])
        root.addWidget(split)

    def set_config(self, config):
        self.config = config
        order = [
            "Motor Output",
            "Current Limits",
            "Closed Loop General",
            "Slot 0",
            "Slot 1",
            "Slot 2",
            "Voltage",
            "Torque Current",
            "Feedback",
            "Differential Sensors",
            "Differential Constants",
        ]
        config.groups.sort(key=lambda g: order.index(g["Name"]) if g["Name"] in order else len(order))
        self.invalid.clear()
        self.groups.clear()
        for group in config.groups:
            self.groups.addItem(group["Name"])
        self.groups.setCurrentRow(0)
        self.update_notice()
        self.filter(self.search.text())

    def show_group(self, index):
        if not self.config or index < 0:
            return
        self.loading = True
        group = self.config.groups[index]
        self.heading.setText(group["Name"] + (" - " + group["Summary"] if group.get("Summary") else ""))
        self.heading.setToolTip(group.get("Description", ""))
        self.description.setText(group.get("Summary", "") + " " + group.get("Description", ""))
        fields = group["Configs"]
        if group["Name"] == "Motor Output":
            order = [
                "Control Timesync Freq Hz",
                "Duty Cycle Neutral Deadband",
                "Inverted",
                "Neutral Mode",
                "Peak Forward Duty Cycle",
                "Peak Reverse Duty Cycle",
            ]
            fields = sorted(
                fields, key=lambda f: order.index(f["Name"]) if f["Name"] in order else len(order)
            )
        self.fields.setRowCount(len(fields))
        for row, field in enumerate(fields):
            sid = int(field["SignalId"])
            name = QTableWidgetItem(field["Name"] + ("\n" + field["Units"] if field.get("Units") else ""))
            name.setToolTip(
                field.get("Summary", "")
                + "\n"
                + field.get("Description", "")
                + f"\nRange: {field.get('MinValue')} to {field.get('MaxValue')}\nSPN {sid}"
            )
            self.fields.setItem(row, 0, name)
            # The rich label paints the visible text; keep searchable plain
            # metadata without painting a duplicate underneath it.
            name.setForeground(QColor(Qt.GlobalColor.transparent))
            display_name = field["Name"]
            units = field.get("Units", "")
            if units and display_name.endswith(" " + units):
                display_name = display_name[: -(len(units) + 1)]
            field_label = label("")
            field_label.setTextFormat(Qt.TextFormat.RichText)
            field_label.setWordWrap(True)
            field_label.setText(
                escape(display_name)
                + (f'<br><span style="font-size:12px;color:#bab5c2">{escape(units)}</span>' if units else "")
            )
            field_label.setToolTip(name.toolTip())
            field_label.setContentsMargins(4, 0, 4, 0)
            self.fields.setCellWidget(row, 0, field_label)
            enums = field.get("EnumValues", [])
            kind = field.get("Type", "").lower()
            if enums or kind in ("bool", "boolean"):
                editor = QComboBox()
                for entry in enums or [{"Name": "False", "Value": 0}, {"Name": "True", "Value": 1}]:
                    editor.addItem(entry["Name"], entry["Value"])
                found = editor.findData(field["Value"])
                if found < 0:
                    editor.addItem(f"Unknown ({field['Value']})", field["Value"])
                    found = editor.count() - 1
                editor.setCurrentIndex(found)
                editor.currentIndexChanged.connect(
                    lambda _, s=sid, e=editor: self.edited(s, e.currentData(), e)
                )
            else:
                editor = QLineEdit(str(field["Value"]))
                # Stage on every edit so Review never omits the still-focused field.
                editor.textChanged.connect(lambda _, s=sid, e=editor: self.edited(s, e.text(), e))
                editor.editingFinished.connect(lambda s=sid, e=editor: self.edited(s, e.text(), e))
            if sid in self.invalid and isinstance(editor, QLineEdit):
                editor.setText(self.invalid[sid])
                editor.setStyleSheet("border: 1px solid #f07878;")
            editor.setToolTip(name.toolTip())
            self.fields.setCellWidget(row, 1, editor)
            self.fields.setItem(row, 2, QTableWidgetItem(field.get("Units", "")))
            self.fields.setItem(row, 3, QTableWidgetItem(str(self.config.baseline[sid])))
        self.loading = False

    def edited(self, sid, value, editor):
        if self.loading:
            return
        try:
            self.config.set(sid, float(value))
            self.invalid.pop(sid, None)
            editor.setStyleSheet("")
            self.update_notice()
        except (ValueError, TunerError) as e:
            self.invalid[sid] = str(value)
            editor.setStyleSheet("border: 1px solid #f07878;")
            self.notice.setText(str(e) if isinstance(e, TunerError) else "Enter a finite numeric value")
            self.apply_button.setEnabled(False)

    def update_notice(self):
        count = len(self.config.changes()) if self.config else 0
        total = len(self.config.values()) if self.config else 0
        self.notice.setText(
            f"{total} parameters read from device  •  {count} staged changes  •  Apply requires confirmation"
        )
        if self.invalid:
            self.notice.setText(
                f"{len(self.invalid)} invalid fields. Correct them before applying configuration."
            )
        self.apply_button.setEnabled(count > 0 and not self.invalid)

    def filter(self, query):
        if not self.config:
            return
        query = query.casefold()
        first = None
        for i, group in enumerate(self.config.groups):
            matches = query in group["Name"].casefold() or any(
                query in (f["Name"] + " " + f.get("Summary", "")).casefold() for f in group["Configs"]
            )
            self.groups.item(i).setHidden(not matches)
            if matches and first is None:
                first = i
        if first is not None and self.groups.item(self.groups.currentRow()).isHidden():
            self.groups.setCurrentRow(first)
