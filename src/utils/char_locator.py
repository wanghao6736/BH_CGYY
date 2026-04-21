#!/usr/bin/env python3
"""
验证码文字定位服务
功能：检测文字区域 → 识别每个字符 → 定位目标字符的 bounding box
"""

import json
from pathlib import Path


def _load_ocr_deps():
    try:
        import cv2
        import ddddocr
        import numpy as np
        from PIL import Image, ImageDraw
    except ImportError as e:
        raise ImportError(
            "❌ CharLocator 缺少 OCR 依赖，请安装 `.[ocr]` 或使用完整打包版本"
        ) from e

    return cv2, ddddocr, np, Image, ImageDraw


class CharLocator:
    """文字定位器"""

    def __init__(self, show_ad=False):
        _, ddddocr, _, _, _ = _load_ocr_deps()
        self.det = ddddocr.DdddOcr(det=True, ocr=False, show_ad=show_ad)
        self.ocr = ddddocr.DdddOcr(show_ad=show_ad, beta=True)

    def locate_char(self, image_path: str = None, image_bytes: bytes = None,
                    target_char: str = None) -> dict:
        """
        定位目标字符在图片中的位置

        Args:
            image_path: 图片文件路径
            image_bytes: 图片字节数据
            target_char: 目标字符（可选，不提供则返回所有字符）

        Returns:
            定位结果
        """
        cv2, _, np, _, _ = _load_ocr_deps()

        # 加载图片
        if image_path:
            with open(image_path, 'rb') as f:
                img_bytes = f.read()
            img_cv = cv2.imread(image_path)
        elif image_bytes:
            img_bytes = image_bytes
            img_cv = cv2.imdecode(np.frombuffer(image_bytes, np.uint8), cv2.IMREAD_COLOR)
        else:
            return {"success": False, "error": "请提供 image_path 或 image_bytes"}

        # 1. 检测所有文字区域
        try:
            bboxes = self.det.detection(img_bytes)
        except Exception as e:
            return {"success": False, "error": f"检测失败：{e}"}

        if not bboxes:
            return {"success": False, "error": "未检测到任何文字区域"}

        # 2. 识别每个区域的字符
        results = []
        for i, bbox in enumerate(bboxes):
            x1, y1, x2, y2 = bbox

            # 裁剪区域
            roi = img_cv[y1:y2, x1:x2]
            roi_bytes = cv2.imencode('.jpg', roi)[1].tobytes()

            # 识别
            try:
                char = self.ocr.classification(roi_bytes)
                char = char.strip() if char else ""
            except BaseException:
                char = ""

            results.append({
                "index": i,
                "bbox": bbox,  # [x1, y1, x2, y2]
                "char": char,
                "size": {"width": x2 - x1, "height": y2 - y1}
            })

        # 3. 查找目标字符
        found = None
        if target_char:
            for r in results:
                if target_char in r["char"]:
                    found = r
                    break

        return {
            "success": True,
            "image_size": {"width": img_cv.shape[1], "height": img_cv.shape[0]},
            "total_chars": len(results),
            "target_char": target_char,
            "found": found is not None,
            "target_bbox": found["bbox"] if found else None,
            "target_index": found["index"] if found else None,
            "all_regions": results
        }

    def locate_multiple_chars(self, image_path: str, target_chars: list) -> dict:
        """
        定位多个目标字符

        Args:
            image_path: 图片路径
            target_chars: 目标字符列表

        Returns:
            定位结果
        """
        result = self.locate_char(image_path=image_path)
        if not result["success"]:
            return result

        found_chars = []
        for char in target_chars:
            for r in result["all_regions"]:
                if char in r["char"]:
                    found_chars.append({
                        "char": char,
                        "bbox": r["bbox"],
                        "index": r["index"]
                    })
                    break

        result["target_chars"] = target_chars
        result["found_chars"] = found_chars
        result["found_count"] = len(found_chars)

        return result


def draw_boxes_with_chars(image_path: str, regions: list, target_bbox: list = None,
                          output_path: str = None) -> str:
    """
    绘制标注图

    Args:
        image_path: 原图路径
        regions: 所有识别区域
        target_bbox: 目标 bbox（高亮显示）
        output_path: 输出路径

    Returns:
        输出图片路径
    """
    _, _, _, Image, ImageDraw = _load_ocr_deps()

    if not output_path:
        base = Path(image_path)
        output_path = str(base.parent / f"{base.stem}_located{base.suffix}")

    img = Image.open(image_path)
    draw = ImageDraw.Draw(img)

    for region in regions:
        x1, y1, x2, y2 = region["bbox"]
        char = region["char"]
        index = region["index"]

        # 判断是否为目标
        is_target = (target_bbox and region["bbox"] == target_bbox)

        # 颜色：目标用绿色，其他用红色
        color = "green" if is_target else "red"

        # 绘制矩形框
        draw.rectangle([x1, y1, x2, y2], outline=color, width=2 if is_target else 1)

        # 绘制标签
        label = f"#{index} {char}"
        draw.text((x1, y1 - 15), label, fill=color)

    img.save(output_path)
    return output_path


def main():
    import argparse
    parser = argparse.ArgumentParser(description='验证码文字定位')
    parser.add_argument('image', help='图片路径')
    parser.add_argument('--char', '-c', help='目标字符')
    parser.add_argument('--chars', nargs='+', help='多个目标字符')
    parser.add_argument('--output', '-o', help='输出标注图片路径')
    parser.add_argument('--json', action='store_true', help='输出 JSON 格式')

    args = parser.parse_args()

    locator = CharLocator()

    if args.chars:
        result = locator.locate_multiple_chars(args.image, args.chars)
    else:
        result = locator.locate_char(image_path=args.image, target_char=args.char)

    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        if result["success"]:
            print(f"✅ 检测到 {result['total_chars']} 个字符")
            print(f"📐 图片尺寸：{result['image_size']['width']}x{result['image_size']['height']}")

            if result["target_char"]:
                if result["found"]:
                    print(f"\n🎯 目标字符 '{result['target_char']}' 已定位:")
                    print(f"   索引：{result['target_index']}")
                    print(f"   bbox: {result['target_bbox']}")
                else:
                    print(f"\n❌ 未找到目标字符 '{result['target_char']}'")

            print("\n📋 所有字符位置:")
            for r in result["all_regions"]:
                marker = "🎯" if (result.get("target_bbox") and r["bbox"] == result["target_bbox"]) else "  "
                print(f"  {marker} [{r['index']}] '{r['char']}' - bbox: {r['bbox']}")

            # 绘制标注图
            output_path = draw_boxes_with_chars(
                args.image,
                result["all_regions"],
                result.get("target_bbox"),
                args.output
            )
            print(f"\n🖼️  标注图片已保存：{output_path}")
        else:
            print(f"❌ 失败：{result.get('error')}")


if __name__ == "__main__":
    main()
