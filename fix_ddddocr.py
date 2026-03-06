#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
ddddocr 包自动修复工具

修复 ddddocr 1.6.0 版本的导入错误：
1. core/__init__.py 中缺少 DdddOcr 导出
2. __init__.py 中导入了不存在的符号

使用方法:
    python tools/fix_ddddocr.py
"""

import shutil
import sys
from pathlib import Path


def find_venv_path():
    """查找虚拟环境路径"""
    # 检查常见的虚拟环境位置
    candidates = [
        Path(".venv"),
        Path("venv"),
    ]

    for candidate in candidates:
        if candidate.exists() and (candidate / "lib").exists():
            return candidate.resolve()

    return None


def find_ddddocr_path(venv_path):
    """查找 ddddocr 包路径"""
    python_version = f"python{sys.version_info.major}.{sys.version_info.minor}"
    site_packages = venv_path / "lib" / python_version / "site-packages"

    if not site_packages.exists():
        return None

    ddddocr_path = site_packages / "ddddocr"

    if not ddddocr_path.exists():
        return None

    return ddddocr_path


def backup_file(file_path):
    """备份文件"""
    backup_path = Path(str(file_path) + ".bak")
    shutil.copy2(file_path, backup_path)
    return backup_path


def fix_core_init(ddddocr_path):
    """修复 core/__init__.py"""
    core_init_path = ddddocr_path / "core" / "__init__.py"

    if not core_init_path.exists():
        print(f"  ✗ 文件不存在: {core_init_path}")
        return False

    # 备份原文件
    backup_path = backup_file(core_init_path)
    print(f"  ✓ 已备份到: {backup_path}")

    # 写入修复后的内容
    content = '''# coding=utf-8
"""
核心功能模块
提供OCR识别、目标检测、滑块匹配等核心功能
"""

from .base import BaseEngine
from .ocr_engine import OCREngine
from .detection_engine import DetectionEngine
from .slide_engine import SlideEngine

# 从 compat.legacy 导入 DdddOcr 以提供向后兼容
from ..compat.legacy import DdddOcr

__all__ = [
    'BaseEngine',
    'OCREngine',
    'DetectionEngine',
    'SlideEngine',
    'DdddOcr'  # 向后兼容
]
'''

    core_init_path.write_text(content, encoding='utf-8')
    print(f"  ✓ 已修复: {core_init_path}")
    return True


def fix_main_init(ddddocr_path):
    """修复主 __init__.py"""
    main_init_path = ddddocr_path / "__init__.py"

    if not main_init_path.exists():
        print(f"  ✗ 文件不存在: {main_init_path}")
        return False

    # 备份原文件
    backup_path = backup_file(main_init_path)
    print(f"  ✓ 已备份到: {backup_path}")

    # 写入修复后的内容
    content = '''# coding=utf-8
from .core import DdddOcr
from .utils import (
    base64_to_image,
    get_img_base64,
    png_rgba_black_preprocess,
    DDDDOCRError,
    ModelLoadError,
    ImageProcessError,
)

# 添加向后兼容的别名
DdddOcrInputError = DDDDOCRError
InvalidImageError = ImageProcessError

__all__ = [
    "DdddOcr",
    "base64_to_image",
    "get_img_base64",
    "png_rgba_black_preprocess",
    "DDDDOCRError",
    "ModelLoadError",
    "ImageProcessError",
    "DdddOcrInputError",  # 向后兼容别名
    "InvalidImageError",   # 向后兼容别名
]
'''

    main_init_path.write_text(content, encoding='utf-8')
    print(f"  ✓ 已修复: {main_init_path}")
    return True


def verify_fix():
    """验证修复是否成功"""
    try:
        import ddddocr
        ocr = ddddocr.DdddOcr(show_ad=False)
        print("  ✓ ddddocr.DdddOcr 初始化成功")
        print(f"    类型: {type(ocr).__name__}")
        return True
    except Exception as e:
        print(f"  ✗ 验证失败: {e}")
        return False


def main():
    """主函数"""
    print("=" * 60)
    print("ddddocr 包自动修复工具")
    print("=" * 60)

    # 查找虚拟环境
    print("\n1. 查找虚拟环境...")
    venv_path = find_venv_path()

    if not venv_path:
        print("  ✗ 未找到虚拟环境")
        print("  提示: 请在项目根目录运行此脚本")
        return 1

    print(f"  ✓ 找到虚拟环境: {venv_path}")

    # 查找 ddddocr 包
    print("\n2. 查找 ddddocr 包...")
    ddddocr_path = find_ddddocr_path(venv_path)

    if not ddddocr_path:
        print("  ✗ 未找到 ddddocr 包")
        print("  提示: 请先安装 ddddocr (uv add ddddocr)")
        return 1

    print(f"  ✓ 找到 ddddocr 包: {ddddocr_path}")

    # 确认修复
    print("\n3. 修复包文件...")
    print("  修复 core/__init__.py:")
    if not fix_core_init(ddddocr_path):
        return 1

    print("  修复 __init__.py:")
    if not fix_main_init(ddddocr_path):
        return 1

    # 验证修复
    print("\n4. 验证修复...")
    if not verify_fix():
        print("\n⚠️  修复可能未完全成功，请手动检查")
        return 1

    print("\n" + "=" * 60)
    print("✓ 修复完成！")
    print("=" * 60)
    print("\n后续步骤:")
    print("  1. 运行测试: python tests/test_login_manager.py")
    print("  2. 如果仍有问题，请查看备份文件 (*.bak)")
    print("\n注意: 如果重新安装 ddddocr 或删除虚拟环境，需要重新运行此工具")

    return 0


if __name__ == "__main__":
    sys.exit(main())
