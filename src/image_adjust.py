"""图像调整：亮度/对比度显示滤镜 + 图像信息"""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
from PyQt5.QtCore import QTimer, Qt
from PyQt5.QtGui import QImage, QPixmap
from PyQt5.QtWidgets import (
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)


def compute_lut(brightness: int, contrast: int) -> np.ndarray:
    """
    根据亮度和对比度生成 256 项查找表。

    brightness: -100 ~ 100（直接加到像素值）
    contrast: -100 ~ 100（用 ImageJ 标准公式）

    返回 uint8 LUT，可传给 cv2.LUT。
    """
    lut = np.arange(256, dtype=np.float32)
    # 对比度: ImageJ 式公式
    if contrast != 0:
        factor = (259.0 * (contrast + 255)) / (255.0 * (259 - contrast))
        lut = factor * (lut - 128) + 128
    # 亮度
    lut = lut + brightness * 2.55  # -100~100 映射到 -255~255
    lut = np.clip(lut, 0, 255).astype(np.uint8)
    return lut


def apply_bc(img: np.ndarray, brightness: int, contrast: int) -> np.ndarray:
    """对图像应用亮度/对比度 LUT（不修改原图）"""
    lut = compute_lut(brightness, contrast)
    if img.ndim == 2:
        return cv2.LUT(img, lut)
    # 彩色图：每个通道用同一个 LUT
    return cv2.LUT(img, cv2.merge([lut, lut, lut]))


def ndarray_to_pixmap(img: np.ndarray) -> QPixmap:
    """OpenCV BGR ndarray → QPixmap（确保数据拷贝，不引用临时 buffer）"""
    if img.ndim == 2:
        h, w = img.shape
        qimg = QImage(img.tobytes(), w, h, w, QImage.Format_Grayscale8)
    else:
        rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        h, w = rgb.shape[:2]
        qimg = QImage(rgb.tobytes(), w, h, 3 * w, QImage.Format_RGB888)
    return QPixmap.fromImage(qimg)


class ImageAdjustDialog(QWidget):
    """亮度/对比度调整面板（非模态，浮动窗口）"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Brightness/Contrast")
        self.setWindowFlags(Qt.Tool | Qt.WindowStaysOnTopHint)
        self.setFixedSize(320, 200)
        self._brightness = 0
        self._contrast = 0
        self._setup_ui()
        # 防抖定时器：滑块停止 300ms 后才应用，避免大图卡顿
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(300)
        self._timer.timeout.connect(self._apply)

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # 亮度
        b_group = QGroupBox("亮度")
        b_layout = QHBoxLayout()
        self.slider_b = QSlider(Qt.Horizontal)
        self.slider_b.setRange(-100, 100)
        self.slider_b.setValue(0)
        self.lbl_b = QLabel("0")
        self.lbl_b.setFixedWidth(30)
        b_layout.addWidget(self.slider_b)
        b_layout.addWidget(self.lbl_b)
        b_group.setLayout(b_layout)
        layout.addWidget(b_group)

        # 对比度
        c_group = QGroupBox("对比度")
        c_layout = QHBoxLayout()
        self.slider_c = QSlider(Qt.Horizontal)
        self.slider_c.setRange(-100, 100)
        self.slider_c.setValue(0)
        self.lbl_c = QLabel("0")
        self.lbl_c.setFixedWidth(30)
        c_layout.addWidget(self.slider_c)
        c_layout.addWidget(self.lbl_c)
        c_group.setLayout(c_layout)
        layout.addWidget(c_group)

        # 按钮
        btn_layout = QHBoxLayout()
        self.btn_reset = QPushButton("重置")
        self.btn_reset.clicked.connect(self._reset)
        btn_layout.addWidget(self.btn_reset)
        layout.addLayout(btn_layout)

        # 信号
        self.slider_b.valueChanged.connect(self._on_slider_changed)
        self.slider_c.valueChanged.connect(self._on_slider_changed)

    @property
    def brightness(self) -> int:
        return self._brightness

    @property
    def contrast(self) -> int:
        return self._contrast

    def _on_slider_changed(self):
        self.lbl_b.setText(str(self.slider_b.value()))
        self.lbl_c.setText(str(self.slider_c.value()))
        self._brightness = self.slider_b.value()
        self._contrast = self.slider_c.value()
        self._timer.start()  # 防抖：重置定时器

    def _apply(self):
        """通知外部应用当前 B/C 值"""
        # 由 MainWindow 连接使用
        pass

    def _reset(self):
        self.slider_b.setValue(0)
        self.slider_c.setValue(0)


def show_image_info(parent: QWidget, img: np.ndarray, image_path: str) -> None:
    """弹出图像信息对话框"""
    p = Path(image_path)
    file_size = p.stat().st_size if p.exists() else 0
    size_str = _human_size(file_size)

    if img.ndim == 2:
        h, w = img.shape
        channels = 1
        dtype = str(img.dtype)
        min_val = int(img.min())
        max_val = int(img.max())
        mean_val = float(img.mean())
    else:
        h, w, channels = img.shape
        dtype = str(img.dtype)
        min_val = int(img.min())
        max_val = int(img.max())
        mean_val = float(img.mean())

    info = (
        f"文件路径: {image_path}\n"
        f"文件大小: {size_str}\n"
        f"文件格式: {p.suffix.upper()[1:]}\n"
        f"─────────────────\n"
        f"宽度: {w} px\n"
        f"高度: {h} px\n"
        f"通道数: {channels}\n"
        f"位深: {dtype}\n"
        f"─────────────────\n"
        f"最小像素值: {min_val}\n"
        f"最大像素值: {max_val}\n"
        f"平均像素值: {mean_val:.1f}\n"
        f"─────────────────\n"
        f"总像素数: {w * h * channels:,}"
    )

    QMessageBox.information(parent, "📷 图像信息", info)


def _human_size(size_bytes: int) -> str:
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"
