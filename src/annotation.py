"""数据模型：标注框 + 标注集合"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class BBox:
    """一个标注框，坐标为原图像素坐标"""

    x1: int
    y1: int
    x2: int
    y2: int
    label: str = ""

    @property
    def cx(self) -> int:
        return (self.x1 + self.x2) // 2

    @property
    def cy(self) -> int:
        return (self.y1 + self.y2) // 2

    @property
    def width(self) -> int:
        return abs(self.x2 - self.x1)

    @property
    def height(self) -> int:
        return abs(self.y2 - self.y1)

    def normalized(self) -> tuple[int, int, int, int]:
        """确保 x1<x2, y1<y2"""
        return (
            min(self.x1, self.x2),
            min(self.y1, self.y2),
            max(self.x1, self.x2),
            max(self.y1, self.y2),
        )

    def area(self) -> int:
        x1, y1, x2, y2 = self.normalized()
        return (x2 - x1) * (y2 - y1)

    def contains_point(self, x: int, y: int, margin: int = 5) -> bool:
        x1, y1, x2, y2 = self.normalized()
        return (x1 - margin <= x <= x2 + margin) and (y1 - margin <= y <= y2 + margin)

    def iou(self, other: BBox) -> float:
        ax1, ay1, ax2, ay2 = self.normalized()
        bx1, by1, bx2, by2 = other.normalized()
        ix1, iy1 = max(ax1, bx1), max(ay1, by1)
        ix2, iy2 = min(ax2, bx2), min(ay2, by2)
        if ix1 >= ix2 or iy1 >= iy2:
            return 0.0
        inter = (ix2 - ix1) * (iy2 - iy1)
        union = self.area() + other.area() - inter
        return inter / union if union > 0 else 0.0


@dataclass
class AnnotationData:
    """一张大图的所有标注数据"""

    image_path: str = ""
    image_width: int = 0
    image_height: int = 0
    bboxes: list[BBox] = field(default_factory=list)
    labels: list[str] = field(default_factory=list)  # 全局类别列表

    def add_bbox(self, bbox: BBox) -> None:
        self.bboxes.append(bbox)
        if bbox.label and bbox.label not in self.labels:
            self.labels.append(bbox.label)

    def remove_bbox(self, bbox: BBox) -> None:
        if bbox in self.bboxes:
            self.bboxes.remove(bbox)

    def find_bbox_at(self, x: int, y: int) -> BBox | None:
        """找到包含 (x, y) 的最上面（最后添加）的框"""
        for bbox in reversed(self.bboxes):
            if bbox.contains_point(x, y):
                return bbox
        return None

    @property
    def is_loaded(self) -> bool:
        return bool(self.image_path) and Path(self.image_path).exists()
