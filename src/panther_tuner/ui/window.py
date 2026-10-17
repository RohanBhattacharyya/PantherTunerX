"""Main desktop workspace, connection lifecycle, and explicit operation review."""

import copy
import json
from datetime import datetime

from PySide6.QtCore import QSettings, Qt, QTimer, QUrl, Slot
from PySide6.QtGui import QColor, QDesktopServices
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QScrollArea,
    QSizeGrip,
    QSizePolicy,
    QSpinBox,
    QSplitter,
    QStackedWidget,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from .. import __version__
from ..backends.diagnostics import DiagnosticsBackend
from ..backends.local import LocalBackend
from ..models import TunerError
from .common import button, fill_table, label, table
from .config_editor import ConfigEditor
from .control_panel import ControlPanel
from .heartbeat import ControlHeartbeat
from .icons import device_picture, icon, tool
from .plotter import Plotter
from .worker import Worker


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"Panther Tuner X · {__version__}")
        self.resize(1662, 1114)
        self.setMinimumSize(1040, 720)
        self.active_control = None
        self.heartbeats = set()
        self.backend = None
        self._pending_backend = None
        self._closing = False
        self.device = None
        self.devices = []
        self.generation = 0
        self.pending_poll = False
        self.pending_discovery = False
        self.operation = False
        self.test_result = None
        self.device_widgets = {}
        self.settings = QSettings("PantherBotics", "Panther Tuner X")
        self.worker = Worker(self)
        self.worker.completed.connect(self.finished)
        root_widget = QWidget()
        self.setCentralWidget(root_widget)
        root = QVBoxLayout(root_widget)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        title = QWidget()
        title.setObjectName("titlebar")
        title.setFixedHeight(60)
        title_layout = QHBoxLayout(title)
        title_layout.setContentsMargins(12, 0, 14, 0)
        title_layout.addWidget(tool("back", lambda: self.navigate(0), "Back to devices", 36))
        title_layout.addSpacing(16)
        title_layout.addWidget(label("Panther Tuner X", "brand"))
        title_layout.addStretch()
        self.mode_badge = label("DISCONNECTED", "badge")
        title_layout.addWidget(self.mode_badge)
        title_layout.addSpacing(20)
        title_layout.addWidget(tool("minimize", self.showMinimized, "Minimize"))
        title_layout.addWidget(tool("maximize", self.toggle_maximized, "Maximize / restore"))
        title_layout.addWidget(tool("close", self.close, "Close"))
        title.mousePressEvent = (
            lambda e: self.windowHandle().startSystemMove()
            if e.button() == Qt.MouseButton.LeftButton and self.windowHandle()
            else None
        )
        title.mouseDoubleClickEvent = lambda e: self.toggle_maximized()
        self.setWindowFlag(Qt.WindowType.FramelessWindowHint)
        root.addWidget(title)
        row = QHBoxLayout()
        row.setSpacing(0)
        row.addWidget(self.build_sidebar())
        body = QWidget()
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(0)
        accent = QFrame()
        accent.setObjectName("accent")
        accent.setFixedHeight(6)
        body_layout.addWidget(accent)
        self.pages = QStackedWidget()
        self.devices_page = self.build_devices()
        self.detail_page = self.build_detail()
        self.history_page = self.build_history()
        self.help_page = self.build_help()
        for page in [self.devices_page, self.detail_page, self.history_page, self.help_page]:
            self.pages.addWidget(page)
        body_layout.addWidget(self.pages, 1)
        row.addWidget(body, 1)
        root.addLayout(row, 1)
        footer = QWidget()
        footer.setObjectName("footer")
        footer.setFixedHeight(24)
        foot = QHBoxLayout(footer)
        foot.setContentsMargins(8, 0, 0, 0)
        self.status = label("Disconnected", "footerText")
        self.status.setMaximumWidth(430)
        self.server_version = label("Server Version: Disconnected", "footerText")
        self.server_version.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.latency = label("Latency: —  –  Jitter: —", "footerText")
        for field in [self.status, self.server_version, self.latency]:
            field.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        foot.addWidget(self.status, 1)
        foot.addWidget(self.server_version, 2)
        foot.addWidget(self.latency, 1, Qt.AlignmentFlag.AlignRight)
        foot.addWidget(QSizeGrip(self))
        root.addWidget(footer)
        self.control_timer = QTimer(self)
        self.control_timer.setInterval(75)
        self.control_timer.timeout.connect(self.control_tick)
        self.control_timer.start()
        self.poll_timer = QTimer(self)
        self.poll_timer.timeout.connect(self.poll)
        self.poll_timer.start(50)
        self.discovery_timer = QTimer(self)
        self.discovery_timer.timeout.connect(self.discover)
        self.discovery_timer.start(3000)
        self.worker.start()

    def toggle_maximized(self):
        self.showNormal() if self.isMaximized() else self.showMaximized()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "cards") and getattr(self, "card_columns", 0) != max(
            1, min(3, (self.width() - 120) // 416)
        ):
            self.render_devices()

    def build_sidebar(self):
        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(60)
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(tool("menu", self.show_connection_menu, "Connection and menu", 60))
        self.nav_buttons = []
        for name, index, tip in [
            ("device", 0, "Devices"),
            ("bus", None, "CANivore connection"),
            ("history", 2, "Device history"),
            ("cloud", None, "Firmware deployment is not supported"),
            ("plot", 1, "Device workspace"),
            ("wand", None, "Generators are not supported"),
            ("profile", 3, "About and capabilities"),
            ("mail", None, "Support: see project documentation"),
        ]:
            action = (
                (lambda checked=False, i=index: self.navigate(i))
                if index is not None
                else self.show_connection_menu
            )
            b = tool(name, action, tip, 60)
            b.setObjectName("nav")
            b.setFixedHeight(68)
            b.setProperty("page", index)
            b.setCheckable(index is not None)
            b.setChecked(index == 0)
            if name in ("cloud", "wand", "mail"):
                b.setEnabled(False)
            layout.addWidget(b)
            self.nav_buttons.append(b)
        layout.addWidget(tool("settings", self.show_connection_menu, "Connection settings", 60))
        layout.addStretch()
        self.connection_menu = QFrame(self)
        self.connection_menu.setObjectName("connectionMenu")
        self.connection_menu.setFixedWidth(320)
        ml = QVBoxLayout(self.connection_menu)
        ml.setContentsMargins(18, 18, 18, 18)
        ml.addWidget(label("Connection", "cardTitle"))
        self.connection_mode = QComboBox()
        self.connection_mode.addItems(["Network diagnostics", "Local CAN / CANivore", "CTRE simulation"])
        self.connection_mode.currentIndexChanged.connect(self.mode_changed)
        ml.addWidget(self.connection_mode)
        self.target = QComboBox()
        self.target.setEditable(True)
        self.target.addItems([self.settings.value("host", "172.22.11.2"), "172.22.11.2", "127.0.0.1"])
        self.target.setToolTip("roboRIO USB: 172.22.11.2 · Ethernet: 10.TE.AM.2 · or hostname")
        ml.addWidget(self.target)
        self.port = QSpinBox()
        self.port.setRange(1, 65535)
        self.port.setValue(1250)
        self.port.setPrefix("Port  ")
        ml.addWidget(self.port)
        self.bus = QLineEdit("can0")
        self.bus.setPlaceholderText("CAN bus name / CANivore serial")
        self.bus.hide()
        ml.addWidget(self.bus)
        self.connect_button = button("Connect", self.toggle_connection, True)
        ml.addWidget(self.connect_button)
        self.connection_note = label(
            "Phoenix Diagnostics must be running on the target controller.", "muted", True
        )
        ml.addWidget(self.connection_note)
        ml.addWidget(button("About && capabilities", lambda: (self.navigate(3), self.connection_menu.hide())))
        self.connection_menu.hide()
        return sidebar

    def show_connection_menu(self):
        self.connection_menu.move(60, 66)
        self.connection_menu.adjustSize()
        self.connection_menu.setVisible(not self.connection_menu.isVisible())
        self.connection_menu.raise_()

    def mode_changed(self, index):
        self.target.setVisible(index == 0)
        self.port.setVisible(index == 0)
        self.bus.setVisible(index == 1)
        self.connection_note.setText(
            [
                "Phoenix Diagnostics must be running on the target controller.",
                "Starts the official SDK locally. CTRE hardware drivers are required.",
                "Isolated CTRE simulated devices. Every reading is simulated; real CAN is never used.",
            ][index]
        )

    def navigate(self, index):
        if index != 1:
            self.stop_controls()
            if self.backend and self.device and self.pages.currentIndex() == 1:
                backend, device = self.backend, self.device
                self.worker.submit(lambda: backend.stop_plot(device), lambda *_: None)
                self.plotter.resume_gap = True
        self.pages.setCurrentIndex(index)
        for b in self.nav_buttons:
            b.setChecked(b.property("page") == index)
        if index == 2:
            self.refresh_history()

    def set_control_enabled(self, enabled):
        if not enabled:
            self.stop_controls()
            return
        if self.active_control or not self.backend or not self.device or self.operation:
            return
        try:
            mode, values = self.control_panel.staged()
        except TunerError as e:
            QMessageBox.warning(self, "Invalid control request", str(e))
            return
        backend, device = self.backend, self.device
        renew = backend.enable_lease if isinstance(backend, LocalBackend) else None
        heartbeat = ControlHeartbeat(backend, device, mode, values, renew, self)
        heartbeat.status.connect(self.control_status)
        heartbeat.ended.connect(self.control_ended)
        self.active_control = heartbeat
        self.heartbeats.add(heartbeat)
        self.control_panel.set_output_enabled(True)
        self.log_event(f"Control enabled for {device.name} (ID {device.id})")
        heartbeat.start()

    def control_request_changed(self):
        if not self.active_control:
            return
        try:
            mode, values = self.control_panel.staged()
        except TunerError as e:
            self.control_panel.note.setText(f"Invalid value, still sending the previous request: {e}")
            return
        self.active_control.update(mode, values)

    def control_tick(self):
        """Feed the GUI liveness deadline; requests are sent by the heartbeat thread."""
        if not self.active_control:
            return
        if self.pages.currentIndex() != 1:
            self.stop_controls()
            return
        self.active_control.feed()

    def control_status(self, heartbeat, healthy, message):
        if heartbeat is not self.active_control:
            return
        self.control_panel.note.setText(message if healthy else "⚠ " + message)
        if not healthy or "gap" in message:
            self.log_event("Control: " + message)

    def control_ended(self, heartbeat, error, stop_error):
        self.heartbeats.discard(heartbeat)
        if stop_error:
            self.log_event(
                "Disable request failed; the server watchdog will neutralize output: " + stop_error
            )
        else:
            self.log_event("Control disabled")
        if heartbeat is self.active_control:
            self.stop_controls()
            if error:
                self.log_event("Control could not start: " + error)
                self.control_panel.note.setText("Control could not start: " + error)

    def stop_controls(self):
        heartbeat = self.active_control
        self.active_control = None
        self.control_panel.set_output_enabled(False)
        if heartbeat:
            # The heartbeat thread sends the disable request after its last control request.
            heartbeat.stop()
        if isinstance(self.backend, LocalBackend):
            self.backend.enable_lease(False)

    def plot_pause_changed(self, paused):
        if paused and self.backend and self.device:
            backend, device = self.backend, self.device
            self.worker.submit(lambda: backend.stop_plot(device), lambda *_: None)

    def plot_selection_changed(self):
        if not self.plotter.selected() and self.backend and self.device:
            backend, device = self.backend, self.device
            self.worker.submit(lambda: backend.stop_plot(device), lambda *_: None)

    def build_devices(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        heading = QHBoxLayout()
        heading.setContentsMargins(10, 6, 16, 7)
        self.device_title = label("Devices (0)", "title")
        heading.addWidget(self.device_title, 1)
        self.device_filter = QLineEdit()
        self.device_filter.setPlaceholderText("Search devices")
        self.device_filter.setMaximumWidth(300)
        self.device_filter.textChanged.connect(self.render_devices)
        heading.addWidget(self.device_filter)
        heading.addWidget(tool("refresh", self.discover, "Refresh devices", 42))
        self.view = QComboBox()
        self.view.addItems(["Card view", "Table view"])
        self.view.currentIndexChanged.connect(lambda i: self.device_views.setCurrentIndex(i))
        heading.addWidget(self.view)
        layout.addLayout(heading)
        self.discovery_note = label(
            "Connect using the menu at the top left to discover devices.", "muted", True
        )
        self.discovery_note.setContentsMargins(12, 3, 12, 3)
        layout.addWidget(self.discovery_note)
        self.device_views = QStackedWidget()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        self.cards = QWidget()
        self.card_grid = QGridLayout(self.cards)
        self.card_grid.setContentsMargins(32, 12, 32, 12)
        self.card_grid.setSpacing(16)
        scroll.setWidget(self.cards)
        self.device_views.addWidget(scroll)
        self.device_table = table(["NAME", "ID", "MODEL", "FIRMWARE", "CAN BUS", "STATUS"])
        self.device_table.cellDoubleClicked.connect(self.open_table_device)
        self.device_views.addWidget(self.device_table)
        layout.addWidget(self.device_views, 1)
        return page

    def render_devices(self, *_):
        while self.card_grid.count():
            item = self.card_grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        for row in range(self.card_grid.rowCount()):
            self.card_grid.setRowStretch(row, 0)
        query = self.device_filter.text().casefold()
        filtered = [d for d in self.devices if query in f"{d.name} {d.id} {d.model} {d.bus}".casefold()]
        self.visible_devices = filtered
        columns = max(1, min(3, (self.width() - 120) // 416))
        self.card_columns = columns
        for col in range(4):
            self.card_grid.setColumnStretch(col, 0)
        for i, d in enumerate(filtered):
            card = QFrame()
            card.setObjectName("card")
            card.setMinimumWidth(390)
            card.setMaximumWidth(510)
            card.setFixedHeight(190)
            card.mouseReleaseEvent = lambda event, dev=d: self.open_device(dev)
            cl = QVBoxLayout(card)
            cl.setContentsMargins(10, 4, 10, 6)
            cl.setSpacing(0)
            top = QHBoxLayout()
            top.addWidget(label("App Vers: " + d.firmware), 1)
            top.addWidget(label(f"ID: {d.id}"))
            top.addWidget(
                tool(
                    "light",
                    lambda checked=False, dev=d: self.blink_card(dev),
                    "Blink / clear sticky faults",
                    28,
                )
            )
            selection = QCheckBox()
            selection.setToolTip("Select device")
            top.addWidget(selection)
            cl.addLayout(top)
            mid = QHBoxLayout()
            picture = QLabel()
            picture.setPixmap(device_picture(d.model, 108))
            mid.addWidget(picture)
            words = QVBoxLayout()
            words.setSpacing(3)
            words.addWidget(label(d.name, "deviceName", True))
            duplicates = sum(x.bus == d.bus and x.id == d.id for x in self.devices) > 1
            words.addWidget(label("Duplicate CAN ID" if duplicates else d.status, "muted", True))
            words.addWidget(label(d.model, "muted"))
            mid.addLayout(words, 1)
            cl.addLayout(mid, 1)
            foot = QHBoxLayout()
            foot.addWidget(label("CAN Bus: " + (d.bus or "default")), 1)
            foot.addWidget(
                tool(
                    "copy",
                    lambda checked=False, dev=d: QApplication.clipboard().setText(
                        json.dumps(dev.raw, indent=2)
                    ),
                    "Copy device details",
                    28,
                )
            )
            foot.addWidget(
                tool("wrench", lambda checked=False, dev=d: self.open_device(dev), "Configure device", 28)
            )
            foot.addWidget(
                tool("selftest", lambda checked=False, dev=d: self.open_for_test(dev), "Open self test", 28)
            )
            if d.raw.get("IsPROLicensed"):
                foot.addWidget(label("PRO", "licensed"))
            cl.addLayout(foot)
            self.card_grid.addWidget(card, i // columns, i % columns, Qt.AlignmentFlag.AlignTop)
        for col in range(columns):
            self.card_grid.setColumnStretch(col, 1)
        self.card_grid.setRowStretch((len(filtered) + columns - 1) // columns, 1)
        fill_table(
            self.device_table,
            [[d.name, d.id, d.model, d.firmware, d.bus or "default", d.status] for d in filtered],
        )
        self.device_title.setText(f"Devices ({len(self.devices)})")

    def blink_card(self, device):
        if self.backend and self.confirm(
            "Blink device?", f"Blink {device.name} (ID {device.id}) and clear its sticky faults?"
        ):
            backend = self.backend
            self.run(lambda: backend.identify(device, confirmed=True), name="Blink device")

    def open_for_test(self, device):
        self.open_device(device)
        self.tabs.setCurrentIndex(0)
        self.self_test()

    def open_table_device(self, row, _):
        self.open_device(self.visible_devices[row])

    def build_detail(self):
        page = QWidget()
        layout = QHBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self.workspace_split = QSplitter(Qt.Orientation.Horizontal)
        self.left_tabs = QTabWidget()
        self.left_tabs.setObjectName("leftTabs")
        self.left_tabs.setMinimumWidth(300)
        info = QWidget()
        il = QVBoxLayout(info)
        il.setContentsMargins(13, 20, 13, 12)
        il.setSpacing(14)
        identity = QHBoxLayout()
        self.device_image = QLabel()
        identity.addWidget(self.device_image)
        details = QVBoxLayout()
        self.detail_title = label("Select a device", "deviceName", True)
        self.detail_subtitle = label("", "muted", True)
        details.addWidget(self.detail_title)
        details.addWidget(self.detail_subtitle)
        identity.addLayout(details, 1)
        il.addLayout(identity)
        il.addSpacing(55)
        self.device_bus = label("CAN Bus: —")
        il.addWidget(self.device_bus)
        links = QHBoxLayout()
        links.addWidget(
            button(
                "User's Guide",
                lambda: QDesktopServices.openUrl(QUrl("https://v6.docs.ctr-electronics.com/en/stable/")),
            )
        )
        links.addWidget(
            button(
                "Product Page", lambda: QDesktopServices.openUrl(QUrl("https://store.ctr-electronics.com/"))
            )
        )
        il.addLayout(links)
        self.id_field = QSpinBox()
        self.id_field.setRange(0, 62)
        self.name_field = QLineEdit()
        for name, field, action in [
            ("ID:", self.id_field, lambda: self.change_id(self.id_field.value())),
            ("Name:", self.name_field, lambda: self.rename(self.name_field.text())),
        ]:
            row = QHBoxLayout()
            text = label(name, "infoLabel")
            text.setFixedWidth(75)
            row.addWidget(text)
            row.addWidget(field, 1)
            set_button = button("Set", action)
            set_button.setMinimumHeight(46)
            row.addWidget(set_button)
            il.addLayout(row)
        blink = button("Blink", self.identify)
        blink.setMinimumHeight(46)
        blink.setToolTip("Blink also clears sticky faults; confirmation required")
        il.addWidget(blink)
        firmware = QHBoxLayout()
        family = QComboBox()
        family.addItems(["Phoenix 6"])
        family.setEnabled(False)
        firmware.addWidget(family)
        year = QComboBox()
        year.addItems(["2026"])
        year.setEnabled(False)
        firmware.addWidget(year)
        firmware.addStretch()
        il.addLayout(firmware)
        crf = QHBoxLayout()
        firmware_file = QComboBox()
        firmware_file.addItems(["Firmware flashing is not supported"])
        firmware_file.setEnabled(False)
        crf.addWidget(firmware_file, 1)
        browse = button("Browse", lambda: None)
        browse.setEnabled(False)
        crf.addWidget(browse)
        il.addLayout(crf)
        flash = button("Update Firmware", lambda: None)
        flash.setMinimumHeight(46)
        flash.setEnabled(False)
        flash.setToolTip("Firmware flashing is not implemented. Use CTRE's official tool.")
        il.addWidget(flash)
        il.addSpacing(12)
        self.info_table = table(["DEVICE DETAIL", "REPORTED VALUE"])
        self.info_table.horizontalHeader().hide()
        self.info_table.setShowGrid(False)
        il.addWidget(self.info_table, 1)
        il.addWidget(button("Copy device details", self.copy_details))
        self.left_tabs.addTab(info, icon("info", "#ffffff"), "Info")
        self.control_panel = ControlPanel()
        self.control_panel.enable_requested.connect(self.set_control_enabled)
        self.control_panel.request_changed.connect(self.control_request_changed)
        self.left_tabs.addTab(self.control_panel, icon("control", "#ffffff"), "Control")
        self.plotter = Plotter()
        self.plotter.export_requested.connect(self.export_csv)
        self.plotter.interval.valueChanged.connect(self.poll_interval_changed)
        self.plotter.pause_changed.connect(self.plot_pause_changed)
        self.plotter.selection_changed.connect(self.plot_selection_changed)
        self.left_tabs.addTab(self.plotter.signal_panel, icon("plot", "#ffffff"), "Signals")
        self.workspace_split.addWidget(self.left_tabs)
        self.detail_split = QSplitter(Qt.Orientation.Vertical)
        self.tabs = QTabWidget()
        self_test = QWidget()
        sl = QVBoxLayout(self_test)
        sl.setContentsMargins(14, 8, 14, 8)
        toolbar = QHBoxLayout()
        toolbar.addWidget(button("Refresh", self.self_test, True))
        toolbar.addWidget(button("Clear Faults", self.identify, True))
        toolbar.addWidget(button("Copy Self Test", self.copy_test, True))
        toolbar.addStretch()
        toolbar.addWidget(tool("copy", self.copy_test, "Copy self-test JSON"))
        sl.addLayout(toolbar)
        self.test_note = label("Refresh to collect a diagnostic snapshot.", "muted", True)
        sl.addWidget(self.test_note)
        self.test_table = table(["SIGNAL", "VALUE", "UNIT", "SPN"])
        sl.addWidget(self.test_table)
        self.tabs.addTab(self_test, icon("selftest", "#ffffff"), "Self Test")
        self.tabs.addTab(self.plotter, icon("plot", "#ffffff"), "Plot")
        self.detail_split.addWidget(self.tabs)
        dock = QWidget()
        dl = QHBoxLayout(dock)
        dl.setContentsMargins(0, 0, 0, 0)
        dl.setSpacing(0)
        rail = QWidget()
        rail.setFixedWidth(54)
        rl = QVBoxLayout(rail)
        rl.setContentsMargins(0, 8, 0, 0)
        wrench = tool("wrench", lambda: None, "Configuration", 54)
        wrench.setObjectName("selectedTool")
        rl.addWidget(wrench)
        analyzer = tool("plot", lambda: None, "Closed-loop analyzer is not implemented", 54)
        analyzer.setEnabled(False)
        rl.addWidget(analyzer)
        rl.addStretch()
        dl.addWidget(rail)
        self.config_editor = ConfigEditor()
        self.config_editor.refresh_requested.connect(self.refresh_config)
        self.config_editor.apply_requested.connect(self.apply_config)
        self.config_editor.save_requested.connect(self.save_config)
        self.config_editor.load_requested.connect(self.load_config)
        self.config_editor.defaults_requested.connect(self.stage_defaults)
        dl.addWidget(self.config_editor, 1)
        self.detail_split.addWidget(dock)
        self.detail_split.setHandleWidth(12)
        self.detail_split.setSizes([680, 340])
        self.workspace_split.addWidget(self.detail_split)
        self.workspace_split.setHandleWidth(2)
        self.workspace_split.setSizes([480, 1120])
        layout.addWidget(self.workspace_split)
        return page

    def build_history(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.addWidget(label("Device history", "title"))
        layout.addWidget(
            label("Previously discovered devices. This view does not imply a current connection.", "subtitle")
        )
        self.history_table = table(["LAST SEEN", "NAME", "MODEL", "ID", "BUS", "FIRMWARE", "SOURCE"])
        layout.addWidget(self.history_table)
        layout.addWidget(label("SESSION EVENTS", "eyebrow"))
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumBlockCount(500)
        layout.addWidget(self.log)
        return page

    def build_help(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.addWidget(label("Built for the whole pit.", "title"))
        layout.addWidget(
            label(
                "Panther Tuner X  ·  " + __version__ + "  ·  Independent, open-source Phoenix workbench",
                "subtitle",
            )
        )
        layout.addSpacing(18)
        text = (
            "CONNECTIONS\n\n"
            "Network diagnostics works on Linux, Windows, and macOS. Connect to a running Phoenix Diagnostics Server, normally port 1250. "
            "roboRIO USB uses 172.22.11.2. Team Ethernet addresses use 10.TE.AM.2.\n\n"
            "Local CAN starts the official Phoenix SDK on Linux or Windows. Linux supports SocketCAN and CANivore; Windows requires CANivore. "
            "CTRE drivers and a configured CAN network are required. macOS supports network connections and simulation.\n\n"
            "CTRE simulation runs in an isolated process with the official SDK. Synthetic physics inputs move simulated sensors; no real hardware is connected.\n\n"
            "CAPABILITIES\n\n"
            "Discovery, reported device details, all configuration fields returned by getconfigv2, configuration import/export, staged defaults, "
            "reviewed writes, self-test snapshots, buffered plots with independent axes, pause, zoom, full-capture CSV, blink/clear faults, names, IDs, and control requests.\n\n"
            "LIMITS\n\n"
            "Protocol verified against Phoenix 26.3.0 simulation. Physical CAN devices and older server versions require hardware validation. "
            "Plots preserve every returned server record with server timestamps and ordinals. A finite server buffer can overrun; missing records are counted and shown as gaps. "
            "The server stream does not guarantee every physical CAN update. Export before Clear, device changes, disconnect, or closing. Unsupported commands report errors.\n\n"
            "Firmware flashing, licenses, automatic server deployment, Phoenix 5 configuration, Pigeon calibration, and generators are not implemented. "
            "Control modes are derived from server metadata; simulated duty output and watchdogs are verified, but physical motors and other modes require validation.\n\n"
            "SAFETY & OWNERSHIP\n\n"
            "Configuration, name, ID and blink changes require explicit confirmation. Blink also clears sticky faults. Refresh before editing and review changes with the robot disabled. "
            "Control works like Tuner X: ENABLED sends the request continuously and edits apply immediately; DISABLED, leaving the device, or disconnecting neutralizes output. "
            "FRC-locked devices also require Driver Station enable. Keep an independent emergency stop available. "
            "A failed or timed-out write can have partially applied; refresh to inspect actual state.\n\n"
            "Panther Tuner X is not affiliated with CTR Electronics. CTRE and Phoenix are their respective owners' trademarks. "
            "Application code is MIT licensed. The separately installed CTRE SDK retains CTRE's license. "
            "See docs/research.md, docs/protocol.md, and THIRD_PARTY_NOTICES.md in the source repository."
        )
        t = QPlainTextEdit(text)
        t.setReadOnly(True)
        layout.addWidget(t)
        return page

    def log_event(self, text):
        self.log.appendPlainText(datetime.now().strftime("%H:%M:%S") + "  " + text)
        self.status.setText(text)

    @Slot(object, object, object)
    def finished(self, callback, result, error):
        if not self._closing:
            callback(result, error)

    def run(self, fn, callback=None, name="Operation"):
        generation = self.generation

        def done(result, error):
            if generation != self.generation:
                return
            if error:
                self.log_event(f"{name} failed: {error}")
                QMessageBox.warning(self, name, str(error))
            elif callback:
                callback(result)

        self.worker.submit(fn, done)

    def confirm(self, title, message, details=""):
        dialog = QMessageBox(self)
        dialog.setWindowTitle(title)
        dialog.setText(message)
        dialog.setTextFormat(Qt.TextFormat.PlainText)
        if details:
            dialog.setDetailedText(details)
        dialog.setStandardButtons(QMessageBox.StandardButton.Apply | QMessageBox.StandardButton.Cancel)
        dialog.setDefaultButton(QMessageBox.StandardButton.Cancel)
        return dialog.exec() == QMessageBox.StandardButton.Apply

    def has_edits(self):
        return self.config_editor.config and bool(self.config_editor.config.changes())

    def discard_edits(self):
        return not self.has_edits() or self.confirm(
            "Discard staged changes?", "This action discards your unapplied configuration edits."
        )

    def toggle_connection(self):
        if self.operation:
            return
        if self.backend:
            if not self.discard_edits():
                return
            self.disconnect()
            return
        self.connect_button.setEnabled(False)
        self.connection_mode.setEnabled(False)
        self.generation += 1
        index = self.connection_mode.currentIndex()
        host, port, bus = self.target.currentText().strip(), self.port.value(), self.bus.text().strip()
        self.log_event("Connecting…")

        def connect():
            backend = DiagnosticsBackend(host, port) if index == 0 else LocalBackend(index == 2, bus)
            self._pending_backend = backend
            try:
                info = backend.connect()
                devices = backend.discover()
                return backend, info, devices
            except Exception:
                backend.close()
                self._pending_backend = None
                raise

        def done(result, error):
            self.connect_button.setEnabled(True)
            if error:
                self.connection_mode.setEnabled(True)
                self.log_event("Connection failed: " + str(error))
                QMessageBox.warning(self, "Connection failed", str(error))
                return
            self.backend, info, devices = result
            self._pending_backend = None
            self.connect_button.setText("Disconnect")
            self.connection_menu.hide()
            self.mode_badge.setText("SIMULATION · SYNTHETIC INPUTS" if index == 2 else "HARDWARE / NETWORK")
            self.settings.setValue("host", host)
            self.log_event("Connected · Phoenix Diagnostics " + self.backend.version)
            self.update_devices(devices)

        self.worker.submit(connect, done)

    def disconnect(self):
        self.stop_controls()
        if self.backend and self.device:
            backend, device = self.backend, self.device
            self.worker.submit(lambda: backend.stop_plot(device), lambda *_: None)
        self.generation += 1
        backend, self.backend = self.backend, None
        self.worker.submit(backend.close, lambda *_: None)
        self.device = None
        self.devices = []
        self.pending_poll = self.pending_discovery = False
        self.operation = False
        self.config_editor.config = None
        self.config_editor.groups.clear()
        self.config_editor.fields.setRowCount(0)
        self.config_editor.apply_button.setEnabled(False)
        self.plotter.set_signals([])
        self.control_panel.set_catalog({})
        self.test_table.setRowCount(0)
        self.info_table.setRowCount(0)
        self.detail_title.setText("Device workspace")
        self.detail_subtitle.setText("Disconnected. Open a device after reconnecting.")
        self.mode_badge.setText("DISCONNECTED")
        self.connection_mode.setEnabled(True)
        self.connect_button.setText("Connect")
        self.discovery_note.setText("Disconnected · Connect to discover devices.")
        self.render_devices()
        self.log_event("Disconnected")
        self.navigate(0)

    def discover(self):
        if not self.backend or self.pending_discovery or self.operation:
            return
        self.pending_discovery = True
        generation, backend = self.generation, self.backend

        def done(result, error):
            if generation != self.generation:
                return
            self.pending_discovery = False
            if error:
                # An enabled control session keeps retrying and reports its own status.
                self.discovery_note.setText("Diagnostics unavailable · " + str(error))
                self.log_event("Connection error: " + str(error))
            else:
                self.update_devices(result)

        self.worker.submit(backend.discover, done)

    def update_devices(self, devices):
        previous = self.devices
        self.devices = devices
        if self.backend.simulated:
            self.mode_badge.setText("SIMULATION · SYNTHETIC INPUTS")
        self.discovery_note.setText(
            f"●  Diagnostics connected  ·  {len(devices)} devices reported  ·  "
            + ("CTRE SIMULATION" if self.backend.simulated else self.target.currentText())
            + (
                "\nNo devices found. Check power, bus name, termination, and CTRE drivers."
                if not devices
                else ""
            )
        )
        if previous != devices:
            self.render_devices()
        if self.active_control and self.device:
            matches = [
                d
                for d in devices
                if (d.bus, d.model, d.id) == (self.device.bus, self.device.model, self.device.id)
            ]
            if len(matches) != 1 or matches[0].key != self.device.key:
                self.stop_controls()
                self.log_event("Control stopped: target missing, replaced, or ambiguous")
        self.update_latency()
        history = json.loads(self.settings.value("history", "{}"))
        source = "SIMULATION" if self.backend.simulated else self.target.currentText()
        for d in devices:
            history[source + "/" + d.key] = [
                datetime.now().isoformat(timespec="seconds"),
                d.name,
                d.model,
                d.id,
                d.bus or "default",
                d.firmware,
                source,
            ]
        self.settings.setValue("history", json.dumps(dict(list(history.items())[-200:])))
        if self.device and not any(d.key == self.device.key for d in devices):
            self.stop_controls()
            self.detail_subtitle.setText(
                "DEVICE DISCONNECTED · Data collection paused. Reopen after rediscovery."
            )
            self.device = None
            self.config_editor.apply_button.setEnabled(False)
            self.plotter.resume_gap = True

    def open_device(self, device):
        if not self.backend or self.operation or not self.discard_edits():
            return
        self.stop_controls()
        if self.device and self.backend:
            previous, backend = self.device, self.backend
            self.worker.submit(lambda: backend.stop_plot(previous), lambda *_: None)
        self.device = device
        self.plotter.device_name = device.name
        self.device_image.setPixmap(device_picture(device.model, 112))
        self.device_bus.setText("CAN Bus: " + (device.bus or "default"))
        self.id_field.setValue(device.id)
        self.name_field.setText(device.name)
        self.control_panel.set_catalog({})
        self.config_editor.config = None
        self.config_editor.groups.clear()
        self.config_editor.fields.setRowCount(0)
        self.config_editor.apply_button.setEnabled(False)
        self.test_result = None
        self.test_table.setRowCount(0)
        self.detail_title.setText(device.name)
        self.detail_subtitle.setText(f"{device.model}\nApp Vers: {device.firmware}")
        fill_table(
            self.info_table,
            [(k, json.dumps(v) if isinstance(v, (dict, list)) else v) for k, v in device.raw.items()],
        )
        self.plotter.set_signals([])
        backend = self.backend

        def loaded(result):
            if self.device != device:
                return
            signals, config, controls, info, control_error = result
            self.plotter.set_signals(signals)
            self.config_editor.set_config(config)
            self.control_panel.set_catalog(controls)
            self.control_panel.set_device_information(info)
            if control_error:
                self.control_panel.note.setText("Control metadata unavailable: " + control_error)
            self.log_event(f"Read {len(signals)} signals and {len(config.values())} configuration parameters")

        def read():
            signals, config = backend.signals(device), backend.read_config(device)
            control_error = ""
            try:
                controls = backend.controls(device)
            except TunerError as e:
                controls, control_error = {}, str(e)
            try:
                info = backend.device_information(device)
            except TunerError:
                info = {}
            return signals, config, controls, info, control_error

        self.run(read, loaded, "Read device")
        self.navigate(1)
        self.left_tabs.setCurrentIndex(2)
        self.tabs.setCurrentIndex(1)

    def poll_interval_changed(self, value):
        self.poll_timer.setInterval(value)

    def poll(self):
        if (
            not self.backend
            or not self.device
            or self.pending_poll
            or self.pending_discovery
            or self.operation
        ):
            return
        if self.pages.currentIndex() != 1 or self.plotter.paused:
            return
        ids = [s.id for s in self.plotter.selected()]
        if not ids:
            return
        self.pending_poll = True
        backend, device, generation = self.backend, self.device, self.generation

        def done(result, error):
            if generation != self.generation:
                return
            self.pending_poll = False
            if self.device != device:
                return
            if error:
                self.status.setText("Telemetry unavailable: " + str(error))
            else:
                try:
                    self.plotter.add_batch(result)
                except TunerError as e:
                    if not self.plotter.paused:
                        self.plotter.toggle_pause()
                    self.log_event(str(e))
                    QMessageBox.critical(self, "Capture storage failed", str(e))
                self.update_latency()

        self.worker.submit(lambda: backend.buffered_samples(device, ids), done)

    def update_latency(self):
        if self.backend:
            self.server_version.setText("Server Version: " + self.backend.version)
            values = self.backend.latencies
            jitter = max(values) - min(values) if values else 0
            self.latency.setText(f"Latency: {self.backend.latency_ms:.1f} ms  –  Jitter: {jitter:.1f} ms")

    def refresh_config(self):
        if self.backend and self.device and self.discard_edits():
            backend, device = self.backend, self.device
            self.run(
                lambda: backend.read_config(device),
                lambda c: self.config_editor.set_config(c) if self.device == device else None,
                "Refresh configuration",
            )

    def apply_config(self):
        if not self.backend or not self.device or not self.config_editor.config or self.operation:
            return
        config = copy.deepcopy(self.config_editor.config)
        changes = config.changes()
        if not changes:
            return
        details = "\n".join(f"{name}: {old} → {new}" for name, old, new in changes)
        if not self.confirm(
            "Write device configuration?",
            f"Apply {len(changes)} changes to {config.device.name} (ID {config.device.id})?\n\n"
            "Disable the robot and ensure the mechanism is safe. A running robot program may overwrite these settings.\n\n"
            + details[:1400],
            details,
        ):
            return
        self.stop_controls()
        self.operation = True
        self.connect_button.setEnabled(False)
        self.config_editor.setEnabled(False)
        backend, device = self.backend, self.device

        def done(result, error):
            self.operation = False
            self.connect_button.setEnabled(True)
            self.config_editor.setEnabled(True)
            if error:
                self.log_event("Configuration write failed: " + str(error))
                QMessageBox.warning(
                    self,
                    "Write failed — refresh device",
                    str(error)
                    + "\n\nThe write may have partially applied. Refresh the device before retrying.",
                )
            elif self.device == device:
                requested = config.values()
                actual = result.values()
                differences = [
                    (k, requested[k], actual.get(k)) for k in requested if requested[k] != actual.get(k)
                ]
                self.config_editor.set_config(result)
                self.log_event("Configuration applied and refreshed from device")
                if differences:
                    QMessageBox.information(
                        self,
                        "Readback differs",
                        "The device returned different values (firmware quantization or rejection). The editor now shows actual readback.\n\n"
                        + "\n".join(f"SPN {k}: requested {a}, returned {b}" for k, a, b in differences),
                    )

        self.worker.submit(lambda: backend.write_config(config, confirmed=True), done)

    def save_config(self):
        if self.config_editor.config:
            path, _ = QFileDialog.getSaveFileName(
                self, "Export staged configuration", "device-config.json", "JSON (*.json)"
            )
            if path:
                try:
                    self.config_editor.config.save(path)
                    self.log_event("Exported staged configuration to " + path)
                except Exception as e:
                    QMessageBox.warning(self, "Export failed", str(e))

    def load_config(self):
        if not self.config_editor.config:
            return
        path, _ = QFileDialog.getOpenFileName(
            self, "Import configuration as staged changes", "", "JSON (*.json)"
        )
        if path:
            try:
                self.config_editor.config.load(path)
                self.config_editor.set_config(self.config_editor.config)
                self.log_event("Imported configuration as staged changes. Review & apply to write.")
            except Exception as e:
                QMessageBox.warning(self, "Import failed", str(e))

    def stage_defaults(self):
        if self.config_editor.config and self.confirm(
            "Stage factory defaults?",
            "Replace staged values with server-reported defaults?\nThis does not write to the device. Review & apply is required to write.",
        ):
            self.config_editor.config.defaults()
            self.config_editor.set_config(self.config_editor.config)

    def self_test(self):
        if self.backend and self.device:
            backend, device = self.backend, self.device

            def done(result):
                if self.device != device:
                    return
                self.test_result = result
                rows = result["signals"]
                fill_table(self.test_table, [[r["name"], r["Value"], r["Units"], r["id"]] for r in rows])
                active = 0
                for i, row in enumerate(rows):
                    if "fault" in row["name"].lower() and str(row["Value"]).lower() not in (
                        "0",
                        "false",
                        "0.000000",
                    ):
                        active += 1
                        self.test_table.item(i, 1).setForeground(QColor("#f07878"))
                self.test_note.setText(
                    f"{result['source']}  ·  {len(rows)} reported signals  ·  {active} asserted fault values  ·  "
                    + datetime.fromtimestamp(result["timestamp"]).isoformat(timespec="seconds")
                )
                self.log_event("Self-test snapshot collected")

            self.run(lambda: backend.self_test(device), done, "Self test")

    def identify(self):
        if (
            self.backend
            and self.device
            and self.confirm(
                "Blink / clear sticky faults?",
                f"Blink {self.device.name} and clear its sticky fault history?\nCTRE's blink command performs both operations.",
            )
        ):
            backend, device = self.backend, self.device
            self.run(
                lambda: backend.identify(device, confirmed=True),
                lambda _: self.log_event("Blink / clear faults completed"),
                "Blink / clear faults",
            )

    def rename(self, name=None):
        if not self.backend or not self.device:
            return
        ok = True
        if not isinstance(name, str):
            name, ok = QInputDialog.getText(
                self, "Device name", "New device name (up to 32 UTF-8 bytes)", text=self.device.name
            )
        if ok and self.confirm("Set device name?", f"Rename {self.device.name} to {name}?"):
            backend, device = self.backend, self.device
            self.run(
                lambda: backend.rename(device, name, confirmed=True), lambda _: self.discover(), "Set name"
            )

    def change_id(self, new_id=None):
        if not self.backend or not self.device:
            return
        ok = True
        if type(new_id) is not int:
            new_id, ok = QInputDialog.getInt(
                self, "Change CAN ID", "New ID (0–62). Robot code must use the new ID.", self.device.id, 0, 62
            )
        if ok and self.confirm(
            "Change device CAN ID?",
            f"Change {self.device.name} from ID {self.device.id} to {new_id}?\nRobot code using the old ID will lose communication.",
        ):
            backend, device = self.backend, self.device
            self.run(
                lambda: backend.set_id(device, new_id, confirmed=True), lambda _: self.discover(), "Change ID"
            )

    def copy_details(self):
        if self.device:
            QApplication.clipboard().setText(json.dumps(self.device.raw, indent=2))
            self.log_event("Device details copied")

    def copy_test(self):
        if self.test_result:
            QApplication.clipboard().setText(json.dumps(self.test_result, indent=2))
            self.log_event("Self-test JSON copied")

    def export_csv(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Export current signal buffer", "telemetry.csv", "CSV (*.csv)"
        )
        if path:
            try:
                self.plotter.buffer.export(path, self.plotter.signals)
                self.log_event("Exported telemetry CSV to " + path)
            except Exception as e:
                QMessageBox.warning(self, "CSV export failed", str(e))

    def refresh_history(self):
        history = json.loads(self.settings.value("history", "{}"))
        fill_table(self.history_table, sorted(history.values(), reverse=True))

    def closeEvent(self, event):
        if not self.discard_edits():
            event.ignore()
            return
        self.poll_timer.stop()
        self.discovery_timer.stop()
        self.control_timer.stop()
        self.stop_controls()
        self._closing = True
        # Each heartbeat sends its Stop before the backend (or SDK host) closes.
        for heartbeat in list(self.heartbeats):
            while not heartbeat.wait(20):
                QApplication.processEvents()

        def cleanup():
            for backend in [self.backend, self._pending_backend]:
                if backend:
                    if self.device:
                        try:
                            backend.stop_plot(self.device)
                        except Exception:
                            pass
                    backend.close()

        self.worker.stop(cleanup)
        # Keep Qt responsive while a bounded request or SDK shutdown finishes.
        while not self.worker.wait(20):
            QApplication.processEvents()
        self.plotter.buffer.close()
        event.accept()
