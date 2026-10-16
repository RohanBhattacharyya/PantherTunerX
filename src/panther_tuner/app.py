import argparse
import sys


def main():
    if "--sdk-host" in sys.argv:
        sys.argv.remove("--sdk-host")
        from .sdk_host import main as host_main

        host_main()
        return
    parser = argparse.ArgumentParser(description="Panther Tuner X desktop device workbench")
    parser.add_argument(
        "--simulate", action="store_true", help="Connect to isolated official CTRE simulation"
    )
    parser.add_argument("--host", help="Connect to a Phoenix Diagnostics Server")
    args = parser.parse_args()
    from PySide6.QtCore import QTimer
    from PySide6.QtGui import QFont
    from PySide6.QtWidgets import QApplication

    from .ui.theme import STYLE
    from .ui.window import MainWindow

    app = QApplication(sys.argv[:1])
    app.setApplicationName("Panther Tuner X")
    app.setOrganizationName("PantherBotics")
    app.setStyle("Fusion")
    app.setFont(QFont("Sans Serif", 10))
    app.setStyleSheet(STYLE)
    window = MainWindow()
    window.show()
    if args.simulate:
        window.connection_mode.setCurrentIndex(2)
        QTimer.singleShot(0, window.toggle_connection)
    elif args.host:
        window.target.setCurrentText(args.host)
        QTimer.singleShot(0, window.toggle_connection)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
