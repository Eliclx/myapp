"""设置对话框：小图尺寸、抖动范围等"""

from __future__ import annotations

from PyQt5.QtWidgets import (
    QDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)


class SettingsDialog(QDialog):
    """导出设置"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("⚙️ 导出设置")
        self.setMinimumWidth(350)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # 裁剪尺寸
        size_group = QGroupBox("裁剪尺寸")
        size_layout = QFormLayout()
        self.spin_crop_w = QSpinBox()
        self.spin_crop_w.setRange(64, 4096)
        self.spin_crop_w.setValue(640)
        self.spin_crop_w.setSingleStep(64)
        self.spin_crop_h = QSpinBox()
        self.spin_crop_h.setRange(64, 4096)
        self.spin_crop_h.setValue(640)
        self.spin_crop_h.setSingleStep(64)
        size_layout.addRow("宽度:", self.spin_crop_w)
        size_layout.addRow("高度:", self.spin_crop_h)
        size_group.setLayout(size_layout)
        layout.addWidget(size_group)

        # 抖动设置
        jitter_group = QGroupBox("随机抖动（防止过拟合）")
        jitter_layout = QFormLayout()
        self.spin_jitter = QSpinBox()
        self.spin_jitter.setRange(0, 2000)
        self.spin_jitter.setValue(50)
        self.spin_jitter.setSingleStep(10)
        self.spin_jitter.setToolTip("裁剪中心相对于目标中心的随机偏移范围（像素）")
        jitter_layout.addRow("抖动范围 (px):", self.spin_jitter)
        jitter_group.setLayout(jitter_layout)
        layout.addWidget(jitter_group)

        # 输出目录
        out_group = QGroupBox("输出目录")
        out_layout = QHBoxLayout()
        self.edit_output_dir = QLineEdit("output")
        out_layout.addWidget(self.edit_output_dir)
        layout.addWidget(out_group)

        # 按钮
        btn_layout = QHBoxLayout()
        btn_ok = QPushButton("确定")
        btn_ok.clicked.connect(self.accept)
        btn_cancel = QPushButton("取消")
        btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(btn_ok)
        btn_layout.addWidget(btn_cancel)
        layout.addLayout(btn_layout)

    @property
    def crop_size(self) -> tuple[int, int]:
        return self.spin_crop_w.value(), self.spin_crop_h.value()

    @property
    def jitter(self) -> int:
        return self.spin_jitter.value()

    @property
    def output_dir(self) -> str:
        return self.edit_output_dir.text().strip() or "output"


class QuickSettingsBar(QWidget):
    """底部快捷设置栏，显示当前参数"""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 2, 4, 2)

        self.lbl_crop = QLabel("裁剪: 640×640")
        self.lbl_jitter = QLabel("抖动: 50px")
        self.lbl_output = QLabel("输出: output/")

        for lbl in (self.lbl_crop, self.lbl_jitter, self.lbl_output):
            lbl.setStyleSheet("color: #666; font-size: 12px;")
            layout.addWidget(lbl)

        layout.addStretch()

    def update_display(
        self, crop_w: int, crop_h: int, jitter: int, output_dir: str
    ) -> None:
        self.lbl_crop.setText(f"裁剪: {crop_w}×{crop_h}")
        self.lbl_jitter.setText(f"抖动: {jitter}px")
        self.lbl_output.setText(f"输出: {output_dir}/")
