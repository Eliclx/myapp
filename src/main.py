"""入口"""
import sys

from PyQt5.QtWidgets import QApplication

from main_window import MainWindow  # pyright: ignore[reportImplicitRelativeImport]


def main():
    app = QApplication(sys.argv)
    _ = app.setStyle("Fusion")
    win = MainWindow()
    win.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
