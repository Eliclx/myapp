"""大图视图：缩放、拖动、画标注框（LabelImg 风格交互）"""

from __future__ import annotations

from PyQt5.QtCore import QPointF, QRectF, Qt, pyqtSignal
from PyQt5.QtGui import QBrush, QColor, QPainter, QPen, QPixmap
from PyQt5.QtWidgets import (
    QGraphicsItem,
    QGraphicsRectItem,
    QGraphicsScene,
    QGraphicsView,
)

from annotation import BBox  # pyright: ignore[reportImplicitRelativeImport]

# 标注框颜色池
COLORS = [
    "#e6194b",
    "#3cb44b",
    "#4363d8",
    "#f58231",
    "#911eb4",
    "#42d4f4",
    "#f032e6",
    "#bfef45",
    "#fabed4",
    "#469990",
    "#dcbeff",
    "#9A6324",
    "#800000",
    "#aaffc3",
    "#808000",
    "#ffd8b1",
    "#000075",
    "#a9a9a9",
]

# 角点拖拽手柄的屏幕像素大小
HANDLE_PX = 6


class BBoxGraphicsItem(QGraphicsRectItem):
    """可交互的标注框图形项（支持选中、移动、角点缩放）"""

    def __init__(self, bbox: BBox, view: ImageView):
        x1, y1, x2, y2 = bbox.normalized()
        super().__init__(x1, y1, x2 - x1, y2 - y1)
        self.bbox = bbox
        self.view = view
        self.setFlag(QGraphicsItem.ItemIsSelectable, True)
        self.setAcceptHoverEvents(True)

        # 拖拽状态
        self._drag_mode: str | None = None  # 'move' / 'resize_tl'/'tr'/'br'/'bl'
        self._drag_start: QPointF | None = None
        self._orig_rect: QRectF | None = None
        self._update_style()

    # ─── 手柄尺寸（随缩放保持固定像素） ───

    def _handle_size(self) -> float:
        """手柄在场景坐标下的尺寸（缩放越大 → 场景尺寸越小 → 屏幕上不变）"""
        scale = self.view.transform().m11()
        return HANDLE_PX / max(scale, 0.01)

    def _corners(self) -> dict[str, QPointF]:
        r = self.rect()
        return {
            "tl": r.topLeft(),
            "tr": r.topRight(),
            "br": r.bottomRight(),
            "bl": r.bottomLeft(),
        }

    # ─── 命中检测 ───

    def _hit_test(self, scene_pos: QPointF) -> str | None:
        """检测鼠标点击位置对应的操作模式"""
        hs = self._handle_size()
        # 优先检测角点（选中状态才能 resize）
        if self.isSelected():
            for name, cp in self._corners().items():
                if abs(scene_pos.x() - cp.x()) <= hs and abs(scene_pos.y() - cp.y()) <= hs:
                    return f"resize_{name}"
        # 再检测框体
        if self.rect().contains(self.mapFromScene(scene_pos)):
            return "move"
        return None

    @staticmethod
    def _cursor_for(mode: str | None):
        if mode in ("resize_tl", "resize_br"):
            return Qt.SizeFDiagCursor
        if mode in ("resize_tr", "resize_bl"):
            return Qt.SizeBDiagCursor
        if mode == "move":
            return Qt.SizeAllCursor
        return Qt.ArrowCursor

    # ─── hover 光标 ───

    def hoverMoveEvent(self, event):  # noqa: N802
        if self.isSelected():
            hit = self._hit_test(event.scenePos())
            self.setCursor(self._cursor_for(hit))
        else:
            self.setCursor(Qt.ArrowCursor)
        super().hoverMoveEvent(event)

    def hoverLeaveEvent(self, event):  # noqa: N802
        self.setCursor(Qt.ArrowCursor)
        super().hoverLeaveEvent(event)

    # ─── 鼠标拖拽（移动 / 角点缩放） ───

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            hit = self._hit_test(event.scenePos())
            if hit:
                self._drag_mode = hit
                self._drag_start = event.scenePos()
                self._orig_rect = QRectF(self.rect())
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._drag_mode and self._drag_start and self._orig_rect:
            delta = event.scenePos() - self._drag_start
            r = self._orig_rect
            mode = self._drag_mode

            if mode == "move":
                new_rect = r.translated(delta)
            elif mode == "resize_br":
                new_rect = QRectF(r.topLeft(), r.bottomRight() + delta)
            elif mode == "resize_tl":
                new_rect = QRectF(r.topLeft() + delta, r.bottomRight())
            elif mode == "resize_tr":
                new_rect = QRectF(
                    QPointF(r.left(), r.top() + delta.y()),
                    QPointF(r.right() + delta.x(), r.bottom()),
                )
            elif mode == "resize_bl":
                new_rect = QRectF(
                    QPointF(r.left() + delta.x(), r.top()),
                    QPointF(r.right(), r.bottom() + delta.y()),
                )
            else:
                new_rect = r

            new_rect = new_rect.normalized()
            # 最小 2×2
            if new_rect.width() >= 2 and new_rect.height() >= 2:
                self.setRect(new_rect)
                self._sync_bbox()
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self._drag_mode:
            self._drag_mode = None
            self._drag_start = None
            self._orig_rect = None
            self._sync_bbox()
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def _sync_bbox(self):
        """图形 rect → 数据 BBox"""
        r = self.rect().normalized()
        self.bbox.x1 = int(r.left())
        self.bbox.y1 = int(r.top())
        self.bbox.x2 = int(r.right())
        self.bbox.y2 = int(r.bottom())

    # ─── 样式 ───

    def _update_style(self):
        color = QColor(self.view.get_label_color(self.bbox.label))
        pen = QPen(color, 3 if self.isSelected() else 2)
        pen.setCosmetic(True)
        self.setPen(pen)
        fill = QColor(color)
        fill.setAlpha(60 if self.isSelected() else 25)
        self.setBrush(QBrush(fill))

    def itemChange(self, change, value):
        if change == QGraphicsItem.ItemSelectedHasChanged:
            if not self.isSelected():
                self._drag_mode = None  # 取消选中时重置拖拽
            self._update_style()
        return super().itemChange(change, value)

    # ─── 绘制 ───

    def paint(self, painter, option, widget=None):
        super().paint(painter, option, widget)

        rect = self.rect()
        label = self.bbox.label or "?"
        color = QColor(self.view.get_label_color(self.bbox.label))

        # 标签文字（随缩放自适应）
        scale = self.view.transform().m11()
        base_px = max(10, min(16, int(14 / max(scale, 0.1))))
        font = painter.font()
        font.setPixelSize(base_px)
        font.setBold(True)
        painter.setFont(font)

        fm = painter.fontMetrics()
        text_width = fm.horizontalAdvance(label)
        text_height = fm.height()
        padding = 2

        label_y = rect.top() - text_height - padding * 2
        scene_top = 0 if not self.scene() else self.scene().sceneRect().top()
        if label_y < scene_top:
            label_y = rect.bottom() - text_height - padding
        label_x = rect.left()

        bg_rect = QRectF(
            label_x - padding,
            label_y - padding,
            text_width + padding * 2,
            text_height + padding * 2,
        )
        bg_color = QColor(color)
        bg_color.setAlpha(200)
        painter.fillRect(bg_rect, bg_color)
        painter.setPen(QPen(QColor("#ffffff")))
        painter.drawText(
            QPointF(label_x, label_y + text_height - fm.descent()), label
        )

        # 选中时绘制四角手柄
        if self.isSelected():
            hs = self._handle_size()
            half = hs / 2
            painter.setBrush(QBrush(QColor(255, 255, 255, 220)))
            painter.setPen(QPen(QColor(0, 0, 0), 1))
            for cp in self._corners().values():
                painter.drawRect(QRectF(cp.x() - half, cp.y() - half, hs, hs))

    def mouseDoubleClickEvent(self, event):
        self.view.label_edit_requested.emit(self.bbox)
        super().mouseDoubleClickEvent(event)


class ImageView(QGraphicsView):
    """大图交互视图（LabelImg 风格）"""

    label_edit_requested = pyqtSignal(object)  # BBox
    bbox_created = pyqtSignal(object)  # BBox
    bbox_deleted = pyqtSignal()
    mouse_moved = pyqtSignal(int, int)  # 原图坐标
    navigate_prev = pyqtSignal()
    navigate_next = pyqtSignal()
    annotate_mode_changed = pyqtSignal(bool)  # True=标注, False=选择
    zoom_changed = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._scene = QGraphicsScene(self)
        self.setScene(self._scene)

        self.setRenderHint(QPainter.Antialiasing)
        self.setRenderHint(QPainter.SmoothPixmapTransform)
        self.setViewportUpdateMode(QGraphicsView.FullViewportUpdate)
        self.setDragMode(QGraphicsView.NoDrag)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)

        # 颜色分配
        self._label_colors: dict[str, str] = {}
        self._color_idx = 0

        # 状态
        self._pixmap_item = None
        self._bbox_items: list[BBoxGraphicsItem] = []
        self._annotate_mode = False  # False=选择模式, True=标注模式
        self._drawing = False
        self._draw_start: QPointF | None = None
        self._temp_rect: QGraphicsRectItem | None = None
        self._current_label = ""
        self._panning = False
        self._pan_start = None
        self._base_scale = 1.0

    @property
    def annotate_mode(self) -> bool:
        return self._annotate_mode

    def set_annotate_mode(self, enabled: bool):
        """切换标注/选择模式"""
        self._annotate_mode = enabled
        if enabled:
            self.setCursor(Qt.CrossCursor)
        else:
            self.setCursor(Qt.ArrowCursor)
            self._cancel_drawing()
        self.annotate_mode_changed.emit(enabled)

    def deselect_all(self):
        """取消选中所有标注框"""
        for item in self._bbox_items:
            item.setSelected(False)

    # ─── 图片加载 ───

    def load_image(self, path: str) -> None:
        self._scene.clear()
        self._pixmap_item = None
        self._bbox_items.clear()
        if self._annotate_mode:
            self._annotate_mode = False
            self.setCursor(Qt.ArrowCursor)

        self._original_pixmap = QPixmap(path)
        if self._original_pixmap.isNull():
            return
        self._pixmap_item = self._scene.addPixmap(self._original_pixmap)
        self._scene.setSceneRect(QRectF(self._original_pixmap.rect()))
        self.fitInView(self._scene.sceneRect(), Qt.KeepAspectRatio)
        self._base_scale = self.transform().m11()
        self.zoom_changed.emit(100)

    def load_from_pixmap(self, pixmap: QPixmap, img_w: int, img_h: int) -> None:
        """从已有 QPixmap 加载显示（不重复读文件）"""
        self._scene.clear()
        self._bbox_items.clear()
        if self._annotate_mode:
            self._annotate_mode = False
            self.setCursor(Qt.ArrowCursor)
        self._original_pixmap = pixmap
        self._pixmap_item = self._scene.addPixmap(pixmap)
        self._scene.setSceneRect(QRectF(0, 0, img_w, img_h))
        self.fitInView(self._scene.sceneRect(), Qt.KeepAspectRatio)
        self._base_scale = self.transform().m11()
        self.zoom_changed.emit(100)

    def update_display_pixmap(self, pixmap: QPixmap) -> None:
        """替换当前显示的 pixmap（B/C 调整用）"""
        if self._pixmap_item is None:
            return
        self._pixmap_item.setPixmap(pixmap)

    # ─── 标注框管理 ───

    def add_bbox_item(self, bbox: BBox) -> BBoxGraphicsItem:
        item = BBoxGraphicsItem(bbox, self)
        self._scene.addItem(item)
        self._bbox_items.append(item)
        return item

    def remove_bbox_item(self, bbox: BBox) -> None:
        for item in self._bbox_items:
            if item.bbox is bbox:
                self._scene.removeItem(item)
                self._bbox_items.remove(item)
                break

    def clear_bbox_items(self) -> None:
        for item in self._bbox_items:
            self._scene.removeItem(item)
        self._bbox_items.clear()

    def sync_bbox_items(self, bboxes: list[BBox]) -> None:
        self.clear_bbox_items()
        for bbox in bboxes:
            self.add_bbox_item(bbox)

    def get_label_color(self, label: str) -> str:
        if label not in self._label_colors:
            self._label_colors[label] = COLORS[self._color_idx % len(COLORS)]
            self._color_idx += 1
        return self._label_colors[label]

    def get_bbox_count(self) -> int:
        return len(self._bbox_items)

    def get_bboxes(self) -> list[BBox]:
        return [item.bbox for item in self._bbox_items]

    def get_scene_rect(self) -> QRectF:
        return self._scene.sceneRect()

    def update_bbox_style(self, bbox: BBox) -> None:
        for item in self._bbox_items:
            if item.bbox is bbox:
                item._update_style()
                break

    def set_current_label(self, label: str) -> None:
        self._current_label = label

    # ─── 缩放 ───

    def wheelEvent(self, event):  # noqa: N802
        factor = 1.15 if event.angleDelta().y() > 0 else 1 / 1.15
        self.scale(factor, factor)
        self._emit_zoom()

    def _emit_zoom(self):
        if self._base_scale > 0:
            pct = int(round(self.transform().m11() / self._base_scale * 100))
            self.zoom_changed.emit(pct)

    # ─── 鼠标交互 ───

    def mousePressEvent(self, event):  # noqa: N802
        # 右键 / 中键：拖动画布
        if event.button() in (Qt.RightButton, Qt.MiddleButton):
            self._panning = True
            self._pan_start = event.pos()
            self.setCursor(Qt.ClosedHandCursor)
            return

        # 标注模式 + 左键：画框
        if event.button() == Qt.LeftButton and self._annotate_mode:
            scene_pos = self.mapToScene(event.pos())
            if self._scene.sceneRect().contains(scene_pos):
                self._drawing = True
                self._draw_start = scene_pos
                pen = QPen(QColor("#00ff00"), 2)
                pen.setCosmetic(True)
                self._temp_rect = self._scene.addRect(
                    QRectF(scene_pos, scene_pos), pen
                )
            return

        # 选择模式 + 左键：传给场景处理选中/拖动
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):  # noqa: N802
        scene_pos = self.mapToScene(event.pos())
        self.mouse_moved.emit(int(scene_pos.x()), int(scene_pos.y()))

        if self._drawing and self._temp_rect and self._draw_start:
            rect = QRectF(self._draw_start, scene_pos).normalized()
            self._temp_rect.setRect(rect)
            return

        if self._panning and self._pan_start:
            delta = event.pos() - self._pan_start
            self._pan_start = event.pos()
            self.horizontalScrollBar().setValue(
                self.horizontalScrollBar().value() - int(delta.x())
            )
            self.verticalScrollBar().setValue(
                self.verticalScrollBar().value() - int(delta.y())
            )
            return

        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):  # noqa: N802
        # 完成画框
        if event.button() == Qt.LeftButton and self._drawing:
            self._drawing = False
            if self._temp_rect:
                self._scene.removeItem(self._temp_rect)
                self._temp_rect = None

                scene_pos = self.mapToScene(event.pos())
                x1 = int(self._draw_start.x())  # pyright: ignore[reportOptionalMemberAccess]
                y1 = int(self._draw_start.y())  # pyright: ignore[reportOptionalMemberAccess]
                x2, y2 = int(scene_pos.x()), int(scene_pos.y())

                if abs(x2 - x1) > 2 and abs(y2 - y1) > 2:
                    bbox = BBox(
                        x1=min(x1, x2),
                        y1=min(y1, y2),
                        x2=max(x1, x2),
                        y2=max(y1, y2),
                        label=self._current_label,
                    )
                    self.add_bbox_item(bbox)
                    self.bbox_created.emit(bbox)
            return

        # 结束拖动画布
        if event.button() in (Qt.RightButton, Qt.MiddleButton):
            self._panning = False
            self.setCursor(Qt.CrossCursor if self._annotate_mode else Qt.ArrowCursor)
            return

        super().mouseReleaseEvent(event)

    def _cancel_drawing(self):
        if self._drawing:
            self._drawing = False
            if self._temp_rect:
                self._scene.removeItem(self._temp_rect)
                self._temp_rect = None

    # ─── 键盘 ───

    def keyPressEvent(self, event):  # noqa: N802
        key = event.key()
        if key == Qt.Key_Escape:
            if self._drawing:
                # ESC 1: 取消正在画的框
                self._cancel_drawing()
            elif self._annotate_mode:
                # ESC 2: 退出标注模式
                self.set_annotate_mode(False)
            else:
                # ESC 3: 取消选中
                self.deselect_all()
        elif key in (Qt.Key_Delete, Qt.Key_Backspace):
            for item in self._bbox_items[:]:
                if item.isSelected():
                    self._scene.removeItem(item)
                    self._bbox_items.remove(item)
                    self.bbox_deleted.emit()
        elif key == Qt.Key_F:
            if self._scene.sceneRect().width() > 0:
                self.fitInView(self._scene.sceneRect(), Qt.KeepAspectRatio)
                self._base_scale = self.transform().m11()
                self.zoom_changed.emit(100)
        elif key == Qt.Key_A:
            self.navigate_prev.emit()
        elif key == Qt.Key_D:
            self.navigate_next.emit()
        elif key == Qt.Key_W:
            self.set_annotate_mode(not self._annotate_mode)
        else:
            super().keyPressEvent(event)
