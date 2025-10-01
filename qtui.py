import sys
import json
import os
import datetime
import time
from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QTextEdit, QProgressBar, QFormLayout, QGroupBox, QDateTimeEdit,
    QMessageBox, QScrollArea, QSizePolicy, QFileDialog, QCheckBox,
    QSpacerItem
)
from PySide6.QtCore import QThread, Signal, QDateTime, Qt, QUrl
from PySide6.QtGui import QTextCursor, QFont, QColor, QTextCharFormat, QPalette, QBrush, QIcon, QDesktopServices

# 导入解耦后的模块
from src.main import run_sports_upload
from src.utils import SportsUploaderError
from src.config_manager import ConfigManager, CONFIGS_DIR, DEFAULT_CONFIG_FILE
from src.help_dialog import HelpDialog

class WorkerThread(QThread):
    """
    工作线程，用于在后台执行跑步数据上传任务，避免UI冻结。
    """
    progress_update = Signal(int, int, str)  # current_value, max_value, message
    log_output = Signal(str, str)  # message, level ("info", "warning", "error", "success")
    finished = Signal(bool, str)  # success, message

    def __init__(self, config_data):
        super().__init__()
        self.config_data = config_data

    def run(self):
        # QThread::isInterruptionRequested() 默认返回 False，直到 requestInterruption() 被调用
        # 这里不需要重置，因为每次 run() 启动时，QThread 的中断状态是独立的

        success = False
        message = "任务已完成。"
        try:
            success, message = run_sports_upload(
                self.config_data,
                progress_callback=self.progress_callback,
                log_cb=self.log_callback,
                stop_check_cb=self.isInterruptionRequested # <-- 传递 QThread 提供的中断检查回调
            )
        except SportsUploaderError as e:
            self.log_output.emit(f"任务中断: {e}", "error")
            message = str(e)
            success = False
        except Exception as e:
            self.log_output.emit(f"发生未预期的错误: {e}", "error")
            message = f"未预期的错误: {e}"
            success = False
        finally:
            # 检查是否是由于中断而退出
            if self.isInterruptionRequested() and not success:
                 self.finished.emit(False, "任务已手动终止。")
            else:
                 self.finished.emit(success, message)

    def progress_callback(self, current, total, message):
        # 即使被请求中断，进度更新也应继续，因为可能在做清理工作
        self.progress_update.emit(current, total, message)

    def log_callback(self, message, level):
        self.log_output.emit(message, level)


class SportsUploaderUI(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("SJTU 体育跑步上传工具")
        self.setWindowIcon(QIcon("assets/SJTURM.png"))

        self.thread = None
        self.config = {}
        self.current_config_filename = DEFAULT_CONFIG_FILE
        self.setup_ui_style()  # 设置UI样式
        self.init_ui()
        self.load_settings_to_ui(self.current_config_filename)

        self.setGeometry(100, 100, 800, 950)  # 设置一个默认的初始窗口大小
        self.setMinimumSize(500, 650)  # 调整最小窗口大小

        # 初始调用 adjust_content_width，确保内容区域宽度正确
        # 最好在窗口显示后或 resizeEvent 首次触发时处理
        # 这里为了确保初始化时就正确，也直接调用一次
        self.adjust_content_width(self.width())

    def setup_ui_style(self):
        """设置UI的整体样式，改为白色背景和Fluent设计。"""
        # 应用浅色主题 (白色背景)
        palette = self.palette()
        palette.setColor(QPalette.Window, QColor(255, 255, 255))  # 纯白色背景
        palette.setColor(QPalette.WindowText, QColor(30, 30, 30))  # 深色文字
        palette.setColor(QPalette.Base, QColor(255, 255, 255))  # 输入框、文本编辑器的背景
        palette.setColor(QPalette.AlternateBase, QColor(240, 240, 240))
        palette.setColor(QPalette.ToolTipBase, QColor(255, 255, 255))
        palette.setColor(QPalette.ToolTipText, QColor(30, 30, 30))
        palette.setColor(QPalette.Text, QColor(30, 30, 30))  # 普通文本颜色
        palette.setColor(QPalette.Button, QColor(225, 225, 225))  # 按钮背景（浅灰）
        palette.setColor(QPalette.ButtonText, QColor(30, 30, 30))  # 按钮文字（深色）
        palette.setColor(QPalette.BrightText, QColor("red"))
        palette.setColor(QPalette.Link, QColor(0, 120, 212))  # Fluent蓝色
        palette.setColor(QPalette.Highlight, QColor(0, 120, 212))  # 选中高亮
        palette.setColor(QPalette.HighlightedText, QColor(255, 255, 255))  # 选中文字（白色）
        self.setPalette(palette)

        # 应用Qt样式表 (QSS)
        self.setStyleSheet("""
            QWidget {
                background-color: rgb(255, 255, 255); /* 纯白色背景 */
                color: rgb(30, 30, 30); /* 深色文字 */
                font-family: "Segoe UI", "Microsoft YaHei", sans-serif;
                font-size: 10pt;
            }
            QGroupBox {
                font-size: 11pt;
                font-weight: bold;
                margin-top: 10px;
                border: 1px solid rgb(220, 220, 220); /* 浅色边框 */
                border-radius: 8px;
                padding-top: 20px;
                padding-bottom: 5px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top center;
                padding: 0 5px;
                color: rgb(0, 120, 212); /* Fluent蓝色标题 */
            }
            QLineEdit, QDateTimeEdit {
                background-color: rgb(255, 255, 255); /* 白色背景 */
                border: 1px solid rgb(220, 220, 220); /* 浅色边框 */
                border-radius: 5px;
                padding: 5px;
                selection-background-color: rgb(0, 120, 212);
                color: rgb(30, 30, 30); /* 深色文字 */
            }
            QDateTimeEdit::drop-down {
                subcontrol-origin: padding;
                subcontrol-position: top right;
                width: 20px;
                border-left-width: 1px;
                border-left-color: rgb(220, 220, 220); /* 浅色分割线 */
                border-left-style: solid;
                border-top-right-radius: 5px;
                border-bottom-right-radius: 5px;
            }
            QPushButton {
                background-color: rgb(0, 120, 212); /* Fluent蓝色按钮 */
                color: white;
                border-radius: 5px;
                padding: 8px 15px;
                font-weight: bold;
                min-height: 28px;
            }
            QPushButton:hover {
                background-color: rgb(0, 96, 173);
            }
            QPushButton:pressed {
                background-color: rgb(0, 77, 140);
            }
            QPushButton:disabled {
                background-color: rgb(204, 204, 204); /* 禁用时浅灰色 */
                color: rgb(106, 106, 106);
            }
            QProgressBar {
                border: 1px solid rgb(220, 220, 220);
                border-radius: 5px;
                text-align: center;
                background-color: rgb(240, 240, 240); /* 进度条背景 */
                color: rgb(30, 30, 30);
            }
            QProgressBar::chunk {
                background-color: rgb(0, 120, 212); /* 进度条填充 */
                border-radius: 5px;
            }
            QTextEdit {
                background-color: rgb(255, 255, 255); /* 白色背景 */
                border: 1px solid rgb(220, 220, 220);
                border-radius: 5px;
                padding: 5px;
                color: rgb(30, 30, 30); /* 深色文字 */
            }
            QScrollArea {
                border: none;
            }
            QCheckBox {
                spacing: 5px;
                color: rgb(30, 30, 30); /* 确保文字可见 */
            }
            QCheckBox::indicator {
                width: 16px;
                height: 16px;
                border-radius: 3px;
                border: 1px solid rgb(142, 142, 142); /* 浅色边框 */
                background-color: rgb(248, 248, 248);
            }
            QCheckBox::indicator:checked {
                background-color: rgb(0, 120, 212); /* 选中时蓝色 */
                border: 1px solid rgb(0, 120, 212);
            }
            QCheckBox::indicator:disabled {
                border: 1px solid rgb(204, 204, 204);
                background-color: rgb(225, 225, 225);
            }
            QFormLayout QLabel {
                padding-top: 5px;
                padding-bottom: 5px;
            }
            /* 调整开始上传按钮的颜色 */
            #startButton { /* 使用ID选择器 */
                background-color: rgb(76, 175, 80); /* 绿色 */
            }
            #startButton:hover {
                background-color: rgb(67, 160, 71);
            }
            #startButton:pressed {
                background-color: rgb(56, 142, 60);
            }
            #stopButton { /* 停止按钮 */
                background-color: rgb(220, 53, 69); /* 红色 */
            }
            #stopButton:hover {
                background-color: rgb(179, 43, 56);
            }
            #stopButton:pressed {
                background-color: rgb(140, 34, 44);
            }
            QLabel#getCookieLink { /* 为链接标签设置样式 */
                color: rgb(0, 120, 212);
                text-decoration: underline;
                padding: 0; /* 移除默认的padding */
            }
            QLabel#getCookieLink:hover {
                color: rgb(0, 96, 173); /* 悬停颜色 */
            }
        """)

    def init_ui(self):
        # 顶层布局，用于居中 center_widget
        top_h_layout = QHBoxLayout()
        top_h_layout.setContentsMargins(0, 0, 0, 0)  # 移除顶层布局的边距
        top_h_layout.setSpacing(0)  # 移除顶层布局的间距

        # main_layout 承载所有可见UI内容，现在嵌套在 center_widget 中
        self.center_widget = QWidget()  # 这是一个中间容器，用于包裹所有可滚动内容
        main_layout = QVBoxLayout(self.center_widget)  # 将QVBoxLayout直接设为center_widget的布局
        main_layout.setContentsMargins(15, 15, 15, 15)  # center_widget的内边距
        main_layout.setSpacing(10)

        # scroll_area 和 scroll_content 保持原样，作为 main_layout 的一个子项
        self.scroll_area = QScrollArea()
        self.scroll_content = QWidget()  # 这个QWidget将承载所有的GroupBox和按钮
        scroll_layout = QVBoxLayout(self.scroll_content)
        scroll_layout.setContentsMargins(10, 10, 10, 10)
        scroll_layout.setSpacing(8)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setWidget(self.scroll_content)

        # 将 scroll_area 添加到 center_widget 的 main_layout 中
        main_layout.addWidget(self.scroll_area)

        # --- 用户信息配置 ---
        user_group = QGroupBox("用户配置")
        user_form_layout = QFormLayout()

        # Cookie 输入项的修改
        cookie_prompt_layout = QHBoxLayout()
        cookie_label = QLabel("Cookie:")
        get_cookie_link = QLabel('<a href="#" id="getCookieLink">获取</a>') # 添加ID用于QSS
        get_cookie_link.setOpenExternalLinks(False) # 禁用自动打开，我们手动处理点击
        get_cookie_link.linkActivated.connect(self.open_cookie_help_url) # 连接到槽函数

        cookie_prompt_layout.addWidget(cookie_label)
        cookie_prompt_layout.addWidget(get_cookie_link)
        cookie_prompt_layout.addStretch(1) # 使得"获取"链接靠近"Cookie:"标签

        cookie_container_widget = QWidget()
        cookie_container_widget.setLayout(cookie_prompt_layout)
        user_form_layout.addRow(cookie_container_widget)

        self.keepalive_input = QLineEdit()
        self.keepalive_input.setPlaceholderText("keepalive='...' (从浏览器复制)")
        self.jsessionid_input = QLineEdit()
        self.jsessionid_input.setPlaceholderText("JSESSIONID='...' (从浏览器复制)")

        user_form_layout.addRow("Keepalive:", self.keepalive_input)
        user_form_layout.addRow("JSESSIONID:", self.jsessionid_input)

        self.user_id_input = QLineEdit()
        self.user_id_input.setPlaceholderText("你的用户ID")
        user_form_layout.addRow("用户ID:", self.user_id_input)
        user_group.setLayout(user_form_layout)
        scroll_layout.addWidget(user_group)

        # --- 跑步路线配置 ---
        route_group = QGroupBox("跑步路线配置")
        route_form_layout = QFormLayout()
        self.start_lat_input = QLineEdit()
        self.start_lon_input = QLineEdit()
        self.end_lat_input = QLineEdit()
        self.end_lon_input = QLineEdit()
        route_form_layout.addRow("起点纬度 (LAT):", self.start_lat_input)
        route_form_layout.addRow("起点经度 (LON):", self.start_lon_input)
        route_form_layout.addRow("终点纬度 (LAT):", self.end_lat_input)
        route_form_layout.addRow("终点经度 (LON):", self.end_lon_input)
        route_group.setLayout(route_form_layout)
        scroll_layout.addWidget(route_group)

        # --- 跑步参数配置 ---
        param_group = QGroupBox("跑步参数配置")
        param_form_layout = QFormLayout()
        self.speed_input = QLineEdit()
        self.speed_input.setPlaceholderText("例如: 2.5 (米/秒, 约9公里/小时)")
        self.interval_input = QLineEdit()
        self.interval_input.setPlaceholderText("例如: 3 (秒)")
        param_form_layout.addRow("跑步速度 (米/秒):<参考：1.9~5.5>", self.speed_input)
        param_form_layout.addRow("轨迹点采样间隔 (秒):", self.interval_input)
        param_group.setLayout(param_form_layout)
        scroll_layout.addWidget(param_group)

        # --- 跑步时间配置 ---
        time_group = QGroupBox("跑步时间配置")
        time_layout = QVBoxLayout()
        self.use_current_time_checkbox = QCheckBox("使用当前时间（注意！你需要等待模拟跑步结束才能上传成功）")
        self.use_current_time_checkbox.setChecked(False)
        self.use_current_time_checkbox.toggled.connect(self.toggle_time_input)

        self.start_datetime_input = QDateTimeEdit()
        self.start_datetime_input.setCalendarPopup(True)
        self.start_datetime_input.setDateTime(QDateTime.currentDateTime())
        self.start_datetime_input.setDisplayFormat("yyyy-MM-dd HH:mm:ss")
        self.start_datetime_input.setEnabled(False)

        time_layout.addWidget(self.use_current_time_checkbox)
        time_layout.addWidget(QLabel("或手动设置开始时间:"))
        time_layout.addWidget(self.start_datetime_input)
        time_group.setLayout(time_layout)
        scroll_layout.addWidget(time_group)

        # --- 配置管理按钮 ---
        config_button_layout = QHBoxLayout()
        self.load_default_button = QPushButton("加载默认配置")
        self.load_default_button.clicked.connect(lambda: self.load_settings_to_ui(DEFAULT_CONFIG_FILE))
        self.save_as_button = QPushButton("保存配置为...")
        self.save_as_button.clicked.connect(self.save_settings_as_dialog)
        self.save_current_button = QPushButton("保存当前配置")
        self.save_current_button.clicked.connect(lambda: self.save_current_settings(self.current_config_filename))

        config_button_layout.addWidget(self.load_default_button)
        config_button_layout.addWidget(self.save_as_button)
        config_button_layout.addWidget(self.save_current_button)
        scroll_layout.addLayout(config_button_layout)

        # --- 动作按钮 ---
        action_button_layout = QHBoxLayout()
        self.start_button = QPushButton("开始上传")
        self.start_button.setObjectName("startButton")  # 设置对象名以便QSS选择
        self.start_button.clicked.connect(self.start_upload)
        action_button_layout.addWidget(self.start_button)

        self.stop_button = QPushButton("停止") # <-- 新增停止按钮
        self.stop_button.setObjectName("stopButton") # 设置对象名以便QSS选择
        self.stop_button.setEnabled(False) # 初始禁用
        self.stop_button.clicked.connect(self.stop_upload) # 连接到槽函数
        action_button_layout.addWidget(self.stop_button)

        self.help_button = QPushButton("帮助")
        self.help_button.clicked.connect(self.show_help_dialog)
        action_button_layout.addWidget(self.help_button)

        scroll_layout.addLayout(action_button_layout)

        # --- 进度条 ---
        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        scroll_layout.addWidget(self.progress_bar)

        # --- 状态和日志输出 ---
        self.status_label = QLabel("状态: 待命")
        scroll_layout.addWidget(self.status_label)
        self.log_output_area = QTextEdit()
        self.log_output_area.setReadOnly(True)
        self.log_output_area.setFont(QFont("Monospace", 9))
        self.log_output_area.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        scroll_layout.addWidget(self.log_output_area)

        # 将 center_widget 居中到顶层 QHBoxLayout
        top_h_layout.addSpacerItem(QSpacerItem(0, 0, QSizePolicy.Expanding, QSizePolicy.Minimum))
        top_h_layout.addWidget(self.center_widget)
        top_h_layout.addSpacerItem(QSpacerItem(0, 0, QSizePolicy.Expanding, QSizePolicy.Minimum))

        self.setLayout(top_h_layout)  # 设置顶层布局

    def resizeEvent(self, event):
        """
        槽函数，用于处理窗口大小调整事件。
        根据窗口宽度调整内部内容区域的最大宽度。
        """
        super().resizeEvent(event)
        self.adjust_content_width(event.size().width())

    def adjust_content_width(self, window_width):
        """
        根据给定的窗口宽度，计算并设置 center_widget 的固定宽度。
        """
        # 计算窗口内容区域的可用宽度（减去顶层 QHBoxLayout 的左右边距，这里我们设为0）
        # main_layout_margins = self.layout().contentsMargins() # 这是顶层QHBoxLayout的边距
        # available_width_for_center_widget = window_width - main_layout_margins.left() - main_layout_margins.right()
        # 由于顶层 QHBoxLayout 边距为0，所以可用宽度就是窗口宽度
        available_width_for_center_widget = window_width

        # 应用规则：max{480px, current_width / 2}
        calculated_width = max(480, available_width_for_center_widget // 2)

        # 设置 center_widget 的固定宽度
        # 这将强制其内部布局元素适应这个宽度，同时通过 QSpacerItem 实现居中
        self.center_widget.setFixedWidth(calculated_width)

    def toggle_time_input(self, checked):
        """根据QCheckBox状态切换时间输入框的启用/禁用状态"""
        self.start_datetime_input.setEnabled(not checked)
        if checked:
            self.start_datetime_input.setDateTime(QDateTime.currentDateTime())

    def open_cookie_help_url(self):
        """打开获取 Cookie 的帮助页面链接"""
        QDesktopServices.openUrl(QUrl("https://pe.sjtu.edu.cn/phone/#/indexPortrait"))


    def load_settings_to_ui(self, filename):
        """从指定文件加载配置并填充UI"""
        self.config = ConfigManager.load_config(filename)
        self.current_config_filename = filename
        self.setWindowTitle(f"SJTU 体育跑步上传工具 - [{os.path.basename(filename)}]")

        full_cookie = self.config.get("COOKIE", "")
        # 尝试从完整的 cookie 字符串中解析 keepalive 和 JSESSIONID
        keepalive_val = ""
        jsessionid_val = ""
        parts = full_cookie.split(';')
        for part in parts:
            part = part.strip()
            if part.startswith("keepalive="):
                keepalive_val = part
            elif part.startswith("JSESSIONID="):
                jsessionid_val = part

        self.keepalive_input.setText(keepalive_val)
        self.jsessionid_input.setText(jsessionid_val)
        self.user_id_input.setText(self.config.get("USER_ID", ""))
        self.start_lat_input.setText(str(self.config.get("START_LATITUDE", "")))
        self.start_lon_input.setText(str(self.config.get("START_LONGITUDE", "")))
        self.end_lat_input.setText(str(self.config.get("END_LATITUDE", "")))
        self.end_lon_input.setText(str(self.config.get("END_LONGITUDE", "")))
        self.speed_input.setText(str(self.config.get("RUNNING_SPEED_MPS", "")))
        self.interval_input.setText(str(self.config.get("INTERVAL_SECONDS", "")))

        start_time_ms = self.config.get("START_TIME_EPOCH_MS", None)
        if start_time_ms is not None:
            dt = QDateTime.fromMSecsSinceEpoch(start_time_ms)
            self.start_datetime_input.setDateTime(dt)
            self.use_current_time_checkbox.setChecked(False)
            self.start_datetime_input.setEnabled(True)
        else:
            self.use_current_time_checkbox.setChecked(True)
            self.start_datetime_input.setEnabled(False)
            self.start_datetime_input.setDateTime(QDateTime.currentDateTime())

        self.log_output_text(f"已加载配置文件: {os.path.basename(filename)}", "info")

    def get_settings_from_ui(self):
        """从UI获取当前配置并返回字典"""
        try:
            # 组合 keepalive 和 JSESSIONID
            keepalive = self.keepalive_input.text().strip()
            jsessionid = self.jsessionid_input.text().strip()
            combined_cookie = ""
            if keepalive:
                combined_cookie += f"keepalive={keepalive}"
            if jsessionid:
                if combined_cookie:
                    combined_cookie += "; "
                combined_cookie += f"JSESSIONID={jsessionid}"

            current_config = {
                "COOKIE": combined_cookie,
                "USER_ID": self.user_id_input.text(),
                "START_LATITUDE": float(self.start_lat_input.text()),
                "START_LONGITUDE": float(self.start_lon_input.text()),
                "END_LATITUDE": float(self.end_lat_input.text()),
                "END_LONGITUDE": float(self.end_lon_input.text()),
                "RUNNING_SPEED_MPS": float(self.speed_input.text()),
                "INTERVAL_SECONDS": int(self.interval_input.text()),
                "HOST": "pe.sjtu.edu.cn",
                "UID_URL": "https://pe.sjtu.edu.cn/sports/my/uid",
                "MY_DATA_URL": "https://pe.sjtu.edu.cn/sports/my/data",
                "POINT_RULE_URL": "https://pe.sjtu.edu.cn/api/running/point-rule",
                "UPLOAD_URL": "https://pe.sjtu.edu.cn/api/running/result/upload"
            }

            if self.use_current_time_checkbox.isChecked():
                current_config["START_TIME_EPOCH_MS"] = None
            else:
                current_config["START_TIME_EPOCH_MS"] = self.start_datetime_input.dateTime().toMSecsSinceEpoch()

            # 验证关键配置项
            if not current_config["COOKIE"] or not current_config["USER_ID"]:
                raise ValueError("Cookie (keepalive 和 JSESSIONID) 和 用户ID 不能为空。")

            return current_config

        except ValueError as e:
            raise ValueError(f"输入错误: {e}")
        except Exception as e:
            raise Exception(f"获取配置时发生未知错误: {e}")

    def save_current_settings(self, filename):
        """将当前UI中的配置保存到指定文件。"""
        try:
            new_config = self.get_settings_from_ui()
            if ConfigManager.save_config(new_config, filename):
                self.config = new_config
                self.current_config_filename = filename
                self.setWindowTitle(f"SJTU 体育跑步上传工具 - [{os.path.basename(filename)}]")
                QMessageBox.information(self, "保存成功", f"配置已成功保存到 '{os.path.basename(filename)}'！")

        except ValueError as e:
            QMessageBox.critical(self, "输入错误", str(e))
        except Exception as e:
            QMessageBox.critical(self, "保存失败", f"保存配置时发生错误: {e}")

    def save_settings_as_dialog(self):
        """通过文件对话框让用户选择文件名来保存配置。"""
        if not os.path.exists(CONFIGS_DIR):
            os.makedirs(CONFIGS_DIR)

        default_filename = os.path.join(CONFIGS_DIR, "custom_config.json")
        filename, _ = QFileDialog.getSaveFileName(
            self, "保存配置为", default_filename, "JSON Files (*.json);;All Files (*)"
        )
        if filename:
            base_filename = os.path.basename(filename)
            self.save_current_settings(base_filename)

    def start_upload(self):
        """开始上传跑步数据"""
        self.log_output_area.clear()
        self.progress_bar.setValue(0)
        self.status_label.setText("状态: 准备中...")
        self.log_output_text("准备开始上传...", "info")

        try:
            current_config_to_send = self.get_settings_from_ui()
        except (ValueError, Exception) as e:
            self.log_output_text(f"配置错误: {e}", "error")
            self.status_label.setText("状态: 错误")
            QMessageBox.critical(self, "配置错误", str(e))
            return

        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True) # 启用停止按钮
        self.save_current_button.setEnabled(False)
        self.save_as_button.setEnabled(False)
        self.load_default_button.setEnabled(False)
        self.use_current_time_checkbox.setEnabled(False)
        self.start_datetime_input.setEnabled(False)
        self.help_button.setEnabled(False)
        self.keepalive_input.setEnabled(False)
        self.jsessionid_input.setEnabled(False)
        self.user_id_input.setEnabled(False)


        self.thread = WorkerThread(current_config_to_send)
        self.thread.progress_update.connect(self.update_progress)
        self.thread.log_output.connect(self.log_output_text)
        self.thread.finished.connect(self.upload_finished)
        self.thread.start()

    def stop_upload(self): # <-- 新增停止槽函数
        """请求工作线程停止。"""
        if self.thread and self.thread.isRunning():
            self.thread.requestInterruption() # 请求中断
            self.log_output_text("已发送停止请求，请等待任务清理并退出...", "warning")
            self.stop_button.setEnabled(False) # 禁用停止按钮防止重复点击
            self.status_label.setText("状态: 正在停止...")
        else:
            self.log_output_text("没有运行中的任务可以停止。", "info")


    def update_progress(self, current, total, message):
        """更新进度条和状态信息"""
        self.progress_bar.setMaximum(total)
        self.progress_bar.setValue(current)
        self.status_label.setText(f"状态: {message}")

    def log_output_text(self, message, level="info"):
        """将日志信息添加到文本区域，并根据级别着色"""
        cursor = self.log_output_area.textCursor()
        cursor.movePosition(QTextCursor.End)

        format = QTextCharFormat()
        if level == "error":
            format.setForeground(QColor("red"))
        elif level == "warning":
            format.setForeground(QColor("#FFA500"))
        elif level == "success":
            format.setForeground(QColor("green"))
        else:
            format.setForeground(QColor("#1e1e1e"))

        cursor.insertText(f"[{level.upper()}] {message}\n", format)
        self.log_output_area.ensureCursorVisible()

    def upload_finished(self, success, message):
        """上传任务完成后的处理"""
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False) # 任务结束后禁用停止按钮
        self.save_current_button.setEnabled(True)
        self.save_as_button.setEnabled(True)
        self.load_default_button.setEnabled(True)
        self.use_current_time_checkbox.setEnabled(True)
        self.start_datetime_input.setEnabled(not self.use_current_time_checkbox.isChecked())
        self.help_button.setEnabled(True)
        self.keepalive_input.setEnabled(True)
        self.jsessionid_input.setEnabled(True)
        self.user_id_input.setEnabled(True)

        self.progress_bar.setValue(100)

        if success:
            self.status_label.setText("状态: 上传成功！")
            self.log_output_text(f"操作完成: {message}", "success")
            QMessageBox.information(self, "上传结果", message)
        else:
            self.status_label.setText("状态: 上传失败！")
            self.log_output_text(f"操作失败: {message}", "error")
            QMessageBox.critical(self, "上传结果", f"上传失败: {message}")

        self.thread = None

    def show_help_dialog(self):
        """显示帮助对话框。"""
        help_dialog = HelpDialog(self)
        help_dialog.exec() # 使用 exec() 使对话框成为模态

if __name__ == "__main__":
    app = QApplication(sys.argv)
    ui = SportsUploaderUI()
    ui.show()
    sys.exit(app.exec())