"""
完整单元测试 + GUI 冒烟测试

用法（在 py_env 里）：
    cd src && python -m pytest test_all.py -v
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path
from xml.etree.ElementTree import fromstring

import cv2
import numpy as np
import pytest

# ─── 确保 offscreen 渲染（无显示器也能跑 Qt）───
os.environ["QT_QPA_PLATFORM"] = "offscreen"

# ═══════════════════════════════════════════════
# 1. annotation.py 纯逻辑测试
# ═══════════════════════════════════════════════

from annotation import BBox, AnnotationData


class TestBBox:
    def test_center(self):
        b = BBox(10, 20, 110, 220)
        assert b.cx == 60
        assert b.cy == 120

    def test_width_height(self):
        b = BBox(0, 0, 100, 50)
        assert b.width == 100
        assert b.height == 50

    def test_normalized_swap(self):
        b = BBox(100, 200, 10, 20)
        assert b.normalized() == (10, 20, 100, 200)

    def test_area(self):
        b = BBox(0, 0, 100, 50)
        assert b.area() == 5000

    def test_contains_point_inside(self):
        b = BBox(10, 10, 100, 100)
        assert b.contains_point(50, 50)

    def test_contains_point_outside(self):
        b = BBox(10, 10, 100, 100)
        assert not b.contains_point(5, 5)

    def test_iou_overlap(self):
        a = BBox(0, 0, 100, 100)
        b = BBox(50, 50, 150, 150)
        assert a.iou(b) > 0
        assert abs(a.iou(b) - b.iou(a)) < 1e-9  # 对称

    def test_iou_no_overlap(self):
        a = BBox(0, 0, 50, 50)
        b = BBox(100, 100, 200, 200)
        assert a.iou(b) == 0.0

    def test_iou_self(self):
        a = BBox(0, 0, 100, 100)
        assert a.iou(a) == 1.0

    def test_label(self):
        b = BBox(0, 0, 10, 10, "cat")
        assert b.label == "cat"


class TestAnnotationData:
    def test_add_bbox(self):
        data = AnnotationData()
        data.add_bbox(BBox(0, 0, 50, 50, "cat"))
        assert len(data.bboxes) == 1
        assert "cat" in data.labels

    def test_remove_bbox(self):
        data = AnnotationData()
        b = BBox(0, 0, 50, 50, "cat")
        data.add_bbox(b)
        data.remove_bbox(b)
        assert len(data.bboxes) == 0

    def test_find_bbox_at(self):
        data = AnnotationData()
        b = BBox(10, 10, 100, 100, "dog")
        data.add_bbox(b)
        assert data.find_bbox_at(50, 50) is b
        assert data.find_bbox_at(200, 200) is None

    def test_is_loaded_false(self):
        data = AnnotationData()
        assert not data.is_loaded


# ═══════════════════════════════════════════════
# 2. export_engine.py 裁剪逻辑测试
# ═══════════════════════════════════════════════

from export_engine import (
    _make_crop_center,
    _compute_crop_rect,
    _bboxes_in_crop,
    crop_and_save_png,
    build_voc_xml,
    export_annotations,
)


class TestCropCenter:
    def test_no_jitter(self):
        bbox = BBox(100, 100, 200, 200)
        cx, cy = _make_crop_center(bbox, 0, 1000, 1000, 640, 640)
        # cx=150 被 clamp 到 crop_w//2=320
        assert cx == 320
        assert cy == 320

    def test_no_clamp_needed(self):
        bbox = BBox(500, 500, 600, 600)
        cx, cy = _make_crop_center(bbox, 0, 2000, 2000, 640, 640)
        assert cx == 550
        assert cy == 550

    def test_clamp_edge(self):
        bbox = BBox(0, 0, 50, 50)
        cx, cy = _make_crop_center(bbox, 0, 1000, 1000, 640, 640)
        assert cx == 320
        assert cy == 320

    def test_clamp_far_edge(self):
        bbox = BBox(950, 950, 1000, 1000)
        cx, cy = _make_crop_center(bbox, 0, 1000, 1000, 640, 640)
        assert cx == 680  # 1000 - 320
        assert cy == 680

    def test_jitter_range(self):
        """jitter 后的裁剪中心应在合理范围内"""
        bbox = BBox(500, 500, 600, 600)
        for _ in range(100):
            cx, cy = _make_crop_center(bbox, 100, 2000, 2000, 640, 640)
            assert 320 <= cx <= 1680
            assert 320 <= cy <= 1680


class TestCropRect:
    def test_normal(self):
        x1, y1, x2, y2 = _compute_crop_rect(500, 500, 640, 640, 2000, 2000)
        assert x2 - x1 == 640
        assert y2 - y1 == 640
        assert x1 == 180
        assert y1 == 180

    def test_near_left_edge(self):
        x1, y1, x2, y2 = _compute_crop_rect(10, 500, 640, 640, 2000, 2000)
        assert x1 == 0
        assert x2 == 640

    def test_near_right_edge(self):
        x1, y1, x2, y2 = _compute_crop_rect(1990, 500, 640, 640, 2000, 2000)
        assert x2 == 2000
        assert x1 == 2000 - 640


class TestBboxesInCrop:
    def test_all_inside(self):
        bboxes = [BBox(100, 100, 200, 200, "a")]
        result = _bboxes_in_crop(bboxes, 0, 0, 640, 640)
        assert len(result) == 1
        assert result[0][0].label == "a"

    def test_all_outside(self):
        bboxes = [BBox(700, 700, 800, 800, "b")]
        result = _bboxes_in_crop(bboxes, 0, 0, 640, 640)
        assert len(result) == 0

    def test_partial_overlap(self):
        bboxes = [BBox(600, 100, 700, 200, "c")]
        result = _bboxes_in_crop(bboxes, 0, 0, 640, 640)
        assert len(result) == 1
        _, lx1, ly1, lx2, ly2 = result[0]
        assert lx1 == 600
        assert lx2 == 640  # clamp 到裁剪边界

    def test_multiple(self):
        bboxes = [
            BBox(100, 100, 200, 200, "a"),
            BBox(700, 700, 800, 800, "b"),
            BBox(300, 300, 400, 400, "c"),
        ]
        result = _bboxes_in_crop(bboxes, 0, 0, 640, 640)
        labels = [r[0].label for r in result]
        assert "a" in labels
        assert "c" in labels
        assert "b" not in labels

    def test_too_small_overlap_filtered(self):
        # 只重叠 3 像素，被过滤
        bboxes = [BBox(637, 100, 640, 200, "tiny")]
        result = _bboxes_in_crop(bboxes, 0, 0, 640, 640)
        assert len(result) == 0  # 3px < 5px 阈值


class TestCropAndSavePng:
    def test_normal_crop(self):
        with tempfile.TemporaryDirectory() as tmp:
            # 创建 200x200 的图
            img = np.zeros((200, 200, 3), dtype=np.uint8)
            img[50:150, 50:150] = 255  # 中间白色方块
            img_path = str(Path(tmp) / "test.png")
            _ = cv2.imwrite(img_path, img)

            # 先通过 imread 模拟实际使用（或直接传 ndarray）
            loaded = cv2.imread(img_path)
            out_path = str(Path(tmp) / "crop.png")
            crop_and_save_png(loaded, 50, 50, 150, 150, 100, 100, out_path)

            result = cv2.imread(out_path)
            assert result is not None
            assert result.shape == (100, 100, 3)
            # 中间应该是白色
            assert result[0, 0, 0] == 255

    def test_edge_padding(self):
        """裁剪区域超出图片边界时用黑色 padding"""
        with tempfile.TemporaryDirectory() as tmp:
            img = np.ones((100, 100, 3), dtype=np.uint8) * 128
            img_path = str(Path(tmp) / "test.png")
            _ = cv2.imwrite(img_path, img)

            out_path = str(Path(tmp) / "crop_pad.png")
            # 裁剪区域 (-20,-20)→(80,80)，但原图是 100x100
            # crop_w=100, crop_h=100，canvas 尺寸固定 100x100
            # src 有效区域: (0,0)→(80,80)，映射到 canvas 的 (20,20)→(100,100)
            # canvas (0,0)→(20,20) 是黑色 padding
            crop_and_save_png(
                img,
                -20,
                -20,
                80,
                80,
                100,
                100,
                out_path,
            )
            result = cv2.imread(out_path)
            assert result is not None
            assert result.shape == (100, 100, 3)
            # 左上角 (0,0) 是黑色 padding 区域
            assert result[0, 0, 0] == 0
            # 右下区域 (30,30) 对应原图有效内容
            assert result[30, 30, 0] == 128


class TestBuildVocXml:
    def test_single_object(self):
        xml = build_voc_xml("test.png", 640, 640, [("cat", 10, 20, 100, 200)])
        root = fromstring(xml)
        assert root.find("filename").text == "test.png"
        assert root.find("size/width").text == "640"
        obj = root.find("object")
        assert obj.find("name").text == "cat"
        assert obj.find("bndbox/xmin").text == "10"

    def test_multiple_objects(self):
        xml = build_voc_xml(
            "test.png",
            640,
            640,
            [
                ("cat", 10, 20, 100, 200),
                ("dog", 200, 300, 400, 500),
            ],
        )
        root = fromstring(xml)
        objects = root.findall("object")
        assert len(objects) == 2
        assert objects[0].find("name").text == "cat"
        assert objects[1].find("name").text == "dog"

    def test_empty_objects(self):
        xml = build_voc_xml("test.png", 640, 640, [])
        root = fromstring(xml)
        assert root.findall("object") == []


class TestExportIntegration:
    def test_full_export(self):
        """完整导出流程：合成大图 → 标注 → 裁剪 → XML"""
        with tempfile.TemporaryDirectory() as tmp:
            img_path = str(Path(tmp) / "big.png")
            fake_img = np.random.randint(0, 255, (800, 1000, 3), dtype=np.uint8)
            _ = cv2.imwrite(img_path, fake_img)

            bboxes = [
                BBox(400, 300, 500, 400, "cat"),
                BBox(100, 100, 200, 200, "dog"),
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

            pngs = sorted([f for f in files if f.endswith(".png")])
            xmls = sorted([f for f in files if f.endswith(".xml")])
            assert len(pngs) == 2
            assert len(xmls) == 2

            # 验证 PNG 尺寸
            for png in pngs:
                img = cv2.imread(png)
                assert img is not None
                h, w = img.shape[:2]
                assert w == 640
                assert h == 640

            # 验证 XML 合法
            for xml_path in xmls:
                content = Path(xml_path).read_text()
                root = fromstring(content)
                assert root.find("size/width").text == "640"
                assert root.find("size/height").text == "640"
                objects = root.findall("object")
                assert len(objects) >= 1
                for obj in objects:
                    xmin = int(obj.find("bndbox/xmin").text)
                    ymin = int(obj.find("bndbox/ymin").text)
                    xmax = int(obj.find("bndbox/xmax").text)
                    ymax = int(obj.find("bndbox/ymax").text)
                    assert 0 <= xmin < xmax <= 640, f"Invalid x: {xmin}-{xmax}"
                    assert 0 <= ymin < ymax <= 640, f"Invalid y: {ymin}-{ymax}"

    def test_overlapping_bboxes_in_same_crop(self):
        """两个重叠的标注框应出现在同一张小图中"""
        with tempfile.TemporaryDirectory() as tmp:
            img_path = str(Path(tmp) / "test.png")
            fake_img = np.zeros((1000, 1000, 3), dtype=np.uint8)
            _ = cv2.imwrite(img_path, fake_img)

            bboxes = [
                BBox(400, 400, 450, 450, "a"),
                BBox(420, 420, 470, 470, "b"),
            ]

            files = export_annotations(
                bboxes=bboxes,
                image_path=img_path,
                img_w=1000,
                img_h=1000,
                crop_w=640,
                crop_h=640,
                jitter=0,
                output_dir=str(Path(tmp) / "out"),
            )

            xmls = [f for f in files if f.endswith(".xml")]
            # 至少有一个 XML 包含两个 object
            found_multi = False
            for xml_path in xmls:
                root = fromstring(Path(xml_path).read_text())
                objects = root.findall("object")
                if len(objects) >= 2:
                    found_multi = True
                    labels = [o.find("name").text for o in objects]
                    assert "a" in labels
                    assert "b" in labels
            assert found_multi, "没有找到包含多个标注的裁剪图"

    def test_empty_bboxes(self):
        with tempfile.TemporaryDirectory() as tmp:
            files = export_annotations(
                bboxes=[],
                image_path="",
                img_w=1000,
                img_h=1000,
                crop_w=640,
                crop_h=640,
                jitter=0,
                output_dir=str(Path(tmp) / "out"),
            )
            assert files == []


# ═══════════════════════════════════════════════
# 3. GUI 冒烟测试（需要 QT_QPA_PLATFORM=offscreen）
# ═══════════════════════════════════════════════

from PyQt5.QtWidgets import QApplication


@pytest.fixture(scope="session")
def qapp():
    """全局 QApplication（offscreen 模式）"""
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    yield app


class TestImageView:
    def test_init(self, qapp):
        from image_view import ImageView

        view = ImageView()
        assert view is not None

    def test_load_image(self, qapp, tmp_path):
        from image_view import ImageView

        # 创建测试图片
        img = np.zeros((200, 300, 3), dtype=np.uint8)
        img_path = str(tmp_path / "test.png")
        _ = cv2.imwrite(img_path, img)

        view = ImageView()
        view.resize(800, 600)
        view.load_image(img_path)
        assert view._pixmap_item is not None

    def test_add_remove_bbox(self, qapp):
        from image_view import ImageView

        view = ImageView()
        view.resize(800, 600)

        bbox = BBox(10, 10, 100, 100, "test")
        item = view.add_bbox_item(bbox)
        assert len(view._bbox_items) == 1

        view.remove_bbox_item(bbox)
        assert len(view._bbox_items) == 0

    def test_clear_bbox_items(self, qapp):
        from image_view import ImageView

        view = ImageView()
        view.resize(800, 600)

        view.add_bbox_item(BBox(0, 0, 50, 50, "a"))
        view.add_bbox_item(BBox(50, 50, 100, 100, "b"))
        assert len(view._bbox_items) == 2

        view.clear_bbox_items()
        assert len(view._bbox_items) == 0

    def test_sync_bbox_items(self, qapp):
        from image_view import ImageView

        view = ImageView()
        view.resize(800, 600)

        bboxes = [BBox(0, 0, 50, 50, "a"), BBox(50, 50, 100, 100, "b")]
        view.sync_bbox_items(bboxes)
        assert len(view._bbox_items) == 2

    def test_set_current_label(self, qapp):
        from image_view import ImageView

        view = ImageView()
        view.set_current_label("cat")
        assert view._current_label == "cat"


class TestLabelPanel:
    def test_init(self, qapp):
        from label_panel import LabelPanel

        panel = LabelPanel()
        assert panel is not None

    def test_add_label(self, qapp):
        from label_panel import LabelPanel

        panel = LabelPanel()
        panel.add_label("cat")
        assert panel.current_label() == "cat"

    def test_add_duplicate(self, qapp):
        from label_panel import LabelPanel

        panel = LabelPanel()
        panel.add_label("cat")
        panel.add_label("cat")
        assert panel.get_all_labels() == ["cat"]

    def test_multiple_labels(self, qapp):
        from label_panel import LabelPanel

        panel = LabelPanel()
        panel.add_label("cat")
        panel.add_label("dog")
        assert panel.get_all_labels() == ["cat", "dog"]

    def test_empty_label(self, qapp):
        from label_panel import LabelPanel

        panel = LabelPanel()
        assert panel.current_label() == ""
        assert panel.get_all_labels() == []


class TestSettingsDialog:
    def test_init(self, qapp):
        from settings_dialog import SettingsDialog

        dlg = SettingsDialog()
        assert dlg is not None

    def test_default_values(self, qapp):
        from settings_dialog import SettingsDialog

        dlg = SettingsDialog()
        assert dlg.crop_size == (640, 640)
        assert dlg.jitter == 50
        assert dlg.output_dir == "output"

    def test_custom_values(self, qapp):
        from settings_dialog import SettingsDialog

        dlg = SettingsDialog()
        dlg.spin_crop_w.setValue(1280)
        dlg.spin_crop_h.setValue(720)
        dlg.spin_jitter.setValue(100)
        dlg.edit_output_dir.setText("custom_out")
        assert dlg.crop_size == (1280, 720)
        assert dlg.jitter == 100
        assert dlg.output_dir == "custom_out"


class TestQuickSettingsBar:
    def test_init(self, qapp):
        from settings_dialog import QuickSettingsBar

        bar = QuickSettingsBar()
        assert bar is not None

    def test_update_display(self, qapp):
        from settings_dialog import QuickSettingsBar

        bar = QuickSettingsBar()
        bar.update_display(1280, 720, "out")
        assert "1280" in bar.lbl_crop.text()
        assert "720" in bar.lbl_crop.text()
        assert "out" in bar.lbl_output.text()


class TestMainWindow:
    def test_init(self, qapp):
        from main_window import MainWindow

        win = MainWindow()
        assert win is not None
        assert win.data is not None

    def test_load_image(self, qapp, tmp_path):
        from main_window import MainWindow

        img = np.zeros((200, 300, 3), dtype=np.uint8)
        img_path = str(tmp_path / "test.png")
        _ = cv2.imwrite(img_path, img)

        win = MainWindow()
        win.resize(1400, 900)
        win._load_image(img_path)
        assert win.data.is_loaded
        assert win.data.image_width == 300
        assert win.data.image_height == 200
        assert "test.png" in win.lbl_img.text()

    def test_bbox_created_signal(self, qapp):
        from main_window import MainWindow

        win = MainWindow()
        win.resize(1400, 900)
        win.label_panel.add_label("cat")

        bbox = BBox(10, 10, 100, 100)
        win._on_bbox_created(bbox)
        assert len(win.data.bboxes) == 1
        assert win.data.bboxes[0].label == "cat"

    def test_bbox_deleted_rebuilds_data(self, qapp):
        from main_window import MainWindow

        win = MainWindow()
        win.resize(1400, 900)

        bbox = BBox(10, 10, 100, 100, "cat")
        win.data.add_bbox(bbox)
        win._on_bbox_deleted()
        assert len(win.data.bboxes) == 0

    def test_update_count(self, qapp):
        from main_window import MainWindow

        win = MainWindow()
        win.data.add_bbox(BBox(0, 0, 10, 10))
        win._update_count()
        assert "1" in win.lbl_count.text()

    def test_label_selected(self, qapp):
        from main_window import MainWindow

        win = MainWindow()
        win._on_label_selected("dog")
        assert win.image_view._current_label == "dog"


# ═══════════════════════════════════════════════
# 7. image_adjust.py B/C + LUT 测试
# ═══════════════════════════════════════════════

from image_adjust import compute_lut, apply_bc, ndarray_to_pixmap


class TestLUT:
    def test_identity(self):
        lut = compute_lut(0, 0)
        assert lut[0] == 0
        assert lut[128] == 128
        assert lut[255] == 255

    def test_brightness_positive(self):
        lut = compute_lut(50, 0)
        assert lut[0] > 0
        assert lut[255] == 255  # 已经最大，被 clip

    def test_brightness_negative(self):
        lut = compute_lut(-50, 0)
        assert lut[0] == 0
        assert lut[255] < 255

    def test_contrast_midpoint(self):
        lut = compute_lut(0, 50)
        assert lut[128] == 128  # 对比度不改变中点

    def test_contrast_darkens_shadows(self):
        lut = compute_lut(0, 50)
        assert lut[50] < 50  # 暗区更暗

    def test_contrast_brightens_highlights(self):
        lut = compute_lut(0, 50)
        assert lut[200] > 200  # 亮区更亮


class TestApplyBC:
    def test_identity_no_change(self):
        img = np.full((100, 100, 3), 128, dtype=np.uint8)
        result = apply_bc(img, 0, 0)
        assert np.array_equal(result, img)

    def test_brightness_changes(self):
        img = np.full((100, 100, 3), 128, dtype=np.uint8)
        result = apply_bc(img, 50, 0)
        assert result[50, 50, 0] > 128

    def test_does_not_modify_original(self):
        img = np.full((100, 100, 3), 128, dtype=np.uint8)
        _ = apply_bc(img, 50, 50)
        assert img[50, 50, 0] == 128  # 原图不变

    def test_grayscale(self):
        img = np.full((100, 100), 128, dtype=np.uint8)
        result = apply_bc(img, 50, 0)
        assert result[50, 50] > 128


class TestNdarrayToPixmap:
    def test_color(self):
        img = np.zeros((100, 100, 3), dtype=np.uint8)
        pm = ndarray_to_pixmap(img)
        assert not pm.isNull()
        assert pm.width() == 100
        assert pm.height() == 100

    def test_grayscale(self):
        img = np.zeros((100, 100), dtype=np.uint8)
        pm = ndarray_to_pixmap(img)
        assert not pm.isNull()
        assert pm.width() == 100


# ═══════════════════════════════════════════════
# 8. export_engine.py crop > img 测试
# ═══════════════════════════════════════════════


class TestCropLargerThanImage:
    def test_crop_center_when_larger(self):
        """crop > img 时居中"""
        bbox = BBox(10, 10, 50, 50)
        cx, cy = _make_crop_center(bbox, 0, 100, 80, 200, 200)
        assert cx == 50  # img_w // 2
        assert cy == 40  # img_h // 2

    def test_crop_rect_when_larger(self):
        """crop > img 时 x1 可以 < 0（padding 区域）"""
        x1, y1, x2, y2 = _compute_crop_rect(50, 40, 200, 200, 100, 80)
        assert x2 - x1 == 200
        assert y2 - y1 == 200

    def test_export_crop_larger_than_image(self):
        """完整导出：crop 大于图片尺寸"""
        with tempfile.TemporaryDirectory() as tmp:
            img_path = str(Path(tmp) / "small.png")
            fake_img = np.random.randint(0, 255, (80, 100, 3), dtype=np.uint8)
            cv2.imwrite(img_path, fake_img)

            bboxes = [BBox(20, 20, 60, 60, "obj")]
            files = export_annotations(
                bboxes=bboxes,
                image_path=img_path,
                img_w=100,
                img_h=80,
                crop_w=200,
                crop_h=200,
                jitter=0,
                output_dir=str(Path(tmp) / "out"),
            )
            pngs = [f for f in files if f.endswith(".png")]
            assert len(pngs) == 1
            result = cv2.imread(pngs[0])
            assert result is not None
            assert result.shape == (200, 200, 3)


# ═══════════════════════════════════════════════
# 9. 文件名唯一性测试
# ═══════════════════════════════════════════════


class TestFilenameUniqueness:
    def test_unique_filenames(self):
        """不同 bbox 应生成不同文件名"""
        with tempfile.TemporaryDirectory() as tmp:
            img_path = str(Path(tmp) / "test.png")
            fake_img = np.zeros((500, 500, 3), dtype=np.uint8)
            cv2.imwrite(img_path, fake_img)

            bboxes = [
                BBox(50, 50, 100, 100, "a"),
                BBox(200, 200, 300, 300, "b"),
            ]
            files = export_annotations(
                bboxes=bboxes,
                image_path=img_path,
                img_w=500,
                img_h=500,
                crop_w=200,
                crop_h=200,
                jitter=0,
                output_dir=str(Path(tmp) / "out"),
            )
            pngs = [Path(f).name for f in files if f.endswith(".png")]
            assert len(pngs) == len(set(pngs))  # 无重复
            # 文件名包含坐标信息
            for name in pngs:
                assert "_cx" in name
                assert "_cy" in name
