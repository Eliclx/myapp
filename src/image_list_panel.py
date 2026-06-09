"""图片列表面板：显示缩略图 + 文件名，点击切换"""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
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


def _make_thumbnail_ndarray(path: str, size: int = 64) -> np.ndarray | None:
    """
    生成缩略图 ndarray（线程安全，不涉及任何 Qt 对象）。
    用 IMREAD_REDUCED_COLOR_2 减半读取，避免大图吃内存。
    """
    img = cv2.imread(path, cv2.IMREAD_REDUCED_COLOR_2)
    if img is None:
        # fallback: 用 IMREAD_REDUCED_COLOR_4 (1/4) 再试
        img = cv2.imread(path, cv2.IMREAD_REDUCED_COLOR_4)
    if img is None:
        return None
    h, w = img.shape[:2]
    scale = size / max(h, w)
    thumb = cv2.resize(
        img, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA
    )
    return thumb


def _ndarray_to_icon_pixmap(thumb: np.ndarray) -> QPixmap:
    """ndarray → QPixmap（仅主线程调用）"""
    rgb = cv2.cvtColor(thumb, cv2.COLOR_BGR2RGB)
    h, w = rgb.shape[:2]
    qimg = QImage(rgb.tobytes(), w, h, 3 * w, QImage.Format_RGB888)
    return QPixmap.fromImage(qimg)


class ThumbnailThread(QThread):
    """
    后台生成缩略图。
    只传 ndarray（不传 QPixmap），避免跨线程 GUI 对象崩溃。
    """

    thumbnail_ready = pyqtSignal(
        int, object
    )  # (index, ndarray) — 不标注类型避免 pyright 报错
    all_done = pyqtSignal()

    def __init__(self, image_list: list[str]):
        super().__init__()
        self._image_list = image_list
        self._cancelled = False

    def run(self):
        for i, path in enumerate(self._image_list):
            if self._cancelled:
                return
            thumb = _make_thumbnail_ndarray(path)
            if thumb is not None:
                self.thumbnail_ready.emit(i, thumb)
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
        self._block_signals = False

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

        # 进度条
        self.progress = QProgressBar()
        self.progress.setFixedHeight(14)
        self.progress.setTextVisible(False)
        self.progress.hide()
        layout.addWidget(self.progress)

    def load_image_list(self, image_list: list[str]) -> None:
        """设置图片列表，后台异步生成缩略图"""
        if self._thumb_thread and self._thumb_thread.isRunning():
            self._thumb_thread.cancel()
            self._thumb_thread.wait(2000)

        self.list_widget.clear()
        self._block_signals = True

        for path in image_list:
            name = Path(path).name
            item = QListWidgetItem(name)
            item.setData(Qt.UserRole, path)
            item.setToolTip(name)
            self.list_widget.addItem(item)

        self._block_signals = False

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
        if not self._block_signals and row >= 0:
            self.image_selected.emit(row)

    def _on_thumbnail_ready(self, index: int, thumb: np.ndarray):
        """主线程：ndarray → QPixmap → 设置图标"""
        item = self.list_widget.item(index)
        if item:
            pm = _ndarray_to_icon_pixmap(thumb)
            item.setIcon(pm)
        self.progress.setValue(self.progress.value() + 1)

    def _on_all_done(self):
        self.progress.hide()
