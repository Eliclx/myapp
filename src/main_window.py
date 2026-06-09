"""主窗口：组装所有组件"""

from __future__ import annotations

from pathlib import Path

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPixmap
from PyQt5.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMainWindow,
    QMessageBox,
    QProgressDialog,
    QStatusBar,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from annotation import AnnotationData, BBox  # pyright: ignore[reportImplicitRelativeImport]
from export_engine import export_annotations  # pyright: ignore[reportImplicitRelativeImport]
from image_view import ImageView  # pyright: ignore[reportImplicitRelativeImport]
from label_panel import LabelPanel  # pyright: ignore[reportImplicitRelativeImport]
from settings_dialog import QuickSettingsBar, SettingsDialog  # pyright: ignore[reportImplicitRelativeImport]


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("🏷️ LabelTool - 目标检测标注工具")
        self.resize(1400, 900)

        self.data = AnnotationData()
        self._crop_w: int = 640
        self._crop_h: int = 640
        self._jitter: int = 50
        self._output_dir: str = "output"

        self.setAcceptDrops(True)

        self._setup_ui()
        self._setup_toolbar()
        self._setup_statusbar()
        self._connect_signals()

    def _setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(4, 4, 4, 4)

        # 上半部分：左类别面板 + 右图视图
        content_layout = QHBoxLayout()
        self.label_panel = LabelPanel()
        self.image_view = ImageView()
        content_layout.addWidget(self.label_panel)
        content_layout.addWidget(self.image_view, stretch=1)
        main_layout.addLayout(content_layout, stretch=1)

        # 底部快捷设置栏
        self.quick_settings = QuickSettingsBar()
        main_layout.addWidget(self.quick_settings)

    def _setup_toolbar(self):
        tb = QToolBar("主工具栏")
        tb.setMovable(False)
        self.addToolBar(tb)

        tb.addAction("📂 打开图片", self._open_image)
        tb.addAction("💾 导出标注", self._export)
        tb.addSeparator()
        tb.addAction("⚙️ 设置", self._open_settings)
        tb.addSeparator()
        tb.addAction("🗑️ 清空标注", self._clear_annotations)

    def _setup_statusbar(self):
        self.status = QStatusBar()
        self.setStatusBar(self.status)

        self.lbl_pos = QLabel("坐标: -")
        self.lbl_img = QLabel("图片: 未加载")
        self.lbl_count = QLabel("标注: 0")
        self.lbl_zoom = QLabel("缩放: 100%")

        for lbl in (self.lbl_pos, self.lbl_img, self.lbl_count, self.lbl_zoom):
            lbl.setStyleSheet("padding: 0 8px;")
            self.status.addPermanentWidget(lbl)

    def _connect_signals(self):
        self.image_view.mouse_moved.connect(self._on_mouse_moved)
        self.image_view.bbox_created.connect(self._on_bbox_created)
        self.image_view.bbox_deleted.connect(self._on_bbox_deleted)
        self.image_view.label_edit_requested.connect(self._on_label_edit)
        self.label_panel.label_selected.connect(self._on_label_selected)

    # ─── 操作 ───

    def _open_image(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "打开图片",
            "",
            "图片 (*.png *.jpg *.jpeg *.bmp *.tif *.tiff);;所有文件 (*)",
        )
        if not path:
            return
        self._load_image(path)

    def _load_image(self, path: str) -> None:
        pixmap = QPixmap(path)
        if pixmap.isNull():
            QMessageBox.warning(self, "错误", f"无法加载图片:\n{path}")
            return

        self.data = AnnotationData(
            image_path=path,
            image_width=pixmap.width(),
            image_height=pixmap.height(),
        )
        self.image_view.load_image(path)
        self.image_view.set_current_label(self.label_panel.current_label())
        self.lbl_img.setText(
            f"图片: {Path(path).name} ({pixmap.width()}×{pixmap.height()})"
        )
        self._update_count()

    def _export(self):
        if not self.data.bboxes:
            QMessageBox.information(self, "提示", "还没有标注，先画几个框吧~")
            return
        if not self.data.is_loaded:
            QMessageBox.warning(self, "错误", "请先打开图片")
            return

        # 收集类别（确保每个框都有标签）
        unlabeled = [i for i, b in enumerate(self.data.bboxes) if not b.label]
        if unlabeled:
            QMessageBox.warning(
                self,
                "提示",
                f"有 {len(unlabeled)} 个框还没有设置类别。\n双击标注框可以修改类别。",
            )
            return

        output_dir = self._output_dir
        crop_w = self._crop_w
        crop_h = self._crop_h
        jitter = self._jitter

        # 进度对话框
        progress = QProgressDialog("导出中...", "取消", 0, len(self.data.bboxes), self)
        progress.setWindowTitle("导出标注")
        progress.setWindowModality(Qt.WindowModal)
        progress.setMinimumDuration(0)

        def on_progress(done, _total):
            progress.setValue(done)
            return progress.wasCanceled()

        files = export_annotations(
            bboxes=self.data.bboxes,
            image_path=self.data.image_path,
            img_w=self.data.image_width,
            img_h=self.data.image_height,
            crop_w=crop_w,
            crop_h=crop_h,
            jitter=jitter,
            output_dir=output_dir,
            progress_cb=on_progress,
        )

        progress.close()

        png_count = len([f for f in files if f.endswith(".png")])
        QMessageBox.information(
            self,
            "导出完成",
            f"生成了 {png_count} 张小图 + XML\n保存到: {Path(str(output_dir)).resolve()}",
        )

    def _open_settings(self):
        dlg = SettingsDialog(self)
        dlg.spin_crop_w.setValue(self._crop_w)
        dlg.spin_crop_h.setValue(self._crop_h)
        dlg.spin_jitter.setValue(self._jitter)
        dlg.edit_output_dir.setText(self._output_dir)

        if dlg.exec_() == dlg.Accepted:
            w, h = dlg.crop_size
            self._crop_w = w
            self._crop_h = h
            self._jitter = dlg.jitter
            self._output_dir = dlg.output_dir
            self.quick_settings.update_display(w, h, dlg.jitter, dlg.output_dir)

    def _clear_annotations(self):
        if self.data.bboxes:
            reply = QMessageBox.question(
                self,
                "确认",
                "清空所有标注？",
                QMessageBox.Yes | QMessageBox.No,
            )
            if reply == QMessageBox.Yes:
                self.data.bboxes.clear()
                self.image_view.clear_bbox_items()
                self._update_count()

    # ─── 信号处理 ───

    def _on_mouse_moved(self, x: int, y: int):
        self.lbl_pos.setText(f"坐标: ({x}, {y})")

    def _on_bbox_created(self, bbox: BBox):
        # 自动赋予当前选中的类别
        label = self.label_panel.current_label()
        if label:
            bbox.label = label
        self.data.add_bbox(bbox)
        self._update_count()
        # 同步图形项的显示
        self.image_view.update_bbox_style(bbox)

    def _on_bbox_deleted(self):
        # 重建数据
        self.data.bboxes = self.image_view.get_bboxes()
        self._update_count()

    def _on_label_edit(self, bbox: BBox):
        labels = self.label_panel.get_all_labels()
        current = bbox.label or ""
        label, ok = QInputDialog.getItem(
            self,
            "修改类别",
            "选择类别:",
            labels,
            labels.index(current) if current in labels else 0,
            editable=True,
        )
        if ok and label.strip():
            bbox.label = label.strip()
            self.label_panel.add_label(label.strip())
            # 更新图形项
            self.image_view.update_bbox_style(bbox)

    def _on_label_selected(self, label: str):
        self.image_view.set_current_label(label)

    def _update_count(self):
        self.lbl_count.setText(f"标注: {len(self.data.bboxes)}")

    # ─── 窗口事件 ───

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # 窗口大小变化时，如果有图片就重新适配
        if self.data.is_loaded:
            self.image_view.fitInView(
                self.image_view.get_scene_rect(), Qt.KeepAspectRatio
            )

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        for url in event.mimeData().urls():
            path = url.toLocalFile()
            if path.lower().endswith(
                (".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff")
            ):
                self._load_image(path)
                break
