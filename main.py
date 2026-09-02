import configparser
import ctypes
import logging
import os

os.environ['OMP_NUM_THREADS'] = '1'
os.environ['MKL_NUM_THREADS'] = '1'

import platform
import subprocess  # 添加 subprocess 导入
import sys
import threading
import time
import tkinter as tk
import re
import json
import traceback
from datetime import datetime
from pathlib import Path
from tkinter import filedialog
from tkinter import ttk, scrolledtext, messagebox
import cv2
import numpy as np
from PIL import Image
from PIL import ImageTk

def resource_path(relative_path):
    """获取资源的绝对路径，打包后资源在 exe 所在目录的 _internal 下"""
    if getattr(sys, 'frozen', False):
        # 打包后，资源位于 exe 同级目录的 _internal 文件夹内
        base_path = os.path.join(os.path.dirname(sys.executable), "_internal")
    else:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

# ==================== 日志模块 ====================
class Logger:
    """
    日志管理类
    负责程序运行日志的记录和输出
    """
    def __init__(self, log_file="log.txt"):
        """
        初始化日志系统
        :param log_file: 日志文件路径
        """
        self.log_file = log_file
        self.callback = None
        self.setup_logger()

    def set_callback(self, callback):
        """
        设置UI回调函数，用于实时显示日志
        :param callback: 回调函数，接收日志字符串作为参数
        """
        self.callback = callback

    def setup_logger(self):
        """配置Python logging模块，同时输出到文件和标准输出"""
        log_path = Path(self.log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)

        self.logger = logging.getLogger('JailMaster')
        self.logger.setLevel(logging.INFO)
        # 清除已有的处理器，避免重复日志
        self.logger.handlers.clear()

        # 文件处理器：将日志写入文件
        file_handler = logging.FileHandler(self.log_file, encoding='utf-8')
        file_handler.setLevel(logging.INFO)

        # 格式化器：定义日志格式
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s',
                                      datefmt='%Y-%m-%d %H:%M:%S')
        file_handler.setFormatter(formatter)
        self.logger.addHandler(file_handler)

    def _output(self, level, message, tag=None):
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        log_entry = f"[{timestamp}] {message}"
        if level == 'INFO':
            self.logger.info(message)
        elif level == 'WARNING':
            self.logger.warning(message)
        elif level == 'ERROR':
            self.logger.error(message)
        else:
            self.logger.info(message)
        if self.callback:
            self.callback(log_entry, tag)

    def info(self, message):
        self._output('INFO', message)

    def warning(self, message):
        self._output('WARNING', message)

    def error(self, message):
        self._output('ERROR', message, tag='error')

    def debug(self, message):
        self._output('DEBUG', message)

    def error_red(self, message):
        """输出红色错误信息（带 traceback）"""
        self._output('ERROR', message, tag='error')


# ==================== 配置管理模块 ====================
class ConfigManager:
    def __init__(self, config_file="configs.ini"):
        self.config_file = resource_path(config_file)
        self._config = configparser.ConfigParser()
        self.load_config()

    def load_config(self):
        """加载配置文件，如果文件不存在则创建默认配置"""
        if Path(self.config_file).exists():
            self._config.read(self.config_file, encoding='utf-8')
        else:
            self.create_default_config()

    def create_default_config(self):
        """创建默认配置，包含所有必需的配置节和默认值"""

        # ADB连接配置
        self._config['ADB'] = {
            'default_port': '5555',
            'screenshot_quality': '90',
            'screenshot_path': 'temp/screenshot.jpg',
            'cn': json.dumps({
                "default_port": "端口",
                "screenshot_quality": "截图质量",
                "screenshot_path": "截图保存路径"
            }),
            'section_cn': 'ADB设置'
        }

        # 图像识别配置
        self._config['Recognition'] = {
            'match_threshold': '0.82',
            'use_gray': 'True',
            'template_folder': 'picture',
            'cn': json.dumps({"match_threshold": "匹配阈值", "use_gray": "使用灰度", "template_folder": "模板文件夹"}),
            'section_cn': '图像识别'
        }

        # OCR识别配置：语种由 ocr 目录内的 Maa 模型决定，无需单独配置语言
        self._config['OCR'] = {
            'preprocess': 'False',
            'text_score': '0.5',
            'box_thresh': '0.5',
            'unclip_ratio': '1.6',
            'cn': json.dumps({
                "preprocess": "识别前二值化",
                "text_score": "识别置信度阈值(0-1)",
                "box_thresh": "检测框置信度阈值(0-1)",
                "unclip_ratio": "检测框扩展倍率(1.0-2.0)"
            }),
            'section_cn': 'OCR识别'
        }

        # 自动化配置
        self._config['Auto'] = {
            'click_interval': '0.5',
            'check_interval': '1.0',
            'default_run_time': '9999999',
            'cn': json.dumps(
                {"click_interval": "点击间隔", "check_interval": "检测间隔", "default_run_time": "默认运行时间"}),
            'section_cn': '自动化设置'
        }

        # 路径配置
        self._config['Paths'] = {
            'picture_folder': 'picture',
            'log_file': 'log.txt',
            'temp_folder': 'temp',
            'cn': json.dumps({"picture_folder": "图片文件夹", "log_file": "日志文件", "temp_folder": "临时文件夹"}),
            'section_cn': '路径设置'
        }

        # Debug配置
        self._config['Debug'] = {
            'debug': '0',
            'cn': json.dumps({"debug": "调试模式"}),
            'section_cn': '调试设置'
        }

        # UI配置
        self._config['UI'] = {
            'version': 'v1.0.0',
            'cn': json.dumps({"version": "版本号"}),
            'section_cn': '界面设置'
        }

        self._config['Medicine'] = {
            'enabled': 'False',
            'cn': json.dumps({"enabled": "是否用药"}),
            'section_cn': '用药设置'
        }

        self._config['Litter'] = {
            'enabled': 'False',
            'click_x': '1100',
            'click_y': '600',
            'click_interval': '0.5',
            'cn': json.dumps({"enabled": "是否捡垃圾", "click_x": "点击X坐标", "click_y": "点击Y坐标",
                              "click_interval": "点击间隔(秒)"}),
            'section_cn': '捡垃圾设置'
        }

        # 城市配置 - 只存储城市列表
        default_cities = '武林源,贡露城,黑月游乐城,塔图站,栖羽站,岚心城,远星大桥,汇流塔,云岫桥基地,海角城,阿妮塔发射中心,淘金乐园,曼德矿场,荒原站,阿妮塔战备工厂,阿妮塔能源研究所,澄明数据中心,铁盟哨站,7号自由港,修格里城'

        self._config['City'] = {
            'cities': default_cities,
            'cn': json.dumps({"cities": "城市列表"}),
            'section_cn': '城市列表'
        }

        # 为每个城市创建详细配置
        cities = [c.strip() for c in default_cities.split(',')]
        for city in cities:
            section_name = f"City_{city}"
            self._config[section_name] = {
                'purchase_book_count': '0',
                'enable_bargain': 'True',
                'enable_price_increase': 'False',
                'cn': json.dumps({
                    "purchase_book_count": "进货书数量",
                    "enable_bargain": "是否砍价",
                    "enable_price_increase": "是否抬价"
                }),
                'section_cn': f'{city}配置'
            }

        self.save_config()

    def save_config(self):
        """将当前配置保存到文件"""
        with open(self.config_file, 'w', encoding='utf-8') as f:
            self._config.write(f)

    def get(self, section, key, fallback=None):
        """获取字符串类型的配置值"""
        try:
            return self._config.get(section, key, fallback=fallback)
        except:
            return fallback

    def get_int(self, section, key, fallback=0):
        """获取整数类型的配置值"""
        try:
            return self._config.getint(section, key, fallback=fallback)
        except:
            return fallback

    def get_float(self, section, key, fallback=0.0):
        """获取浮点数类型的配置值"""
        try:
            return self._config.getfloat(section, key, fallback=fallback)
        except:
            return fallback

    def get_bool(self, section, key, fallback=False):
        """获取布尔类型的配置值"""
        try:
            return self._config.getboolean(section, key, fallback=fallback)
        except:
            return fallback

    def set(self, section, key, value):
        """设置配置值并保存"""
        if section not in self._config:
            self._config[section] = {}
        self._config[section][key] = str(value)
        self.save_config()

    def get_section_cn(self, section):
        """获取配置节的中文显示名称"""
        section_cn = self.get(section, 'section_cn', '')
        if section_cn:
            return section_cn
        return section

    def get_cn_name(self, section, key):
        """获取配置项的中文显示名称"""
        cn_str = self.get(section, 'cn', '{}')
        try:
            cn_str = cn_str.replace("'", '"')
            cn_dict = json.loads(cn_str)
            return cn_dict.get(key, key)
        except:
            return key

    def get_section_keys(self, section, debug_mode=0):
        """
        获取配置节中的所有键名（排除 cn 和 section_cn 键）
        :param section: 配置节
        :param debug_mode: 调试模式，0=只显示cn中定义的键，1=显示所有键
        :return: 键名列表
        """
        if section not in self._config:  # 修复：使用 self._config
            return []

        # 排除 cn 和 section_cn 键
        exclude_keys = ['cn', 'section_cn']
        all_keys = [k for k in self._config[section] if k not in exclude_keys]

        if debug_mode == 0:
            # 正常模式：只显示 cn 中定义的键
            cn_str = self.get(section, 'cn', '{}')
            try:

                cn_str = cn_str.replace("'", '"')
                cn_dict = json.loads(cn_str)
                cn_keys = list(cn_dict.keys())
                return [k for k in all_keys if k in cn_keys]
            except:
                return all_keys
        else:
            return all_keys

    def get_city_config(self, city_name, key, default='0'):
        """获取指定城市的配置"""
        section_name = f"City_{city_name}"
        if self._config.has_section(section_name):
            value = self.get(section_name, key, default)
            return value
        return default

    def set_city_config(self, city_name, key, value):
        """设置指定城市的配置"""
        section_name = f"City_{city_name}"

        if not self._config.has_section(section_name):
            self._config.add_section(section_name)
            self._config.set(section_name, 'cn',
                             '{"purchase_book_count":"进货书数量","enable_bargain":"是否砍价","enable_price_increase":"是否抬价"}')
            self._config.set(section_name, 'section_cn', f'{city_name}配置')

        self._config.set(section_name, key, str(value))
        self.save_config()

    def has_section(self, section):
        """检查配置节是否存在"""
        return self._config.has_section(section)

# ==================== ADB控制模块 ====================
class ADBController:
    """
    ADB控制类
    使用本地adb.exe实现与Android设备的通信
    提供截图、点击、滑动、输入文本等功能
    """

    def __init__(self, config_manager, logger):
        """
        初始化ADB控制器
        :param config_manager: 配置管理器实例
        :param logger: 日志记录器实例
        """
        self.config = config_manager
        self.logger = logger
        self.device = None
        self.connected = False
        self.host = None
        self.port = None
        self.adb_path = self._get_adb_path()

        # 隐藏子进程窗口（仅 Windows）
        if platform.system() == "Windows":
            self.creationflags = subprocess.CREATE_NO_WINDOW
        else:
            self.creationflags = 0

    def _get_adb_path(self):
        local_adb = Path(resource_path("adb/adb.exe"))
        if not local_adb.exists():
            raise FileNotFoundError(f"本地 ADB 不存在: {local_adb}")
        return str(local_adb)

    def connect(self, port="7555"):
        """连接到ADB设备"""
        try:
            host = "127.0.0.1"
            self.logger.info(f"正在连接 {host}:{port}...")
            self.logger.info(f"使用ADB路径: {self.adb_path}")

            result = subprocess.run(
                [self.adb_path, "connect", f"{host}:{port}"],
                capture_output=True, text=True, timeout=10,
                creationflags=self.creationflags
            )
            self.logger.info(f"ADB输出: {result.stdout}")

            if "connected" in result.stdout.lower():
                self.connected = True
                self.host = host
                self.port = port
                self.logger.info(f"连接成功: {host}:{port}")
                return True
            elif "already connected" in result.stdout.lower():
                self.connected = True
                self.host = host
                self.port = port
                self.logger.info(f"已连接: {host}:{port}")
                return True
            else:
                self.logger.error(f"连接失败: {result.stdout}")
                return False
        except Exception as e:
            self.logger.error(f"连接异常: {str(e)}")
            return False

    def disconnect(self):
        """断开ADB连接"""
        if self.port:
            try:
                subprocess.run(
                    [self.adb_path, "disconnect", f"{self.host}:{self.port}"],
                    capture_output=True, timeout=5,
                    creationflags=self.creationflags
                )
            except:
                pass
        self.connected = False
        self.device = None
        self.host = None
        self.port = None
        self.logger.info("已断开ADB连接")

    def screenshot(self, save_path=None):
        """截取设备屏幕并保存到本地"""
        if not self.connected:
            self.logger.error("ADB未连接")
            return None

        try:
            # 未显式指定路径时，使用配置中的截图保存路径与截图质量
            if save_path is None:
                save_path = self.config.get('ADB', 'screenshot_path', 'temp/screenshot.jpg')
            screenshot_quality = min(100, max(1, self.config.get_int('ADB', 'screenshot_quality', 90)))

            Path(save_path).parent.mkdir(parents=True, exist_ok=True)
            device_serial = f"{self.host}:{self.port}"
            temp_path = "/sdcard/screenshot_temp.png"

            subprocess.run(
                [self.adb_path, "-s", device_serial, "shell", "screencap", "-p", temp_path],
                capture_output=True, timeout=5,
                creationflags=self.creationflags
            )
            subprocess.run(
                [self.adb_path, "-s", device_serial, "pull", temp_path, save_path],
                capture_output=True, timeout=5,
                creationflags=self.creationflags
            )
            subprocess.run(
                [self.adb_path, "-s", device_serial, "shell", "rm", temp_path],
                capture_output=True, timeout=5,
                creationflags=self.creationflags
            )

            if Path(save_path).exists() and Path(save_path).stat().st_size > 0:
                # 截图质量对 JPG/JPEG 输出生效：先取出 PNG，再按配置质量编码为 JPG
                if Path(save_path).suffix.lower() in ('.jpg', '.jpeg'):
                    file_bytes = np.fromfile(save_path, dtype=np.uint8)
                    image = cv2.imdecode(file_bytes, cv2.IMREAD_COLOR)
                    if image is None:
                        self.logger.error(f"截图文件读取失败，无法应用截图质量: {save_path}")
                        return None
                    ok, encoded = cv2.imencode(
                        '.jpg', image,
                        [cv2.IMWRITE_JPEG_QUALITY, screenshot_quality]
                    )
                    if not ok:
                        self.logger.error(f"JPG 编码失败，无法应用截图质量: {save_path}")
                        return None
                    encoded.tofile(save_path)
                    self.logger.info(f"截图已按质量 {screenshot_quality}% 保存为 JPG: {save_path}")
                self.logger.info(f"截图保存至: {save_path}")
                return save_path
            else:
                self.logger.error("截图失败：文件为空")
                return None
        except Exception as e:
            self.logger.error(f"截图失败: {str(e)}")
            return None

    def click(self, x, y, log=True):
        """模拟点击屏幕指定坐标"""
        if not self.connected:
            if log:
                self.logger.error("ADB未连接")
            return False

        try:
            device_serial = f"{self.host}:{self.port}"
            subprocess.run(
                [self.adb_path, "-s", device_serial, "shell", f"input tap {x} {y}"],
                capture_output=True, timeout=5,
                creationflags=self.creationflags
            )
            if log:
                self.logger.info(f"点击坐标: ({x}, {y})")
            return True
        except Exception as e:
            if log:
                self.logger.error(f"点击失败: {str(e)}")
            return False

    def swipe(self, x1, y1, x2, y2, duration=300):
        """模拟滑动操作"""
        if not self.connected:
            self.logger.error("ADB未连接")
            return False

        try:
            device_serial = f"{self.host}:{self.port}"
            subprocess.run(
                [self.adb_path, "-s", device_serial, "shell", f"input swipe {x1} {y1} {x2} {y2} {duration}"],
                capture_output=True, timeout=5,
                creationflags=self.creationflags
            )
            self.logger.info(f"滑动: ({x1},{y1}) -> ({x2},{y2}), 时长: {duration}ms")
            return True
        except Exception as e:
            self.logger.error(f"滑动失败: {str(e)}")
            return False

    def input_text(self, text):
        """输入文本到当前焦点输入框"""
        if not self.connected:
            self.logger.error("ADB未连接")
            return False

        try:
            device_serial = f"{self.host}:{self.port}"
            escaped_text = text.replace(" ", "%s").replace("&", "\\&").replace('"', '\\"')
            subprocess.run(
                [self.adb_path, "-s", device_serial, "shell", f'input text "{escaped_text}"'],
                capture_output=True, timeout=5,
                creationflags=self.creationflags
            )
            self.logger.info(f"输入文本: {text}")
            return True
        except Exception as e:
            self.logger.error(f"输入失败: {str(e)}")
            return False

    def get_screen_size(self):
        """获取设备屏幕分辨率"""
        if not self.connected:
            self.logger.error("ADB未连接")
            return None

        try:
            device_serial = f"{self.host}:{self.port}"
            result = subprocess.run(
                [self.adb_path, "-s", device_serial, "shell", "wm size"],
                capture_output=True, text=True, timeout=5,
                creationflags=self.creationflags
            )
            if result.stdout:
                match = re.search(r'(\d+)x(\d+)', result.stdout)
                if match:
                    width = int(match.group(1))
                    height = int(match.group(2))
                    self.logger.info(f"屏幕尺寸: {width}x{height}")
                    return (width, height)
            return None
        except Exception as e:
            self.logger.error(f"获取屏幕尺寸失败: {str(e)}")
            return None

    def press_key(self, key_code):
        """按下系统按键"""
        if not self.connected:
            self.logger.error("ADB未连接")
            return False

        try:
            device_serial = f"{self.host}:{self.port}"
            subprocess.run(
                [self.adb_path, "-s", device_serial, "shell", f"input keyevent {key_code}"],
                capture_output=True, timeout=5,
                creationflags=self.creationflags
            )
            self.logger.info(f"按下按键: {key_code}")
            return True
        except Exception as e:
            self.logger.error(f"按键失败: {str(e)}")
            return False

    def back(self):
        """模拟返回键"""
        return self.press_key('KEYCODE_BACK')

    def home(self):
        """模拟Home键"""
        return self.press_key('KEYCODE_HOME')

    def recent(self):
        """模拟最近任务键"""
        return self.press_key('KEYCODE_APP_SWITCH')

    def get_devices(self):
        """获取已连接的设备列表"""
        try:
            result = subprocess.run(
                [self.adb_path, "devices"],
                capture_output=True, text=True, timeout=5,
                creationflags=self.creationflags
            )
            devices = []
            lines = result.stdout.strip().split('\n')[1:]
            for line in lines:
                if 'device' in line and 'offline' not in line:
                    device = line.split('\t')[0]
                    devices.append(device)
            return devices
        except Exception as e:
            self.logger.error(f"获取设备列表失败: {str(e)}")
            return []

    def detect_adb_port(self):
        """自动检测可用的ADB端口"""
        common_ports = [7555, 5555, 62001, 21503, 5037, 5557, 5558, 26944]
        self.logger.info("开始检测ADB端口...")
        for port in common_ports:
            try:
                self.logger.info(f"尝试连接端口 {port}...")
                result = subprocess.run(
                    [self.adb_path, "connect", f"127.0.0.1:{port}"],
                    capture_output=True, text=True, timeout=5,
                    creationflags=self.creationflags
                )
                output = result.stdout.lower()
                if "connected" in output or "already connected" in output:
                    self.logger.info(f"发现可用端口: {port}")
                    return str(port)
                elif "unable to connect" not in output:
                    devices_result = subprocess.run(
                        [self.adb_path, "devices"],
                        capture_output=True, text=True, timeout=5,
                        creationflags=self.creationflags
                    )
                    if f"127.0.0.1:{port}" in devices_result.stdout and "device" in devices_result.stdout:
                        self.logger.info(f"发现已连接设备，端口: {port}")
                        return str(port)
            except Exception as e:
                self.logger.debug(f"端口 {port} 检测异常: {str(e)}")
                continue
        self.logger.warning("未检测到可用ADB端口")
        return None

# ==================== 图像识别模块 ====================
class ImageRecognition:
    def __init__(self, config_manager, logger):
        """
        初始化图像识别器
        :param config_manager: 配置管理器实例
        :param logger: 日志记录器实例
        """
        self.config = config_manager
        self.logger = logger
        # 从配置读取匹配阈值，范围0-1，值越大匹配越严格
        self.match_threshold = self.config.get_float('Recognition', 'match_threshold', 0.8)
        self.picture_folder = resource_path(self.config.get('Recognition', 'template_folder', 'picture'))
        # 确保模板文件夹存在
        Path(self.picture_folder).mkdir(parents=True, exist_ok=True)

        # 初始化 Maa OCR（MaaCommonAssets PP-OCR 转 ONNX + RapidOCR/ONNX Runtime）
        self.ocr_engine = None
        self.ocr_model_dir = None
        self._setup_ocr()

    @staticmethod
    def _find_ocr_model_dir(root_dir):
        """在 ocr 目录（含解压产生的多级子目录）中查找 Maa OCR 模型目录。

        MaaCommonAssets 模型需要同时包含 det.onnx、rec.onnx、keys.txt 三个文件。
        """
        required = {"det.onnx", "rec.onnx", "keys.txt"}

        if root_dir.is_dir():
            root_files = {p.name for p in root_dir.iterdir() if p.is_file()}
            if required.issubset(root_files):
                return Path(root_dir)

        # 兼容下载压缩包直接解压到 ocr/ 后多一层目录的情况
        matches = []
        for det_file in root_dir.rglob("det.onnx"):
            if not det_file.is_file():
                continue
            model_dir = det_file.parent
            model_files = {p.name for p in model_dir.iterdir() if p.is_file()}
            if required.issubset(model_files):
                matches.append(model_dir)

        if not matches:
            return None
        # 多个模型目录时，优先使用层级最浅（最接近 ocr/ 根目录）的一组
        matches.sort(key=lambda p: (len(p.parts), str(p).lower()))
        return matches[0]

    def _setup_ocr(self):
        """初始化 Maa OCR：加载 MaaCommonAssets 的 PP-OCR ONNX 模型。

        模型文件位于 ocr 目录：det.onnx、rec.onnx、keys.txt。
        下载地址（官方 MaaCommonAssets）：
        https://download.maafw.xyz/MaaCommonAssets/OCR/ppocr_v6/ppocr_v6-small.zip
        """
        try:
            model_root = Path(resource_path("ocr"))
            model_root.mkdir(parents=True, exist_ok=True)
            self.logger.info(f"OCR 模型根目录: {model_root}")

            model_dir = self._find_ocr_model_dir(model_root)
            if model_dir is None:
                self.logger.error(
                    "未找到 Maa OCR 模型文件（需要 det.onnx、rec.onnx、keys.txt）。"
                    "请下载 https://download.maafw.xyz/MaaCommonAssets/OCR/ppocr_v6/ppocr_v6-small.zip "
                    "并解压到 ocr/ 目录。注意：新引擎不再使用 ocr/*.pth 旧 EasyOCR 模型。"
                )
                self.ocr_engine = None
                return

            old_pth_files = list(model_root.rglob("*.pth"))
            if old_pth_files:
                self.logger.warning(
                    f"发现 {len(old_pth_files)} 个旧 EasyOCR 模型(.pth)，新引擎已不再使用，"
                    "可在确认新 OCR 正常后手动删除以节省约 100MB 空间。"
                )

            self.logger.info(f"使用 Maa OCR 模型目录: {model_dir}")

            try:
                from rapidocr_onnxruntime import RapidOCR
            except ImportError as exc:
                raise RuntimeError(
                    "缺少 RapidOCR/ONNX Runtime 依赖，请先执行: "
                    "pip install rapidocr-onnxruntime==1.4.4"
                ) from exc

            # RapidOCR 初始化时会读取 config.yaml 并创建方向分类器；
            # 这里显式传入项目内自带的配置与 cls.onnx，保证 PyInstaller 打包后不依赖
            # rapidocr_onnxruntime 包内的文件。实际识别时 use_cls=False，cls.onnx 不会被调用。
            maa_engine_config = model_root / "rapidocr_config.yaml"
            maa_cls_model = model_root / "cls.onnx"
            if not maa_engine_config.is_file() or not maa_cls_model.is_file():
                raise RuntimeError(
                    "缺少 RapidOCR 引擎配套文件 ocr/rapidocr_config.yaml 或 ocr/cls.onnx，"
                    "请检查项目是否完整。"
                )

            # Maa 模型只提供检测与识别模型，不含方向分类模型；
            # 因此方向分类(use_cls=False)关闭，推理使用 CPU 版 ONNX Runtime。
            self.ocr_engine = RapidOCR(
                config_path=str(maa_engine_config),
                det_model_path=str(model_dir / "det.onnx"),
                cls_model_path=str(maa_cls_model),
                rec_model_path=str(model_dir / "rec.onnx"),
                rec_keys_path=str(model_dir / "keys.txt"),
                use_det=True,
                use_cls=False,
                use_rec=True,
                print_verbose=False,
                intra_op_num_threads=2,
                inter_op_num_threads=1,
            )
            self.ocr_model_dir = str(model_dir)
            self.logger.info("Maa OCR 已就绪（PP-OCR 转 ONNX + RapidOCR/ONNX Runtime，CPU 推理）")

        except Exception as e:
            self.logger.error(f"Maa OCR 初始化失败: {str(e)}")
            self.logger.error(traceback.format_exc())
            self.ocr_engine = None

    def recognize_text(self, screenshot_path, area=None):
        """
        使用 Maa OCR 识别截图中的文字
        :param screenshot_path: 截图文件路径
        :param area: 识别区域 (x1, y1, x2, y2)，None表示全图识别
        :return: 识别出的文字字符串
        """
        if self.ocr_engine is None:
            self.logger.error("Maa OCR 引擎未初始化（缺少模型或依赖），无法识别文字")
            return ""

        try:
            # 从配置读取 OCR 调优参数（RapidOCR 每次调用都会应用新值）
            box_thresh = min(1.0, max(0.0, self.config.get_float('OCR', 'box_thresh', 0.5)))
            unclip_ratio = min(2.0, max(1.0, self.config.get_float('OCR', 'unclip_ratio', 1.6)))
            text_score = min(1.0, max(0.0, self.config.get_float('OCR', 'text_score', 0.5)))

            # 读取图片
            image = cv2.imread(screenshot_path)
            if image is None:
                # 支持中文路径
                image = self._imread_chinese(screenshot_path)
                if image is None:
                    self.logger.error(f"无法读取图片: {screenshot_path}")
                    return ""

            # 如果指定了区域，裁剪图像
            if area:
                x1, y1, x2, y2 = area
                image = image[y1:y2, x1:x2]
                self.logger.info(f"识别区域: ({x1},{y1}) -> ({x2},{y2})")

            # 可选：图像预处理，提高识别率
            if self.config.get_bool('OCR', 'preprocess', False):
                # 转为灰度图
                gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
                # 二值化，将文字与背景分离
                _, binary = cv2.threshold(gray, 127, 255, cv2.THRESH_BINARY)
                # ONNX/PaddleOCR 模型要求 3 通道输入，二值化后转回 BGR
                image = cv2.cvtColor(binary, cv2.COLOR_GRAY2BGR)

            # 执行 OCR 识别（use_cls=False：Maa 模型不含方向分类模型）
            output = self.ocr_engine(
                image,
                use_det=True,
                use_cls=False,
                use_rec=True,
                box_thresh=box_thresh,
                unclip_ratio=unclip_ratio,
                text_score=text_score,
            )
            result = output[0] if isinstance(output, (tuple, list)) else output

            if result:
                # RapidOCR 返回 [[box, 文本, 置信度], ...]，这里只取文本合并
                text_lines = []
                for item in result:
                    if isinstance(item, (list, tuple)) and len(item) >= 2:
                        text_lines.append(str(item[1]))
                text = '\n'.join(text_lines)
                text = text.strip()
                self.logger.info(f"识别到 {len(text_lines)} 行文字")
                if len(text) > 200:
                    self.logger.info(f"识别文本预览: {text[:200]}...")
                else:
                    self.logger.info(f"识别文本: {text}")
                return text
            else:
                self.logger.warning("未识别到任何文字")
                return ""

        except Exception as e:
            self.logger.error(f"OCR识别失败: {str(e)}")
            return ""

    def recognize_text_with_positions(self, screenshot_path, area=None):
        """
        识别文字并返回带位置和置信度的详细结果
        :param screenshot_path: 截图文件路径
        :param area: 识别区域 (x1, y1, x2, y2)，None表示全图识别
        :return: 列表，每个元素为 ([[坐标]], 文本, 置信度)
        """
        if self.ocr_engine is None:
            self.logger.error("Maa OCR 引擎未初始化（缺少模型或依赖），无法识别文字")
            return []

        try:
            box_thresh = min(1.0, max(0.0, self.config.get_float('OCR', 'box_thresh', 0.5)))
            unclip_ratio = min(2.0, max(1.0, self.config.get_float('OCR', 'unclip_ratio', 1.6)))
            text_score = min(1.0, max(0.0, self.config.get_float('OCR', 'text_score', 0.5)))

            # 读取图片
            image = cv2.imread(screenshot_path)
            if image is None:
                # 使用支持中文路径的方法
                image = self._imread_chinese(screenshot_path)

            if image is None:
                self.logger.error(f"无法读取图片: {screenshot_path}")
                return []

            # 如果指定了区域，裁剪图像并记录偏移量
            offset_x = 0
            offset_y = 0
            if area:
                x1, y1, x2, y2 = area
                offset_x = x1
                offset_y = y1
                image = image[y1:y2, x1:x2]
                self.logger.info(f"识别区域: ({x1},{y1}) -> ({x2},{y2})")

            # 可选：图像预处理
            if self.config.get_bool('OCR', 'preprocess', False):
                gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
                _, binary = cv2.threshold(gray, 127, 255, cv2.THRESH_BINARY)
                image = cv2.cvtColor(binary, cv2.COLOR_GRAY2BGR)

            output = self.ocr_engine(
                image,
                use_det=True,
                use_cls=False,
                use_rec=True,
                box_thresh=box_thresh,
                unclip_ratio=unclip_ratio,
                text_score=text_score,
            )
            results = output[0] if isinstance(output, (tuple, list)) else output
            if results is None:
                results = []

            # 将 RapidOCR 结果统一成 EasyOCR 兼容格式: ([[4点坐标]], 文本, 置信度)
            normalized = []
            for item in results:
                if not isinstance(item, (list, tuple)) or len(item) < 3:
                    continue
                bbox, text, confidence = item[0], item[1], item[2]
                if bbox is None:
                    continue
                bbox_list = [[float(point[0]), float(point[1])] for point in bbox]
                normalized.append((bbox_list, str(text), float(confidence)))
            results = normalized

            # 如果有区域偏移，调整坐标
            if offset_x != 0 or offset_y != 0:
                adjusted_results = []
                for bbox, text, confidence in results:
                    # 调整坐标：加上偏移量
                    adjusted_bbox = [[p[0] + offset_x, p[1] + offset_y] for p in bbox]
                    adjusted_results.append((adjusted_bbox, text, confidence))
                results = adjusted_results

            if results:
                self.logger.info(f"识别到 {len(results)} 个文字区域")

            return results

        except Exception as e:
            self.logger.error(f"OCR识别失败: {str(e)}")
            return []

    # ==================== 原有的图像匹配方法 ====================

    def find_image(self, screenshot_path, template_name, threshold=None):
        """
        在截图中查找指定模板图片 - 支持中文路径
        :param screenshot_path: 截图文件路径
        :param template_name: 模板图片文件名或完整路径
        :param threshold: 匹配阈值，如果为None则使用配置的默认值
        :return: 成功返回(中心点X, 中心点Y, 匹配度)，失败返回None
        """
        if threshold is None:
            threshold = self.match_threshold  # 使用初始化时从配置读取的值
            #self.logger.debug(f"使用默认匹配阈值: {threshold}")

        try:

            # 使用 Path 处理路径
            if Path(template_name).is_absolute():
                template_path = Path(template_name)
            else:
                picture_path = Path(self.picture_folder)
                template_path = None

                # 搜索图片
                for file_path in picture_path.rglob("*"):
                    if file_path.is_file() and file_path.name == template_name:
                        template_path = file_path
                        break
                    elif file_path.is_file() and file_path.stem == Path(template_name).stem:
                        template_path = file_path
                        break

                if not template_path:
                    self.logger.error_red(f"[Warning]模板图片不存在: {template_name}")
                    return None

            # 读取截图 - 支持中文路径
            screenshot = self._imread_chinese(str(screenshot_path))
            if screenshot is None:
                self.logger.error(f"截图读取失败: {screenshot_path}")
                return None

            # 读取模板 - 支持中文路径
            template = self._imread_chinese(str(template_path))
            if template is None:
                self.logger.error(f"模板读取失败: {template_path}")
                return None

            # 检查模板尺寸
            if template.shape[0] > screenshot.shape[0] or template.shape[1] > screenshot.shape[1]:
                self.logger.error(f"模板图片尺寸大于截图: 模板{template.shape} > 截图{screenshot.shape}")
                return None

            # 灰度图匹配
            if self.config.get_bool('Recognition', 'use_gray', True):
                screenshot_gray = cv2.cvtColor(screenshot, cv2.COLOR_BGR2GRAY)
                template_gray = cv2.cvtColor(template, cv2.COLOR_BGR2GRAY)
                result = cv2.matchTemplate(screenshot_gray, template_gray, cv2.TM_CCOEFF_NORMED)
            else:
                result = cv2.matchTemplate(screenshot, template, cv2.TM_CCOEFF_NORMED)

            min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)

            if max_val >= threshold:
                h, w = template.shape[:2]
                center_x = max_loc[0] + w // 2
                center_y = max_loc[1] + h // 2
                self.logger.info(
                    f"找到图片 {template_path.name}, 匹配度: {max_val:.2f}, 位置: ({center_x}, {center_y})")
                return (center_x, center_y, max_val)
            else:
                self.logger.info(f"未找到图片 {template_path.name}, 最佳匹配度: {max_val:.2f}")
                return None

        except Exception as e:
            self.logger.error(f"图像识别失败: {str(e)}")
            self.logger.error(traceback.format_exc())
            return None

    def _imread_chinese(self, filepath):
        """
        支持中文路径的图片读取函数
        使用多种方法尝试读取，确保兼容性
        :param filepath: 文件路径
        :return: 图片数组，失败返回None
        """
        if not Path(filepath).exists():
            self.logger.error(f"文件不存在: {filepath}")
            return None

        try:
            # 方法1: 使用 numpy.fromfile + cv2.imdecode
            file_bytes = np.fromfile(filepath, dtype=np.uint8)
            img = cv2.imdecode(file_bytes, cv2.IMREAD_COLOR)
            if img is not None:
                return img
        except Exception as e:
            self.logger.debug(f"方法1失败: {e}")

        try:
            # 方法2: 使用 open 读取二进制 + cv2.imdecode
            with open(filepath, 'rb') as f:
                file_bytes = f.read()
            img = cv2.imdecode(np.frombuffer(file_bytes, np.uint8), cv2.IMREAD_COLOR)
            if img is not None:
                return img
        except Exception as e:
            self.logger.debug(f"方法2失败: {e}")

        try:
            # 方法3: 使用 PIL 读取，然后转换

            img_pil = Image.open(filepath)
            img = cv2.cvtColor(np.array(img_pil), cv2.COLOR_RGB2BGR)
            if img is not None:
                return img
        except Exception as e:
            self.logger.debug(f"方法3失败: {e}")

        self.logger.error(f"所有方法都无法读取图片: {filepath}")
        return None

    def find_and_click(self, adb_controller, template_name, threshold=None):
        """查找图片并在找到的位置点击"""
        screenshot_path = adb_controller.screenshot()
        if not screenshot_path:
            return False

        result = self.find_image(screenshot_path, template_name, threshold)
        if result:
            x, y, _ = result
            return adb_controller.click(x, y)
        return False

    def wait_for_image(self, adb_controller, template_name, timeout=10, interval=0.5):
        """等待图片出现"""
        start_time = time.time()
        while time.time() - start_time < timeout:
            result = self.find_and_click(adb_controller, template_name)
            if result:
                return True
            time.sleep(interval)
        return False

    def get_all_matches(self, screenshot_path, template_name, threshold=None):
        """获取截图中所有匹配的位置"""
        if threshold is None:
            threshold = self.match_threshold

        try:
            template_path = os.path.join(self.picture_folder, template_name)
            if not os.path.exists(template_path):
                return []

            screenshot = cv2.imread(screenshot_path)
            template = cv2.imread(template_path)

            if screenshot is None or template is None:
                return []

            screenshot_gray = cv2.cvtColor(screenshot, cv2.COLOR_BGR2GRAY)
            template_gray = cv2.cvtColor(template, cv2.COLOR_BGR2GRAY)

            result = cv2.matchTemplate(screenshot_gray, template_gray, cv2.TM_CCOEFF_NORMED)
            y_indices, x_indices = np.where(result >= threshold)
            matches = []
            h, w = template.shape[:2]
            for y, x in zip(y_indices, x_indices):
                center_x = x + w // 2
                center_y = y + h // 2
                match_value = result[y, x]
                matches.append((center_x, center_y, match_value))

            self.logger.info(f"找到 {len(matches)} 个匹配位置")
            return matches

        except Exception as e:
            self.logger.error(f"获取所有匹配位置失败: {str(e)}")
            return []

# ==================== 主界面 ====================
class JailMasterGUI:
    """幻帮跑商主界面类"""

    def __init__(self):
        """初始化主界面，创建所有模块和UI组件"""
        self.btn_test_sell = None
        self.btn_ocr_area = None
        self.btn_swipe = None
        self.btn_ocr = None
        self.btn_test_buy = None
        self.btn_test_map = None
        self.status_label = None
        self.swipe_duration_var = None
        self.swipe_duration_entry = None
        self.swipe_end_var = None
        self.swipe_start_var = None
        self.swipe_end_entry = None
        self.swipe_start_entry = None
        self.btn_click = None
        self.click_pos_var = None
        self.click_pos_entry = None
        self.btn_find_image = None
        self.find_image_entry = None
        self.find_image_var = None
        self.medicine_check = None
        self.medicine_enabled_var = None
        self.litter_interval_entry = None
        self.litter_interval_var = None
        self.litter_y_var = None
        self.litter_y_entry = None
        self.litter_x_var = None
        self.litter_check = None
        self.litter_enabled_var = None
        self.trailer_count_entry = None
        self.trailer_count_var = None
        self.trailer_check = None
        self.trailer_enabled_var = None
        self.city_b_var = None
        self.log_text = None
        self.city_a_combo = None
        self.city_a_var = None
        self.litter_x_entry = None
        self.city_b_combo = None
        self.root = tk.Tk()
        self.root.title("幻帮跑商")
        self.root.geometry("1200x800")
        icon_path = resource_path("p2.ico")  # 修改这里
        Path(resource_path("picture")).mkdir(exist_ok=True)
        Path(resource_path("picture/ui")).mkdir(exist_ok=True)
        Path(resource_path("picture/SHOP")).mkdir(exist_ok=True)
        Path(resource_path("temp")).mkdir(exist_ok=True)
        # 方法1：使用 ctypes 直接设置窗口句柄的图标（对任务栏有效）
        try:
            # 设置 AppUserModelID 使任务栏图标正确分组
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("AutoLS.JailMaster")# type: ignore
            # 获取窗口句柄
            hwnd = ctypes.windll.user32.GetParent(self.root.winfo_id())# type: ignore
            # 加载大图标和小图标
            large_icon = ctypes.windll.user32.LoadImageW(0, icon_path, 1, 0, 0, 0x00001000 | 0x00002000)# type: ignore
            small_icon = ctypes.windll.user32.LoadImageW(0, icon_path, 1, 0, 0, 0x00001000 | 0x00002000)# type: ignore
            if large_icon:
                ctypes.windll.user32.SendMessageW(hwnd, 0x0080, 0, large_icon)  # type: ignore # ICON_BIG
                ctypes.windll.user32.SendMessageW(hwnd, 0x0080, 1, small_icon)  # type: ignore # ICON_SMALL
        except Exception as e:
            print(f"ctypes 图标设置失败: {e}")

        # 方法3：使用 iconphoto 备用（支持 PNG，保留引用）
        try:

            img = Image.open(icon_path)
            self.icon_photo = ImageTk.PhotoImage(img)
            self.root.iconphoto(True, self.icon_photo)# type: ignore
        except:
            pass
        # 初始化各个模块
        self.logger = Logger("log.txt")
        self.config = ConfigManager("configs.ini")
        self.adb = ADBController(self.config, self.logger)
        self.image_rec = ImageRecognition(self.config, self.logger)

        # 初始化跑商控制器
        self.trade_route = TradeRoute(self.adb, self.image_rec, self.config, self.logger)

        # 运行状态标志（保留用于UI状态）
        self.running = False
        self.paused = False
        self.auto_thread = None

        # 窗口管理标志
        self.config_window = None
        self.monitor_window = None
        self.adb_window = None
        self.monitor_refresh_running = False

        # 获取调试模式
        self.debug_mode = self.config.get_int('Debug', 'debug', 0)

        # 设置日志回调
        self.logger.set_callback(self.log_callback)

        # 创建UI界面
        self.create_ui()
        self.load_cities()  # 加载城市列表
        self._restore_saved_cities()  # 恢复上次选择
        self._setup_city_linking()  # 设置联动并自动保存
        # 创建必要的文件夹
        Path("temp").mkdir(exist_ok=True)

        # 启动后自动连接ADB
        self.auto_connect_on_startup()
        def global_exception_handler(exc_type, exc_value, exc_tb):
            error_msg = ''.join(traceback.format_exception(exc_type, exc_value, exc_tb))
            self.logger.error_red(f"[Warning]未捕获的异常:\n{error_msg}")
            messagebox.showerror("程序错误", "发生严重错误，请查看日志。")

        sys.excepthook = global_exception_handler
    # ==================== 窗口关闭函数 ====================

    def on_config_close(self):
        """配置窗口关闭时的回调"""
        if self.config_window:
            self.config_window.destroy()
        self.config_window = None

    def on_monitor_close(self):
        """监控窗口关闭时的回调"""
        self.monitor_refresh_running = False
        if self.monitor_window:
            self.monitor_window.destroy()
        self.monitor_window = None

    def on_adb_close(self):
        """ADB窗口关闭时的回调"""
        if self.adb_window:
            self.adb_window.destroy()
        self.adb_window = None

    # ==================== 自动连接函数 ====================

    def auto_connect_on_startup(self):
        """启动后自动连接ADB，使用配置文件中的端口号"""
        port = self.config.get('ADB', 'default_port', '7555')
        self.logger.info(f"启动自动连接，目标端口: {port}")
        # 延迟1秒后连接，确保UI完全加载
        self.root.after(1000, lambda: self._do_auto_connect(port))

    def _do_auto_connect(self, port):
        """执行自动连接"""
        if self.adb.connect(port):
            self.status_label.config(text=f"已连接 127.0.0.1:{port}", foreground="green")
            self.logger.info(f"自动连接成功: 127.0.0.1:{port}")
        else:
            self.status_label.config(text="连接失败", foreground="red")
            self.logger.warning(f"自动连接失败，请手动连接或使用自动检测")

    # ==================== UI创建函数 ====================

    def create_ui(self):
        """创建用户界面，包括菜单栏、左侧日志区域、右侧按钮区域"""

        # ==================== 顶部菜单栏 ====================
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)

        # "配置"菜单
        config_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="配置", menu=config_menu)
        config_menu.add_command(label="配置设置", command=self.show_config_tab)

        # "画面监控"菜单
        monitor_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="画面监控", menu=monitor_menu)
        monitor_menu.add_command(label="开启监控", command=self.open_monitor)

        # "ADB链接设置"菜单
        adb_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="ADB链接设置", menu=adb_menu)
        adb_menu.add_command(label="ADB设置", command=self.show_adb_tab)

        # ==================== 主框架 ====================
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # ==================== 左侧：日志文本框 ====================
        left_frame = ttk.Frame(main_frame)
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        ttk.Label(left_frame, text="日志信息", font=("微软雅黑", 12)).pack(anchor=tk.W)
        self.log_text = scrolledtext.ScrolledText(left_frame, width=50, height=40,
                                                  font=("Consolas", 9))
        self.log_text.pack(fill=tk.BOTH, expand=True)
        self.log_text.config(state="disabled")  # 设置为只读

        # ==================== 右侧：功能按钮区 ====================
        right_frame = ttk.Frame(main_frame)
        right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, padx=10)

        # 城市A选择 - 只读
        ttk.Label(right_frame, text="城市A:", font=("微软雅黑", 11)).pack(anchor=tk.W, pady=(0, 5))
        self.city_a_var = tk.StringVar()
        self.city_a_combo = ttk.Combobox(right_frame, textvariable=self.city_a_var, width=15, state="readonly")
        self.city_a_combo.pack(pady=(0, 10))

        # 城市B选择 - 只读
        ttk.Label(right_frame, text="城市B:", font=("微软雅黑", 11)).pack(anchor=tk.W, pady=(0, 5))
        self.city_b_var = tk.StringVar()
        self.city_b_combo = ttk.Combobox(right_frame, textvariable=self.city_b_var, width=15, state="readonly")
        self.city_b_combo.pack(pady=(0, 10))

        # 加载城市列表
        self.load_cities()

        # 分隔线
        ttk.Separator(right_frame, orient='horizontal').pack(fill=tk.X, pady=10)

        # ==================== 控制按钮区域（支持多列布局） ====================
        control_label_frame = ttk.LabelFrame(right_frame, text="控制按钮", padding=5)
        control_label_frame.pack(fill=tk.X, pady=5)

        # 使用网格布局，每列4个按钮
        buttons_per_column = 4

        # 定义所有按钮（文本, 命令, 宽度）
        buttons_config = [
            ("START!", self.start_auto, 12),
            ("暂停", self.pause_auto, 12),
            ("恢复", self.resume_auto, 12),
            ("停止", self.stop_auto, 12),
        ]

        # 拖车和捡垃圾设置放在按钮上方的一行
        settings_frame = ttk.Frame(control_label_frame)
        settings_frame.grid(row=0, column=0, columnspan=buttons_per_column, sticky=tk.W, pady=5)

        # 拖车设置
        self.trailer_enabled_var = tk.BooleanVar(value=self.config.get_bool('Trailer', 'enabled', False))
        self.trailer_check = ttk.Checkbutton(settings_frame, text="拖车", variable=self.trailer_enabled_var)
        self.trailer_check.pack(side=tk.LEFT, padx=5)

        self.trailer_count_var = tk.StringVar(value=str(self.config.get_int('Trailer', 'count', 0)))
        vcmd = (self.root.register(self._validate_int_input), '%P')
        self.trailer_count_entry = ttk.Entry(settings_frame, textvariable=self.trailer_count_var, width=6,
                                             validate='key', validatecommand=vcmd)
        self.trailer_count_entry.pack(side=tk.LEFT, padx=2)
        ttk.Label(settings_frame, text="辆").pack(side=tk.LEFT)

        # 分隔线
        ttk.Separator(settings_frame, orient='vertical').pack(side=tk.LEFT, fill=tk.Y, padx=10, pady=2)

        # 捡垃圾设置
        self.litter_enabled_var = tk.BooleanVar(value=self.config.get_bool('Litter', 'enabled', False))
        self.litter_check = ttk.Checkbutton(settings_frame, text="捡垃圾", variable=self.litter_enabled_var)
        self.litter_check.pack(side=tk.LEFT, padx=5)

        self.litter_x_var = tk.StringVar(value=str(self.config.get_int('Litter', 'click_x', 1100)))
        self.litter_y_var = tk.StringVar(value=str(self.config.get_int('Litter', 'click_y', 600)))
        self.litter_x_entry = ttk.Entry(settings_frame, textvariable=self.litter_x_var, width=6, validate='key',
                                        validatecommand=vcmd)
        self.litter_x_entry.pack(side=tk.LEFT, padx=2)
        ttk.Label(settings_frame, text=",").pack(side=tk.LEFT)
        self.litter_y_entry = ttk.Entry(settings_frame, textvariable=self.litter_y_var, width=6, validate='key',
                                        validatecommand=vcmd)
        self.litter_y_entry.pack(side=tk.LEFT, padx=2)

        # 添加间隔输入框
        ttk.Label(settings_frame, text="间隔:").pack(side=tk.LEFT, padx=(10, 2))
        self.litter_interval_var = tk.StringVar(value=str(self.config.get_float('Litter', 'click_interval', 0.5)))
        vcmd_float = (self.root.register(self._validate_float_input), '%P')
        self.litter_interval_entry = ttk.Entry(settings_frame, textvariable=self.litter_interval_var, width=6,
                                               validate='key', validatecommand=vcmd_float)
        self.litter_interval_entry.pack(side=tk.LEFT, padx=2)
        ttk.Label(settings_frame, text="秒").pack(side=tk.LEFT)
        # 添加跟踪
        self.litter_interval_var.trace_add('write', lambda *args: save_litter_config())
        # 在拖车捡垃圾设置那一行后面添加
        self.medicine_enabled_var = tk.BooleanVar(value=self.config.get_bool('Medicine', 'enabled', False))
        self.medicine_check = ttk.Checkbutton(settings_frame, text="用药", variable=self.medicine_enabled_var)
        self.medicine_check.pack(side=tk.LEFT, padx=5)

        def save_medicine_config():
            self.config.set('Medicine', 'enabled', 'True' if self.medicine_enabled_var.get() else 'False')
            self.logger.info(f"用药配置已保存: {self.medicine_enabled_var.get()}")

        self.medicine_enabled_var.trace_add('write', lambda *args: save_medicine_config())

        # 保存配置的回调
        def save_trailer_config():
            self.config.set('Trailer', 'enabled', 'True' if self.trailer_enabled_var.get() else 'False')
            self.config.set('Trailer', 'count', self.trailer_count_var.get())
            self.logger.info(
                f"拖车配置已保存: 启用={self.trailer_enabled_var.get()}, 数量={self.trailer_count_var.get()}")

        def save_litter_config():
            self.config.set('Litter', 'enabled', 'True' if self.litter_enabled_var.get() else 'False')
            self.config.set('Litter', 'click_x', self.litter_x_var.get())
            self.config.set('Litter', 'click_y', self.litter_y_var.get())
            self.config.set('Litter', 'click_interval', self.litter_interval_var.get())
            self.logger.info(
                f"捡垃圾配置已保存: 启用={self.litter_enabled_var.get()}, 坐标=({self.litter_x_var.get()},{self.litter_y_var.get()}), 间隔={self.litter_interval_var.get()}秒")

        self.trailer_enabled_var.trace_add('write', lambda *args: save_trailer_config())
        self.trailer_count_var.trace_add('write', lambda *args: save_trailer_config())
        self.litter_enabled_var.trace_add('write', lambda *args: save_litter_config())
        self.litter_x_var.trace_add('write', lambda *args: save_litter_config())
        self.litter_y_var.trace_add('write', lambda *args: save_litter_config())

        # 计算行数和列数
        total_buttons = len(buttons_config)
        rows = (total_buttons + buttons_per_column - 1) // buttons_per_column

        # 创建按钮并放置到网格中
        for idx, (text, command, width) in enumerate(buttons_config):
            row = idx % rows
            col = idx // rows
            btn = ttk.Button(control_label_frame, text=text, command=command, width=width)
            btn.grid(row=row + 1, column=col, padx=5, pady=5, sticky=tk.W)
        # ==================== Debug模式专属按钮 ====================
        if self.debug_mode == 1:
            # 分隔线
            ttk.Separator(right_frame, orient='horizontal').pack(fill=tk.X, pady=10)

            # Debug工具组
            debug_frame = ttk.LabelFrame(right_frame, text="Debug工具", padding=5)
            debug_frame.pack(fill=tk.X, pady=5)

            # ===== 寻图功能 =====
            ttk.Label(debug_frame, text="寻图:", font=("微软雅黑", 10)).pack(anchor=tk.W, pady=(5, 0))

            image_path_frame = ttk.Frame(debug_frame)
            image_path_frame.pack(fill=tk.X, pady=5)

            self.find_image_var = tk.StringVar()
            self.find_image_entry = ttk.Entry(image_path_frame, textvariable=self.find_image_var, width=20)
            self.find_image_entry.pack(side=tk.LEFT, padx=(0, 5))

            self.btn_find_image = ttk.Button(image_path_frame, text="寻图", command=self.debug_find_image, width=8)
            self.btn_find_image.pack(side=tk.LEFT)

            ttk.Label(debug_frame, text="输入图片文件名(picture文件夹下)",
                      foreground="gray", font=("微软雅黑", 8)).pack(anchor=tk.W, pady=(0, 5))

            # ===== 点击功能 =====
            ttk.Label(debug_frame, text="点击坐标:", font=("微软雅黑", 10)).pack(anchor=tk.W, pady=(5, 0))

            click_frame = ttk.Frame(debug_frame)
            click_frame.pack(fill=tk.X, pady=5)

            self.click_pos_var = tk.StringVar()
            self.click_pos_entry = ttk.Entry(click_frame, textvariable=self.click_pos_var, width=20)
            self.click_pos_entry.pack(side=tk.LEFT, padx=(0, 5))
            self.click_pos_entry.insert(0, "100,100")

            self.btn_click = ttk.Button(click_frame, text="点击", command=self.debug_click, width=8)
            self.btn_click.pack(side=tk.LEFT)

            ttk.Label(debug_frame, text="注意添加MAP_新城市时候截图以1725, 810为比例",
                      foreground="gray", font=("微软雅黑", 8)).pack(anchor=tk.W, pady=(0, 5))

            # ===== 滑动功能 =====
            ttk.Separator(debug_frame, orient='horizontal').pack(fill=tk.X, pady=5)

            ttk.Label(debug_frame, text="滑动:", font=("微软雅黑", 10)).pack(anchor=tk.W, pady=(5, 0))

            # 起始坐标
            start_frame = ttk.Frame(debug_frame)
            start_frame.pack(fill=tk.X, pady=2)
            ttk.Label(start_frame, text="起始坐标:", width=8).pack(side=tk.LEFT)
            self.swipe_start_var = tk.StringVar(value="500,500")
            self.swipe_start_entry = ttk.Entry(start_frame, textvariable=self.swipe_start_var, width=15)
            self.swipe_start_entry.pack(side=tk.LEFT, padx=5)

            # 终点坐标
            end_frame = ttk.Frame(debug_frame)
            end_frame.pack(fill=tk.X, pady=2)
            ttk.Label(end_frame, text="终点坐标:", width=8).pack(side=tk.LEFT)
            self.swipe_end_var = tk.StringVar(value="100,500")
            self.swipe_end_entry = ttk.Entry(end_frame, textvariable=self.swipe_end_var, width=15)
            self.swipe_end_entry.pack(side=tk.LEFT, padx=5)

            # 持续时间
            duration_frame = ttk.Frame(debug_frame)
            duration_frame.pack(fill=tk.X, pady=2)
            ttk.Label(duration_frame, text="持续时间(ms):", width=12).pack(side=tk.LEFT)
            self.swipe_duration_var = tk.StringVar(value="300")
            self.swipe_duration_entry = ttk.Entry(duration_frame, textvariable=self.swipe_duration_var, width=10)
            self.swipe_duration_entry.pack(side=tk.LEFT, padx=5)

            # 滑动按钮
            self.btn_swipe = ttk.Button(debug_frame, text="滑动", command=self.debug_swipe, width=8)
            self.btn_swipe.pack(anchor=tk.W, pady=5, padx=10)

            ttk.Label(debug_frame, text="格式: x,y 例如 500,500 到 100,500",
                      foreground="gray", font=("微软雅黑", 8)).pack(anchor=tk.W, pady=(0, 5))

            # ===== 文字识别功能 =====
            ttk.Separator(debug_frame, orient='horizontal').pack(fill=tk.X, pady=5)

            ttk.Label(debug_frame, text="文字识别:", font=("微软雅黑", 10)).pack(anchor=tk.W, pady=(5, 0))

            ocr_frame = ttk.Frame(debug_frame)
            ocr_frame.pack(fill=tk.X, pady=5)

            self.btn_ocr = ttk.Button(ocr_frame, text="识别全屏文字", command=self.debug_ocr_full, width=15)
            self.btn_ocr.pack(side=tk.LEFT, padx=(0, 10))

            self.btn_ocr_area = ttk.Button(ocr_frame, text="框选区域识别", command=self.debug_ocr_area, width=15)
            self.btn_ocr_area.pack(side=tk.LEFT)

            ttk.Label(debug_frame, text="点击按钮后截图并识别其中的文字，结果在日志中查看",
                      foreground="gray", font=("微软雅黑", 8)).pack(anchor=tk.W, pady=(0, 5))

            # ===== 测试功能分隔线 =====
            ttk.Separator(debug_frame, orient='horizontal').pack(fill=tk.X, pady=5)

            ttk.Label(debug_frame, text="测试功能:", font=("微软雅黑", 10, "bold"), foreground="purple").pack(anchor=tk.W, pady=(5, 0))

            # 测试按钮框架
            test_frame = ttk.Frame(debug_frame)
            test_frame.pack(fill=tk.X, pady=5)

            # 测试买入按钮
            self.btn_test_buy = ttk.Button(test_frame, text="测试买入", command=self.debug_test_buy, width=12)
            self.btn_test_buy.pack(side=tk.LEFT, padx=5)

            # 测试卖出按钮
            self.btn_test_sell = ttk.Button(test_frame, text="测试卖出", command=self.debug_test_sell, width=12)
            self.btn_test_sell.pack(side=tk.LEFT, padx=5)

            # 测试地图按钮
            self.btn_test_map = ttk.Button(test_frame, text="测试地图", command=self.debug_test_map, width=12)
            self.btn_test_map.pack(side=tk.LEFT, padx=5)

            ttk.Label(debug_frame, text="测试买入/卖出: 单次买入或卖出操作\n测试地图: 执行启程寻城流程",
                      foreground="gray", font=("微软雅黑", 8)).pack(anchor=tk.W, pady=(5, 0))       # 分隔线


        ttk.Separator(right_frame, orient='horizontal').pack(fill=tk.X, pady=10)

        # ==================== 状态信息区 ====================
        status_frame = ttk.Frame(right_frame)
        status_frame.pack(fill=tk.X)

        ttk.Label(status_frame, text="连接状态:").pack(side=tk.LEFT)
        self.status_label = ttk.Label(status_frame, text="未连接", foreground="red")
        self.status_label.pack(side=tk.LEFT, padx=5)

        # 显示Debug模式状态
        if self.debug_mode == 1:
            debug_label = ttk.Label(right_frame, text="【开发模式已启用】", foreground="orange")
            debug_label.pack(anchor=tk.W, pady=2)

        # 作者和版本信息
        ttk.Label(right_frame, text="作者：幻").pack(anchor=tk.W, pady=2)
        version = self.config.get('UI', 'version', 'v2.4')
        ttk.Label(right_frame, text=f"版本号：{version}").pack(anchor=tk.W, pady=2)
        ttk.Label(right_frame, text="群号：858084260").pack(anchor=tk.W, pady=2)

        # 版权声明
        ttk.Label(right_frame, text="该脚本为免费软件\n若你在其他地方付费获取到该软件\n可以加群反应",
                  foreground="red", justify=tk.LEFT).pack(anchor=tk.W, pady=10)

    def load_cities(self):
        """从配置文件加载城市列表，填充下拉框选项"""
        cities_str = self.config.get('City', 'cities', '')
        if ',' in cities_str:
            cities = [c.strip() for c in cities_str.split(',') if c.strip()]
        else:
            cities = [c.strip() for c in cities_str.split('\n') if c.strip()]

        self.city_a_combo['values'] = cities
        self.city_b_combo['values'] = cities
        # 不再设置默认值，由 _restore_saved_cities() 恢复上次选择

    def _save_city_selection(self):
        """保存当前选中的城市到配置文件"""
        city_a = self.city_a_var.get()
        city_b = self.city_b_var.get()
        if city_a:
            self.config.set('UI', 'last_city_a', city_a)
        if city_b:
            self.config.set('UI', 'last_city_b', city_b)

    def _restore_saved_cities(self):
        """从配置文件恢复上次选中的城市"""
        all_cities = self.city_a_combo['values']
        last_a = self.config.get('UI', 'last_city_a', '')
        last_b = self.config.get('UI', 'last_city_b', '')
        if last_a and last_a in all_cities:
            self.city_a_var.set(last_a)
        else:
            # 如果上次选择无效，默认选第一个
            self.city_a_var.set(all_cities[0] if all_cities else '')
        if last_b and last_b in all_cities and last_b != self.city_a_var.get():
            self.city_b_var.set(last_b)
        else:
            # 选择不同于城市A的第二个城市
            candidates = [c for c in all_cities if c != self.city_a_var.get()]
            self.city_b_var.set(candidates[0] if candidates else '')

    def _setup_city_linking(self):
        """设置城市选择联动：不允许相同，并自动保存"""

        def on_city_a_change(*args):
            city_a = self.city_a_var.get()
            all_cities = self.city_a_combo['values']
            if city_a:
                # 更新城市B的下拉选项（排除城市A）
                new_options = [c for c in all_cities if c != city_a]
                self.city_b_combo['values'] = new_options
                # 如果当前城市B等于城市A，则自动设置为第一个可用选项
                if self.city_b_var.get() == city_a and new_options:
                    self.city_b_var.set(new_options[0])
            else:
                self.city_b_combo['values'] = all_cities
            self._save_city_selection()

        def on_city_b_change(*args):
            city_b = self.city_b_var.get()
            all_cities = self.city_b_combo['values']  # 注意：此时可能已被排除，但原始列表需要从 city_a_combo 取
            original_cities = self.city_a_combo['values']
            if city_b:
                new_options = [c for c in original_cities if c != city_b]
                self.city_a_combo['values'] = new_options
                if self.city_a_var.get() == city_b and new_options:
                    self.city_a_var.set(new_options[0])
            else:
                self.city_a_combo['values'] = original_cities
            self._save_city_selection()

        # 绑定事件
        self.city_a_var.trace_add('write', on_city_a_change)
        self.city_b_var.trace_add('write', on_city_b_change)

    # ==================== 日志函数 ====================

    def log_callback(self, message, tag=None):
        self.log_text.config(state="normal")
        if tag == 'error':
            self.log_text.insert(tk.END, message + "\n", 'error')
            self.log_text.tag_config('error', foreground='red')
        else:
            self.log_text.insert(tk.END, message + "\n")
        self.log_text.see(tk.END)
        self.log_text.config(state="disabled")
        self.root.update_idletasks()


    # ==================== 菜单功能函数 ====================

    def show_config_tab(self):
        """打开配置窗口 - 如果已存在则弹出到前台"""
        self.logger.info("打开配置界面")

        # 如果窗口已存在且未销毁，则将其弹出到前台
        if self.config_window is not None and self.config_window.winfo_exists():
            self.config_window.lift()
            self.config_window.focus_force()
            return

        # 创建新窗口
        self.open_config_window()

    def _create_config_frame_with_auto_save(self, parent, section, keys):
        """创建配置框架 - 实时保存版本"""
        # 使用Canvas实现滚动
        canvas = tk.Canvas(parent)
        scrollbar = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)

        scrollable_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        row = 0
        for key in keys:
            cn_name = self.config.get_cn_name(section, key)
            value = self.config.get(section, key, '')

            # 创建标签
            label = ttk.Label(scrollable_frame, text=f"{cn_name}:", font=("微软雅黑", 9))
            label.grid(row=row, column=0, sticky=tk.W, pady=5, padx=5)

            if key == 'screenshot_path':
                # 截图保存路径是完整文件名，不能使用目录选择，显示普通输入框
                var = tk.StringVar(value=value)
                entry = ttk.Entry(scrollable_frame, textvariable=var, width=40)
                entry.grid(row=row, column=1, pady=5, padx=5, sticky=tk.W)

                def save_screenshot_path(sv=var, sec=section, k=key):
                    self.config.set(sec, k, sv.get())
                    self.logger.info(f"配置已保存: {sec}.{k} = {sv.get()}")

                var.trace_add('write', lambda *args, sv=var, sec=section, k=key: save_screenshot_path(sv, sec, k))

            elif 'path' in key.lower() or 'folder' in key.lower():
                # 路径选择
                entry_frame = ttk.Frame(scrollable_frame)
                entry_frame.grid(row=row, column=1, pady=5, padx=5, sticky=tk.W)
                var = tk.StringVar(value=value)
                entry = ttk.Entry(entry_frame, textvariable=var, width=40)
                entry.pack(side=tk.LEFT)

                # 实时保存
                def save_on_change(path_var=var, sec=section, k=key):
                    self.config.set(sec, k, path_var.get())
                    self.logger.info(f"配置已保存: {sec}.{k} = {path_var.get()}")

                var.trace_add('write', lambda *args, sv=var, sec=section, k=key: save_on_change(sv, sec, k))

                def browse(path_var=var):
                    path = filedialog.askdirectory()
                    if path:
                        path_var.set(path)

                ttk.Button(entry_frame, text="浏览", command=lambda v=var: browse(v)).pack(side=tk.LEFT, padx=5)

            elif key == 'cities':
                # 城市列表使用多行文本框
                cities_list = [c.strip() for c in value.split(',') if c.strip()]
                text_height = max(8, min(len(cities_list) + 2, 15))
                text_widget = tk.Text(scrollable_frame, height=text_height, width=50,
                                      font=("Consolas", 9), wrap=tk.WORD)
                text_widget.grid(row=row, column=1, pady=5, padx=5, columnspan=2, sticky=tk.W)
                formatted_value = '\n'.join(cities_list)
                text_widget.insert('1.0', formatted_value)

                # 实时保存
                def save_text():
                    text_value = text_widget.get('1.0', tk.END).strip()
                    lines = [line.strip() for line in text_value.split('\n') if line.strip()]
                    new_value = ','.join(lines)
                    self.config.set(section, 'cities', new_value)
                    self.logger.info(f"配置已保存: {section}.cities")
                    # 重新加载城市列表
                    self.load_cities()

                text_widget.bind('<FocusOut>', lambda e: save_text())

                tip_frame = ttk.Frame(scrollable_frame)
                tip_frame.grid(row=row, column=3, padx=5, sticky=tk.W)
                ttk.Label(tip_frame, text="每行一个城市", foreground="gray", font=("微软雅黑", 8)).pack(anchor=tk.W)
                ttk.Label(tip_frame, text="保存时自动转换为逗号分隔", foreground="gray", font=("微软雅黑", 8)).pack(
                    anchor=tk.W)

            elif key == 'debug':
                # Debug 模式使用复选框
                var = tk.BooleanVar(value=value == '1' or value.lower() == 'true')
                check = ttk.Checkbutton(scrollable_frame, variable=var)
                check.grid(row=row, column=1, pady=5, padx=5, sticky=tk.W)

                def save_debug():
                    new_value = '1' if var.get() else '0'
                    self.config.set(section, key, new_value)
                    self.logger.info(f"配置已保存: {section}.{key} = {new_value}")

                var.trace_add('write', lambda *args: save_debug())

            elif key == 'use_gray' or key == 'preprocess':
                # 其他布尔值使用复选框
                var = tk.BooleanVar(value=value.lower() == 'true')
                check = ttk.Checkbutton(scrollable_frame, text="启用", variable=var)
                check.grid(row=row, column=1, pady=5, padx=5, sticky=tk.W)

                def save_bool():
                    new_value = 'True' if var.get() else 'False'
                    self.config.set(section, key, new_value)
                    self.logger.info(f"配置已保存: {section}.{key} = {new_value}")

                var.trace_add('write', lambda *args: save_bool())

            elif ('_score' in key.lower() or '_thresh' in key.lower()
                  or '_ratio' in key.lower() or 'threshold' in key.lower()):
                # OCR 置信度/阈值等使用浮点数输入框
                vcmd = (parent.register(self._validate_float_input), '%P')
                var = tk.StringVar(value=value)
                entry = ttk.Entry(scrollable_frame, textvariable=var, width=12,
                                  font=("微软雅黑", 9), validate='key', validatecommand=vcmd)
                entry.grid(row=row, column=1, pady=5, padx=5, sticky=tk.W)

                def save_float(sv=var, sec=section, k=key):
                    self.config.set(sec, k, sv.get())
                    self.logger.info(f"配置已保存: {sec}.{k} = {sv.get()}")

                var.trace_add('write', lambda *args, sv=var, sec=section, k=key: save_float(sv, sec, k))

            elif key == 'screenshot_quality':
                # 截图质量使用整数输入框
                vcmd = (parent.register(self._validate_int_input), '%P')
                var = tk.StringVar(value=value)
                entry_frame = ttk.Frame(scrollable_frame)
                entry_frame.grid(row=row, column=1, pady=5, padx=5, sticky=tk.W)
                entry = ttk.Entry(entry_frame, textvariable=var, width=6,
                                  font=("微软雅黑", 9), validate='key', validatecommand=vcmd)
                entry.pack(side=tk.LEFT)

                def save_quality(sv=var, sec=section, k=key):
                    self.config.set(sec, k, sv.get())
                    self.logger.info(f"配置已保存: {sec}.{k} = {sv.get()}")

                var.trace_add('write', lambda *args, sv=var, sec=section, k=key: save_quality(sv, sec, k))

                unit_label = ttk.Label(entry_frame, text="%", foreground="gray", font=("微软雅黑", 9))
                unit_label.pack(side=tk.LEFT, padx=(1, 0))

            elif 'count' in key.lower() or 'number' in key.lower() or 'num' in key.lower():
                # 数量输入框（只允许数字）
                vcmd = (parent.register(self._validate_int_input), '%P')
                var = tk.StringVar(value=value)
                entry = ttk.Entry(scrollable_frame, textvariable=var, width=12,
                                  font=("微软雅黑", 9), validate='key', validatecommand=vcmd)
                entry.grid(row=row, column=1, pady=5, padx=5, sticky=tk.W)

                # 实时保存
                def save_count(sv=var, sec=section, k=key):
                    self.config.set(sec, k, sv.get())
                    self.logger.info(f"配置已保存: {sec}.{k} = {sv.get()}")

                var.trace_add('write', lambda *args, sv=var, sec=section, k=key: save_count(sv, sec, k))

                # 添加单位标签
                unit_label = ttk.Label(scrollable_frame, text="次", foreground="gray", font=("微软雅黑", 9))
                unit_label.grid(row=row, column=2, sticky=tk.W, pady=5, padx=2)

            else:
                # 普通输入框
                var = tk.StringVar(value=value)
                entry = ttk.Entry(scrollable_frame, textvariable=var, width=30, font=("微软雅黑", 9))
                entry.grid(row=row, column=1, pady=5, padx=5, sticky=tk.W)

                # 实时保存
                def save_entry(sv=var, sec=section, k=key):
                    self.config.set(sec, k, sv.get())
                    self.logger.info(f"配置已保存: {sec}.{k} = {sv.get()}")

                var.trace_add('write', lambda *args, sv=var, sec=section, k=key: save_entry(sv, sec, k))

            row += 1

        # 添加底部弹簧
        spacer = ttk.Frame(scrollable_frame, height=20)
        spacer.grid(row=row, column=0, pady=10)

    def _create_city_config_frame_with_auto_save(self, parent, section, keys, city_name):
        """创建城市配置框架 - 实时保存版本"""
        # 使用Canvas实现滚动
        canvas = tk.Canvas(parent)
        scrollbar = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)

        scrollable_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        row = 0

        # 添加城市名称标题
        title_label = ttk.Label(scrollable_frame, text=f"【{city_name}】跑商配置",
                                font=("微软雅黑", 12, "bold"), foreground="blue")
        title_label.grid(row=row, column=0, columnspan=3, pady=15, padx=10, sticky=tk.W)
        row += 1

        # 添加分隔线
        separator = ttk.Separator(scrollable_frame, orient='horizontal')
        separator.grid(row=row, column=0, columnspan=3, sticky="ew", pady=5, padx=10)
        row += 1

        for key in keys:
            cn_name = self.config.get_cn_name(section, key)
            # 使用 get_city_config 获取值
            value = self.config.get_city_config(city_name, key, '0')

            # 创建标签
            label = ttk.Label(scrollable_frame, text=f"{cn_name}:", font=("微软雅黑", 10))
            label.grid(row=row, column=0, sticky=tk.W, pady=8, padx=10)

            if key == 'purchase_book_count':
                # 数量输入框（只允许数字）
                vcmd = (parent.register(self._validate_int_input), '%P')
                var = tk.StringVar(value=value)
                entry = ttk.Entry(scrollable_frame, textvariable=var, width=12,
                                  font=("微软雅黑", 10), validate='key', validatecommand=vcmd)
                entry.grid(row=row, column=1, pady=8, padx=10, sticky=tk.W)

                # 实时保存 - 不输出日志
                def save_count(*args, c=city_name, k=key, v=var):
                    new_value = v.get()
                    self.config.set_city_config(c, k, new_value)

                var.trace_add('write', save_count)

                # 添加单位标签
                unit_label = ttk.Label(scrollable_frame, text="本", foreground="gray", font=("微软雅黑", 9))
                unit_label.grid(row=row, column=2, sticky=tk.W, pady=8, padx=5)

            elif key == 'enable_bargain' or key == 'enable_price_increase':
                # 是否砍价/是否抬价 - 使用复选框
                is_enabled = value.lower() in ['true', '1', 'yes']
                var = tk.BooleanVar(value=is_enabled)
                check = ttk.Checkbutton(scrollable_frame, variable=var)
                check.grid(row=row, column=1, pady=8, padx=10, sticky=tk.W)

                # 实时保存 - 不输出日志
                def save_bool(*args, c=city_name, k=key, v=var):
                    new_value = 'True' if v.get() else 'False'
                    self.config.set_city_config(c, k, new_value)

                var.trace_add('write', save_bool)

                # 添加说明标签
                if key == 'enable_bargain':
                    tip_label = ttk.Label(scrollable_frame, text="启用后会在买入时自动砍价到20%",
                                          foreground="gray", font=("微软雅黑", 8))
                    tip_label.grid(row=row, column=2, columnspan=2, sticky=tk.W, pady=8, padx=5)
                elif key == 'enable_price_increase':
                    tip_label = ttk.Label(scrollable_frame, text="启用后会在买入时自动抬价",
                                          foreground="gray", font=("微软雅黑", 8))
                    tip_label.grid(row=row, column=2, columnspan=2, sticky=tk.W, pady=8, padx=5)

            row += 1

        # 添加说明文字
        info_frame = ttk.Frame(scrollable_frame)
        info_frame.grid(row=row, column=0, columnspan=3, pady=15, padx=10, sticky=tk.W)

        info_label = ttk.Label(info_frame, text="💡 提示：",
                               foreground="blue", font=("微软雅黑", 9))
        info_label.pack(anchor=tk.W)

        info_text = ttk.Label(info_frame,
                              text="• 进货书数量：每次跑商使用的进货书本数\n• 是否砍价：是否自动砍价到20.0%\n• 是否抬价：是否自动抬价（预留功能）\n• 修改后自动保存，无需点击保存按钮",
                              foreground="gray", font=("微软雅黑", 8), justify=tk.LEFT)
        info_text.pack(anchor=tk.W, padx=15)

    def open_config_window(self):
        """打开配置窗口，允许用户修改各项配置 - 实时保存"""
        self.config_window = tk.Toplevel(self.root)
        self.config_window.title("配置设置")
        self.config_window.geometry("850x650")

        # 绑定关闭事件
        self.config_window.protocol("WM_DELETE_WINDOW", self.on_config_close)

        # 使用Notebook创建多个配置标签页
        notebook = ttk.Notebook(self.config_window)
        notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # 定义要显示的配置节
        sections = ['ADB', 'Recognition', 'OCR', 'Auto', 'Paths']

        if self.debug_mode == 1:
            sections.append('Debug')

        # 普通配置页
        for section in sections:
            # 使用 has_section 方法检查
            if not self.config.has_section(section):
                continue

            keys = self.config.get_section_keys(section, self.debug_mode)
            if not keys:
                continue

            frame = ttk.Frame(notebook)
            notebook.add(frame, text=self.config.get_section_cn(section))

            self._create_config_frame_with_auto_save(frame, section, keys)

        # ==================== 城市配置 ====================
        city_main_frame = ttk.Frame(notebook)
        notebook.add(city_main_frame, text="城市配置")

        city_notebook = ttk.Notebook(city_main_frame)
        city_notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # 城市列表配置页
        city_list_frame = ttk.Frame(city_notebook)
        city_notebook.add(city_list_frame, text="城市列表")

        if self.config.has_section('City'):
            city_keys = self.config.get_section_keys('City', self.debug_mode)
            if city_keys:
                self._create_config_frame_with_auto_save(city_list_frame, 'City', city_keys)

        # 各城市配置页（延迟到第一次点击对应页签时才创建，加快配置窗口打开速度）
        cities_str = self.config.get('City', 'cities', '')
        cities = [c.strip() for c in cities_str.split(',') if c.strip()]

        self.logger.info(f"加载 {len(cities)} 个城市配置")

        city_built = set()

        def ensure_city_section(city):
            city_section = f"City_{city}"

            # 确保配置节存在
            if not self.config.has_section(city_section):
                self.config.set(city_section, 'purchase_book_count', '0')
                self.config.set(city_section, 'enable_bargain', 'True')
                self.config.set(city_section, 'enable_price_increase', 'False')
                self.config.set(city_section, 'cn',
                                '{"purchase_book_count":"进货书数量","enable_bargain":"是否砍价","enable_price_increase":"是否抬价"}')
                self.config.set(city_section, 'section_cn', f'{city}配置')

            keys = ['purchase_book_count', 'enable_bargain', 'enable_price_increase']
            return city_section, keys

        def on_city_tab_changed(event=None):
            selected = city_notebook.select()
            if not selected:
                return
            try:
                index = city_notebook.index(selected)
            except Exception:
                return
            if index < 1 or index - 1 >= len(cities):
                return

            city = cities[index - 1]
            if city in city_built:
                return
            city_built.add(city)

            frame = city_notebook.nametowidget(selected)
            city_section, keys = ensure_city_section(city)
            self._create_city_config_frame_with_auto_save(frame, city_section, keys, city)

        for city in cities:
            city_frame = ttk.Frame(city_notebook)
            city_notebook.add(city_frame, text=city)

        city_notebook.bind('<<NotebookTabChanged>>', on_city_tab_changed)

    def _create_config_frame(self, parent, section, keys):
        """创建配置框架"""
        # 使用Canvas实现滚动
        canvas = tk.Canvas(parent)
        scrollbar = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)

        scrollable_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        row = 0
        for key in keys:
            cn_name = self.config.get_cn_name(section, key)
            value = self.config.get(section, key, '')

            # 创建标签
            label = ttk.Label(scrollable_frame, text=f"{cn_name}:", font=("微软雅黑", 9))
            label.grid(row=row, column=0, sticky=tk.W, pady=5, padx=5)

            if 'path' in key.lower() or 'folder' in key.lower():
                # 路径选择
                entry_frame = ttk.Frame(scrollable_frame)
                entry_frame.grid(row=row, column=1, pady=5, padx=5, sticky=tk.W)
                var = tk.StringVar(value=value)
                entry = ttk.Entry(entry_frame, textvariable=var, width=40)
                entry.pack(side=tk.LEFT)

                def browse(path_var=var):

                    path = filedialog.askdirectory()
                    if path:
                        path_var.set(path)

                ttk.Button(entry_frame, text="浏览", command=lambda v=var: browse(v)).pack(side=tk.LEFT, padx=5)
                self.config_vars[f'{section}_{key}'] = ('entry', var)

            elif key == 'cities':
                # 城市列表使用多行文本框
                cities_list = [c.strip() for c in value.split(',') if c.strip()]
                text_height = max(8, min(len(cities_list) + 2, 15))
                text_widget = tk.Text(scrollable_frame, height=text_height, width=50,
                                      font=("Consolas", 9), wrap=tk.WORD)
                text_widget.grid(row=row, column=1, pady=5, padx=5, columnspan=2, sticky=tk.W)
                formatted_value = '\n'.join(cities_list)
                text_widget.insert('1.0', formatted_value)
                self.config_vars[f'{section}_{key}'] = ('text', text_widget)

                tip_frame = ttk.Frame(scrollable_frame)
                tip_frame.grid(row=row, column=3, padx=5, sticky=tk.W)
                ttk.Label(tip_frame, text="每行一个城市", foreground="gray", font=("微软雅黑", 8)).pack(anchor=tk.W)
                ttk.Label(tip_frame, text="保存时自动转换为逗号分隔", foreground="gray", font=("微软雅黑", 8)).pack(
                    anchor=tk.W)

            elif key == 'debug':
                # Debug 模式使用复选框，但存储为 0 或 1
                var = tk.BooleanVar(value=value == '1' or value.lower() == 'true')
                check = ttk.Checkbutton(scrollable_frame, text="启用", variable=var)
                check.grid(row=row, column=1, pady=5, padx=5, sticky=tk.W)
                self.config_vars[f'{section}_{key}'] = ('debug_bool', var)

            elif key == 'use_gray' or key == 'preprocess':
                # 其他布尔值使用复选框
                var = tk.BooleanVar(value=value.lower() == 'true')
                check = ttk.Checkbutton(scrollable_frame, text="启用", variable=var)
                check.grid(row=row, column=1, pady=5, padx=5, sticky=tk.W)
                self.config_vars[f'{section}_{key}'] = ('bool', var)

            elif 'count' in key.lower() or 'number' in key.lower() or 'num' in key.lower():
                # 数量输入框（只允许数字）
                vcmd = (parent.register(self._validate_int_input), '%P')
                var = tk.StringVar(value=value)
                entry = ttk.Entry(scrollable_frame, textvariable=var, width=12,
                                  font=("微软雅黑", 9), validate='key', validatecommand=vcmd)
                entry.grid(row=row, column=1, pady=5, padx=5, sticky=tk.W)
                self.config_vars[f'{section}_{key}'] = ('entry', var)

                unit_label = ttk.Label(scrollable_frame, text="次", foreground="gray", font=("微软雅黑", 9))
                unit_label.grid(row=row, column=2, sticky=tk.W, pady=5, padx=2)

            else:
                # 普通输入框
                var = tk.StringVar(value=value)
                entry = ttk.Entry(scrollable_frame, textvariable=var, width=30, font=("微软雅黑", 9))
                entry.grid(row=row, column=1, pady=5, padx=5, sticky=tk.W)
                self.config_vars[f'{section}_{key}'] = ('entry', var)

            row += 1

        # 添加底部弹簧，使内容靠上
        spacer = ttk.Frame(scrollable_frame, height=20)
        spacer.grid(row=row, column=0, pady=10)

    def _create_city_config_frame(self, parent, section, keys, city_name):
        """创建城市配置框架"""
        # 使用Canvas实现滚动
        canvas = tk.Canvas(parent)
        scrollbar = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)

        scrollable_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        row = 0

        # 添加城市名称标题
        title_label = ttk.Label(scrollable_frame, text=f"【{city_name}】跑商配置",
                                font=("微软雅黑", 12, "bold"), foreground="blue")
        title_label.grid(row=row, column=0, columnspan=3, pady=15, padx=10, sticky=tk.W)
        row += 1

        # 添加分隔线
        separator = ttk.Separator(scrollable_frame, orient='horizontal')
        separator.grid(row=row, column=0, columnspan=3, sticky="ew", pady=5, padx=10)
        row += 1

        for key in keys:
            cn_name = self.config.get_cn_name(section, key)
            # 使用 get_city_config 获取值
            value = self.config.get_city_config(city_name, key, '0')

            # 创建标签
            label = ttk.Label(scrollable_frame, text=f"{cn_name}:", font=("微软雅黑", 10))
            label.grid(row=row, column=0, sticky=tk.W, pady=8, padx=10)

            if key == 'purchase_book_count':
                # 数量输入框（只允许数字）
                vcmd = (parent.register(self._validate_int_input), '%P')
                var = tk.StringVar(value=value)
                entry = ttk.Entry(scrollable_frame, textvariable=var, width=12,
                                  font=("微软雅黑", 10), validate='key', validatecommand=vcmd)
                entry.grid(row=row, column=1, pady=8, padx=10, sticky=tk.W)
                self.config_vars[f'city_{city_name}|{key}'] = ('city_entry', var)

                # 添加单位标签
                unit_label = ttk.Label(scrollable_frame, text="本", foreground="gray", font=("微软雅黑", 9))
                unit_label.grid(row=row, column=2, sticky=tk.W, pady=8, padx=5)

            elif key == 'enable_bargain' or key == 'enable_price_increase':
                # 是否砍价/是否抬价 - 使用复选框
                # 处理值：如果是 'True' 或 'true' 或 '1' 则为 True
                is_enabled = value.lower() in ['true', '1', 'yes']
                var = tk.BooleanVar(value=is_enabled)
                check = ttk.Checkbutton(scrollable_frame, variable=var)
                check.grid(row=row, column=1, pady=8, padx=10, sticky=tk.W)
                self.config_vars[f'city_{city_name}|{key}'] = ('city_bool', var)

                # 添加说明标签
                if key == 'enable_bargain':
                    tip_label = ttk.Label(scrollable_frame, text="启用后会在买入时自动砍价到20%",
                                          foreground="gray", font=("微软雅黑", 8))
                    tip_label.grid(row=row, column=2, columnspan=2, sticky=tk.W, pady=8, padx=5)
                elif key == 'enable_price_increase':
                    tip_label = ttk.Label(scrollable_frame, text="启用后会在买入时自动抬价",
                                          foreground="gray", font=("微软雅黑", 8))
                    tip_label.grid(row=row, column=2, columnspan=2, sticky=tk.W, pady=8, padx=5)

            row += 1

        # 添加说明文字
        info_frame = ttk.Frame(scrollable_frame)
        info_frame.grid(row=row, column=0, columnspan=3, pady=15, padx=10, sticky=tk.W)

        info_label = ttk.Label(info_frame, text="💡 提示：",
                               foreground="blue", font=("微软雅黑", 9))
        info_label.pack(anchor=tk.W)

        info_text = ttk.Label(info_frame,
                              text="• 进货书数量：每次跑商使用的进货书本数\n• 是否砍价：是否自动砍价到20.0%\n• 是否抬价：是否自动抬价（预留功能）",
                              foreground="gray", font=("微软雅黑", 8), justify=tk.LEFT)
        info_text.pack(anchor=tk.W, padx=15)


    def _validate_int_input(self, value):
        """验证整数输入"""
        if value == "":
            return True
        try:
            int(value)
            return True
        except ValueError:
            return False

    def open_monitor(self):
        """打开画面监控窗口 - 如果已存在则弹出到前台"""
        self.logger.info("开启画面监控")

        # 如果窗口已存在且未销毁，则将其弹出到前台
        if self.monitor_window is not None and self.monitor_window.winfo_exists():
            self.monitor_window.lift()
            self.monitor_window.focus_force()
            return

        # 创建新窗口
        self.monitor_window = tk.Toplevel(self.root)
        self.monitor_window.title("画面监控")
        self.monitor_window.geometry("650x550")

        # 绑定关闭事件
        self.monitor_window.protocol("WM_DELETE_WINDOW", self.on_monitor_close)

        # 创建图片显示标签
        image_label = ttk.Label(self.monitor_window)
        image_label.pack(pady=10)

        # 添加刷新按钮和状态标签
        control_frame = ttk.Frame(self.monitor_window)
        control_frame.pack(pady=5)

        status_label = ttk.Label(control_frame, text="监控中...")
        status_label.pack(side=tk.LEFT, padx=10)

        refresh_btn = ttk.Button(control_frame, text="手动刷新",
                                 command=lambda: self._refresh_monitor(image_label, status_label))
        refresh_btn.pack(side=tk.LEFT, padx=10)

        # 自动刷新标志
        self.monitor_refresh_running = True

        def refresh_loop():
            """定时刷新画面"""
            if not self.monitor_refresh_running:
                return
            if self.monitor_window and self.monitor_window.winfo_exists():
                self._refresh_monitor(image_label, status_label)
                self.monitor_window.after(3000, refresh_loop)

        refresh_loop()

    def _validate_float_input(self, value):
        """验证浮点数输入（允许空、整数、小数）"""
        if value == "":
            return True
        try:
            float(value)
            return True
        except ValueError:
            return False


    def _refresh_monitor(self, image_label, status_label):
        """刷新监控画面"""
        if not self.adb.connected:
            status_label.config(text="未连接", foreground="red")
            return

        screenshot_path = self.adb.screenshot()
        if screenshot_path and Path(screenshot_path).exists():
            try:
                img = Image.open(screenshot_path)
                # 缩放图片以适应窗口
                img.thumbnail((600, 450))
                photo = ImageTk.PhotoImage(img)
                image_label.config(image=photo)
                image_label.image = photo  # 保持引用
                status_label.config(text="已刷新", foreground="green")
                self.logger.info("刷新画面")
            except Exception as e:
                self.logger.error(f"显示图片失败: {e}")
                status_label.config(text="显示失败", foreground="red")
        else:
            status_label.config(text="截图失败", foreground="red")

    def show_adb_tab(self):
        """打开ADB设置窗口 - 如果已存在则弹出到前台"""
        self.logger.info("打开ADB设置")

        # 如果窗口已存在且未销毁，则将其弹出到前台
        if self.adb_window is not None and self.adb_window.winfo_exists():
            self.adb_window.lift()
            self.adb_window.focus_force()
            return

        # 创建新窗口
        self.open_adb_window()

    def open_adb_window(self):
        """打开ADB连接设置窗口"""
        self.adb_window = tk.Toplevel(self.root)
        self.adb_window.title("ADB链接设置")
        self.adb_window.geometry("450x400")

        # 绑定关闭事件
        self.adb_window.protocol("WM_DELETE_WINDOW", self.on_adb_close)

        ttk.Label(self.adb_window, text="端口号:", font=("微软雅黑", 11)).pack(anchor=tk.W, pady=5, padx=20)
        port_var = tk.StringVar(value=self.config.get('ADB', 'default_port', '7555'))
        port_entry = ttk.Entry(self.adb_window, textvariable=port_var, font=("微软雅黑", 11))
        port_entry.pack(fill=tk.X, padx=20, pady=5)

        # 添加提示标签
        tip_label = ttk.Label(self.adb_window, text="常见模拟器端口：\n雷电:5555 | MuMu:7555 | 夜神:62001 | 逍遥:21503",
                              foreground="gray", font=("微软雅黑", 9))
        tip_label.pack(anchor=tk.W, padx=20, pady=5)

        # 添加状态标签
        status_var = tk.StringVar(value="就绪")
        status_label = ttk.Label(self.adb_window, textvariable=status_var, foreground="blue")
        status_label.pack(anchor=tk.W, padx=20, pady=5)

        def save_port_to_config(port):
            """保存端口号到配置文件"""
            self.config.set('ADB', 'default_port', port)
            self.logger.info(f"已保存默认端口: {port}")

        def auto_detect_and_connect():
            """自动检测并连接第一个可用的端口"""
            status_var.set("正在检测端口...")
            status_label.config(foreground="orange")
            self.adb_window.update()
            self.logger.info("开始自动检测端口")

            def detect_thread():
                port = self.adb.detect_adb_port()
                if port:
                    self.adb_window.after(0, lambda p=port: port_var.set(p))
                    self.adb_window.after(0, lambda: status_var.set(f"检测到端口: {port}，正在连接..."))
                    self.adb_window.after(0, lambda: status_label.config(foreground="blue"))

                    if self.adb.connect(port):
                        # 连接成功后保存端口到配置文件
                        save_port_to_config(port)
                        self.adb_window.after(0, lambda: status_var.set(f"连接成功! 端口: {port}"))
                        self.adb_window.after(0, lambda: status_label.config(foreground="green"))
                        self.adb_window.after(0, lambda: self.status_label.config(text=f"已连接 127.0.0.1:{port}",
                                                                                  foreground="green"))
                        self.logger.info(f"自动连接成功: 127.0.0.1:{port}")
                        self.adb_window.after(2000, self.on_adb_close)
                    else:
                        self.adb_window.after(0, lambda: status_var.set("连接失败，请重试"))
                        self.adb_window.after(0, lambda: status_label.config(foreground="red"))
                        self.logger.error(f"自动连接失败: 端口 {port}")
                else:
                    self.adb_window.after(0, lambda: status_var.set("未检测到可用端口"))
                    self.adb_window.after(0, lambda: status_label.config(foreground="red"))
                    self.logger.warning("自动检测未找到可用端口")

            threading.Thread(target=detect_thread, daemon=True).start()

        def connect_adb():
            """执行ADB连接（使用手动输入的端口）"""
            port = port_var.get()
            status_var.set(f"正在连接 {port}...")
            status_label.config(foreground="orange")
            self.adb_window.update()

            def connect_thread():
                if self.adb.connect(port):
                    # 连接成功后保存端口到配置文件
                    save_port_to_config(port)
                    self.adb_window.after(0, lambda: status_var.set(f"连接成功! 端口: {port}"))
                    self.adb_window.after(0, lambda: status_label.config(foreground="green"))
                    self.adb_window.after(0, lambda: self.status_label.config(text=f"已连接 127.0.0.1:{port}",
                                                                              foreground="green"))
                    self.logger.info(f"手动连接成功: 127.0.0.1:{port}")
                    self.adb_window.after(2000, self.on_adb_close)
                else:
                    self.adb_window.after(0, lambda: status_var.set("连接失败，请检查端口号"))
                    self.adb_window.after(0, lambda: status_label.config(foreground="red"))
                    self.logger.error(f"手动连接失败: 端口 {port}")

            threading.Thread(target=connect_thread, daemon=True).start()

        button_frame = ttk.Frame(self.adb_window)
        button_frame.pack(pady=20)

        ttk.Button(button_frame, text="自动检测并连接", command=auto_detect_and_connect).pack(side=tk.LEFT, padx=10)
        ttk.Button(button_frame, text="手动连接", command=connect_adb).pack(side=tk.LEFT, padx=10)

    # ==================== 跑商功能函数 ====================

    def start_auto(self):
        """START!功能 - 启动跑商循环"""
        if not self.adb.connected:
            messagebox.showwarning("警告", "请先连接ADB")
            return

        if self.trade_route.is_running():
            messagebox.showwarning("警告", "跑商已在运行中")
            return

        # 获取选择的城市
        city_a = self.city_a_var.get()
        city_b = self.city_b_var.get()

        if not city_a or not city_b:
            messagebox.showwarning("警告", "请选择城市A和城市B")
            return

        if city_a == city_b:
            messagebox.showwarning("警告", "城市A和城市B不能相同")
            return

        # 设置跑商控制器
        self.trade_route.set_target_city(city_a, city_b)

        # 启动跑商
        if self.trade_route.start():
            self.logger.info(f"启动跑商: {city_a} -> {city_b}")
        else:
            self.logger.error("启动跑商失败")

    def pause_auto(self):
        """暂停自动托管"""
        if self.trade_route.is_running() and not self.trade_route.is_paused():
            self.trade_route.pause()
            self.logger.info("暂停托管")
        else:
            self.logger.warning("无法暂停：跑商未运行或已暂停")

    def resume_auto(self):
        """恢复自动托管"""
        if self.trade_route.is_running() and self.trade_route.is_paused():
            self.trade_route.resume()
            self.logger.info("恢复托管")
        else:
            self.logger.warning("无法恢复：跑商未运行或未暂停")

    def stop_auto(self):
        """停止自动托管"""
        if self.trade_route.is_running():
            self.trade_route.stop()
            self.logger.info("停止托管")
        else:
            self.logger.warning("跑商未在运行")

    def _check_and_list_images(self):
        """检查并列出 picture 文件夹中的所有图片"""
        picture_folder = Path("picture")
        if not picture_folder.exists():
            self.logger.warning("picture 文件夹不存在")
            picture_folder.mkdir(exist_ok=True)
            return

        self.logger.info("=== picture 文件夹内容 ===")
        for file_path in picture_folder.rglob("*"):
            if file_path.is_file() and file_path.suffix.lower() in ['.png', '.jpg', '.jpeg', '.bmp']:
                rel_path = file_path.relative_to(picture_folder)
                self.logger.info(f"  - {rel_path}")
        self.logger.info("========================")

    def _test_image_read(self, image_path):
        """测试图片是否可以正常读取"""
        try:
            img = cv2.imread(str(image_path))
            if img is not None:
                self.logger.info(f"图片读取成功: {image_path}, 尺寸: {img.shape}")
                return True
            else:
                self.logger.error(f"图片读取失败: {image_path}")
                return False
        except Exception as e:
            self.logger.error(f"图片读取异常: {image_path}, 错误: {e}")
            return False

    def update_trailer_display(self):
        """更新UI中的拖车数量显示"""
        count = self.config.get_int('Trailer', 'count', 0)
        if hasattr(self, 'trailer_count_var'):
            self.trailer_count_var.set(str(count))



    # ==================== Debug模式功能函数 ====================

    def debug_find_image(self):
        """
        Debug模式：寻图功能
        对模拟器截图并识别指定图片
        """
        if not self.adb.connected:
            self.logger.error("ADB未连接，无法寻图")
            messagebox.showwarning("警告", "请先连接ADB")
            return

        image_name = self.find_image_var.get().strip()
        if not image_name:
            self.logger.error("请输入图片文件名")
            messagebox.showwarning("警告", "请输入图片文件名")
            return

        self.logger.info(f"开始寻图: {image_name}")

        # 截图（使用临时英文文件名保存）
        screenshot_path = self.adb.screenshot()
        if not screenshot_path:
            self.logger.error("截图失败，无法寻图")
            return

        # 测试截图是否可读
        test_img = self.image_rec._imread_chinese(screenshot_path)
        if test_img is None:
            self.logger.error("截图文件无法读取，可能是中文路径问题")
            # 尝试重新截图到英文路径
            temp_path = Path("temp") / "debug_screenshot.png"
            self.adb.screenshot(str(temp_path))
            screenshot_path = str(temp_path)

            test_img2 = self.image_rec._imread_chinese(screenshot_path)
            if test_img2 is None:
                self.logger.error("截图文件仍然无法读取")
                messagebox.showerror("错误", "截图文件无法读取，请检查ADB连接")
                return

        # 搜索图片
        picture_folder = Path("picture")
        found_paths = []

        for file_path in picture_folder.rglob("*"):
            if file_path.is_file() and file_path.suffix.lower() in ['.png', '.jpg', '.jpeg', '.bmp']:
                if file_path.name == image_name or file_path.stem == Path(image_name).stem:
                    found_paths.append(file_path)

        if not found_paths:
            self.logger.error(f"在 picture 文件夹中找不到图片: {image_name}")
            messagebox.showwarning("寻图失败", f"找不到图片文件: {image_name}\n请检查 picture 文件夹")
            return

        # 尝试匹配每个找到的图片
        best_result = None
        best_match = -1

        for img_path in found_paths:
            self.logger.info(f"尝试匹配: {img_path}")

            # 使用支持中文路径的 find_image
            result = self.image_rec.find_image(screenshot_path, str(img_path))

            if result:
                x, y, match_value = result
                if match_value > best_match:
                    best_match = match_value
                    best_result = (x, y, match_value, img_path)

        if best_result:
            x, y, match_value, img_path = best_result
            self.logger.info(f"寻图成功! 图片: {image_name}, 位置: ({x}, {y}), 匹配度: {match_value:.2f}")
            self.logger.info(f"使用图片: {img_path}")
            messagebox.showinfo("寻图成功", f"找到图片: {image_name}\n坐标: ({x}, {y})\n匹配度: {match_value:.2f}")
        else:
            self.logger.warning(f"寻图失败! 未找到匹配的图片: {image_name}")
            messagebox.showwarning("寻图失败", f"未找到匹配的图片: {image_name}")

    def debug_click(self):
        """
        Debug模式：点击功能
        对模拟器发送指定坐标的点击
        """
        if not self.adb.connected:
            self.logger.error("ADB未连接，无法点击")
            messagebox.showwarning("警告", "请先连接ADB")
            return

        coord_text = self.click_pos_var.get().strip()
        if not coord_text:
            self.logger.error("请输入坐标")
            messagebox.showwarning("警告", "请输入坐标，格式: x,y")
            return

        try:
            # 解析坐标，支持 "100,100" 或 "100 100" 或 "100, 100" 格式
            coord_text = coord_text.replace(' ', '')
            if ',' in coord_text:
                parts = coord_text.split(',')
            else:
                parts = coord_text.split()

            if len(parts) != 2:
                raise ValueError("坐标格式错误")

            x = int(parts[0])
            y = int(parts[1])

            self.logger.info(f"Debug点击: 坐标 ({x}, {y})")

            if self.adb.click(x, y):
                self.logger.info(f"点击成功: ({x}, {y})")
            else:
                self.logger.error(f"点击失败: ({x}, {y})")

        except ValueError as e:
            self.logger.error(f"坐标解析失败: {coord_text}, 错误: {e}")
            messagebox.showwarning("格式错误", "坐标格式错误，请使用格式: x,y\n例如: 100,100")

    def debug_ocr_full(self):
        """
        Debug模式：全屏文字识别功能
        对模拟器截图并识别全屏文字，结果输出到日志
        """
        if not self.adb.connected:
            self.logger.error("ADB未连接，无法识别文字")
            messagebox.showwarning("警告", "请先连接ADB")
            return

        self.logger.info("开始全屏文字识别")

        # 截图
        screenshot_path = self.adb.screenshot()
        if not screenshot_path:
            self.logger.error("截图失败，无法识别文字")
            return

        # 识别文字
        text = self.image_rec.recognize_text(screenshot_path)

        if text:
            self.logger.info(f"识别到文字:\n{text}")
            messagebox.showinfo("识别成功", f"识别到文字，已输出到日志")
        else:
            self.logger.warning("未识别到文字")
            messagebox.showwarning("识别失败", "未识别到任何文字")

    def debug_ocr_area(self):
        """
        Debug模式：区域文字识别功能
        允许用户用鼠标框选区域，识别该区域的文字
        """
        if not self.adb.connected:
            self.logger.error("ADB未连接，无法识别文字")
            messagebox.showwarning("警告", "请先连接ADB")
            return

        self.logger.info("开始区域文字识别，请在弹出的截图中框选识别区域")

        # 截图
        screenshot_path = self.adb.screenshot()
        if not screenshot_path:
            self.logger.error("截图失败，无法识别文字")
            return

        # 打开截图供用户框选
        self.select_area_and_ocr(screenshot_path)

    def select_area_and_ocr(self, screenshot_path):
        """
        打开截图窗口，让用户框选区域进行OCR识别
        :param screenshot_path: 截图路径
        """
        # 创建选择窗口
        select_win = tk.Toplevel(self.root)
        select_win.title("框选识别区域")
        select_win.geometry("800x600")

        # 加载图片
        img = Image.open(screenshot_path)
        # 缩放图片以适应窗口
        display_img = img.copy()
        display_img.thumbnail((750, 500))

        photo = ImageTk.PhotoImage(display_img)

        # 创建画布显示图片
        canvas = tk.Canvas(select_win, width=display_img.width, height=display_img.height)
        canvas.pack(pady=10)
        canvas.create_image(0, 0, anchor=tk.NW, image=photo)
        canvas.image = photo  # 保持引用

        # 坐标变量
        start_x = tk.IntVar()
        start_y = tk.IntVar()
        end_x = tk.IntVar()
        end_y = tk.IntVar()
        rect_id = None

        # 缩放比例
        scale_x = img.width / display_img.width
        scale_y = img.height / display_img.height

        def on_mouse_down(event):
            nonlocal rect_id
            start_x.set(event.x)
            start_y.set(event.y)
            if rect_id:
                canvas.delete(rect_id)
            rect_id = canvas.create_rectangle(start_x.get(), start_y.get(),
                                              start_x.get(), start_y.get(),
                                              outline="red", width=2)

        def on_mouse_move(event):
            if rect_id:
                canvas.coords(rect_id, start_x.get(), start_y.get(), event.x, event.y)

        def on_mouse_up(event):
            end_x.set(event.x)
            end_y.set(event.y)

            # 计算实际坐标
            x1 = int(min(start_x.get(), end_x.get()) * scale_x)
            y1 = int(min(start_y.get(), end_y.get()) * scale_y)
            x2 = int(max(start_x.get(), end_x.get()) * scale_x)
            y2 = int(max(start_y.get(), end_y.get()) * scale_y)

            # 关闭选择窗口
            select_win.destroy()

            # 识别区域文字
            self.logger.info(f"识别区域: ({x1},{y1}) -> ({x2},{y2})")
            area = (x1, y1, x2, y2)
            text = self.image_rec.recognize_text(screenshot_path, area)

            if text:
                self.logger.info(f"识别到文字:\n{text}")
                messagebox.showinfo("识别成功", f"识别到文字，已输出到日志")
            else:
                self.logger.warning("未识别到文字")
                messagebox.showwarning("识别失败", "未识别到任何文字")

        canvas.bind("<ButtonPress-1>", on_mouse_down)
        canvas.bind("<B1-Motion>", on_mouse_move)
        canvas.bind("<ButtonRelease-1>", on_mouse_up)

        # 添加提示标签
        ttk.Label(select_win, text="请在图片上按住鼠标左键拖动，框选要识别的区域",
                  foreground="blue").pack(pady=5)
        ttk.Label(select_win, text="松开鼠标后自动识别所选区域的文字",
                  foreground="gray").pack()

    def debug_test_buy(self):
        """
        测试买入功能
        执行一次完整的买入流程，与跑商逻辑相同
        """
        if not self.adb.connected:
            self.logger.error("ADB未连接，无法测试买入")
            messagebox.showwarning("警告", "请先连接ADB")
            return

        if self.trade_route.is_running():
            self.logger.warning("跑商流程正在运行，请先停止")
            messagebox.showwarning("警告", "跑商流程正在运行，请先停止")
            return

        # 获取选择的城市
        expected_city = self.city_a_var.get()
        if not expected_city:
            self.logger.error("请选择城市A")
            messagebox.showwarning("警告", "请选择城市A")
            return

        self.logger.info(f"========== 测试买入: {expected_city} ==========")

        # 临时设置 trade_route 的城市A和城市B，用于 _click_access_city 中的遍历判断
        self.trade_route.city_a = self.city_a_var.get()
        self.trade_route.city_b = self.city_b_var.get()

        self.trade_route.test_mode = True
        self.trade_route.running = False
        self.trade_route.paused = False
        self.trade_route.stop_flag = False

        def test_buy_thread():
            try:
                if self.trade_route.stop_flag:
                    self.logger.info("测试买入被停止")
                    return

                # 1. 返回主界面
                self.trade_route._back_to_main_ui()
                time.sleep(1)

                if self.trade_route.stop_flag:
                    return

                # 2. 点击访问城市并识别当前城市
                actual_city = self.trade_route._click_access_city(expected_city)
                if not actual_city:
                    actual_city = expected_city
                self.logger.info(f"实际当前城市: {actual_city}")

                if self.trade_route.stop_flag:
                    return

                # 3. 点击交易所
                if not self.trade_route._click_exchange(actual_city):
                    self.logger.error(f"找不到 {actual_city} 的交易所")
                    return
                time.sleep(1)

                if self.trade_route.stop_flag:
                    return

                # 4. 点击我要买
                if not self.trade_route._click_buy_button():
                    self.logger.error("点击我要买失败")
                    return
                time.sleep(1)

                # 5. 执行买入操作
                self.trade_route._execute_full_buy_operation(actual_city)

                self.logger.info("测试买入完成")
                messagebox.showinfo("测试买入", f"买入测试完成!\n城市: {actual_city}")

            except Exception:
                self.logger.error_red(f"[Warning]测试买入异常:\n{traceback.format_exc()}")
                messagebox.showerror("测试错误", "买入测试失败，请查看日志。")
            finally:
                self.trade_route.test_mode = False
                self.trade_route.stop_flag = False
                # 恢复原来的城市设置
                self.trade_route.city_a = self.city_a_var.get()
                self.trade_route.city_b = self.city_b_var.get()

        threading.Thread(target=test_buy_thread, daemon=True).start()

    def debug_test_sell(self):
        """
        测试卖出功能
        执行一次完整的卖出流程，与跑商逻辑相同
        """
        if not self.adb.connected:
            self.logger.error("ADB未连接，无法测试卖出")
            messagebox.showwarning("警告", "请先连接ADB")
            return

        if self.trade_route.is_running():
            self.logger.warning("跑商流程正在运行，请先停止")
            messagebox.showwarning("警告", "跑商流程正在运行，请先停止")
            return

        # 获取选择的城市
        expected_city = self.city_b_var.get()
        if not expected_city:
            self.logger.error("请选择城市B")
            messagebox.showwarning("警告", "请选择城市B")
            return

        self.logger.info(f"========== 测试卖出: {expected_city} ==========")

        self.trade_route.test_mode = True
        self.trade_route.running = False
        self.trade_route.paused = False
        self.trade_route.stop_flag = False

        def test_sell_thread():
            try:
                if self.trade_route.stop_flag:
                    self.logger.info("测试卖出被停止")
                    return

                # 1. 返回主界面
                self.trade_route._back_to_main_ui()
                time.sleep(1)

                if self.trade_route.stop_flag:
                    return

                # 2. 点击访问城市并识别当前城市
                actual_city = self.trade_route._click_access_city(expected_city)
                if not actual_city:
                    actual_city = expected_city
                self.logger.info(f"实际当前城市: {actual_city}")

                if self.trade_route.stop_flag:
                    return

                # 3. 点击交易所
                if not self.trade_route._click_exchange(actual_city):
                    self.logger.error(f"找不到 {actual_city} 的交易所")
                    return
                time.sleep(1)

                if self.trade_route.stop_flag:
                    return

                # 4. 点击我要卖
                if not self.trade_route._click_sell_button():
                    self.logger.error("点击我要卖失败")
                    return
                time.sleep(1)

                # 5. 执行卖出操作
                self.trade_route._execute_full_sell_operation(actual_city)

                self.logger.info("测试卖出完成")
                messagebox.showinfo("测试卖出", f"卖出测试完成!\n城市: {actual_city}")

            except Exception:
                self.logger.error_red(f"[Warning]测试卖出异常:\n{traceback.format_exc()}")
                messagebox.showerror("测试错误", "卖出测试失败，请查看日志。")
            finally:
                self.trade_route.test_mode = False
                self.trade_route.stop_flag = False

        threading.Thread(target=test_sell_thread, daemon=True).start()

    def debug_test_map(self):
        """
        测试地图功能
        执行一次完整的地图导航流程
        """
        if not self.adb.connected:
            self.logger.error("ADB未连接，无法测试地图")
            messagebox.showwarning("警告", "请先连接ADB")
            return

        # 如果主流程正在运行，提示用户
        if self.trade_route.is_running():
            self.logger.warning("跑商流程正在运行，请先停止")
            messagebox.showwarning("警告", "跑商流程正在运行，请先停止")
            return

        self.logger.info("========== 测试地图: 完整地图导航流程 ==========")

        # 设置测试模式
        self.trade_route.test_mode = True
        self.trade_route.running = False
        self.trade_route.paused = False
        self.trade_route.stop_flag = False

        def test_map_thread():
            try:
                # 检查是否被停止
                if self.trade_route.stop_flag:
                    self.logger.info("测试地图被停止")
                    return

                # 步骤1：检查并进入主界面
                self.logger.info("步骤1: 检查并进入主界面")
                if not self.trade_route._check_and_enter_main_ui():
                    self.logger.error("无法进入主界面")
                    messagebox.showerror("测试地图", "无法进入主界面")
                    return

                time.sleep(1)

                # 检查是否被停止
                if self.trade_route.stop_flag:
                    self.logger.info("测试地图被停止")
                    return

                # 步骤2：等待启程按钮出现
                self.logger.info("步骤2: 等待启程按钮")
                if not self.trade_route._wait_for_departure():
                    self.logger.error("未检测到启程按钮")
                    messagebox.showerror("测试地图", "未检测到启程按钮")
                    return

                time.sleep(1)

                # 步骤3：点击启程
                self.logger.info("步骤3: 点击启程按钮")
                max_attempts = 10
                found = False
                for attempt in range(max_attempts):
                    if self.trade_route.stop_flag:
                        return
                    result = self.image_rec.find_and_click(self.adb, "启程.png",  )
                    if result:
                        self.logger.info("点击启程成功")
                        found = True
                        break
                    self.logger.info(f"未找到启程按钮，第{attempt + 1}次重试")
                    time.sleep(1)

                if not found:
                    self.logger.warning("未找到启程按钮")
                    messagebox.showwarning("测试地图", "未找到启程按钮")
                    return

                time.sleep(2)

                # 检查是否被停止
                if self.trade_route.stop_flag:
                    self.logger.info("测试地图被停止")
                    return

                # 步骤4：获取目标城市
                target_city = self.city_b_var.get()
                if not target_city:
                    target_city = self.city_a_var.get()
                if not target_city:
                    self.logger.error("请选择城市A或城市B")
                    messagebox.showwarning("测试地图", "请选择城市A或城市B")
                    return

                self.logger.info(f"步骤4: 导航到目标城市 {target_city}")

                # 步骤5：执行地图导航
                if self.trade_route._navigate_to_city(target_city):
                    self.logger.info(f"成功导航到目标城市: {target_city}")
                    messagebox.showinfo("测试地图", f"导航成功!\n目标城市: {target_city}")
                else:
                    self.logger.error(f"导航失败，无法到达目标城市: {target_city}")
                    messagebox.showerror("测试地图", f"导航失败!\n无法找到目标城市: {target_city}")


            except Exception:

                self.logger.error_red(f"[Warning]测试买入异常:\n{traceback.format_exc()}")

                messagebox.showerror("测试错误", "买入测试失败，请查看日志。")

            finally:

                self.trade_route.test_mode = False

                self.trade_route.stop_flag = False

        threading.Thread(target=test_map_thread, daemon=True).start()

    def debug_swipe(self):
        """
        Debug模式：滑动功能
        对模拟器发送指定坐标的滑动，完成后点击(1909,17)
        """
        if not self.adb.connected:
            self.logger.error("ADB未连接，无法滑动")
            messagebox.showwarning("警告", "请先连接ADB")
            return

        # 获取起始坐标
        start_text = self.swipe_start_var.get().strip()
        if not start_text:
            self.logger.error("请输入起始坐标")
            messagebox.showwarning("警告", "请输入起始坐标，格式: x,y")
            return

        # 获取终点坐标
        end_text = self.swipe_end_var.get().strip()
        if not end_text:
            self.logger.error("请输入终点坐标")
            messagebox.showwarning("警告", "请输入终点坐标，格式: x,y")
            return

        # 获取持续时间
        duration_text = self.swipe_duration_var.get().strip()
        if not duration_text:
            duration = 300
        else:
            try:
                duration = int(duration_text)
            except ValueError:
                self.logger.error("持续时间格式错误，请输入数字")
                messagebox.showwarning("警告", "持续时间格式错误，请输入数字")
                return

        try:
            # 解析起始坐标
            start_text = start_text.replace(' ', '')
            if ',' in start_text:
                start_parts = start_text.split(',')
            else:
                start_parts = start_text.split()

            if len(start_parts) != 2:
                raise ValueError("起始坐标格式错误")

            x1 = int(start_parts[0])
            y1 = int(start_parts[1])

            # 解析终点坐标
            end_text = end_text.replace(' ', '')
            if ',' in end_text:
                end_parts = end_text.split(',')
            else:
                end_parts = end_text.split()

            if len(end_parts) != 2:
                raise ValueError("终点坐标格式错误")

            x2 = int(end_parts[0])
            y2 = int(end_parts[1])

            self.logger.info(f"Debug滑动: 起始({x1}, {y1}) -> 终点({x2}, {y2}), 持续时间: {duration}ms")

            if self.adb.swipe(x1, y1, x2, y2, duration):
                self.logger.info(f"滑动成功")
                # 滑动完成后点击固定坐标
                self.adb.click(1919, 1079)
                self.logger.info("点击坐标: (1919, 1079)")
            else:
                self.logger.error(f"滑动失败")

        except ValueError as e:
            self.logger.error(f"坐标解析失败: {e}")
            messagebox.showwarning("格式错误", "坐标格式错误，请使用格式: x,y\n例如: 500,500")

    # ==================== 主程序入口 ====================

    def run(self):
        """启动主程序"""
        self.root.mainloop()

# ==================== 跑商功能 ====================
class TradeRoute:
    """跑商流程控制类"""

    def __init__(self, adb_controller, image_recognition, config_manager, logger):
        """
        初始化跑商控制器
        :param adb_controller: ADB控制器实例
        :param image_recognition: 图像识别实例
        :param config_manager: 配置管理器实例
        :param logger: 日志记录器实例
        """
        self.adb = adb_controller
        self.image_rec = image_recognition
        self.config = config_manager
        self.logger = logger

        # 状态标志
        self.running = False
        self.paused = False
        self.stop_flag = False
        self.test_mode = False  # 新增：测试模式标志
        self.city_a = ""
        self.city_b = ""
        self.litter_running = False  # 捡垃圾线程控制标志

        # 新增 Event 用于高效等待
        self._stop_event = threading.Event()  # 停止事件（set=停止）
        self._pause_event = threading.Event()  # 暂停事件（set=暂停，clear=运行）

        # 初始状态：运行中，未停止，未暂停
        self._stop_event.clear()
        self._pause_event.clear()

        # 跑商线程
        self.trade_thread = None
        # 坐标定义
        self.ACCESS_CITY_AREA = (1584, 683, 1907, 780)  # 访问城市按钮区域
        self.CITY_RECOGNITION_AREA = (7, 772, 814, 969)  # 城市名称识别区域
        self.USE_ITEM_AREA = (1533, 133, 1866, 191)  # 使用道具按钮区域
        self.USE_BUTTON_AREA = (1326, 235, 1418, 278)  # 使用按钮区域
        self.CONFIRM_AREA = (1303, 754, 1541, 841)  # 确认按钮区域
        self.BUY_ALL_AREA = (1643, 660, 1858, 731)  # 全部买入/砍价按钮区域
        self.BARGAIN_TARGET_AREA = (1464, 670, 1633, 731)  # 20.0% 目标区域
        self.BUY_BUTTON_AREA = (1487, 916, 1692, 1016)  # 买入按钮区域
        self.SETTLEMENT_AREA = (512, 739, 798, 821)  # 结算报告区域
        self.BUY_BUTTON_AREA_NEW = (1116, 455, 1295, 519)  # 我要买按钮区域
        self.SELL_BUTTON_AREA = (1116, 568, 1295, 644)  # 我要卖按钮区域
        self.BUY_CONFIRM_AREA = (1159, 455, 1297, 506)  # 卖出后检测我要买的区域

    def set_target_city(self, city_a, city_b):
        """设置目标城市"""
        self.city_a = city_a
        self.city_b = city_b
        self.logger.info(f"跑商目标: {self.city_a} <-> {self.city_b}")

    def start(self):
        """开始跑商流程"""
        # 检查是否已在运行
        if self.running:
            self.logger.warning("跑商已在运行中")
            return False

        # 重置所有状态
        self.running = True
        self.paused = False
        self.stop_flag = False
        self.test_mode = False

        # 重置 Event
        self._stop_event.clear()
        self._pause_event.clear()

        self.logger.info("开始跑商流程")

        self.trade_thread = threading.Thread(target=self._run_trade_loop, daemon=True)
        self.trade_thread.start()
        return True
    def stop(self):
        """停止跑商（包括测试模式）"""
        self.logger.info("停止跑商流程")
        self.stop_flag = True
        self.running = False
        self.paused = False
        self.test_mode = False
        self._stop_event.set()  # 设置停止事件
        self._pause_event.set()  # 唤醒可能正在等待的线程

    def pause(self):
        """暂停跑商（包括测试模式）"""
        if not self.running and not self.test_mode:
            return
        if self.paused:
            return
        self.logger.info("暂停跑商流程")
        self.paused = True
        self._pause_event.set()  # 设置暂停信号

    def resume(self):
        """恢复跑商（包括测试模式）"""
        if not self.running and not self.test_mode:
            return
        if not self.paused:
            return
        self.logger.info("恢复跑商流程")
        self.paused = False
        self._pause_event.clear()  # 清除暂停信号，唤醒等待的线程

    def _check_stop(self):
        """检查是否停止"""
        return self.stop_flag or self._stop_event.is_set()

    def _wait_if_paused(self):
        """
        如果处于暂停状态则等待，返回 True 表示应该停止
        使用 Event.wait() 阻塞，不消耗 CPU
        """
        if self.paused:
            self.logger.debug("进入暂停等待...")
            # 等待直到：暂停被清除（resume）或收到停止信号（stop）
            while self.paused and not self.stop_flag and not self._stop_event.is_set():
                self._pause_event.wait(0.5)  # 每0.5秒检查一次，以便响应停止
            self.logger.debug("退出暂停等待...")
        return self.stop_flag or self._stop_event.is_set()

    def is_running(self):
        """检查是否正在运行（包括测试模式）"""
        return self.running or self.test_mode

    def is_paused(self):
        """检查是否暂停"""
        return self._pause_event.is_set() and not self._stop_event.is_set()

    def _finish(self):
        self.running = False
        self.paused = False
        self.stop_flag = False
        self.logger.info("跑商流程结束")

    # ==================== 主循环 ====================
    def _run_trade_loop(self):
        try:
            # 初始进入主界面
            if self._wait_if_paused():
                self._finish()
                return
            if not self._check_and_enter_main_ui():
                self._finish()
                return

            if self._wait_if_paused():
                self._finish()
                return
            if not self._wait_for_departure():
                self._finish()
                return

            # 获取当前实际所在城市
            current_city = self._get_current_city_from_ui()
            if not current_city:
                self.logger.error("无法识别当前城市，跑商终止")
                self._finish()
                return
            self.logger.info(f"初始城市: {current_city}")

            # 确定另一个城市
            other_city = self.city_b if current_city == self.city_a else self.city_a
            self.logger.info(f"跑商路线: {current_city} -> {other_city} -> {current_city}")

            run_time = int(self.config.get('Auto', 'default_run_time', '9999999'))
            start_time = time.time()
            cycle = 0

            # 第一次在当前城市完整买入
            self.logger.info(f"========== 初始完整买入 - 在 {current_city} ==========")
            if not self._execute_city_trade(current_city, is_buy=True):
                self._finish()
                return

            while self.running and (time.time() - start_time) < run_time:
                # 检查停止和暂停
                if self.stop_flag:
                    break
                if self._wait_if_paused():
                    break

                # 1. 前往另一城市
                self.logger.info(f"========== 从 {current_city} 前往 {other_city} ==========")
                if not self._travel_to_city(other_city):
                    break

                # 检查停止和暂停
                if self.stop_flag:
                    break
                if self._wait_if_paused():
                    break

                # 2. 在另一城市卖出
                self.logger.info(f"========== 在 {other_city} 卖出 ==========")
                ready_to_buy = self._execute_city_trade(other_city, is_buy=False)

                # 检查停止和暂停
                if self.stop_flag:
                    break
                if self._wait_if_paused():
                    break

                # 3. 卖出后简化买入（已处于交易所界面）
                if ready_to_buy:
                    self.logger.info(f"========== 在 {other_city} 简化买入 ==========")
                    self._execute_full_buy_operation(other_city)
                else:
                    self.logger.info(f"========== 在 {other_city} 完整买入 ==========")
                    self._execute_city_trade(other_city, is_buy=True)

                # 检查停止和暂停
                if self.stop_flag:
                    break
                if self._wait_if_paused():
                    break

                # 4. 返回原城市
                self.logger.info(f"========== 从 {other_city} 返回 {current_city} ==========")
                if not self._travel_to_city(current_city):
                    break

                # 检查停止和暂停
                if self.stop_flag:
                    break
                if self._wait_if_paused():
                    break

                # 5. 在原城市卖出
                self.logger.info(f"========== 在 {current_city} 卖出 ==========")
                ready_to_buy = self._execute_city_trade(current_city, is_buy=False)

                # 检查停止和暂停
                if self.stop_flag:
                    break
                if self._wait_if_paused():
                    break

                # 6. 简化买入
                if ready_to_buy:
                    self.logger.info(f"========== 在 {current_city} 简化买入 ==========")
                    self._execute_full_buy_operation(current_city)
                else:
                    self.logger.info(f"========== 在 {current_city} 完整买入 ==========")
                    self._execute_city_trade(current_city, is_buy=True)

                cycle += 1
                self.logger.info(f"完成第 {cycle} 次往返跑商")

            self._finish()
        except Exception:
            self.logger.error_red(f"[Warning]跑商异常:\n{traceback.format_exc()}")
            self._finish()
    # ==================== 基础操作 ====================
    def _check_and_enter_main_ui(self):
        """
        检查并进入主界面
        流程：循环检测主界面.png -> 找到则点击进入
             如果未找到主界面.png，尝试寻找启程.png
             如果找到启程.png，则认为已在主界面
             如果都未找到，继续循环
        """
        self.logger.info("检查主界面...")

        max_attempts = 30
        for attempt in range(max_attempts):
            if self._check_stop():
                return False
            while self.paused and self.running:
                time.sleep(0.5)

            screenshot = self.adb.screenshot()
            if not screenshot:
                time.sleep(1)
                continue

            # 优先寻找主界面.png
            result = self.image_rec.find_image(screenshot, "ui/主界面.png",  )
            if result:
                x, y, match = result
                self.logger.info(f"找到主界面, 匹配度: {match:.2f}")
                self.adb.click(x, y)
                time.sleep(1)
                return True

            # 未找到主界面.png，尝试寻找启程.png
            result = self.image_rec.find_image(screenshot, "启程.png",  )
            if result:
                self.logger.info("找到启程按钮，认为已在主界面")
                return True

            self.logger.info(f"未找到主界面或启程，第{attempt + 1}次重试")
            time.sleep(1)

        self.logger.warning("未找到主界面或启程按钮")
        return True  # 超时也继续，可能已经在主界面

    def _wait_for_departure(self):
        """等待启程按钮出现（不点击）"""
        self.logger.info("等待启程按钮...")

        max_attempts = 30
        for attempt in range(max_attempts):
            if self._check_stop():
                return False
            while self.paused and self.running:
                time.sleep(0.5)

            screenshot = self.adb.screenshot()
            if screenshot:
                result = self.image_rec.find_image(screenshot, "启程.png",  )
                if result:
                    self.logger.info("检测到启程按钮")
                    return True

            self.logger.info(f"等待启程按钮，第{attempt + 1}次")
            time.sleep(1)

        self.logger.warning("未检测到启程按钮")
        return True  # 超时也继续

    def _click_access_city(self, target_city=None):
        """
        点击访问城市 - 先识别"访问城市"文字，再寻图UI_City_目标城市，最后点击访问城市
        返回实际找到的城市名称
        :param target_city: 目标城市名称
        :return: 实际确认的城市名称，未找到返回None
        """
        self.logger.info("准备点击访问城市...")

        # UI城市图片识别使用的阈值
        UI_CITY_THRESHOLD = 0.7

        # 访问城市文字识别区域
        ACCESS_TEXT_AREA = (1689, 711, 1827, 749)

        # 实际确认的城市
        confirmed_city = None

        # 步骤1：等待并识别"访问城市"文字
        self.logger.info("等待识别'访问城市'文字...")
        max_attempts = 5
        found_access_text = False

        for attempt in range(max_attempts):
            if self._check_stop():
                return None
            while self.paused and self.running:
                time.sleep(0.5)

            screenshot = self.adb.screenshot()
            if not screenshot:
                time.sleep(1)
                continue

            text = self.image_rec.recognize_text(screenshot, ACCESS_TEXT_AREA)
            self.logger.info(f"识别到文字: '{text}'")

            if text and "访问城市" in text:
                self.logger.info("检测到'访问城市'文字")
                found_access_text = True
                break

            self.logger.info(f"未检测到'访问城市'，第{attempt + 1}次重试")
            time.sleep(1)

        if not found_access_text:
            self.logger.warning("未检测到'访问城市'文字，继续执行")

        # 步骤2：寻图UI_City_目标城市
        if target_city:
            self.logger.info(f"寻图UI_City_{target_city}.png...")

            for attempt in range(2):  # 只尝试2次
                if self._check_stop():
                    return None
                while self.paused and self.running:
                    time.sleep(0.5)

                screenshot = self.adb.screenshot()
                if not screenshot:
                    time.sleep(1)
                    continue

                result = self.image_rec.find_image(screenshot, f"UI_City_{target_city}.png",
                                                   threshold=UI_CITY_THRESHOLD)
                if result:
                    x, y, match = result
                    self.logger.info(f"找到UI_City_{target_city}, 位置: ({x}, {y}), 匹配度: {match:.2f}")
                    confirmed_city = target_city
                    self.logger.info(f"确认当前城市: {confirmed_city}")
                    self.adb.click(x, y)
                    self.logger.info(f"点击UI_City_{target_city}")
                    time.sleep(1)
                    break

                self.logger.info(f"未找到UI_City_{target_city}，第{attempt + 1}次重试")
                time.sleep(1)

        # 步骤3：如果找不到目标城市，尝试判断城市A和城市B
        if not confirmed_city:
            self.logger.info("尝试判断城市A和城市B")
            cities_to_check = [self.city_a, self.city_b]
            screenshot = self.adb.screenshot()

            if screenshot:
                for city in cities_to_check:
                    if self._check_stop():
                        return None

                    for attempt in range(2):
                        result = self.image_rec.find_image(screenshot, f"UI_City_{city}.png",
                                                           threshold=UI_CITY_THRESHOLD)
                        if result:
                            x, y, match = result
                            self.logger.info(f"找到UI_City_{city}, 位置: ({x}, {y}), 匹配度: {match:.2f}")
                            confirmed_city = city
                            self.logger.info(f"确认当前城市: {confirmed_city}")
                            self.adb.click(x, y)
                            self.logger.info(f"点击UI_City_{city}")
                            time.sleep(1)
                            break
                        time.sleep(0.5)

                    if confirmed_city:
                        break

        # 步骤4：点击访问城市按钮
        x1, y1, x2, y2 = self.ACCESS_CITY_AREA
        center_x = (x1 + x2) // 2
        center_y = (y1 + y2) // 2
        self.logger.info(f"点击访问城市按钮: ({center_x}, {center_y})")
        self.adb.click(center_x, center_y)
        time.sleep(2)

        return confirmed_city

    def _recognize_current_city(self):
        max_attempts = 10
        for attempt in range(max_attempts):
            if self._check_stop():
                return None
            while self.paused and self.running:
                time.sleep(0.5)
            screenshot = self.adb.screenshot()
            if not screenshot:
                time.sleep(1)
                continue
            text = self.image_rec.recognize_text(screenshot, self.CITY_RECOGNITION_AREA)
            if text:
                cities = [c.strip() for c in self.config.get('City', 'cities', '').split(',')]
                for city in cities:
                    if city in text:
                        return city
                for city in cities:
                    if len(set(city) & set(text)) >= 2:
                        self.logger.info(f"模糊匹配: '{text}' 可能为 '{city}'")
                        return city
            self.logger.info(f"未识别到城市，第{attempt + 1}次重试")
            time.sleep(1)
        return None

    def _click_exchange(self, city_name):
        self.logger.info(f"点击 {city_name} 交易所...")
        max_attempts = 10
        for attempt in range(max_attempts):
            if self._check_stop():
                return False
            while self.paused and self.running:
                time.sleep(0.5)
            screenshot = self.adb.screenshot()
            if not screenshot:
                time.sleep(1)
                continue
            result = self.image_rec.find_image(screenshot, f"SHOP/{city_name}交易所.png",  )
            if result:
                x, y, match = result
                self.logger.info(f"找到交易所, 位置: ({x}, {y})")
                return self.adb.click(x, y)
            self.logger.info(f"未找到交易所，第{attempt + 1}次重试")
            time.sleep(1)
        self.logger.error(f"找不到交易所图片: SHOP/{city_name}交易所.png")
        return False

    def _click_buy_button(self):
        self.logger.info("点击我要买...")
        x1, y1, x2, y2 = self.BUY_BUTTON_AREA_NEW
        center_x = (x1 + x2) // 2
        center_y = (y1 + y2) // 2

        max_attempts = 10
        for attempt in range(max_attempts):
            if self._check_stop():
                return False
            while self.paused and self.running:
                time.sleep(0.5)
            screenshot = self.adb.screenshot()
            if screenshot:
                text = self.image_rec.recognize_text(screenshot, self.BUY_BUTTON_AREA_NEW)
                if text and "我要买" in text:
                    self.logger.info(f"找到'我要买'按钮, 点击坐标: ({center_x}, {center_y})")
                    return self.adb.click(center_x, center_y)
            self.logger.info(f"未找到'我要买'按钮，第{attempt + 1}次重试")
            time.sleep(1)
        self.logger.warning("未找到'我要买'按钮，使用默认坐标")
        return self.adb.click(center_x, center_y)

    def _click_sell_button(self):
        self.logger.info("点击我要卖...")
        x1, y1, x2, y2 = self.SELL_BUTTON_AREA
        center_x = (x1 + x2) // 2
        center_y = (y1 + y2) // 2

        max_attempts = 10
        for attempt in range(max_attempts):
            if self._check_stop():
                return False
            while self.paused and self.running:
                time.sleep(0.5)
            screenshot = self.adb.screenshot()
            if screenshot:
                text = self.image_rec.recognize_text(screenshot, self.SELL_BUTTON_AREA)
                if text and "我要卖" in text:
                    self.logger.info(f"找到'我要卖'按钮, 点击坐标: ({center_x}, {center_y})")
                    return self.adb.click(center_x, center_y)
            self.logger.info(f"未找到'我要卖'按钮，第{attempt + 1}次重试")
            time.sleep(1)
        self.logger.warning("未找到'我要卖'按钮，使用默认坐标")
        return self.adb.click(center_x, center_y)

    def _execute_city_trade(self, city_name, is_buy):
        trade_type = "买入" if is_buy else "卖出"
        self.logger.info(f"在 {city_name} 执行{trade_type}操作")
        if is_buy:
            # 完整买入（包含访问城市、交易所、我要买等）
            actual_city = self._click_access_city(city_name)
            if not actual_city:
                actual_city = city_name
            if not self._click_exchange(actual_city):
                return False
            time.sleep(1)
            if not self._click_buy_button():
                return False
            time.sleep(1)
            self._execute_full_buy_operation(actual_city)
            return True
        else:
            # 卖出流程
            actual_city = self._click_access_city(city_name)
            if not actual_city:
                actual_city = city_name
            if not self._click_exchange(actual_city):
                return False
            time.sleep(1)
            if not self._click_sell_button():
                return False
            time.sleep(1)
            # 返回是否已进入可简化买入状态（即已退出并看到我要买）
            return self._execute_full_sell_operation(actual_city)

    def _travel_to_city(self, target_city):
        self.logger.info(f"导航到目标城市: {target_city}")

        # 返回主界面并点击启程（第一次尝试）
        self._back_to_main_ui()
        time.sleep(1)
        if self._wait_if_paused():
            return False
        if not self._click_qicheng():
            return False

        # 地图选点 - 增加重试机制（最多尝试10次）
        max_retries = 10
        for attempt in range(max_retries):
            if self._wait_if_paused():
                return False
            if self._navigate_to_city(target_city):
                break  # 导航成功，跳出循环
            else:
                self.logger.warning(f"第{attempt + 1}次导航到 {target_city} 失败，返回主界面重试")
                # 返回主界面并重新点击启程
                self._back_to_main_ui()
                time.sleep(1)
                if self._wait_if_paused():
                    return False
                if not self._click_qicheng():
                    return False
        else:
            # 所有尝试都失败
            self.logger.error(f"多次导航到 {target_city} 失败")
            return False

        # 启动旅途（拖车或前往目的地）
        if self._wait_if_paused():
            return False
        trailer_used = self._use_trailer_if_needed()
        if not trailer_used:
            if not self._click_go_destination_button():
                return False
            time.sleep(1)

        # 等待行车检测（添加检查）
        self.logger.info("等待行车检测或周提示出发...")
        for _ in range(20):
            if self.stop_flag:
                return False
            if self._wait_if_paused():
                return False

            screenshot = self.adb.screenshot()
            if not screenshot:
                time.sleep(1)
                continue

            if self.image_rec.find_image(screenshot, "行车检测.png"):
                self.logger.info("检测到行车检测，旅途已开始")
                break

            result = self.image_rec.find_image(screenshot, "周提示出发.png")
            if result:
                self.logger.info("检测到周提示出发，准备点击")
                self.adb.click(1331, 775)
                time.sleep(0.5)
                self.adb.click(result[0], result[1])
                self.logger.info("已点击周提示出发，旅途开始")
                break

            time.sleep(1)
        else:
            self.logger.warning("未检测到行车检测或周提示出发")

        # 户外环节
        if self._wait_if_paused():
            return False
        self._handle_outdoor_phase()

        # 确认到达
        time.sleep(2)
        self._confirm_arrival_by_ui(target_city)
        return True

    def _get_current_city_from_ui(self):
        """
        通过UI_City图片获取当前所在城市
        :return: 城市名称，未找到返回None
        """
        self.logger.info("通过UI图片获取当前城市...")

        UI_CITY_THRESHOLD = 0.7
        cities_to_check = [self.city_a, self.city_b]

        for attempt in range(3):
            if self._check_stop():
                return None
            screenshot = self.adb.screenshot()
            if not screenshot:
                time.sleep(0.5)
                continue
            for city in cities_to_check:
                result = self.image_rec.find_image(screenshot, f"UI_City_{city}.png", threshold=UI_CITY_THRESHOLD)
                if result:
                    self.logger.info(f"找到UI_City_{city}, 匹配度: {result[2]:.2f}")
                    return city
            time.sleep(0.5)
        return None

    def _click_qicheng(self):
        """点击启程按钮"""
        for _ in range(10):
            if self.image_rec.find_and_click(self.adb, "启程.png",  ):
                self.logger.info("点击启程成功")
                return True
            time.sleep(1)
        self.logger.warning("未找到启程按钮")
        return False

    def _click_go_destination_button(self):
        """点击前往目的地按钮"""
        for _ in range(10):
            if self.image_rec.find_and_click(self.adb, "前往目的地.png",  ):
                self.logger.info("点击前往目的地成功")
                return True
            time.sleep(1)
        self.logger.error("未找到前往目的地按钮")
        return False

    def _check_and_handle_full_fatigue(self):
        """检测满疲劳图片，若存在则进入用药流程"""
        screenshot = self.adb.screenshot()
        if not screenshot:
            return
        result = self.image_rec.find_image(screenshot, "满疲劳.png",  )
        if result:
            self.logger.info("检测到满疲劳，进入用药流程")
            self._use_medicine()

    def _use_medicine(self):
        if not self.config.get_bool('Medicine', 'enabled', False):
            self.logger.warning("未开启用药，跑商停止")
            self.stop()
            return

        # 尝试便当路线
        screenshot = self.adb.screenshot()
        if screenshot and self.image_rec.find_image(screenshot, "有便当.png"):  # 移除 threshold
            self.logger.info("找到有便当，开始使用便当")
            if self.image_rec.find_and_click(self.adb, "前往便当柜.png"):  # 同样移除
                time.sleep(0.5)
                if self.image_rec.find_and_click(self.adb, "便当全部使用.png"):
                    time.sleep(0.5)
                    self.image_rec.find_and_click(self.adb, "便当确认.png")
                    time.sleep(0.5)
                    # 两次返回
                    return_count = 0
                    while return_count < 2:
                        found = False
                        for _ in range(10):
                            if self.image_rec.find_and_click(self.adb, "返回.png"):
                                self.logger.info(f"点击返回成功 ({return_count + 1}/2)")
                                found = True
                                break
                            else:
                                self.adb.click(885, 949)
                                time.sleep(0.5)
                        if found:
                            return_count += 1
                            time.sleep(2)
                        else:
                            self.logger.warning("未找到返回按钮，停止用药返回")
                            break
            return

        # 尝试提神棒棒糖
        screenshot = self.adb.screenshot()
        if screenshot and self.image_rec.find_image(screenshot, "提神棒棒糖.png"):  # 移除 threshold
            self.logger.info("找到提神棒棒糖")
            if self.image_rec.find_and_click(self.adb, "提神棒棒糖.png"):
                time.sleep(1)
                if self.image_rec.find_and_click(self.adb, "药补充.png"):
                    self.logger.info("药补充成功")
                    return

        # 尝试提神口香糖
        screenshot = self.adb.screenshot()
        if screenshot and self.image_rec.find_image(screenshot, "提神口香糖.png"):  # 移除 threshold
            self.logger.info("找到提神口香糖")
            if self.image_rec.find_and_click(self.adb, "提神口香糖.png"):
                time.sleep(1)
                if self.image_rec.find_and_click(self.adb, "药补充.png"):
                    self.logger.info("药补充成功")
                    return

        self.logger.warning("用药失败，跑商停止")
        self.stop()

    # ==================== 买入流程 ====================
    def _use_purchase_book(self, city_name):
        """
        使用进货书
        流程：点击使用道具 -> 识别进货采买书.png -> 点击右侧使用按钮1次（选中）
              -> 识别+1书.png -> 点击+1书位置 n-1 次 -> 点击确认
        """
        self.logger.info(f"在 {city_name} 使用进货书...")
        book_count = int(self.config.get_city_config(city_name, 'purchase_book_count', '0'))
        self.logger.info(f"进货书数量: {book_count}")
        if book_count <= 0:
            return True

        # 步骤1：点击使用道具
        x1, y1, x2, y2 = self.USE_ITEM_AREA
        self.adb.click((x1 + x2) // 2, (y1 + y2) // 2)
        self.logger.info("已点击使用道具按钮")
        time.sleep(1)

        # 步骤2：寻找进货采买书.png
        max_attempts = 10
        book_position = None

        for attempt in range(max_attempts):
            if self._check_stop():
                return False
            while self.paused and self.running:
                time.sleep(0.5)

            screenshot = self.adb.screenshot()
            if not screenshot:
                time.sleep(1)
                continue

            result = self.image_rec.find_image(screenshot, "进货采买书.png",  )
            if result:
                book_position = (result[0], result[1])
                self.logger.info(
                    f"找到进货采买书, 位置: ({book_position[0]}, {book_position[1]}), 匹配度: {result[2]:.2f}")
                break

            self.logger.info(f"未找到进货采买书.png，第{attempt + 1}次重试")
            time.sleep(1)

        if book_position is None:
            self.logger.warning("未找到进货采买书.png，跳过使用进货书")
            return False

        # 步骤3：点击进货采买书右侧的使用按钮（1次，用于选中）
        use_x = book_position[0] + 80  # 右侧偏移80像素
        use_y = book_position[1]
        self.logger.info(f"点击使用按钮(选中), 坐标: ({use_x}, {use_y})")
        self.adb.click(use_x, use_y)
        time.sleep(0.5)

        # 步骤4：寻找+1书.png
        max_attempts = 10
        plus_one_position = None

        for attempt in range(max_attempts):
            if self._check_stop():
                return False
            while self.paused and self.running:
                time.sleep(0.5)

            screenshot = self.adb.screenshot()
            if not screenshot:
                time.sleep(1)
                continue

            result = self.image_rec.find_image(screenshot, "+1书.png",  )
            if result:
                plus_one_position = (result[0], result[1])
                self.logger.info(
                    f"找到+1书, 位置: ({plus_one_position[0]}, {plus_one_position[1]}), 匹配度: {result[2]:.2f}")
                break

            self.logger.info(f"未找到+1书.png，第{attempt + 1}次重试")
            time.sleep(1)

        if plus_one_position is None:
            self.logger.warning("未找到+1书.png，跳过后续使用")
            return False

        # 步骤5：点击+1书位置 n-1 次
        use_times = max(0, book_count - 1)
        for i in range(use_times):
            if self._check_stop():
                break
            while self.paused and self.running:
                time.sleep(0.5)

            self.logger.info(f"使用第 {i + 1}/{use_times} 次进货书")
            self.adb.click(plus_one_position[0], plus_one_position[1])
            time.sleep(0.5)

        # 步骤6：点击确认按钮
        cx1, cy1, cx2, cy2 = self.CONFIRM_AREA
        confirm_x = (cx1 + cx2) // 2
        confirm_y = (cy1 + cy2) // 2
        self.logger.info(f"点击确认按钮, 坐标: ({confirm_x}, {confirm_y})")
        self.adb.click(confirm_x, confirm_y)
        time.sleep(1)

        return True

    def _click_buy_all(self):
        self.logger.info("点击全部买入...")
        max_attempts = 10
        for attempt in range(max_attempts):
            if self._check_stop():
                return False
            while self.paused and self.running:
                time.sleep(0.5)
            result = self.image_rec.find_and_click(self.adb, "全部买入.png",  )
            if result:
                self.logger.info("点击全部买入成功")
                return True
            self.logger.info(f"未找到全部买入按钮，第{attempt + 1}次重试")
            time.sleep(1)
        # 使用固定坐标
        x1, y1, x2, y2 = self.BUY_ALL_AREA
        self.logger.info("使用固定坐标点击全部买入")
        return self.adb.click((x1 + x2) // 2, (y1 + y2) // 2)

    def _execute_bargain_flow(self):
        self.logger.info("开始砍价流程...")
        max_attempts = 20
        for attempt in range(max_attempts):
            # 添加检查
            if self.stop_flag:
                break
            if self._wait_if_paused():
                break
            # 检查是否已达到20.0%
            screenshot = self.adb.screenshot()
            if screenshot:
                text = self.image_rec.recognize_text(screenshot, self.BARGAIN_TARGET_AREA)
                if text and "20.0%" in text:
                    self.logger.info("已达到20.0%砍价目标")
                    break

            # 点击砍价按钮
            x1, y1, x2, y2 = self.BUY_ALL_AREA
            self.adb.click((x1 + x2) // 2, (y1 + y2) // 2)
            self.logger.info(f"点击砍价按钮, 第{attempt + 1}次")
            time.sleep(0.5)

            # 插入满疲劳检测
            self._check_and_handle_full_fatigue()

            # 插入无法议价检测（霉比）
            if self._check_and_handle_unable_to_bargain():
                self.logger.info("检测到无法议价，停止砍价流程")
                break

        self.logger.info("砍价流程结束")

    def _click_buy_until_empty(self):
        """点击买入按钮1次"""
        self.logger.info("开始买入流程...")
        x1, y1, x2, y2 = self.BUY_BUTTON_AREA
        self.adb.click((x1 + x2) // 2, (y1 + y2) // 2)
        self.logger.info(f"点击买入按钮, 共1次")
        self.logger.info("买入流程结束")

    def _execute_full_buy_operation(self, city_name):
        """
        执行完整的买入操作流程
        包括：使用进货书 -> 全部买入 -> 砍价(可选) -> 买入 -> 退出交易界面
        """
        self.logger.info(f"在 {city_name} 执行完整买入操作")
        enable_bargain = self.config.get_city_config(city_name, 'enable_bargain', 'True').lower() == 'true'
        self.logger.info(f"砍价: {enable_bargain}")

        # 步骤1：使用进货书
        self._use_purchase_book(city_name)
        time.sleep(0.5)

        # 步骤2：点击全部买入
        self._click_buy_all()
        time.sleep(0.5)

        # 步骤3：根据配置决定是否执行砍价
        if enable_bargain:
            self._execute_bargain_flow()
        else:
            self.logger.info("跳过砍价流程")

        # 步骤4：点击买入直到没有买入
        self._click_buy_until_empty()

        # 步骤5：买入结束后处理退出（点击空白区域）
        self._handle_buy_exit()

    # ==================== 卖出流程 ====================
    def _click_sell_all(self):
        self.logger.info("点击全部卖出...")
        max_attempts = 10
        for attempt in range(max_attempts):
            if self._check_stop():
                return False
            while self.paused and self.running:
                time.sleep(0.5)
            result = self.image_rec.find_and_click(self.adb, "全部卖出.png",  )
            if result:
                self.logger.info("点击全部卖出成功")
                return True
            self.logger.info(f"未找到全部卖出按钮，第{attempt + 1}次重试")
            time.sleep(1)
        # 使用固定坐标
        x1, y1, x2, y2 = self.BUY_ALL_AREA
        self.logger.info("使用固定坐标点击全部卖出")
        return self.adb.click((x1 + x2) // 2, (y1 + y2) // 2)

    def _execute_price_increase_flow(self):
        self.logger.info("开始抬价流程...")
        max_attempts = 20
        for attempt in range(max_attempts):
            # 添加检查
            if self.stop_flag:
                break
            if self._wait_if_paused():
                break
            # 检查是否已达到20.0%
            screenshot = self.adb.screenshot()
            if screenshot:
                text = self.image_rec.recognize_text(screenshot, self.BARGAIN_TARGET_AREA)
                if text and "20.0%" in text:
                    self.logger.info("已达到20.0%抬价目标")
                    break

            # 点击抬价按钮
            x1, y1, x2, y2 = self.BUY_ALL_AREA
            self.adb.click((x1 + x2) // 2, (y1 + y2) // 2)
            self.logger.info(f"点击抬价按钮, 第{attempt + 1}次")
            time.sleep(0.5)

            # 插入满疲劳检测
            self._check_and_handle_full_fatigue()

            # 插入无法议价检测（霉比）
            if self._check_and_handle_unable_to_bargain():
                self.logger.info("检测到无法议价，停止抬价流程")
                break

        self.logger.info("抬价流程结束")

    def _check_and_handle_unable_to_bargain(self):
        """
        检测无法议价图片（霉比.png），如果找到则点击交易所取消并返回True
        只进行一次检测，不循环查找
        :return: True=检测到无法议价，False=未检测到
        """
        screenshot = self.adb.screenshot()
        if not screenshot:
            return False

        result = self.image_rec.find_image(screenshot, "霉比.png", )
        if result:
            self.logger.info("检测到无法议价（霉比），点击交易所取消")
            # 寻图点击交易所取消
            if self.image_rec.find_and_click(self.adb, "交易所取消.png", ):
                self.logger.info("点击交易所取消成功")
            else:
                # 备用坐标点击
                self.logger.warning("未找到交易所取消按钮，使用备用坐标")
                self.adb.click(800, 600)
            time.sleep(0.5)
            return True

        return False

    def _click_sell_until_empty(self):
        """点击卖出按钮1次"""
        self.logger.info("开始卖出流程...")
        x1, y1, x2, y2 = self.BUY_BUTTON_AREA
        self.adb.click((x1 + x2) // 2, (y1 + y2) // 2)
        self.logger.info(f"点击卖出按钮, 共1次")
        self.logger.info("卖出流程结束")

    def _execute_full_sell_operation(self, city_name):
        self.logger.info(f"在 {city_name} 执行完整卖出操作")
        enable_price_increase = self.config.get_city_config(city_name, 'enable_price_increase',
                                                            'False').lower() == 'true'
        self.logger.info(f"抬价: {enable_price_increase}")

        # 点击全部卖出
        if not self._click_sell_all():
            self.logger.warning("点击全部卖出失败")
            return False
        time.sleep(0.5)

        if enable_price_increase:
            self._execute_price_increase_flow()
        else:
            self.logger.info("跳过抬价流程")

        # 固定次数卖出（例如3次）
        self._click_sell_until_empty()

        # 退出界面并返回状态
        return self._exit_trade_interface()

    def _handle_sell_exit_and_enter_buy(self, city_name):
        """
        卖出结束后处理退出并进入买入流程
        检测区域(832,982)->(1085,1059)是否有'触碰空白区域退出'文字
        有则点击退出，然后检测'我要买'并点击进入买入流程
        否则直接检测'我要买'并点击进入买入流程
        """
        self.logger.info("卖出结束，准备进入买入流程...")

        # 空白区域坐标
        BLANK_AREA = (832, 982, 1085, 1059)
        blank_center_x = (BLANK_AREA[0] + BLANK_AREA[2]) // 2
        blank_center_y = (BLANK_AREA[1] + BLANK_AREA[3]) // 2

        # 我要买按钮区域
        BUY_BUTTON_AREA = (1159, 455, 1297, 506)
        buy_center_x = (BUY_BUTTON_AREA[0] + BUY_BUTTON_AREA[2]) // 2
        buy_center_y = (BUY_BUTTON_AREA[1] + BUY_BUTTON_AREA[3]) // 2

        max_attempts = 5
        for attempt in range(max_attempts):
            if self._check_stop():
                return
            while self.paused and self.running:
                time.sleep(0.5)

            screenshot = self.adb.screenshot()
            if not screenshot:
                time.sleep(0.5)
                continue

            # 检查空白区域是否有'触碰空白区域退出'文字
            text = self.image_rec.recognize_text(screenshot, BLANK_AREA)
            self.logger.info(f"空白区域识别到文字: '{text}'")

            if text and "触碰空白区域退出" in text:
                self.logger.info(f"检测到'触碰空白区域退出'文字，点击坐标: ({blank_center_x}, {blank_center_y})")
                self.adb.click(blank_center_x, blank_center_y)
                time.sleep(0.5)
                # 点击后继续检测我要买按钮
                continue

            # 检查是否检测到'我要买'按钮
            buy_text = self.image_rec.recognize_text(screenshot, BUY_BUTTON_AREA)
            self.logger.info(f"我要买区域识别到文字: '{buy_text}'")

            if buy_text and "我要买" in buy_text:
                self.logger.info(f"检测到'我要买'按钮，点击进入买入流程，坐标: ({buy_center_x}, {buy_center_y})")
                self.adb.click(buy_center_x, buy_center_y)
                time.sleep(1)

                # 进入买入流程
                self.logger.info(f"在 {city_name} 继续执行买入操作")
                self._execute_full_buy_operation(city_name)
                return

            self.logger.info(f"未检测到退出文字或我要买，第{attempt + 1}次重试")
            time.sleep(0.5)

        self.logger.warning("未检测到退出文字或我要买，跳过买入流程")

    def _handle_buy_exit(self):
        """
        买入结束后处理退出
        检测区域(832,982)->(1085,1059)是否有'触碰空白区域退出'文字
        有则点击退出
        如果没有，则检测'商店买入'，检测到后点击，然后继续检测触碰空白区域退出
        """
        self.logger.info("买入结束，处理退出...")
        time.sleep(2)
        # 空白区域坐标
        BLANK_AREA = (832, 982, 1085, 1059)
        blank_center_x = (BLANK_AREA[0] + BLANK_AREA[2]) // 2
        blank_center_y = (BLANK_AREA[1] + BLANK_AREA[3]) // 2

        max_attempts = 50
        for attempt in range(max_attempts):
            if self._check_stop():
                return
            while self.paused and self.running:
                time.sleep(0.5)

            screenshot = self.adb.screenshot()
            if not screenshot:
                time.sleep(0.5)
                continue

            # 1. 检查空白区域是否有'触碰空白区域退出'文字
            text = self.image_rec.recognize_text(screenshot, BLANK_AREA)
            self.logger.info(f"空白区域识别到文字: '{text}'")

            if text and "触碰空白区域退出" in text:
                self.logger.info(f"检测到'触碰空白区域退出'文字，点击坐标: ({blank_center_x}, {blank_center_y})")
                self.adb.click(blank_center_x, blank_center_y)
                time.sleep(0.5)
                return

            # 2. 没有找到退出文字，尝试检测'商店买入'
            shop_buy_result = self.image_rec.find_image(screenshot, "商店买入.png")
            if shop_buy_result:
                self.logger.info("检测到商店买入，点击确认")
                self.adb.click(shop_buy_result[0], shop_buy_result[1])
                time.sleep(0.5)
                # 点击后继续循环，检测触碰空白区域退出
                self.logger.info("等待触碰空白区域退出...")
                continue

            self.logger.info(f"未检测到退出文字或商店买入，第{attempt + 1}次重试")
            time.sleep(0.5)

        self.logger.warning("未检测到退出文字或商店买入，继续执行")

    def _exit_trade_interface(self):
        """退出交易界面（卖出后调用）- 检测空白区域文字后点击退出"""
        self.logger.info("退出交易界面...")
        time.sleep(2)
        BLANK_AREA = (832, 982, 1085, 1059)
        blank_center = ((BLANK_AREA[0] + BLANK_AREA[2]) // 2,
                        (BLANK_AREA[1] + BLANK_AREA[3]) // 2)

        max_attempts = 50
        for attempt in range(max_attempts):
            if self._check_stop():
                return False
            while self.paused and self.running:
                time.sleep(0.5)

            screenshot = self.adb.screenshot()
            if not screenshot:
                time.sleep(0.5)
                continue

            # 1. 检查空白区域是否有'触碰空白区域退出'文字
            text = self.image_rec.recognize_text(screenshot, BLANK_AREA)
            self.logger.info(f"空白区域识别到文字: '{text}'")

            if text and "触碰空白区域退出" in text:
                self.logger.info(f"检测到'触碰空白区域退出'文字，点击坐标: ({blank_center[0]}, {blank_center[1]})")
                self.adb.click(blank_center[0], blank_center[1])
                time.sleep(0.5)
                break

            # 2. 没有找到退出文字，尝试检测'商店卖出'
            shop_sell_result = self.image_rec.find_image(screenshot, "商店卖出.png")
            if shop_sell_result:
                self.logger.info("检测到商店卖出，点击确认")
                self.adb.click(shop_sell_result[0], shop_sell_result[1])
                time.sleep(0.5)
                # 点击后继续循环，检测触碰空白区域退出
                self.logger.info("等待触碰空白区域退出...")
                continue

            self.logger.info(f"未检测到退出文字或商店卖出，第{attempt + 1}次重试")
            time.sleep(0.5)

        # 检测“我要买”按钮（为下一轮买入做准备）
        screenshot = self.adb.screenshot()
        if screenshot:
            buy_text = self.image_rec.recognize_text(screenshot, self.BUY_CONFIRM_AREA)
            if buy_text and "我要买" in buy_text:
                buy_center = ((self.BUY_CONFIRM_AREA[0] + self.BUY_CONFIRM_AREA[2]) // 2,
                              (self.BUY_CONFIRM_AREA[1] + self.BUY_CONFIRM_AREA[3]) // 2)
                self.logger.info(f"文字识别到我要买，点击坐标: {buy_center}")
                self.adb.click(buy_center[0], buy_center[1])
                time.sleep(1)
                return True

        self.logger.warning("未检测到我要买按钮")
        return False
    # ==================== 公共操作 ====================
    def _handle_settlement(self):
        """
        处理结算报告或退出交易界面
        检测区域(832,982)->(1085,1059)是否有'触碰空白区域退出'文字
        有则点击该区域退出
        否则检测(1187,458)->(1287,511)是否有'我要买'按钮，有则认为已退出
        """
        self.logger.info("处理交易界面退出...")

        # 空白区域坐标
        BLANK_AREA = (832, 982, 1085, 1059)
        blank_center_x = (BLANK_AREA[0] + BLANK_AREA[2]) // 2
        blank_center_y = (BLANK_AREA[1] + BLANK_AREA[3]) // 2

        # 我要买按钮区域
        BUY_BUTTON_AREA = (1187, 458, 1287, 511)

        max_attempts = 5
        for attempt in range(max_attempts):
            if self._check_stop():
                return
            while self.paused and self.running:
                time.sleep(0.5)

            screenshot = self.adb.screenshot()
            if not screenshot:
                time.sleep(0.5)
                continue

            # 检查区域是否有'触碰空白区域退出'文字
            text = self.image_rec.recognize_text(screenshot, BLANK_AREA)
            self.logger.info(f"空白区域识别到文字: '{text}'")

            if text and "触碰空白区域退出" in text:
                self.logger.info(f"检测到'触碰空白区域退出'文字，点击坐标: ({blank_center_x}, {blank_center_y})")
                self.adb.click(blank_center_x, blank_center_y)
                time.sleep(0.5)
                return

            # 检查是否已经回到交易所界面（检测"我要买"按钮）
            buy_text = self.image_rec.recognize_text(screenshot, BUY_BUTTON_AREA)
            if buy_text and "我要买" in buy_text:
                self.logger.info("检测到'我要买'按钮，认为已退出交易界面")
                return

            self.logger.info(f"未检测到退出文字或我要买，第{attempt + 1}次重试")
            time.sleep(0.5)

        self.logger.warning("未检测到退出文字或我要买，继续执行")

    def _back_to_main_ui(self):
        """返回主界面"""
        self.logger.info("返回主界面...")

        max_attempts = 10
        for attempt in range(max_attempts):
            if self._check_stop():
                return
            while self.paused and self.running:
                time.sleep(0.5)

            screenshot = self.adb.screenshot()
            if screenshot:
                # 先尝试寻找主界面.png
                result = self.image_rec.find_image(screenshot, "ui/主界面.png",  )
                if result:
                    x, y, match = result
                    self.logger.info(f"找到主界面, 点击返回, 位置: ({x}, {y})")
                    self.adb.click(x, y)
                    time.sleep(1)
                    return

                # 尝试寻找启程.png，找到则认为已在主界面
                result = self.image_rec.find_image(screenshot, "启程.png",  )
                if result:
                    self.logger.info("找到启程按钮，认为已在主界面")
                    return

            self.logger.info(f"未找到主界面，第{attempt + 1}次重试")
            time.sleep(1)

        # 使用返回键作为备用
        self.logger.info("使用返回键返回")
        self.adb.back()
        time.sleep(1)

    def _confirm_arrival_by_ui(self, target_city):
        """
        通过UI图片确认已到达目标城市
        :param target_city: 目标城市名称
        :return: 成功返回True，失败返回False
        """
        self.logger.info(f"通过UI图片确认城市: {target_city}")

        max_attempts = 10
        for attempt in range(max_attempts):
            if self._check_stop():
                return False
            while self.paused and self.running:
                time.sleep(0.5)

            screenshot = self.adb.screenshot()
            if not screenshot:
                time.sleep(0.5)
                continue

            # 尝试识别UI_City_目标城市图片
            result = self.image_rec.find_image(screenshot, f"UI_City_{target_city}.png",  )
            if result:
                x, y, match = result
                self.logger.info(f"找到UI_City_{target_city}, 匹配度: {match:.2f}")
                self.logger.info(f"确认已到达城市: {target_city}")
                return True

            self.logger.info(f"未确认到达 {target_city}，第{attempt + 1}次重试")
            time.sleep(1)

        self.logger.warning(f"无法确认到达 {target_city}，继续执行")
        return False

    def _handle_sell_exit(self):
        """
        卖出结束后退出交易界面（点击空白区域或检测到我要买按钮）
        返回 True 表示已退出/已就绪
        """
        self.logger.info("卖出结束，退出交易界面...")

        BLANK_AREA = (832, 982, 1085, 1059)
        blank_center = ((BLANK_AREA[0] + BLANK_AREA[2]) // 2, (BLANK_AREA[1] + BLANK_AREA[3]) // 2)
        BUY_BUTTON_AREA = (1159, 455, 1297, 506)

        for attempt in range(5):
            if self._check_stop():
                return False
            screenshot = self.adb.screenshot()
            if not screenshot:
                time.sleep(0.5)
                continue

            # 检查空白区域
            text = self.image_rec.recognize_text(screenshot, BLANK_AREA)
            if text and "触碰空白区域退出" in text:
                self.logger.info("点击空白区域退出")
                self.adb.click(blank_center[0], blank_center[1])
                time.sleep(0.5)
                return True

            # 检查是否已经出现“我要买”按钮（说明已回到交易所主界面）
            buy_text = self.image_rec.recognize_text(screenshot, BUY_BUTTON_AREA)
            if buy_text and "我要买" in buy_text:
                self.logger.info("已回到交易所主界面，准备买入")
                return True

            time.sleep(0.5)

        self.logger.warning("未能正常退出交易界面，继续执行")
        return False
    # ==================== 地图环节 ====================

    def _slide_from_top_left_to_bottom_right(self):
        """从左上角往右下滑动屏幕，范围 (399,212) -> (1536,847)"""
        self.logger.info("从左上角往右下滑动")
        # 起始(400,220) -> 终点(1500,830)，确保在范围内
        self.adb.swipe(400, 220, 1500, 830, 500)
        # 滑动完成后点击固定坐标
        self.adb.click(1919,1079)
        self.logger.info("点击坐标: (1919, 1079)")
        time.sleep(0.8)  # 等待惯性停止

    def _slide_from_right_to_left(self):
        """从右边往左滑动，范围 (399,212) -> (1536,847)"""
        self.logger.info("从右边往左滑动")
        # 起始(1500,530) -> 终点(420,530)，确保在范围内
        self.adb.swipe(1500, 530, 420, 530, 500)
        # 滑动完成后点击固定坐标
        self.adb.click(1919, 1079)
        self.logger.info("点击坐标: (1919, 1079)")
        time.sleep(0.8)  # 等待惯性停止

    def _slide_from_bottom_right_to_top_left(self):
        """从右下角往左上滑动，范围 (399,212) -> (1536,847)"""
        self.logger.info("从右下角往左上滑动")
        # 起始(1500,830) -> 终点(400,220)，确保在范围内
        self.adb.swipe(1500, 830, 400, 220, 500)
        # 滑动完成后点击固定坐标
        self.adb.click(1919, 1079)
        self.logger.info("点击坐标: (1919, 1079)")
        time.sleep(0.8)  # 等待惯性停止

    def _slide_from_left_to_right(self):
        """从左往右滑动，范围 (399,212) -> (1536,847)"""
        self.logger.info("从左往右滑动")
        # 起始(420,530) -> 终点(1500,530)，确保在范围内
        self.adb.swipe(420, 530, 1500, 530, 500)
        # 滑动完成后点击固定坐标
        self.adb.click(1919, 1079)
        self.logger.info("点击坐标: (1919, 1079)")
        time.sleep(0.8)  # 等待惯性停止

    def _find_and_click_city_on_map(self, city_name):
        """在地图上寻找并点击目标城市 - 使用配置的阈值"""
        self.logger.info(f"在地图上寻找城市: {city_name}")

        # 从配置获取匹配阈值，默认0.7
        threshold = self.config.get_float('Recognition', 'match_threshold', 0.7)

        screenshot = self.adb.screenshot()
        if not screenshot:
            return False

        # 使用新的文件名格式 MAP_城市名.png
        result = self.image_rec.find_image(screenshot, f"map/MAP_{city_name}.png", threshold=threshold)
        if result:
            x, y, match = result
            self.logger.info(f"找到城市 {city_name}, 位置: ({x}, {y}), 匹配度: {match:.2f}")
            self.adb.click(x, y)
            time.sleep(1)
            return True

        self.logger.info(f"未找到城市 {city_name} (匹配度低于{threshold})")
        return False

    def _full_map_search(self, target_city):
        """
        全图搜索流程
        通过滑动覆盖整个地图来寻找目标城市
        """
        self.logger.info(f"开始全图搜索流程，目标城市: {target_city}")

        # ========== 辅助竖直滑动函数 ==========
        def _slide_vertical():
            """竖直滑动 (800,850) -> (800,300)"""
            self.logger.info("竖直滑动: (800,850) -> (800,300)")
            self.adb.swipe(800, 850, 800, 300, 500)
            self.adb.click(1919, 1079)
            self.logger.info("点击坐标: (1919, 1079)")
            time.sleep(0.8)

        # ========== 阶段1：确保在地图左上角 ==========
        self.logger.info("阶段1: 移动到地图左上角")
        for i in range(3):
            if self._check_stop():
                return False
            while self.paused and self.running:
                time.sleep(0.5)

            self._slide_from_top_left_to_bottom_right()
            self.logger.info(f"左上角定位第{i + 1}次")

            # 每次滑动后尝试识别
            if self._find_and_click_city_on_map(target_city):
                return True

        # ========== 阶段2：从右往左滑动搜索（3次）==========
        self.logger.info("阶段2: 从右往左滑动搜索")
        for i in range(3):
            if self._check_stop():
                return False
            while self.paused and self.running:
                time.sleep(0.5)

            self._slide_from_right_to_left()
            if self._find_and_click_city_on_map(target_city):
                return True
            self.logger.info(f"右滑搜索第{i + 1}次完成")

        # 竖直滑动
        _slide_vertical()
        if self._find_and_click_city_on_map(target_city):
            return True

        # ========== 阶段3：从左往右滑动搜索（3次）==========
        self.logger.info("阶段3: 从左往右滑动搜索")
        for i in range(3):
            if self._check_stop():
                return False
            while self.paused and self.running:
                time.sleep(0.5)

            self._slide_from_left_to_right()
            if self._find_and_click_city_on_map(target_city):
                return True
            self.logger.info(f"左滑搜索第{i + 1}次完成")

        # 竖直滑动
        _slide_vertical()
        if self._find_and_click_city_on_map(target_city):
            return True

        # ========== 阶段4：再次从右往左滑动搜索（3次）==========
        self.logger.info("阶段4: 再次从右往左滑动搜索")
        for i in range(3):
            if self._check_stop():
                return False
            while self.paused and self.running:
                time.sleep(0.5)

            self._slide_from_right_to_left()
            if self._find_and_click_city_on_map(target_city):
                return True
            self.logger.info(f"再次右滑搜索第{i + 1}次完成")

        # 最后一次尝试
        if self._find_and_click_city_on_map(target_city):
            return True

        self.logger.error(f"全图搜索完成，未找到目标城市: {target_city}")
        return False

    def _slide_diagonal(self):
        """对角线滑动 (800,800) -> (300,300)"""
        self.logger.info("对角线滑动: (800,800) -> (300,300)")
        self.adb.swipe(800, 800, 300, 300, 500)
        self.adb.click(1919, 1079)
        self.logger.info("点击坐标: (1919, 1079)")
        time.sleep(0.8)

    def _navigate_to_city(self, target_city):
        """
        仅在地图上找到并点击目标城市图标
        返回: True=点击成功，False=失败
        """
        self.logger.info(f"地图选点: {target_city}")
        time.sleep(2)
        # 点击地图比例减
        self.adb.click(1725, 810)
        time.sleep(0.5)

        # 尝试直接点击目标城市图标
        for attempt in range(5):
            if self._find_and_click_city_on_map(target_city):
                return True
            time.sleep(0.5)

        # 全图搜索
        return self._full_map_search(target_city)

    def _use_trailer_if_needed(self):
        enabled = self.config.get_bool('Trailer', 'enabled', False)
        count = self.config.get_int('Trailer', 'count', 0)
        if not enabled or count <= 0:
            return False

        # 点击拖车
        if not self.image_rec.find_and_click(self.adb, "拖车.png"):
            self.logger.warning("未找到拖车按钮")
            return False
        time.sleep(1.6)

        # 点击拖车确认（此操作即启动旅途）
        if not self.image_rec.find_and_click(self.adb, "拖车确认.png"):
            self.logger.warning("未找到拖车确认按钮")
            return False
        self.logger.info("拖车确认已点击，旅途启动")

        # 延迟0.5秒后检测拖车过次
        time.sleep(0.5)

        # 检测拖车过次
        screenshot = self.adb.screenshot()
        if screenshot:
            result = self.image_rec.find_image(screenshot, "拖车过次.png")
            if result:
                self.logger.info("检测到拖车过次，点击拖车过次确认")
                if self.image_rec.find_and_click(self.adb, "拖车过次确认.png"):
                    self.logger.info("点击拖车过次确认成功")
                else:
                    self.logger.warning("未找到拖车过次确认按钮")
                time.sleep(0.5)

        # 数量减1
        new_count = count - 1
        self.config.set('Trailer', 'count', str(new_count))
        if hasattr(self, 'trailer_count_var'):
            self.trailer_count_var.set(str(new_count))

        return True

    def _handle_outdoor_phase(self):
        self.logger.info("进入户外环节...")
        self.litter_running = True

        def litter_click_loop():
            """捡垃圾线程 - 降低优先级以减少前台卡顿"""

            # ========== 降低线程优先级（仅Windows） ==========
            try:
                if platform.system() == "Windows":
                    # 获取当前线程句柄
                    current_thread = ctypes.windll.kernel32.GetCurrentThread()
                    # 设置为低于正常优先级 (1 = THREAD_PRIORITY_BELOW_NORMAL)
                    ctypes.windll.kernel32.SetThreadPriority(current_thread, 1)
            except Exception as e:
                self.logger.debug(f"设置线程优先级失败（不影响功能）: {e}")
            # ========== 线程主循环 ==========
            self.logger.info("捡垃圾线程启动")
            while self.litter_running and not self._check_stop():
                litter_enabled = self.config.get_bool('Litter', 'enabled', False)
                if litter_enabled and not self.paused:
                    litter_x = self.config.get_int('Litter', 'click_x', 1100)
                    litter_y = self.config.get_int('Litter', 'click_y', 600)
                    self.adb.click(litter_x, litter_y, log=False)
                interval = self.config.get_float('Litter', 'click_interval', 0.5)
                time.sleep(interval)

        # 启动捡垃圾线程
        litter_thread = threading.Thread(target=litter_click_loop, daemon=True)
        litter_thread.start()

        try:
            # 等待行车检测（添加检查）
            self.logger.info("等待行车检测...")
            for _ in range(30):
                if self.stop_flag:
                    return False
                if self._wait_if_paused():
                    return False
                screenshot = self.adb.screenshot()
                if screenshot and self.image_rec.find_image(screenshot, "行车检测.png"):
                    self.logger.info("检测到行车检测，进入户外")
                    break
                time.sleep(1)

            # 等待到站检测（添加检查）
            self.logger.info("等待到站检测...")
            for _ in range(600):
                if self.stop_flag:
                    return False
                if self._wait_if_paused():
                    return False
                screenshot = self.adb.screenshot()
                if screenshot:
                    result = self.image_rec.find_image(screenshot, "进入站点.png")
                    if result:
                        self.logger.info(f"检测到进入站点，点击坐标: ({result[0]}, {result[1]})")
                        self.adb.click(result[0], result[1])
                        self.logger.info("户外环节完成，进入卖出环节")
                        return True
                time.sleep(9)

            self.logger.error_red("[Warning]未检测到进入站点，超时")
            return False
        finally:
            self.litter_running = False
            if litter_thread.is_alive():
                litter_thread.join(timeout=1)
            self.logger.info("捡垃圾线程已停止")
# ==================== 程序入口 ====================
if __name__ == "__main__":
    app = JailMasterGUI()
    app.run()
