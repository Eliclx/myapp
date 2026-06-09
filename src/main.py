"""入口"""
import logging
import sys
import traceback
from pathlib import Path

from PyQt5.QtCore import qInstallMessageHandler, QtMsgType
from PyQt5.QtWidgets import QApplication


# ─── 日志配置 ───

LOG_DIR = Path(__file__).parent.parent / "logs"
LOG_DIR.mkdir(exist_ok=True)
LOG_FILE = LOG_DIR / "myapp.log"

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.FileHandler(str(LOG_FILE), encoding="utf-8"),
        logging.StreamHandler(sys.stderr),
    ],
)
log = logging.getLogger("myapp")


def _qt_message_handler(msg_type, context, msg):
    """捕获 Qt 内部日志（包括 QThread 崩溃前的警告）"""
    level_map = {
        QtMsgType.QtDebugMsg: logging.DEBUG,
        QtMsgType.QtInfoMsg: logging.INFO,
        QtMsgType.QtWarningMsg: logging.WARNING,
        QtMsgType.QtCriticalMsg: logging.ERROR,
        QtMsgType.QtFatalMsg: logging.CRITICAL,
    }
    level = level_map.get(msg_type, logging.WARNING)
    logging.log(level, f"[Qt] {msg}  (file={context.file}, line={context.line})")


qInstallMessageHandler(_qt_message_handler)


def _global_excepthook(exc_type, exc_value, exc_tb):
    """捕获所有未处理异常，写入日志"""
    tb = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
    log.critical(f"未捕获异常:\n{tb}")
    # 也弹窗提示用户
    try:
        from PyQt5.QtWidgets import QMessageBox

        app = QApplication.instance()
        if app:
            msg = QMessageBox()
            msg.setIcon(QMessageBox.Critical)
            msg.setWindowTitle("程序出错")
            msg.setText(f"{exc_type.__name__}: {exc_value}")
            msg.setDetailedText(tb)
            msg.exec_()
    except Exception:
        pass


sys.excepthook = _global_excepthook


def main():
    log.info("=== myapp 启动 ===")
    log.info(f"日志文件: {LOG_FILE}")

    app = QApplication(sys.argv)
    _ = app.setStyle("Fusion")

    from main_window import MainWindow  # pyright: ignore[reportImplicitRelativeImport]

    win = MainWindow()
    win.show()
    log.info("主窗口已显示")
    exit_code = app.exec_()
    log.info(f"=== myapp 退出 (code={exit_code}) ===")
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
