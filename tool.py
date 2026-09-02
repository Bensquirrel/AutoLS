"""
批量重命名图片文件脚本
可以自定义目标目录、前缀、是否包含子目录等


pyinstaller --onedir --windowed --icon=p2.ico --name=幻帮跑商v1.0.0 --add-data "picture;picture" --add-data "adb;adb" --add-data "ocr/det.onnx;ocr" --add-data "ocr/rec.onnx;ocr" --add-data "ocr/keys.txt;ocr" --add-data "ocr/rapidocr_config.yaml;ocr" --add-data "ocr/cls.onnx;ocr" --add-data "configs.ini;." --add-data "p2.ico;." --exclude-module easyocr --exclude-module torch --exclude-module torchvision --exclude-module scipy --exclude-module skimage --exclude-module bidi main.py

推荐使用项目内的 幻帮跑商.spec 打包，spec 会自动把发布版 configs.ini 的 Debug.debug 设为 0。

"""
import os
from pathlib import Path

# ==================== 配置区域 ====================
# 目标目录（相对于脚本所在目录的路径）
TARGET_DIR = "picture/UI_City"

# 重命名前缀
PREFIX = "UI_City_"

# 是否包含子目录（True: 递归处理所有子目录，False: 只处理当前目录）
INCLUDE_SUBDIRS = False

# 支持的图片格式（可自行添加或删除）
IMAGE_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.bmp', '.gif', '.webp'}

# 是否跳过已包含前缀的文件（True: 跳过，False: 重新命名）
SKIP_IF_ALREADY_HAS_PREFIX = True

# 文件名冲突处理方式 ('auto_rename': 自动添加序号, 'skip': 跳过, 'overwrite': 覆盖)
CONFLICT_HANDLE = "auto_rename"

# 是否显示详细日志
VERBOSE = True
# ==================== 配置区域结束 ====================


def get_all_images(directory):
    """
    获取目录下所有图片文件
    :param directory: 目录路径
    :return: 图片文件列表
    """
    images = []

    if INCLUDE_SUBDIRS:
        # 递归搜索所有子目录
        for ext in IMAGE_EXTENSIONS:
            images.extend(directory.rglob(f"*{ext}"))
            # 也支持大写扩展名
            images.extend(directory.rglob(f"*{ext.upper()}"))
    else:
        # 只搜索当前目录
        for ext in IMAGE_EXTENSIONS:
            images.extend(directory.glob(f"*{ext}"))
            images.extend(directory.glob(f"*{ext.upper()}"))

    # 去重并转为Path对象
    return list(set(images))


def get_new_filename(old_name, counter=0):
    """
    生成新文件名
    :param old_name: 原文件名
    :param counter: 序号（用于冲突处理）
    :return: 新文件名
    """
    path = Path(old_name)
    stem = path.stem
    ext = path.suffix

    if counter > 0:
        return f"{PREFIX}{stem}_{counter}{ext}"
    else:
        return f"{PREFIX}{stem}{ext}"


def rename_images():
    """
    批量重命名图片文件
    """
    # 检查目录是否存在
    target_path = Path(TARGET_DIR)

    if not target_path.exists():
        print(f"❌ 错误: 目录不存在 - {target_path.absolute()}")
        return

    if not target_path.is_dir():
        print(f"❌ 错误: 路径不是目录 - {target_path.absolute()}")
        return

    # 获取所有图片文件
    images = get_all_images(target_path)

    if not images:
        print(f"⚠️ 未找到图片文件 (目录: {target_path.absolute()})")
        print(f"   支持的格式: {', '.join(IMAGE_EXTENSIONS)}")
        return

    print(f"📁 目标目录: {target_path.absolute()}")
    print(f"🏷️  前缀: {PREFIX}")
    print(f"📂 包含子目录: {'是' if INCLUDE_SUBDIRS else '否'}")
    print(f"📄 找到 {len(images)} 个图片文件")
    print("=" * 60)

    renamed_count = 0
    skipped_count = 0
    error_count = 0

    for file_path in images:
        old_name = file_path.name
        rel_path = file_path.relative_to(target_path) if INCLUDE_SUBDIRS else old_name

        # 检查是否已包含前缀
        if SKIP_IF_ALREADY_HAS_PREFIX and old_name.startswith(PREFIX):
            if VERBOSE:
                print(f"⏭️  跳过 (已有前缀): {rel_path}")
            skipped_count += 1
            continue

        # 生成新文件名
        new_name = get_new_filename(old_name)
        new_path = file_path.parent / new_name

        # 处理文件名冲突
        if new_path.exists():
            if CONFLICT_HANDLE == "skip":
                if VERBOSE:
                    print(f"⚠️  跳过 (目标已存在): {rel_path} -> {new_name}")
                skipped_count += 1
                continue
            elif CONFLICT_HANDLE == "overwrite":
                if VERBOSE:
                    print(f"⚠️  覆盖: {rel_path} -> {new_name}")
            else:  # auto_rename
                counter = 1
                while new_path.exists():
                    new_name = get_new_filename(old_name, counter)
                    new_path = file_path.parent / new_name
                    counter += 1
                if VERBOSE:
                    print(f"⚠️  冲突自动重命名: {rel_path} -> {new_name}")

        # 执行重命名
        try:
            file_path.rename(new_path)
            print(f"✅ 重命名: {rel_path} -> {new_name}")
            renamed_count += 1
        except Exception as e:
            print(f"❌ 错误: 重命名失败 {rel_path} - {e}")
            error_count += 1

    print("=" * 60)
    print(f"📊 完成! 重命名 {renamed_count} 个, 跳过 {skipped_count} 个, 错误 {error_count} 个")


def preview_changes():
    """
    预览将要进行的重命名操作（不实际执行）
    """
    target_path = Path(TARGET_DIR)

    if not target_path.exists():
        print(f"❌ 目录不存在: {target_path.absolute()}")
        return

    images = get_all_images(target_path)

    if not images:
        print("⚠️ 未找到图片文件")
        return

    print("=" * 60)
    print("预览重命名操作:")
    print("=" * 60)

    for file_path in images:
        old_name = file_path.name
        rel_path = file_path.relative_to(target_path) if INCLUDE_SUBDIRS else old_name

        if SKIP_IF_ALREADY_HAS_PREFIX and old_name.startswith(PREFIX):
            new_name = old_name + " (保持不变)"
        else:
            new_name = get_new_filename(old_name)

        print(f"  {rel_path} -> {new_name}")

    print("=" * 60)
    print(f"共 {len(images)} 个文件")


if __name__ == "__main__":
    import sys

    print("=" * 60)
    print("批量重命名图片脚本")
    print("=" * 60)

    if len(sys.argv) > 1 and sys.argv[1] == "--preview":
        preview_changes()
    elif len(sys.argv) > 1 and sys.argv[1] == "--help":
        print("使用方法:")
        print("  python rename_images.py          # 执行重命名（会询问确认）")
        print("  python rename_images.py --preview # 预览模式，不实际执行")
        print("  python rename_images.py --help    # 显示帮助")
        print()
        print("配置项（修改脚本开头的配置区域）:")
        print("  TARGET_DIR           - 目标目录")
        print("  PREFIX               - 重命名前缀")
        print("  INCLUDE_SUBDIRS      - 是否包含子目录")
        print("  IMAGE_EXTENSIONS     - 支持的图片格式")
        print("  SKIP_IF_ALREADY_HAS_PREFIX - 是否跳过已包含前缀的文件")
        print("  CONFLICT_HANDLE      - 冲突处理方式 (auto_rename/skip/overwrite)")
    else:
        preview_changes()
        print()
        response = input("是否执行重命名? (y/n): ").strip().lower()
        if response in ['y', 'yes', '是']:
            print()
            rename_images()
        else:
            print("操作已取消")
