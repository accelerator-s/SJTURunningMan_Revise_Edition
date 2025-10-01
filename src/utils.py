import math
import time
import datetime

# --- 常量 ---
EARTH_RADIUS_METERS = 6371000  # 地球半径，单位米
# 轨迹点经纬度精度，根据最终请求内容示例调整为7位小数
TRACK_POINT_DECIMAL_PLACES = 7

class SportsUploaderError(Exception):
    """自定义异常类，用于在UI中捕获和显示错误"""
    pass

def log_output(message, level="info", callback=None):
    """统一的日志输出函数，可传递给UI回调"""
    if callback:
        callback(message, level)
    else:
        # 命令行输出时，附带时间戳
        timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        if level == "error":
            print(f"[{timestamp}][ERROR] {message}")
        elif level == "warning":
            print(f"[{timestamp}][WARNING] {message}")
        else:
            print(f"[{timestamp}][INFO] {message}")


def haversine_distance(lat1, lon1, lat2, lon2):
    """
    计算两个经纬度点之间的Haversine距离（单位：米）。
    """
    R = EARTH_RADIUS_METERS
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = math.sin(delta_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

def get_current_epoch_ms():
    """获取当前的Unix Epoch毫秒时间戳"""
    return int(time.time() * 1000)