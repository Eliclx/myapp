"""图片列表面板：显示缩略图 + 文件名，点击切换"""

from __future__ import annotations

from pathlib import Path

import cv2
from PyQt5.QtCore import QThread, Qt, pyqtSignal, QSize
from PyQt5.QtGui import QImage, QPixmap
from PyQt5.QtWidgets import (
    QLabel,
    QListWidget,
    QListWidgetItem,
    QProgressBar,
    QVBoxLayout,
    QWidget,
)

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff"}


def _make_thumbnail(path: str, size: int = 64) -> QPixmap:
    """快速生成缩略图（跳过行数，超快）"""
    img = cv2.imread(path, cv2.IMREAD_REDUCED_COLOR_2)  # 1/2 尺寸读
    if img is None:
        # fallback: 再试正常读
        img = cv2.imread(path, cv2.IMREAD_COLOR)
    if img is None:
        return QPixmap()
    h, w = img.shape[:2]
    scale = size / max(h, w)
    thumb = cv2.resize(img, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)
    rgb = cv2.cvtColor(thumb, cv2.COLOR_BGR2RGB)
    th, tw = rgb.shape[:2]
    qimg = QImage(rgb.tobytes(), tw, th, 3 * tw, QImage.Format_RGB888)
    return QPixmap.fromImage(qimg)


class ThumbnailThread(QThread):
    """后台生成缩略图"""

    thumbnail_ready = pyqtSignal(int, QPixmap)  # (index, pixmap)
    all_done = pyqtSignal()

    def __init__(self, image_list: list[str]):
        super().__init__()
        self._image_list = image_list
        self._cancelled = False

    def run(self):
        for i, path in enumerate(self._image_list):
            if self._cancelled:
                return
            pm = _make_thumbnail(path)
            if not pm.isNull():
                self.thumbnail_ready.emit(i, pm)
        self.all_done.emit()

    def cancel(self):
        self._cancelled = True


class ImageListPanel(QWidget):
    """左侧图片列表：缩略图 + 文件名，点击切换"""

    image_selected = pyqtSignal(int)  # 点击的图片索引

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(220)
        self._setup_ui()
        self._thumb_thread: ThumbnailThread | None = None

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # 标题
        title = QLabel("🖼️ 图片列表")
        title.setStyleSheet("font-weight: bold; font-size: 13px; padding: 4px;")
        layout.addWidget(title)

        # 列表
        self.list_widget = QListWidget()
        self.list_widget.setIconSize(QSize(48, 48))
        self.list_widget.currentRowChanged.connect(self._on_row_changed)
        layout.addWidget(self.list_widget)

        # 进度条（缩略图生成时显示）
        self.progress = QProgressBar()
        self.progress.setFixedHeight(14)
        self.progress.setTextVisible(False)
        self.progress.hide()
        layout.addWidget(self.progress)

    def load_image_list(self, image_list: list[str]) -> None:
        """设置图片列表，后台生成缩略图"""
        # 取消上一次的缩略图生成
        if self._thumb_thread and self._thumb_thread.isRunning():
            self._thumb_thread.cancel()
            self._thumb_thread.wait(1000)

        self.list_widget.clear()
        self._block_signals = True

        for i, path in enumerate(image_list):
            name = Path(path).name
            item = QListWidgetItem(name)
            item.setData(Qt.UserRole, path)
            item.setToolTip(name)
            self.list_widget.addItem(item)

        self._block_signals = False

        # 后台生成缩略图
        if image_list:
            self.progress.setRange(0, len(image_list))
            self.progress.setValue(0)
            self.progress.show()
            self._thumb_thread = ThumbnailThread(image_list)
            self._thumb_thread.thumbnail_ready.connect(self._on_thumbnail_ready)
            self._thumb_thread.all_done.connect(self._on_all_done)
            self._thumb_thread.start()

    def set_current_index(self, index: int) -> None:
        """程序切换图片时同步高亮（不触发信号）"""
        self._block_signals = True
        self.list_widget.setCurrentRow(index)
        self._block_signals = False

    def _on_row_changed(self, row: int):
        if not getattr(self, "_block_signals", False) and row >= 0:
            self.image_selected.emit(row)

    def _on_thumbnail_ready(self, index: int, pixmap: QPixmap):
        item = self.list_widget.item(index)
        if item:
            item.setIcon(pixmap)
        self.progress.setValue(self.progress.value() + 1)

    def _on_all_done(self):
        self.progress.hide()
