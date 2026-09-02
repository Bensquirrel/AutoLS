# -*- mode: python ; coding: utf-8 -*-

import atexit
import configparser
import shutil
import tempfile
from pathlib import Path

# 发布用配置暂存区：AutoLS/configs.ini 保留开发值 debug=1，
# 进入 _internal 的 configs.ini 强制为 debug=0，避免把调试入口带进分发版。
_release_cfg_dir = Path(tempfile.mkdtemp(prefix='autols_release_cfg_'))
atexit.register(lambda: shutil.rmtree(_release_cfg_dir, ignore_errors=True))

_release_config = configparser.ConfigParser()
_release_config.read(Path('configs.ini'), encoding='utf-8')
if _release_config.has_section('Debug'):
    _release_config.set('Debug', 'debug', '0')

_release_config_path = _release_cfg_dir / 'configs.ini'
with open(_release_config_path, 'w', encoding='utf-8') as _cfg_file:
    _release_config.write(_cfg_file)


a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    # OCR 只收集 Maa 模型本身；旧的 *.pth 与下载压缩包不再进入发行版
    datas=[
        ('picture', 'picture'),
        ('adb', 'adb'),
        ('ocr/det.onnx', 'ocr'),
        ('ocr/rec.onnx', 'ocr'),
        ('ocr/keys.txt', 'ocr'),
        ('ocr/rapidocr_config.yaml', 'ocr'),
        ('ocr/cls.onnx', 'ocr'),
        (str(_release_config_path), '.'),
        ('p2.ico', '.'),
    ],
    # RapidOCR 在 ImageRecognition._setup_ocr 内惰性导入，显式声明便于 PyInstaller 收集
    hiddenimports=['rapidocr_onnxruntime'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    # 新 OCR 引擎不再使用 EasyOCR/PyTorch，显式排除以压缩发行版体积
    excludes=['easyocr', 'torch', 'torchvision', 'scipy', 'skimage', 'bidi'],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='幻帮跑商v1.0.0',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['p2.ico'],
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='幻帮跑商',
)
