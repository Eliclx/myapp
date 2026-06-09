"""大图视图：缩放、拖动、画标注框"""

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


class BBoxGraphicsItem(QGraphicsRectItem):
    """可交互的标注框图形项"""

    def __init__(self, bbox: BBox, view: ImageView):
        x1, y1, x2, y2 = bbox.normalized()
        super().__init__(x1, y1, x2 - x1, y2 - y1)
        self.bbox = bbox
        self.view = view
        self.setFlag(QGraphicsItem.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.ItemIsMovable, True)
        self.setAcceptHoverEvents(True)
        self._update_style()

    def _update_style(self):
        color = QColor(self.view.get_label_color(self.bbox.label))
        pen = QPen(color, 3 if self.isSelected() else 2)
        pen.setCosmetic(True)  # 固定像素宽度，不随缩放变化
        self.setPen(pen)
        fill = QColor(color)
        fill.setAlpha(60 if self.isSelected() else 25)
        self.setBrush(QBrush(fill))
        self.setOpacity(1.0)

    def itemChange(self, change, value):
        if change == QGraphicsItem.ItemPositionHasChanged:
            # 同步位置回 BBox 数据模型
            pos = self.pos()
            rect = self.rect()
            self.bbox.x1 = int(rect.x() + pos.x())
            self.bbox.y1 = int(rect.y() + pos.y())
            self.bbox.x2 = int(rect.x() + rect.width() + pos.x())
            self.bbox.y2 = int(rect.y() + rect.height() + pos.y())
        elif change == QGraphicsItem.ItemSelectedHasChanged:
            self._update_style()
        return super().itemChange(change, value)

    def paint(self, painter, option, widget=None):
        super().paint(painter, option, widget)
        # 在框上方绘制标签背景 + 文字
        rect = self.rect()
        label = self.bbox.label or "?"
        color = QColor(self.view.get_label_color(self.bbox.label))
        font = painter.font()
        font.setPixelSize(14)
        font.setBold(True)
        painter.setFont(font)

        fm = painter.fontMetrics()
        text_width = fm.horizontalAdvance(label)
        text_height = fm.height()
        padding = 3
        label_x = rect.left()
        label_y = rect.top() - text_height - padding * 2

        # 标签背景色块
        bg_rect = QRectF(
            label_x - padding,
            label_y - padding,
            text_width + padding * 2,
            text_height + padding * 2,
        )
        bg_color = QColor(color)
        bg_color.setAlpha(200)
        painter.fillRect(bg_rect, bg_color)

        # 标签文字（白色）
        painter.setPen(QPen(QColor("#ffffff")))
        painter.drawText(QPointF(label_x, label_y + text_height - fm.descent()), label)

    def mouseDoubleClickEvent(self, event):
        # 双击编辑标签 → 由 view 处理
        self.view.label_edit_requested.emit(self.bbox)
        super().mouseDoubleClickEvent(event)


class ImageView(QGraphicsView):
    """大图交互视图"""

    label_edit_requested = pyqtSignal(object)  # BBox
    bbox_created = pyqtSignal(object)  # BBox
    bbox_deleted = pyqtSignal()
    mouse_moved = pyqtSignal(int, int)  # 原图坐标

    def __init__(self, parent=None):
        super().__init__(parent)
        self._scene = QGraphicsScene(self)
        self.setScene(self._scene)

        # 渲染优化
        self.setRenderHint(QPainter.Antialiasing)
        self.setRenderHint(QPainter.SmoothPixmapTransform)
        self.setViewportUpdateMode(QGraphicsView.FullViewportUpdate)
        self.setDragMode(QGraphicsView.NoDrag)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)

        # 颜色分配（实例级，避免多实例共享）
        self._label_colors: dict[str, str] = {}
        self._color_idx = 0

        # 状态
        self._pixmap_item = None
        self._bbox_items: list[BBoxGraphicsItem] = []
        self._drawing = False
        self._draw_start = None
        self._temp_rect = None
        self._current_label = ""
        self._panning = False
        self._pan_start = None

    # ─── 图片加载 ───

    def load_image(self, path: str) -> None:
        self._scene.clear()
        self._pixmap_item = None
        self._bbox_items.clear()

        pixmap = QPixmap(path)
        if pixmap.isNull():
            return
        self._pixmap_item = self._scene.addPixmap(pixmap)
        self._scene.setSceneRect(QRectF(pixmap.rect()))
        self.fitInView(self._scene.sceneRect(), Qt.KeepAspectRatio)

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
        """从数据模型重建图形项"""
        self.clear_bbox_items()
        for bbox in bboxes:
            self.add_bbox_item(bbox)

    def get_label_color(self, label: str) -> str:
        """为类别分配颜色（实例级）"""
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
        """更新指定 bbox 对应图形项的样式"""
        for item in self._bbox_items:
            if item.bbox is bbox:
                item._update_style()
                break

    def set_current_label(self, label: str) -> None:
        self._current_label = label

    # ─── 缩放 ───

    def wheelEvent(self, event):
        factor = 1.15 if event.angleDelta().y() > 0 else 1 / 1.15
        self.scale(factor, factor)

    # ─── 鼠标交互：画框 + 拖动 ───

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and not event.modifiers():
            # 开始画框
            scene_pos = self.mapToScene(event.pos())
            if self._scene.sceneRect().contains(scene_pos):
                self._drawing = True
                self._draw_start = scene_pos
                pen = QPen(QColor("#00ff00"), 2)
                pen.setCosmetic(True)
                self._temp_rect = self._scene.addRect(QRectF(scene_pos, scene_pos), pen)
                return

        if event.button() == Qt.RightButton or event.button() == Qt.MiddleButton:
            # 右键或中键：拖动画布
            self._panning = True
            self._pan_start = event.pos()
            self.setCursor(Qt.ClosedHandCursor)
            return

        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        scene_pos = self.mapToScene(event.pos())
        # 发送鼠标位置（原图坐标）
        x, y = int(scene_pos.x()), int(scene_pos.y())
        self.mouse_moved.emit(x, y)

        if self._drawing and self._temp_rect:
            rect = QRectF(self._draw_start, scene_pos).normalized()
            self._temp_rect.setRect(rect)
            return

        if self._panning:
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

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton and self._drawing:
            self._drawing = False
            if self._temp_rect:
                self._scene.removeItem(self._temp_rect)
                self._temp_rect = None

                scene_pos = self.mapToScene(event.pos())
                x1, y1 = int(self._draw_start.x()), int(self._draw_start.y())  # pyright: ignore[reportOptionalMemberAccess]
                x2, y2 = int(scene_pos.x()), int(scene_pos.y())

                # 忽略太小的框（误点击）
                if abs(x2 - x1) > 5 and abs(y2 - y1) > 5:
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

        if event.button() == Qt.RightButton or event.button() == Qt.MiddleButton:
            self._panning = False
            self.setCursor(Qt.ArrowCursor)
            return

        super().mouseReleaseEvent(event)

    def _cancel_drawing(self):
        """取消正在画的标注框"""
        if self._drawing:
            self._drawing = False
            if self._temp_rect:
                self._scene.removeItem(self._temp_rect)
                self._temp_rect = None

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            # ESC 取消正在画的标注框
            self._cancel_drawing()
        elif event.key() in (Qt.Key_Delete, Qt.Key_Backspace):
            # 删除选中的标注框
            for item in self._bbox_items[:]:
                if item.isSelected():
                    self._scene.removeItem(item)
                    self._bbox_items.remove(item)
                    self.bbox_deleted.emit()
        elif event.key() == Qt.Key_F:
            # F 键适配视口
            if self._scene.sceneRect().width() > 0:
                self.fitInView(self._scene.sceneRect(), Qt.KeepAspectRatio)
        else:
            super().keyPressEvent(event)
