# convert_to_ico.py
from PIL import Image
import sys
from pathlib import Path

def convert_high_quality_ico(input_png, output_ico=None):
    input_path = Path(input_png)
    if not input_path.exists():
        print(f"错误：文件 {input_png} 不存在")
        return
    if output_ico is None:
        output_ico = input_path.with_suffix('.ico')

    img = Image.open(input_path)
    if img.mode != 'RGBA':
        img = img.convert('RGBA')

    # 目标尺寸（包含最大 256x256）
    sizes = [(256,256)]

    # 先缩放到 256x256（如果原始大于 256 则缩放到 256，否则保持）
    target_max = 256
    if img.width > target_max or img.height > target_max:
        img.thumbnail((target_max, target_max), Image.Resampling.LANCZOS)
    else:
        # 如果原始小于 256，可以进行适当放大（可能会轻微模糊，但 536 远大于 256，所以无需放大）
        pass

    # 生成各个尺寸
    icons = []
    for w, h in sizes:
        # 如果原始图片尺寸小于目标尺寸，则直接缩放（注意：上面已经缩放到 256，所以所有尺寸 <=256 均可靠）
        resized = img.resize((w, h), Image.Resampling.LANCZOS)
        icons.append(resized)

    # 保存为 ICO
    icons[0].save(output_ico, format='ICO', sizes=[(icon.width, icon.height) for icon in icons], append_images=icons[1:])
    print(f"已生成高质量 ICO：{output_ico}，包含尺寸：{sizes}")

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("用法：python convert_to_ico.py 图片.png")
    else:
        convert_high_quality_ico(sys.argv[1])