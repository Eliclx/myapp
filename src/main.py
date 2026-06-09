"""入口"""

from __future__ import annotations

import sys

from PyQt5.QtWidgets import QApplication

from main_window import MainWindow  # pyright: ignore[reportImplicitRelativeImport]


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    # 深色主题
    palette = app.palette()
    palette.setColor(palette.ColorRole.Window, palette.color(palette.ColorRole.Window))
    app.setPalette(palette)

    win = MainWindow()
    win.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
