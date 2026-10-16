"""A wrapping toolbar that keeps compact desktop actions usable in narrow windows."""

from PySide6.QtCore import QRect, QSize, Qt
from PySide6.QtWidgets import QLayout, QSizePolicy, QSpacerItem


class FlowLayout(QLayout):
    def __init__(self, spacing=9):
        super().__init__()
        self.items = []
        self.setContentsMargins(0, 0, 0, 0)
        self.setSpacing(spacing)

    def addItem(self, item):
        self.items.append(item)

    def addStretch(self):
        self.addItem(QSpacerItem(0, 0, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum))

    def count(self):
        return len(self.items)

    def itemAt(self, index):
        return self.items[index] if 0 <= index < len(self.items) else None

    def takeAt(self, index):
        return self.items.pop(index) if 0 <= index < len(self.items) else None

    def expandingDirections(self):
        return Qt.Orientation(0)

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, width):
        return self.arrange(QRect(0, 0, width, 0), measure=True)

    def minimumSize(self):
        size = QSize()
        for item in self.items:
            size = size.expandedTo(item.minimumSize())
        return size

    def sizeHint(self):
        return self.minimumSize()

    def setGeometry(self, rect):
        super().setGeometry(rect)
        self.arrange(rect)

    def arrange(self, rect, measure=False):
        x, y, height = rect.x(), rect.y(), 0
        gap = self.spacing()
        for i, item in enumerate(self.items):
            size = item.sizeHint()
            if item.spacerItem():
                remaining = sum(it.sizeHint().width() + gap for it in self.items[i + 1 :])
                x += max(0, rect.right() - x - remaining + gap + 1)
                continue
            if x > rect.x() and x + size.width() > rect.right() + 1:
                x, y = rect.x(), y + height + gap
                height = 0
            if not measure:
                item.setGeometry(QRect(x, y, size.width(), size.height()))
            x += size.width() + gap
            height = max(height, size.height())
        return y + height - rect.y()
