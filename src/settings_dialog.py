"""设置对话框：小图尺寸、抖动范围等"""

from __future__ import annotations

from PyQt5.QtWidgets import (
    QFileDialog,
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
        self.spin_crop_w.setRange(64, 9999)
        self.spin_crop_w.setValue(640)
        self.spin_crop_w.setSingleStep(64)
        self.spin_crop_h = QSpinBox()
        self.spin_crop_h.setRange(64, 9999)
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
        btn_browse = QPushButton("浏览...")
        btn_browse.clicked.connect(self._browse_output_dir)
        out_layout.addWidget(self.edit_output_dir)
        out_layout.addWidget(btn_browse)
        out_group.setLayout(out_layout)
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

    def _browse_output_dir(self):
        dir_path = QFileDialog.getExistingDirectory(self, "选择输出目录")
        if dir_path:
            self.edit_output_dir.setText(dir_path)

    @property
    def output_dir(self) -> str:
        return self.edit_output_dir.text().strip() or "output"


class QuickSettingsBar(QWidget):
    """底部快捷设置栏，可实时调整抖动参数"""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 2, 4, 2)

        self.lbl_crop = QLabel("裁剪: 640×640")
        self.lbl_output = QLabel("输出: output/")

        # 抖动 SpinBox（可直接修改）
        jitter_label = QLabel("抖动:")
        self.spin_jitter = QSpinBox()
        self.spin_jitter.setRange(0, 2000)
        self.spin_jitter.setValue(50)
        self.spin_jitter.setSingleStep(10)
        self.spin_jitter.setFixedWidth(70)
        jitter_px = QLabel("px")

        for w in (self.lbl_crop, self.lbl_output, jitter_label):
            w.setStyleSheet("color: #666; font-size: 12px;")
        layout.addWidget(self.lbl_crop)
        layout.addWidget(self.lbl_output)
        layout.addWidget(jitter_label)
        layout.addWidget(self.spin_jitter)
        layout.addWidget(jitter_px)

        layout.addStretch()

    def update_display(self, crop_w: int, crop_h: int, output_dir: str) -> None:
        self.lbl_crop.setText(f"裁剪: {crop_w}×{crop_h}")
        self.lbl_output.setText(f"输出: {output_dir}/")
