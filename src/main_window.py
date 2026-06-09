"""主窗口：组装所有组件"""

from __future__ import annotations

from pathlib import Path

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff"}

import cv2
import numpy as np

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QKeySequence
from PyQt5.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMainWindow,
    QMessageBox,
    QProgressDialog,
    QShortcut,
    QStatusBar,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from annotation import AnnotationData, BBox  # pyright: ignore[reportImplicitRelativeImport]
from export_engine import export_annotations  # pyright: ignore[reportImplicitRelativeImport]
from image_adjust import (
    ImageAdjustDialog,
    apply_lut,
    ndarray_to_pixmap,
    show_image_info,
)  # pyright: ignore[reportImplicitRelativeImport]
from image_list_panel import ImageListPanel  # pyright: ignore[reportImplicitRelativeImport]
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

        # 文件夹导航
        self._image_list: list[str] = []
        self._image_index: int = -1
        self._annotations_cache: dict[str, list[BBox]] = {}

        # 当前图片 ndarray（用于读取像素值 + B/C 调整）
        self._current_img: np.ndarray | None = None

        # B/C 调整对话框
        self._bc_dialog: ImageAdjustDialog | None = None

        self.setAcceptDrops(True)

        self._setup_ui()
        self._setup_toolbar()
        self._setup_statusbar()
        self._setup_shortcuts()
        self._connect_signals()

    def _setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(4, 4, 4, 4)

        # 上半部分：左侧面板（图片列表 + 类别）+ 右图视图
        content_layout = QHBoxLayout()

        # 左侧垂直面板
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(2)
        self.image_list_panel = ImageListPanel()
        self.label_panel = LabelPanel()
        left_layout.addWidget(self.image_list_panel, stretch=1)
        left_layout.addWidget(self.label_panel)

        self.image_view = ImageView()
        content_layout.addWidget(left_panel)
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
        tb.addAction("📁 打开文件夹", self._open_folder)
        tb.addSeparator()
        tb.addAction("⬅ 上一张", self._prev_image)
        tb.addAction("➡ 下一张", self._next_image)
        tb.addSeparator()
        tb.addAction("💾 导出标注", self._export)
        tb.addSeparator()
        tb.addAction("🔆 亮度/对比度", self._open_bc_dialog)
        tb.addAction("📷 图像信息", self._show_image_info)
        tb.addSeparator()
        tb.addAction("⚙️ 设置", self._open_settings)
        tb.addSeparator()
        tb.addAction("🗑️ 清空标注", self._clear_annotations)

    def _setup_statusbar(self):
        self.status = QStatusBar()
        self.setStatusBar(self.status)

        self.lbl_pos = QLabel("坐标: -")
        self.lbl_pixel = QLabel("像素: -")
        self.lbl_img = QLabel("图片: 未加载")
        self.lbl_count = QLabel("标注: 0")
        self.lbl_zoom = QLabel("缩放: 100%")

        for lbl in (
            self.lbl_pos,
            self.lbl_pixel,
            self.lbl_img,
            self.lbl_count,
            self.lbl_zoom,
        ):
            lbl.setStyleSheet("padding: 0 8px;")
            self.status.addPermanentWidget(lbl)

    def _setup_shortcuts(self):
        QShortcut(QKeySequence("Ctrl+O"), self, self._open_image)
        QShortcut(QKeySequence("Ctrl+Shift+O"), self, self._open_folder)
        QShortcut(QKeySequence("Ctrl+S"), self, self._export)
        QShortcut(QKeySequence("Ctrl+,"), self, self._open_settings)
        QShortcut(QKeySequence("Ctrl+I"), self, self._show_image_info)
        QShortcut(QKeySequence("Ctrl+B"), self, self._open_bc_dialog)

    def _connect_signals(self):
        self.image_view.mouse_moved.connect(self._on_mouse_moved)
        self.image_view.bbox_created.connect(self._on_bbox_created)
        self.image_view.bbox_deleted.connect(self._on_bbox_deleted)
        self.image_view.label_edit_requested.connect(self._on_label_edit)
        self.image_view.navigate_prev.connect(self._prev_image)
        self.image_view.navigate_next.connect(self._next_image)
        self.image_view.zoom_changed.connect(self._on_zoom_changed)
        self.image_list_panel.image_selected.connect(self._on_list_image_selected)
        self.label_panel.label_selected.connect(self._on_label_selected)
        # 底部抖动 SpinBox 联动
        self.quick_settings.spin_jitter.valueChanged.connect(self._on_jitter_changed)

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
        # 单张打开时清空文件夹导航
        self._save_current_annotations()
        self._image_list = []
        self._image_index = -1
        self._load_image(path)

    def _open_folder(self):
        dir_path = QFileDialog.getExistingDirectory(self, "打开图片文件夹")
        if not dir_path:
            return
        self._save_current_annotations()
        self._image_list = self._scan_images(dir_path)
        if not self._image_list:
            QMessageBox.information(self, "提示", "该文件夹下没有找到图片文件")
            return
        self._image_index = 0
        self.image_list_panel.load_image_list(self._image_list)
        self._load_image(self._image_list[0])

    def _scan_images(self, dir_path: str) -> list[str]:
        """扫描文件夹下所有图片，按文件名排序"""
        images: list[str] = []
        for f in sorted(Path(dir_path).iterdir(), key=lambda p: p.name.lower()):
            if f.is_file() and f.suffix.lower() in IMAGE_EXTS:
                images.append(str(f))
        return images

    def _prev_image(self):
        if self._image_list and self._image_index > 0:
            self._navigate_to(self._image_index - 1)

    def _next_image(self):
        if self._image_list and self._image_index < len(self._image_list) - 1:
            self._navigate_to(self._image_index + 1)

    def _on_list_image_selected(self, index: int):
        """从图片列表点击选择"""
        if 0 <= index < len(self._image_list):
            self._navigate_to(index)

    def _navigate_to(self, index: int) -> None:
        """切换到指定图片，保存当前标注 + 恢复目标标注"""
        self._save_current_annotations()
        self._image_index = index
        self._load_image(self._image_list[index])
        # 同步列表高亮
        self.image_list_panel.set_current_index(index)
        # 恢复缓存标注
        path = self._image_list[index]
        if path in self._annotations_cache:
            for bbox in self._annotations_cache[path]:
                self.data.add_bbox(bbox)
            self.image_view.sync_bbox_items(self.data.bboxes)
            self._update_count()

    def _save_current_annotations(self) -> None:
        """把当前图片的标注存入缓存"""
        if self.data.is_loaded and self.data.bboxes:
            self._annotations_cache[self.data.image_path] = list(self.data.bboxes)

    def _load_image(self, path: str) -> None:
        # 只读一次文件：cv2.imread → ndarray → QPixmap
        img = cv2.imread(path, cv2.IMREAD_COLOR)
        if img is None:
            QMessageBox.warning(self, "错误", f"无法加载图片:\n{path}")
            return
        self._current_img = img

        h, w = img.shape[:2]
        pixmap = ndarray_to_pixmap(img)
        if pixmap.isNull():
            QMessageBox.warning(self, "错误", f"无法渲染图片:\n{path}")
            return

        self.data = AnnotationData(
            image_path=path,
            image_width=w,
            image_height=h,
        )
        self.image_view.load_from_pixmap(pixmap, w, h)
        self.image_view.set_current_label(self.label_panel.current_label())

        # 更新状态栏
        name = Path(path).name
        size_info = f"{w}×{h}"
        if self._image_list:
            idx_info = f"{self._image_index + 1}/{len(self._image_list)}"
            self.lbl_img.setText(f"图片: {name} ({size_info}) [{idx_info}]")
        else:
            self.lbl_img.setText(f"图片: {name} ({size_info})")
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
            self.quick_settings.spin_jitter.setValue(dlg.jitter)
            self.quick_settings.update_display(w, h, dlg.output_dir)

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
        # 显示像素值
        if self._current_img is not None:
            h, w = self._current_img.shape[:2]
            if 0 <= x < w and 0 <= y < h:
                val = self._current_img[y, x]
                if self._current_img.ndim == 2:
                    self.lbl_pixel.setText(f"像素: {int(val)}")
                else:
                    # OpenCV BGR 顺序
                    b, g, r = int(val[0]), int(val[1]), int(val[2])
                    self.lbl_pixel.setText(f"像素: ({r}, {g}, {b})")
            else:
                self.lbl_pixel.setText("像素: -")
        else:
            self.lbl_pixel.setText("像素: -")

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

    def _on_jitter_changed(self, value: int):
        self._jitter = value

    def _on_zoom_changed(self, pct: int):
        self.lbl_zoom.setText(f"缩放: {pct}%")

    # ─── B/C 调整 ───

    def _open_bc_dialog(self):
        if not self.data.is_loaded:
            QMessageBox.information(self, "提示", "请先打开图片")
            return
        if self._bc_dialog is None:
            self._bc_dialog = ImageAdjustDialog(self)
            self._bc_dialog.changed.connect(self._apply_bc)
        # 更新直方图数据
        if self._current_img is not None:
            self._bc_dialog.set_histogram(self._current_img)
        self._bc_dialog.show()
        self._bc_dialog.raise_()

    def _apply_bc(self):
        if self._current_img is None or self._bc_dialog is None:
            return
        lut = self._bc_dialog.get_lut()
        adjusted = apply_lut(self._current_img, lut)
        pixmap = ndarray_to_pixmap(adjusted)
        self.image_view.update_display_pixmap(pixmap)

    def _auto_bc(self):
        """Auto 按钮：自动拉伸"""
        if self._bc_dialog and self._current_img is not None:
            self._bc_dialog.auto_stretch(self._current_img)

    # ─── 图像信息 ───

    def _show_image_info(self):
        if self._current_img is None or not self.data.is_loaded:
            QMessageBox.information(self, "提示", "请先打开图片")
            return
        show_image_info(self, self._current_img, self.data.image_path)

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
