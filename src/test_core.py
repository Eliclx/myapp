"""单元测试：核心逻辑（不需要 GUI）"""
from __future__ import annotations

import tempfile
from pathlib import Path

import cv2
import numpy as np

from annotation import BBox, AnnotationData
from export_engine import (
    _make_crop_center,
    _compute_crop_rect,
    _bboxes_in_crop,
    build_voc_xml,
    export_annotations,
)


class TestBBox:
    def test_center(self):
        b = BBox(10, 20, 110, 220)
        assert b.cx == 60
        assert b.cy == 120

    def test_normalized_swap(self):
        b = BBox(100, 200, 10, 20)
        assert b.normalized() == (10, 20, 100, 200)

    def test_area(self):
        b = BBox(0, 0, 100, 50)
        assert b.area() == 5000

    def test_contains_point(self):
        b = BBox(10, 10, 100, 100)
        assert b.contains_point(50, 50)
        assert not b.contains_point(5, 5)

    def test_iou_overlap(self):
        a = BBox(0, 0, 100, 100)
        b = BBox(50, 50, 150, 150)
        assert a.iou(b) > 0

    def test_iou_no_overlap(self):
        a = BBox(0, 0, 50, 50)
        b = BBox(100, 100, 200, 200)
        assert a.iou(b) == 0.0


class TestAnnotationData:
    def test_add_bbox_auto_label(self):
        data = AnnotationData()
        data.add_bbox(BBox(0, 0, 50, 50, "cat"))
        assert "cat" in data.labels
        assert len(data.bboxes) == 1

    def test_find_bbox_at(self):
        data = AnnotationData()
        b = BBox(10, 10, 100, 100, "dog")
        data.add_bbox(b)
        assert data.find_bbox_at(50, 50) is b
        assert data.find_bbox_at(200, 200) is None


class TestCropLogic:
    def test_crop_center_no_jitter(self):
        bbox = BBox(100, 100, 200, 200)
        cx, cy = _make_crop_center(bbox, jitter=0, img_w=1000, img_h=1000, crop_w=640, crop_h=640)
        # cx=150 被 clamp 到 crop_w//2=320（确保裁剪区域不超出图片）
        assert cx == 320
        assert cy == 320

    def test_crop_center_no_clamp(self):
        bbox = BBox(500, 500, 600, 600)
        cx, cy = _make_crop_center(bbox, jitter=0, img_w=2000, img_h=2000, crop_w=640, crop_h=640)
        assert cx == 550
        assert cy == 550

    def test_crop_center_clamp_edge(self):
        bbox = BBox(0, 0, 50, 50)  # 左上角
        cx, cy = _make_crop_center(bbox, jitter=0, img_w=1000, img_h=1000, crop_w=640, crop_h=640)
        assert cx == 320  # 被 clamp 到 crop_w//2
        assert cy == 320

    def test_compute_crop_rect(self):
        x1, y1, x2, y2 = _compute_crop_rect(500, 500, 640, 640, 2000, 2000)
        assert x2 - x1 == 640
        assert y2 - y1 == 640

    def test_compute_crop_rect_near_edge(self):
        x1, y1, x2, y2 = _compute_crop_rect(10, 10, 640, 640, 2000, 2000)
        assert x1 == 0
        assert y1 == 0
        assert x2 - x1 == 640

    def test_bboxes_in_crop(self):
        bboxes = [
            BBox(100, 100, 200, 200, "a"),  # 完全在裁剪区域内
            BBox(700, 700, 800, 800, "b"),  # 完全在外面
            BBox(600, 100, 700, 200, "c"),  # 部分重叠
        ]
        result = _bboxes_in_crop(bboxes, 0, 0, 640, 640)
        labels = [b.label for b, *_ in result]
        assert "a" in labels
        assert "b" not in labels
        assert "c" in labels  # 部分重叠也会被纳入


class TestVocXml:
    def test_build_voc_xml(self):
        xml = build_voc_xml("test.png", 640, 640, [("cat", 10, 20, 100, 200)])
        assert "<name>cat</name>" in xml
        assert "<xmin>10</xmin>" in xml
        assert "<width>640</width>" in xml


class TestExportIntegration:
    def test_full_export(self):
        """用一张合成大图测试完整导出流程"""
        with tempfile.TemporaryDirectory() as tmp:
            # 生成一张 1000x800 的假图
            img_path = str(Path(tmp) / "test.png")
            fake_img = np.random.randint(0, 255, (800, 1000, 3), dtype=np.uint8)
            cv2.imwrite(img_path, fake_img)

            bboxes = [
                BBox(100, 100, 200, 200, "cat"),
                BBox(400, 300, 500, 400, "dog"),
                BBox(150, 150, 180, 180, "bird"),  # 和 cat 重叠，可能出现在同一小图
            ]

            output_dir = str(Path(tmp) / "output")
            files = export_annotations(
                bboxes=bboxes,
                image_path=img_path,
                img_w=1000,
                img_h=800,
                crop_w=640,
                crop_h=640,
                jitter=0,
                output_dir=output_dir,
            )

            # 应该生成 PNG + XML 文件
            pngs = [f for f in files if f.endswith(".png")]
            xmls = [f for f in files if f.endswith(".xml")]
            assert len(pngs) >= 1
            assert len(xmls) >= 1

            # 验证 PNG 尺寸
            for png in pngs:
                img = cv2.imread(png)
                assert img is not None
                h, w = img.shape[:2]
                assert w == 640
                assert h == 640

            # 验证 XML 格式
            for xml_path in xmls:
                content = Path(xml_path).read_text()
                assert "<annotation>" in content
                assert "<object>" in content
