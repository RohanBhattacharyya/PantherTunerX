"""Original outline icons and offline official product photos (see asset sources)."""

from pathlib import Path

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QIcon, QPainter, QPixmap, QRegion
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QPushButton

PATHS = {
    "menu": "M4 7h24M4 16h24M4 25h24",
    "back": "M27 16H5m9-9-9 9 9 9",
    "device": "M11 3h10v19H11zM14 22v7m4-7v7M8 8h3m10 0h3M8 17h3m10 0h3",
    "bus": "M8 3h16v24H8zM12 8h8m-8 5h8m-8 5h8M12 27v3m8-3v3",
    "history": "M5 10a12 12 0 1 1-1 10M5 3v8h8m3-3v9l6 4",
    "plot": "M4 3v25h25M7 22l7-9 6 4 8-12",
    "info": "M16 3a13 13 0 1 0 0 26 13 13 0 0 0 0-26m0 11v10m0-17v2",
    "control": "M9 9h14l6 14-3 3-8-5h-4l-8 5-3-3 6-14m-1 6h8m-4-4v8m10-4h1m-3 4h1",
    "selftest": "M4 5l6 6-3 3-6-6m9 6 4 4m-3-9a12 12 0 0 1 12 14m-9-19a18 18 0 0 1 15 23m-17-9 5-5",
    "wrench": "M19 4a9 9 0 0 0-9 12L2 25l5 5 10-10a9 9 0 0 0 12-10l-6 6-7-7 6-6z",
    "refresh": "M26 10a12 12 0 1 0 1 11M26 3v8h-8",
    "download": "M16 2v19m-7-7 7 7 7-7M5 23v6h22v-6",
    "upload": "M16 23V4m-7 7 7-7 7 7M5 23v6h22v-6",
    "more": "M16 5v2m0 8v2m0 8v2",
    "copy": "M11 3h15v21H11zM6 9H3v20h17v-3",
    "clipboard": "M12 5H5v24h22V5h-7M12 2h8v7h-8zm-3 12h14M9 20h14",
    "light": "M10 21a10 10 0 1 1 12 0l-2 4h-8zm2 8h8",
    "grid": "M3 3h11v11H3zm15 0h11v11H18zM3 18h11v11H3zm15 0h11v11H18z",
    "check": "m4 16 7 8L29 5m-13 18L29 10",
    "search": "M14 3a10 10 0 1 0 0 20 10 10 0 0 0 0-20m7 18 9 9",
    "settings": "M13 2h6l1 5 5 3 5-1v6l-4 3-2 5 1 5h-6l-3-4-5-1-5 2-3-5 3-4 1-5-2-5 5-3zm3 9a5 5 0 1 0 0 10 5 5 0 0 0 0-10",
    "mail": "M3 6h26v21H3zm0 0 13 12L29 6",
    "minus": "M9 16h14",
    "cloud": "M8 25a7 7 0 1 1 0-14 10 10 0 0 1 19 0 7 7 0 0 1-2 14zm8-8v13m-5-5 5 5 5-5",
    "wand": "m5 29 23-23-4-4L1 25zm8-14 4 4M7 2v7M3 5h8m16 14v9m-4-4h8",
    "profile": "M16 2a6 6 0 1 0 0 12 6 6 0 0 0 0-12M3 30v-6a13 10 0 0 1 26 0v6M3 28q13 6 26 0",
    "minimize": "M8 16h16",
    "maximize": "M8 8h16v16H8z",
    "close": "m9 9 14 14m0-14L9 23",
}


def icon(name, color="#ededed"):
    svg = f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32"><path d="{PATHS[name]}" fill="none" stroke="{color}" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/></svg>'
    pixmap = QPixmap(64, 64)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    QSvgRenderer(svg.encode()).render(painter)
    painter.end()
    return QIcon(pixmap)


def tool(name, callback=None, tooltip="", size=32):
    widget = QPushButton()
    widget.setIcon(icon(name))
    pixels = min(32, max(20, size - 6))
    widget.setIconSize(QSize(pixels, pixels))
    widget.setObjectName("icon")
    widget.setToolTip(tooltip)
    widget.setFixedSize(size, size)
    if callback:
        widget.clicked.connect(callback)
    return widget


# Family artwork is representative: discovery does not identify every motor or
# wiring variant. Product imagery is kept separate from the original UI icons.
DEVICE_IMAGES = {
    "talonfxs": "talon-fxs.png",
    "talonfx": "talon-fx.png",
    "falcon": "falcon500.png",
    "cancoder": "cancoder.png",
    "pigeon2": "pigeon2.png",
    "canrange": "canrange.png",
    "candi": "candi.png",
    "candle": "candle.png",
}
DEVICE_ASSETS = Path(__file__).resolve().parents[1] / "assets" / "devices"


def device_picture(model, size=112):
    normalized = "".join(c for c in model.casefold() if c.isalnum())
    filename = next((value for key, value in DEVICE_IMAGES.items() if key in normalized), None)
    source = QPixmap(str(DEVICE_ASSETS / filename)) if filename else QPixmap()
    if source.isNull():
        source = icon("device", "#b8b6be").pixmap(size, size)
    elif source.hasAlphaChannel():
        # Store images have different transparent margins. Fit the visible
        # product consistently while preserving the original downloaded files.
        bounds = QRegion(source.mask()).boundingRect()
        if not bounds.isEmpty():
            source = source.copy(bounds.adjusted(-4, -4, 4, 4).intersected(source.rect()))
    scaled = source.scaled(
        size, size, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
    )
    picture = QPixmap(size, size)
    picture.fill(Qt.GlobalColor.transparent)
    painter = QPainter(picture)
    painter.drawPixmap((size - scaled.width()) // 2, (size - scaled.height()) // 2, scaled)
    painter.end()
    return picture
