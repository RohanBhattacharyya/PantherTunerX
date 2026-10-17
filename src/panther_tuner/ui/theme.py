"""Pastel yellow palette with Phoenix Tuner's compact workspace geometry."""

ACCENT = "#f3e6a4"

STYLE = """
QWidget { background: #1c1b1f; color: #eeeeee; font-family: 'Segoe UI', 'Noto Sans', 'Helvetica Neue', sans-serif; font-size: 15px; }
QLabel { background: transparent; }
QLabel#brand { font-size: 20px; font-weight: 600; }
QLabel#title { font-size: 25px; font-weight: 600; }
QLabel#deviceName { font-size: 24px; font-weight: 600; }
QLabel#cardTitle { font-size: 19px; font-weight: 600; }
QLabel#muted, QLabel#subtitle { color: #b8b6be; }
QLabel#badge { font-size: 12px; color: #f3e6a4; }
QLabel#footerText { color: #e6dba7; font-size: 13px; }
QLabel#integrity { font-size: 12px; }
QLabel#configHeading { color: #f3e6a4; font-weight: 600; padding: 4px 0; }
QLabel#callout { background: #3e392b; color: #f3e6bd; border-radius: 5px; }
QLabel#licensed { background: #e5d89d; color: #111111; padding: 1px 4px; font-size: 12px; font-weight: bold; }
QWidget#titlebar { background: #202020; }
QWidget#footer { background: #1c1b1f; }
QFrame#accent { background: #f3e6a4; }
QFrame#sidebar { background: #202020; }
QFrame#connectionMenu { background: #242328; border: 1px solid #66636d; }
QFrame#card { border: 1px solid #8c835e; border-radius: 5px; background: #1c1b1f; }
QFrame#card:hover { border-color: #f3e6a4; background: #242228; }
QPushButton { background: #3b393f; border: 0; border-radius: 4px; padding: 9px 11px; }
QPushButton:hover { background: #504d55; }
QPushButton:pressed { background: #66626c; }
QPushButton:disabled { color: #77747d; background: #29272e; }
QPushButton#primary { color: #141414; background: #f3e6a4; font-weight: 600; }
QPushButton#primary:hover { background: #fff1bd; }
QPushButton#primary:disabled { color: #9e977c; background: #454237; }
QPushButton#disabled { background: #b83b41; color: white; font-weight: 700; font-size: 17px; }
QPushButton#disabled:hover { background: #d64d51; }
QPushButton#enabled { background: #2e8b47; color: white; font-weight: 700; font-size: 17px; }
QPushButton#enabled:hover { background: #38a656; }
QPushButton#icon { padding: 0; background: transparent; border-radius: 0; }
QPushButton#icon:hover { background: #37343c; }
QPushButton#icon::menu-indicator { image: none; width: 0; }
QPushButton#nav { padding: 0; background: #202020; border-radius: 0; border-left: 3px solid transparent; }
QPushButton#nav:checked { background: #303036; border-left-color: #f3e6a4; }
QPushButton#nav:hover { background: #37343c; }
QPushButton#selectedTool { padding: 0; border-radius: 0; border-left: 4px solid #f3e6a4; background: #28262d; }
QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox { background: #29272e; border: 0; border-bottom: 1px solid #7e7985; border-radius: 4px; padding: 8px; selection-background-color: #625b3d; min-height: 22px; }
QLineEdit:focus, QSpinBox:focus, QComboBox:focus { border-bottom-color: #f3e6a4; }
QComboBox QAbstractItemView { background: #2d2a33; selection-background-color: #514b36; }
QTabWidget::pane { border: 0; }
QTabBar::tab { height: 44px; min-width: 110px; padding: 5px 18px; background: #1c1b1f; border-bottom: 4px solid transparent; color: #eeeeee; font-weight: 600; font-size: 17px; }
QTabBar::tab:selected { border-bottom-color: #f3e6a4; }
QTabBar::tab:hover { background: #28262c; }
QTabBar { qproperty-iconSize: 25px 25px; }
QTableWidget, QTreeWidget, QListWidget, QPlainTextEdit { background: #1c1b1f; border: 0; alternate-background-color: #242228; gridline-color: #343039; }
QTableWidget::item { padding: 3px 5px; }
QTableWidget QLineEdit, QTableWidget QComboBox { margin: 3px 0; }
QListWidget::item { padding: 7px 6px; border: 0; }
QListWidget::item:selected, QTreeWidget::item:selected, QTableWidget::item:selected { background: #444031; color: #f3e6a4; }
QTreeWidget#signals::item { padding: 1px 0; }
QHeaderView::section { background: #28262d; color: #bfbac7; padding: 8px; border: 0; font-size: 13px; }
QScrollArea { border: 0; }
QScrollBar:vertical { background: #1c1b1f; width: 8px; margin: 0; }
QScrollBar::handle:vertical { background: #605b68; min-height: 30px; border-radius: 3px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar:horizontal { background: #1c1b1f; height: 8px; }
QScrollBar::handle:horizontal { background: #605b68; min-width: 30px; }
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }
QSplitter::handle { background: #090909; width: 2px; height: 12px; }
QCheckBox { spacing: 8px; background: transparent; }
QCheckBox::indicator, QTreeView::indicator { width: 16px; height: 16px; border: 2px solid #a7a2ae; border-radius: 1px; background: transparent; }
QCheckBox::indicator:checked, QTreeView::indicator:checked { background: #f3e6a4; border-color: #f3e6a4; image: url(:/qt-project.org/styles/commonstyle/images/standardbutton-apply-16.png); }
QToolTip { background: #353039; color: #f4f0f6; border: 1px solid #756c7d; padding: 6px; }
QMenu { background: #2d2932; border: 1px solid #5c5665; }
QMenu::item { padding: 9px 18px; }
QMenu::item:selected { background: #514b36; }
"""
