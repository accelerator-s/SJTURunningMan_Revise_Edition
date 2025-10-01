import json
import os
from PySide6.QtWidgets import QMessageBox
from src.utils import get_current_epoch_ms, get_base_path

CONFIGS_DIR = os.path.join(get_base_path(), "configs")
DEFAULT_CONFIG_FILE_NAME = "default.json"
DEFAULT_CONFIG_FILE = os.path.join(CONFIGS_DIR, DEFAULT_CONFIG_FILE_NAME)


class ConfigManager:
    """管理配置的加载和保存，支持默认值和自定义文件名。"""

    @staticmethod
    def get_default_config():
        """提供硬编码的默认配置。"""
        return {
            "COOKIE": "",
            "USER_ID": "",
            "START_LATITUDE": 31.031599,
            "START_LONGITUDE": 121.442938,
            "END_LATITUDE": 31.026400,
            "END_LONGITUDE": 121.455100,
            "RUNNING_SPEED_MPS": 2.5,
            "INTERVAL_SECONDS": 3,
            "START_TIME_EPOCH_MS": None,
            "HOST": "pe.sjtu.edu.cn",
            "UID_URL": "https://pe.sjtu.edu.cn/sports/my/uid",
            "MY_DATA_URL": "https://pe.sjtu.edu.cn/sports/my/data",
            "POINT_RULE_URL": "https://pe.sjtu.edu.cn/api/running/point-rule",
            "UPLOAD_URL": "https://pe.sjtu.edu.cn/api/running/result/upload"
        }

    @staticmethod
    def load_config(filename=DEFAULT_CONFIG_FILE_NAME):
        """
        从指定文件加载配置。如果文件不存在或加载失败，则返回默认配置。
        """
        if not os.path.exists(CONFIGS_DIR):
            os.makedirs(CONFIGS_DIR)

        config_path = os.path.join(CONFIGS_DIR, filename)

        if os.path.exists(config_path):
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    loaded_config = json.load(f)
                    default_config = ConfigManager.get_default_config()
                    final_config = {**default_config, **loaded_config}
                    return final_config
            except json.JSONDecodeError as e:
                QMessageBox.warning(None, "配置加载错误",
                                    f"'{os.path.basename(config_path)}' 文件格式不正确: {e}\n将使用默认配置。")
            except Exception as e:
                QMessageBox.warning(None, "配置加载错误",
                                    f"无法加载 '{os.path.basename(config_path)}' 文件: {e}\n将使用默认配置。")

        return ConfigManager.get_default_config()

    @staticmethod
    def save_config(config_data, filename):
        """
        将配置保存到指定文件。
        """
        if not os.path.exists(CONFIGS_DIR):
            os.makedirs(CONFIGS_DIR)

        full_path = os.path.join(CONFIGS_DIR, filename)
        try:
            with open(full_path, 'w', encoding='utf-8') as f:
                json.dump(config_data, f, indent=4, ensure_ascii=False)
            return True
        except Exception as e:
            QMessageBox.critical(None, "配置保存错误", f"无法保存文件 '{os.path.basename(filename)}': {e}")
            return False