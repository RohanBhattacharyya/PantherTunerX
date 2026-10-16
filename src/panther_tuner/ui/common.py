from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHeaderView, QLabel, QPushButton, QTableWidget, QTableWidgetItem


def label(text, role="", wrap=False):
    w = QLabel(text)
    w.setObjectName(role)
    w.setWordWrap(wrap)
    w.setTextFormat(Qt.TextFormat.PlainText)
    return w


def button(text, callback=None, primary=False):
    b = QPushButton(text)
    if primary:
        b.setObjectName("primary")
    if callback:
        b.clicked.connect(callback)
    return b


def table(headers):
    w = QTableWidget(0, len(headers))
    w.setHorizontalHeaderLabels(headers)
    w.setAlternatingRowColors(True)
    w.verticalHeader().hide()
    w.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
    w.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
    w.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
    w.horizontalHeader().setStretchLastSection(True)
    return w


def fill_table(w, rows):
    w.setRowCount(len(rows))
    for i, row in enumerate(rows):
        for j, value in enumerate(row):
            item = QTableWidgetItem(str(value))
            w.setItem(i, j, item)
