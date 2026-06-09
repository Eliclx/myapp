"""导出引擎：裁剪小图 + 生成 VOC XML"""

from __future__ import annotations

import random
from pathlib import Path
from xml.etree.ElementTree import Element, SubElement, indent

import cv2
import numpy as np

from annotation import BBox  # pyright: ignore[reportImplicitRelativeImport]


def _make_crop_center(
    bbox: BBox, jitter: int, img_w: int, img_h: int, crop_w: int, crop_h: int
) -> tuple[int, int]:
    """计算裁剪中心（目标中心 + 随机抖动），clamp 到有效范围"""
    cx = bbox.cx + random.randint(-jitter, jitter)
    cy = bbox.cy + random.randint(-jitter, jitter)
    half_w, half_h = crop_w // 2, crop_h // 2
    # crop > img 时居中放置，否则 clamp 到图片范围内
    if crop_w <= img_w:
        cx = max(half_w, min(img_w - half_w, cx))
    else:
        cx = img_w // 2
    if crop_h <= img_h:
        cy = max(half_h, min(img_h - half_h, cy))
    else:
        cy = img_h // 2
    return cx, cy


def _compute_crop_rect(
    cx: int, cy: int, crop_w: int, crop_h: int, img_w: int, img_h: int
) -> tuple[int, int, int, int]:
    """计算裁剪区域，返回 (x1, y1, x2, y2) 原图像素坐标"""
    x1 = cx - crop_w // 2
    y1 = cy - crop_h // 2
    x2 = x1 + crop_w
    y2 = y1 + crop_h
    if crop_w <= img_w:
        if x1 < 0:
            x1, x2 = 0, crop_w
        if x2 > img_w:
            x1, x2 = img_w - crop_w, img_w
    if crop_h <= img_h:
        if y1 < 0:
            y1, y2 = 0, crop_h
        if y2 > img_h:
            y1, y2 = img_h - crop_h, img_h
    return x1, y1, x2, y2


def _bboxes_in_crop(
    bboxes: list[BBox], crop_x1: int, crop_y1: int, crop_x2: int, crop_y2: int
) -> list[tuple[BBox, int, int, int, int]]:
    """找出裁剪区域内的所有标注框，返回 (bbox, local_x1, local_y1, local_x2, local_y2)"""
    result: list[tuple[BBox, int, int, int, int]] = []
    for bbox in bboxes:
        bx1, by1, bx2, by2 = bbox.normalized()
        # 检查交集
        ix1 = max(bx1, crop_x1)
        iy1 = max(by1, crop_y1)
        ix2 = min(bx2, crop_x2)
        iy2 = min(by2, crop_y2)
        if ix1 < ix2 and iy1 < iy2:
            # 转为裁剪区域内的局部坐标
            lx1 = ix1 - crop_x1
            ly1 = iy1 - crop_y1
            lx2 = ix2 - crop_x1
            ly2 = iy2 - crop_y1
            # clamp 到 crop 边界
            lx2 = min(lx2, crop_x2 - crop_x1)
            ly2 = min(ly2, crop_y2 - crop_y1)
            # 过滤太小的残框
            if (lx2 - lx1) >= 5 and (ly2 - ly1) >= 5:
                result.append((bbox, lx1, ly1, lx2, ly2))
    return result


def crop_and_save_png(
    img: np.ndarray,
    crop_x1: int,
    crop_y1: int,
    crop_x2: int,
    crop_y2: int,
    crop_w: int,
    crop_h: int,
    save_path: str,
) -> None:
    """从大图裁剪指定区域，padding 到 crop_w × crop_h，保存为 PNG"""
    h, w = img.shape[:2]

    # 计算有效区域
    src_x1 = max(0, crop_x1)
    src_y1 = max(0, crop_y1)
    src_x2 = min(w, crop_x2)
    src_y2 = min(h, crop_y2)

    # 创建目标画布（黑色 padding）
    canvas = np.zeros((crop_h, crop_w, 3), dtype=np.uint8)
    dst_x1 = src_x1 - crop_x1
    dst_y1 = src_y1 - crop_y1
    canvas[dst_y1 : dst_y1 + (src_y2 - src_y1), dst_x1 : dst_x1 + (src_x2 - src_x1)] = (
        img[src_y1:src_y2, src_x1:src_x2]
    )

    Path(save_path).parent.mkdir(parents=True, exist_ok=True)
    _ = cv2.imwrite(save_path, canvas)


def build_voc_xml(
    image_name: str,
    img_w: int,
    img_h: int,
    objects: list[tuple[str, int, int, int, int]],  # (label, x1, y1, x2, y2)
) -> str:
    """生成 VOC 格式 XML 字符串"""
    root = Element("annotation")

    SubElement(root, "folder").text = "images"
    SubElement(root, "filename").text = image_name

    size = SubElement(root, "size")
    SubElement(size, "width").text = str(img_w)
    SubElement(size, "height").text = str(img_h)
    SubElement(size, "depth").text = "3"

    for label, x1, y1, x2, y2 in objects:
        obj = SubElement(root, "object")
        SubElement(obj, "name").text = label
        SubElement(obj, "pose").text = "Unspecified"
        SubElement(obj, "truncated").text = "0"
        SubElement(obj, "difficult").text = "0"
        bndbox = SubElement(obj, "bndbox")
        SubElement(bndbox, "xmin").text = str(x1)
        SubElement(bndbox, "ymin").text = str(y1)
        SubElement(bndbox, "xmax").text = str(x2)
        SubElement(bndbox, "ymax").text = str(y2)

    indent(root)
    from xml.etree.ElementTree import tostring

    return tostring(root, encoding="unicode", xml_declaration=True)


def export_annotations(
    bboxes: list[BBox],
    image_path: str,
    img_w: int,
    img_h: int,
    crop_w: int,
    crop_h: int,
    jitter: int,
    output_dir: str,
    progress_cb=None,
) -> list[str]:
    """
    导出所有标注：每个标注框生成一张小图 + XML。

    返回生成的文件路径列表。
    """
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    generated: list[str] = []

    if not bboxes:
        return generated

    # 只读一次大图，避免重复 I/O
    img = cv2.imread(image_path, cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError(f"无法读取图片: {image_path}")

    for i, bbox in enumerate(bboxes):
        x1, y1, x2, y2 = bbox.normalized()
        if (x2 - x1) < 5 or (y2 - y1) < 5:
            continue  # 跳过无效框

        # 1. 裁剪中心（带抖动）
        cx, cy = _make_crop_center(bbox, jitter, img_w, img_h, crop_w, crop_h)

        # 2. 裁剪区域
        crop_x1, crop_y1, crop_x2, crop_y2 = _compute_crop_rect(
            cx, cy, crop_w, crop_h, img_w, img_h
        )

        # 3. 找区域内所有标注框 + 转换坐标
        local_objects = _bboxes_in_crop(bboxes, crop_x1, crop_y1, crop_x2, crop_y2)
        if not local_objects:
            continue

        # 4. 生成文件名（文件夹名 + 文件名 + 裁剪中心坐标 + 索引，保证唯一）
        p = Path(image_path)
        folder_name = p.parent.name
        stem = p.stem
        base_name = f"{folder_name}_{stem}_cx{cx}_cy{cy}_{i:04d}"
        png_name = f"{base_name}.png"
        xml_name = f"{base_name}.xml"

        # 5. 裁剪保存 PNG
        actual_crop_w = crop_x2 - crop_x1
        actual_crop_h = crop_y2 - crop_y1
        png_path = str(output_path / png_name)
        crop_and_save_png(
            img,
            crop_x1,
            crop_y1,
            crop_x2,
            crop_y2,
            actual_crop_w,
            actual_crop_h,
            png_path,
        )

        # 6. 生成 VOC XML（坐标映射到实际裁剪尺寸）
        xml_objects = [
            (b.label, lx1, ly1, lx2, ly2) for b, lx1, ly1, lx2, ly2 in local_objects
        ]
        xml_str = build_voc_xml(png_name, actual_crop_w, actual_crop_h, xml_objects)
        xml_path = str(output_path / xml_name)
        _ = Path(xml_path).write_text(xml_str, encoding="utf-8")

        generated.extend([png_path, xml_path])

        if progress_cb and progress_cb(i + 1, len(bboxes)):
            break  # 用户取消

    return generated
