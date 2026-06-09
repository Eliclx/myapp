"""图像调整：ImageJ 风格 Brightness/Contrast + Min/Max + 图像信息"""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
from PyQt5.QtCore import QTimer, Qt, pyqtSignal
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


# ═══════════════════════════════════════════════
# 纯函数：LUT 计算
# ═══════════════════════════════════════════════


def compute_minmax_lut(min_val: int, max_val: int) -> np.ndarray:
    """
    ImageJ 式 Min/Max 映射 LUT。

    pixel < min → 0
    pixel > max → 255
    min <= pixel <= max → 线性映射到 [0, 255]
    """
    if max_val <= min_val:
        return np.full(256, 128, dtype=np.uint8)
    lut = np.arange(256, dtype=np.float32)
    lut = (lut - min_val) * 255.0 / (max_val - min_val)
    lut = np.clip(lut, 0, 255).astype(np.uint8)
    return lut


def compute_bc_lut(brightness: int, contrast: int) -> np.ndarray:
    """
    亮度/对比度 LUT（ImageJ 公式）。

    brightness: -100 ~ 100
    contrast: -100 ~ 100
    """
    lut = np.arange(256, dtype=np.float32)
    if contrast != 0:
        factor = (259.0 * (contrast + 255)) / (255.0 * (259 - contrast))
        lut = factor * (lut - 128) + 128
    lut = lut + brightness * 2.55
    lut = np.clip(lut, 0, 255).astype(np.uint8)
    return lut


def apply_lut(img: np.ndarray, lut: np.ndarray) -> np.ndarray:
    """对图像应用 LUT（不修改原图）"""
    if img.ndim == 2:
        return cv2.LUT(img, lut)
    return cv2.LUT(img, cv2.merge([lut, lut, lut]))


def ndarray_to_pixmap(img: np.ndarray) -> QPixmap:
    """OpenCV BGR ndarray → QPixmap（确保数据拷贝）"""
    if img.ndim == 2:
        h, w = img.shape
        qimg = QImage(img.tobytes(), w, h, w, QImage.Format_Grayscale8)
    else:
        rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        h, w = rgb.shape[:2]
        qimg = QImage(rgb.tobytes(), w, h, 3 * w, QImage.Format_RGB888)
    return QPixmap.fromImage(qimg)


# ═══════════════════════════════════════════════
# B/C 对话框（ImageJ 风格）
# ═══════════════════════════════════════════════


class ImageAdjustDialog(QWidget):
    """ImageJ 风格亮度/对比度 + Min/Max 调整面板"""

    # 信号：参数变化时发出，由 MainWindow 监听
    changed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Brightness/Contrast")
        self.setWindowFlags(Qt.Tool | Qt.WindowStaysOnTopHint)
        self.setFixedSize(340, 340)

        self._min_val = 0
        self._max_val = 255
        self._brightness = 0
        self._contrast = 0

        self._setup_ui()

        # 防抖定时器：滑块停止 300ms 后才发出信号
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(300)
        self._timer.timeout.connect(self.changed.emit)

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # Min
        min_group = QGroupBox("Minimum")
        min_layout = QHBoxLayout()
        self.slider_min = QSlider(Qt.Horizontal)
        self.slider_min.setRange(0, 255)
        self.slider_min.setValue(0)
        self.lbl_min = QLabel("0")
        self.lbl_min.setFixedWidth(30)
        min_layout.addWidget(self.slider_min)
        min_layout.addWidget(self.lbl_min)
        min_group.setLayout(min_layout)
        layout.addWidget(min_group)

        # Max
        max_group = QGroupBox("Maximum")
        max_layout = QHBoxLayout()
        self.slider_max = QSlider(Qt.Horizontal)
        self.slider_max.setRange(0, 255)
        self.slider_max.setValue(255)
        self.lbl_max = QLabel("255")
        self.lbl_max.setFixedWidth(30)
        max_layout.addWidget(self.slider_max)
        max_layout.addWidget(self.lbl_max)
        max_group.setLayout(max_layout)
        layout.addWidget(max_group)

        # 亮度
        b_group = QGroupBox("Brightness")
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
        c_group = QGroupBox("Contrast")
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
        btn_reset = QPushButton("Reset")
        btn_reset.clicked.connect(self._reset)
        btn_auto = QPushButton("Auto")
        btn_auto.clicked.connect(self._auto)
        btn_layout.addWidget(btn_reset)
        btn_layout.addWidget(btn_auto)
        layout.addLayout(btn_layout)

        # 信号
        self.slider_min.valueChanged.connect(self._on_min_changed)
        self.slider_max.valueChanged.connect(self._on_max_changed)
        self.slider_b.valueChanged.connect(self._on_bc_changed)
        self.slider_c.valueChanged.connect(self._on_bc_changed)

    # ─── 属性 ───

    @property
    def min_val(self) -> int:
        return self._min_val

    @property
    def max_val(self) -> int:
        return self._max_val

    @property
    def brightness(self) -> int:
        return self._brightness

    @property
    def contrast(self) -> int:
        return self._contrast

    def get_lut(self) -> np.ndarray:
        """计算最终的组合 LUT：先 Min/Max 映射，再 B/C 调整"""
        lut_mm = compute_minmax_lut(self._min_val, self._max_val)
        if self._brightness != 0 or self._contrast != 0:
            lut_bc = compute_bc_lut(self._brightness, self._contrast)
            # 组合：minmax 输出作为 bc 输入
            lut = lut_bc[lut_mm]
        else:
            lut = lut_mm
        return lut

    # ─── 槽函数 ───

    def _on_min_changed(self, val: int):
        self.lbl_min.setText(str(val))
        # min 不能超过 max
        if val >= self._max_val:
            self._max_val = val + 1
            self.slider_max.setValue(self._max_val)
            self.lbl_max.setText(str(self._max_val))
        self._min_val = val
        self._timer.start()

    def _on_max_changed(self, val: int):
        self.lbl_max.setText(str(val))
        if val <= self._min_val:
            self._min_val = max(0, val - 1)
            self.slider_min.setValue(self._min_val)
            self.lbl_min.setText(str(self._min_val))
        self._max_val = val
        self._timer.start()

    def _on_bc_changed(self):
        self._brightness = self.slider_b.value()
        self._contrast = self.slider_c.value()
        self.lbl_b.setText(str(self._brightness))
        self.lbl_c.setText(str(self._contrast))
        self._timer.start()

    def _reset(self):
        self._block_slider_signals(True)
        self.slider_min.setValue(0)
        self.slider_max.setValue(255)
        self.slider_b.setValue(0)
        self.slider_c.setValue(0)
        self._min_val = 0
        self._max_val = 255
        self._brightness = 0
        self._contrast = 0
        self.lbl_min.setText("0")
        self.lbl_max.setText("255")
        self.lbl_b.setText("0")
        self.lbl_c.setText("0")
        self._block_slider_signals(False)
        self.changed.emit()

    def _auto(self):
        """Auto: 根据图像直方图自动设置 min/max（由 MainWindow 调用）"""
        self.changed.emit()

    def _block_slider_signals(self, block: bool):
        for s in (self.slider_min, self.slider_max, self.slider_b, self.slider_c):
            s.blockSignals(block)

    def auto_stretch(self, img: np.ndarray) -> None:
        """ImageJ Auto: 用直方图找到 0.1%~99.9% 分位数作为 min/max"""
        if img is None:
            return
        vals = img.flatten()
        if img.ndim == 3:
            # 灰度化再算
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            vals = gray.flatten()
        lo = int(np.percentile(vals, 0.1))
        hi = int(np.percentile(vals, 99.9))
        if hi <= lo:
            hi = lo + 1
        self._block_slider_signals(True)
        self.slider_min.setValue(lo)
        self.slider_max.setValue(hi)
        self._min_val = lo
        self._max_val = hi
        self.lbl_min.setText(str(lo))
        self.lbl_max.setText(str(hi))
        self._block_slider_signals(False)
        self.changed.emit()


# ═══════════════════════════════════════════════
# 图像信息
# ═══════════════════════════════════════════════


def show_image_info(parent: QWidget, img: np.ndarray, image_path: str) -> None:
    """弹出图像信息对话框"""
    p = Path(image_path)
    file_size = p.stat().st_size if p.exists() else 0
    size_str = _human_size(file_size)

    if img.ndim == 2:
        h, w = img.shape
        channels = 1
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
    if size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    if size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    return f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"
