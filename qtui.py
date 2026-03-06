import sys
import os
import re
from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QTextEdit, QProgressBar, QFormLayout, QGroupBox, QDateTimeEdit,
    QMessageBox, QScrollArea, QSizePolicy, QCheckBox,
    QSpacerItem, QDialog, QComboBox
)
from PySide6.QtCore import QThread, Signal, QDateTime, Qt, QUrl, QEvent
from PySide6.QtGui import QTextCursor, QFont, QColor, QTextCharFormat, QPalette, QBrush, QIcon, QDesktopServices

from src.main import run_sports_upload
import src.login as login
from utils.auxiliary_util import SportsUploaderError, get_base_path
import src.config as config


from src.info_dialog import HelpWidget

RESOURCES_SUB_DIR = "assets"

RESOURCES_FULL_PATH = os.path.join(get_base_path(), RESOURCES_SUB_DIR)

class WorkerThread(QThread):
    progress_update = Signal(int, int, str)
    log_output = Signal(str, str)
    finished = Signal(bool, str)

    def __init__(self, config_data):
        super().__init__()
        self.config_data = config_data

    def run(self):
        success = False
        message = "任务已完成。"
        try:
            success, message = run_sports_upload(
                self.config_data,
                progress_callback=self.progress_callback,
                log_cb=self.log_callback,
                stop_check_cb=self.isInterruptionRequested
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
            if self.isInterruptionRequested() and not success:
                 self.finished.emit(False, "任务已手动终止。")
            else:
                 self.finished.emit(success, message)

    def progress_callback(self, current, total, message):
        self.progress_update.emit(current, total, message)

    def log_callback(self, message, level):
        self.log_output.emit(message, level)


class SportsUploaderUI(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("SJTU 校园轻松跑 - Version " + config.global_version)
        self.setWindowIcon(QIcon(os.path.join(RESOURCES_FULL_PATH, "SJTURM.png")))

        # 后台线程引用（私有）
        self._thread = None
        # 关于窗口引用，防止被垃圾回收
        self._help_window = None

        self.config = {}

        self.setup_ui_style()
        self.init_ui()

        self.setGeometry(300, 100, 380, 500)
        self.setMinimumSize(380, 500)

        # 根据当前窗口宽度调整内容区域宽度
        self.adjust_content_width(self.width())
        # 启动时居中主窗口
        try:
            self.center_window()
        except Exception:
            pass

    def setup_ui_style(self):
        palette = self.palette()
        palette.setColor(QPalette.Window, QColor(255, 255, 255))
        palette.setColor(QPalette.WindowText, QColor(51, 51, 51))
        palette.setColor(QPalette.Base, QColor(255, 255, 255))
        palette.setColor(QPalette.AlternateBase, QColor(255, 255, 255))
        palette.setColor(QPalette.ToolTipBase, QColor(255, 255, 255))
        palette.setColor(QPalette.ToolTipText, QColor(51, 51, 51))
        palette.setColor(QPalette.Text, QColor(51, 51, 51))
        palette.setColor(QPalette.Button, QColor(255, 255, 255))
        palette.setColor(QPalette.ButtonText, QColor(51, 51, 51))
        palette.setColor(QPalette.BrightText, QColor("red"))
        palette.setColor(QPalette.Link, QColor(106, 153, 200))
        palette.setColor(QPalette.Highlight, QColor(106, 153, 200))
        palette.setColor(QPalette.HighlightedText, QColor(255, 255, 255))
        self.setPalette(palette)

        self.setStyleSheet("""
            QWidget, QScrollArea, QGroupBox {
                background-color: rgb(255, 255, 255);
            }

            QGroupBox {
                font-size: 12pt;
                font-weight: bold;
                margin-top: 15px;
                border: 1px solid rgb(220, 220, 220);
                border-radius: 6px;
                padding-top: 25px;
                padding-bottom: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top center;
                padding: 0 8px;
                color: rgb(55, 85, 125);
            }
            QLineEdit, QDateTimeEdit {
                background-color: rgb(255, 255, 255);
                border: 1px solid rgb(204, 204, 204);
                border-radius: 4px;
                padding: 8px;
                selection-background-color: rgb(106, 153, 200);
                color: rgb(51, 51, 51);
            }
            QLineEdit:focus, QDateTimeEdit:focus {
                border: 1px solid rgb(106, 153, 200);
            }
            QDateTimeEdit::drop-down {
                subcontrol-origin: padding;
                subcontrol-position: top right;
                width: 20px;
                border-left-width: 1px;
                border-left-color: rgb(204, 204, 204);
                border-left-style: solid;
                border-top-right-radius: 4px;
                border-bottom-right-radius: 4px;
            }
            QPushButton {
                background-color: rgb(255, 255, 255);
                color: rgb(51, 51, 51);
                border: 1px solid rgb(204, 204, 204);
                border-radius: 4px;
                padding: 8px 16px;
                min-height: 24px;
                max-height: 36px;
            }
            QPushButton:hover {
                border: 1px solid rgb(106, 153, 200);
                background-color: rgb(250, 250, 250);
            }
            QPushButton:pressed {
                background-color: rgb(240, 240, 240);
            }
            QPushButton:disabled {
                background-color: rgb(255, 255, 255);
                color: rgb(180, 180, 180);
                border: 1px solid rgb(230, 230, 230);
            }
            QProgressBar {
                border: 1px solid rgb(220, 220, 220);
                border-radius: 4px;
                text-align: center;
                background-color: rgb(255, 255, 255);
                color: rgb(51, 51, 51);
                max-height: 20px;
            }
            QProgressBar::chunk {
                background-color: rgb(116, 160, 205);
                border-radius: 4px;
            }
            QTextEdit {
                background-color: rgb(245, 245, 247);
                border: 1px solid rgb(220, 220, 220);
                border-radius: 4px;
                padding: 8px;
                color: rgb(51, 51, 51);
            }
            QScrollArea {
                border: none;
            }
            QCheckBox {
                spacing: 5px;
                color: rgb(51, 51, 51);
            }
            QCheckBox::indicator {
                width: 16px;
                height: 16px;
                border-radius: 3px;
                border: 1px solid rgb(204, 204, 204);
                background-color: rgb(255, 255, 255);
            }
            QCheckBox::indicator:checked {
                background-color: rgb(106, 153, 200);
                border: 1px solid rgb(106, 153, 200);
            }
            QCheckBox::indicator:disabled {
                border: 1px solid rgb(230, 230, 230);
                background-color: rgb(255, 255, 255);
            }
            QFormLayout QLabel {
                padding-top: 8px;
                padding-bottom: 8px;
                color: rgb(102, 102, 102);
            }
            #startButton {
                background-color: rgb(106, 153, 200);
                color: white;
                border: 1px solid rgb(106, 153, 200);
            }
            #startButton:hover {
                background-color: rgb(86, 133, 180);
                border: 1px solid rgb(86, 133, 180);
            }
            #startButton:pressed {
                background-color: rgb(70, 115, 160);
            }
            #stopButton {
                background-color: rgb(150, 155, 162);
                color: white;
                border: 1px solid rgb(150, 155, 162);
            }
            #stopButton:hover {
                background-color: rgb(130, 135, 142);
                border: 1px solid rgb(130, 135, 142);
            }
            #stopButton:pressed {
                background-color: rgb(115, 120, 128);
            }
            QLabel#getCookieLink {
                color: rgb(106, 153, 200);
                text-decoration: underline;
                padding: 0;
            }
            QLabel#getCookieLink:hover {
                color: rgb(70, 115, 160);
            }
        """)

    def init_ui(self):
        top_h_layout = QHBoxLayout()
        top_h_layout.setContentsMargins(20, 20, 20, 20)
        top_h_layout.setSpacing(0)

        self.center_widget = QWidget()
        main_layout = QVBoxLayout(self.center_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        self.scroll_area = QScrollArea()
        self.scroll_content = QWidget()
        scroll_layout = QVBoxLayout(self.scroll_content)
        scroll_layout.setContentsMargins(0, 0, 0, 0)
        scroll_layout.setSpacing(20)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setWidget(self.scroll_content)

        main_layout.addWidget(self.scroll_area)

        user_group = QGroupBox("用户配置")
        user_form_layout = QFormLayout()
        user_form_layout.setVerticalSpacing(15)
        user_form_layout.setContentsMargins(15, 15, 15, 15)

        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText("Jaccount用户名")
        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText("密码")
        self.password_input.setEchoMode(QLineEdit.Password)

        user_form_layout.addRow("用户名:", self.username_input)
        user_form_layout.addRow("密码:", self.password_input)
        user_group.setLayout(user_form_layout)
        scroll_layout.addWidget(user_group)

        action_button_layout = QHBoxLayout()
        action_button_layout.setSpacing(12)
        self.start_button = QPushButton("一键跑步")
        self.start_button.setObjectName("startButton")
        self.start_button.clicked.connect(self.start_upload)
        action_button_layout.addWidget(self.start_button)

        self.stop_button = QPushButton("停止")
        self.stop_button.setObjectName("stopButton")
        self.stop_button.setEnabled(False)
        self.stop_button.clicked.connect(self.stop_upload)
        action_button_layout.addWidget(self.stop_button)

        self.info_button = QPushButton("关于")
        self.info_button.clicked.connect(self.show_info_dialog)
        action_button_layout.addWidget(self.info_button)

        scroll_layout.addLayout(action_button_layout)

        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        scroll_layout.addWidget(self.progress_bar)

        self.status_label = QLabel("状态: 待命")
        scroll_layout.addWidget(self.status_label)
        
        self.log_output_area = QTextEdit()
        self.log_output_area.setReadOnly(True)
        self.log_output_area.setFont(QFont("Monospace", 9))
        self.log_output_area.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        scroll_layout.addWidget(self.log_output_area)

        top_h_layout.addWidget(self.center_widget)

        self.setLayout(top_h_layout)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.adjust_content_width(event.size().width())

    def adjust_content_width(self, window_width):
        calculated_width = int(min(window_width * 0.9, 600))
        calculated_width = max(280, calculated_width)
        self.center_widget.setFixedWidth(calculated_width)

    def center_window(self):
        try:
            screen = QApplication.primaryScreen()
            if screen is None:
                return
            available = screen.availableGeometry()
            fg = self.frameGeometry()
            fg.moveCenter(available.center())
            self.move(fg.topLeft())
        except Exception:
            return

    def get_settings_from_ui(self):
        """从UI获取当前配置"""
        username = self.username_input.text().strip()
        password = self.password_input.text()

        if not username or not password:
            raise ValueError("用户名和密码不能为空。")

        return {
            "USER_ID": username,
            "PASSWORD": password,
            "START_LATITUDE": 31.031599,
            "START_LONGITUDE": 121.442938,
            "RUNNING_SPEED_MPS": round(1000.0 / (5 * 60), 3),
            "INTERVAL_SECONDS": 3,
            "HOST": "pe.sjtu.edu.cn",
            "UID_URL": "https://pe.sjtu.edu.cn/sports/my/uid",
            "MY_DATA_URL": "https://pe.sjtu.edu.cn/sports/my/data",
            "POINT_RULE_URL": "https://pe.sjtu.edu.cn/api/running/point-rule",
            "UPLOAD_URL": "https://pe.sjtu.edu.cn/api/running/result/upload"
        }

    def _2fa_select_method(self):
        """二次验证：让用户选择验证方式"""
        dialog = QDialog(self)
        dialog.setWindowTitle("异地登录验证")
        dialog.setWindowFlags(Qt.Dialog | Qt.WindowCloseButtonHint)
        dialog.setFixedSize(360, 180)
        dialog.setWindowModality(Qt.WindowModal)

        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(14)

        label = QLabel("请选择验证方式:")
        label.setStyleSheet("font-size: 11pt; color: #333;")
        layout.addWidget(label)

        combo = QComboBox()
        combo.addItems(["交我办消息", "邮箱", "短信"])
        combo.setStyleSheet("padding: 6px; font-size: 10pt;")
        layout.addWidget(combo)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        ok_btn = QPushButton("确定")
        ok_btn.setFixedWidth(80)
        ok_btn.clicked.connect(dialog.accept)
        cancel_btn = QPushButton("取消")
        cancel_btn.setFixedWidth(80)
        cancel_btn.clicked.connect(dialog.reject)
        btn_layout.addWidget(ok_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)

        method_map = {"交我办消息": "app", "邮箱": "email", "短信": "sms"}
        if dialog.exec() == QDialog.Accepted:
            return method_map.get(combo.currentText(), "app")
        return None

    def _2fa_get_code(self):
        """二次验证：获取用户输入的验证码"""
        dialog = QDialog(self)
        dialog.setWindowTitle("输入验证码")
        dialog.setWindowFlags(Qt.Dialog | Qt.WindowCloseButtonHint)
        dialog.setFixedSize(360, 180)
        dialog.setWindowModality(Qt.WindowModal)

        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(14)

        label = QLabel("请输入6位验证码（输入 r 可重新发送）:")
        label.setStyleSheet("font-size: 11pt; color: #333;")
        layout.addWidget(label)

        line_edit = QLineEdit()
        line_edit.setPlaceholderText("验证码")
        line_edit.setStyleSheet("padding: 6px; font-size: 10pt;")
        layout.addWidget(line_edit)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        ok_btn = QPushButton("确定")
        ok_btn.setFixedWidth(80)
        ok_btn.clicked.connect(dialog.accept)
        cancel_btn = QPushButton("取消")
        cancel_btn.setFixedWidth(80)
        cancel_btn.clicked.connect(dialog.reject)
        btn_layout.addWidget(ok_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)

        if dialog.exec() == QDialog.Accepted:
            code = line_edit.text().strip()
            return code if code else None
        return None

    def _2fa_show_message(self, msg):
        """二次验证：显示提示信息"""
        self.log_output_text(msg, "info")

    def start_upload(self):
        self.log_output_area.clear()
        self.progress_bar.setValue(0)
        self.status_label.setText("状态: 准备中...")
        self.log_output_text("开始准备...", "info")

        try:
            current_config_to_send = self.get_settings_from_ui()
        except (ValueError, Exception) as e:
            self.log_output_text(f"配置错误: {e}", "error")
            self.status_label.setText("状态: 错误")
            return

        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.info_button.setEnabled(False)
        self.username_input.setEnabled(False)
        self.password_input.setEnabled(False)

        try:
            username = current_config_to_send.get("USER_ID")
            password = current_config_to_send.get("PASSWORD")

            two_fa_cb = {
                'select_method': self._2fa_select_method,
                'get_code': self._2fa_get_code,
                'show_message': self._2fa_show_message,
            }

            session = login.login(username, password, two_fa_cb=two_fa_cb)
            current_config_to_send["SESSION"] = session
            current_config_to_send["USER_ID"] = username
        except Exception as e:
            self.log_output_text(f"登录失败: {e}", "error")
            QMessageBox.critical(self, "登录失败", str(e))
            self.start_button.setEnabled(True)
            self.stop_button.setEnabled(False)
            self.username_input.setEnabled(True)
            self.password_input.setEnabled(True)
            self.info_button.setEnabled(True)
            return

        self._thread = WorkerThread(current_config_to_send)
        self._thread.progress_update.connect(self.update_progress)
        self._thread.log_output.connect(self.log_output_text)
        self._thread.finished.connect(self.upload_finished)
        self._thread.start()

    def stop_upload(self):
        if self._thread and self._thread.isRunning():
            self._thread.requestInterruption()
            self.log_output_text("正在停止...", "warning")
            self.stop_button.setEnabled(False)
            self.status_label.setText("状态: 正在停止...")
        else:
            self.log_output_text("没有运行中的任务。", "info")


    def update_progress(self, current, total, message):
        self.progress_bar.setMaximum(total)
        self.progress_bar.setValue(current)
        self.status_label.setText(f"状态: {message}")

    def log_output_text(self, message, level="info"):
        cursor = self.log_output_area.textCursor()
        cursor.movePosition(QTextCursor.End)

        format = QTextCharFormat()
        if level == "error":
            format.setForeground(QColor("#A0705A"))
        elif level == "warning":
            format.setForeground(QColor("#C49A3C"))
        elif level == "success":
            format.setForeground(QColor("#5A7DA0"))
        else:
            format.setForeground(QColor("#333333"))

        # 如果是进度类短消息（例如: 已完成1/25），尝试替换最后一行以便在同一行更新
        try:
            if re.match(r"^已完成\d+/\d+", message):
                # 选择最后一段文本（最后一个 block）并检查是否包含“已完成”关键词
                doc = self.log_output_area.document()
                last_block = doc.lastBlock()
                if last_block.isValid() and "已完成" in last_block.text():
                    # 选中最后一个 block 并替换
                    cursor.movePosition(QTextCursor.End)
                    cursor.select(QTextCursor.BlockUnderCursor)
                    cursor.removeSelectedText()
                    # 插入新的进度信息（不额外换行），随后插入换行字符
                    cursor.insertText(f"[{level.upper()}] {message}\n", format)
                    self.log_output_area.ensureCursorVisible()
                    return
        except Exception:
            # 如果替换失败，退回到普通追加方式
            pass

        cursor.insertText(f"[{level.upper()}] {message}\n", format)
        self.log_output_area.ensureCursorVisible()

    def upload_finished(self, success, message):
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.info_button.setEnabled(True)
        self.username_input.setEnabled(True)
        self.password_input.setEnabled(True)

        self.progress_bar.setValue(100)

        if success:
            self.status_label.setText("状态: 上传成功！")
            self.log_output_text(f"完成: {message}", "success")
            QMessageBox.information(self, "上传结果", message)
        else:
            self.status_label.setText("状态: 上传失败！")
            self.log_output_text(f"失败: {message}", "error")

        self._thread = None


    def show_info_dialog(self):
        try:
            # 如果已有关于窗口实例：
            # - 若窗口仍可见，则激活并返回；
            # - 若已被隐藏/关闭但引用未清理，则清理引用并继续创建新的实例
            existing = getattr(self, "_help_window", None)
            if existing is not None:
                try:
                    if existing.isVisible():
                        try:
                            existing.activateWindow()
                            existing.raise_()
                        except Exception:
                            pass
                        return
                    else:
                        # 已存在但不可见，尝试移除事件过滤并清理引用以便重新创建
                        try:
                            existing.removeEventFilter(self)
                        except Exception:
                            pass
                        self._help_window = None
                except Exception:
                    self._help_window = None

            # 创建 HelpWidget 实例并以非模态方式显示
            self._help_window = HelpWidget()
            self._help_window.setWindowModality(Qt.WindowModality.NonModal)
            try:
                self._help_window.installEventFilter(self)
            except Exception:
                pass

            def _on_help_destroyed():
                try:
                    if getattr(self, "_help_window", None) is not None:
                        self._help_window = None
                except Exception:
                    self._help_window = None

            try:
                self._help_window.destroyed.connect(_on_help_destroyed)
            except Exception:
                pass

            # 显示窗口（非模态）
            self._help_window.show()

        except Exception as e:
            # 记录异常并弹出对话框，不影响后台线程
            self.log_output_text(f"无法显示关于窗口: {e}", "error")
            QMessageBox.warning(self, "显示失败", f"无法显示关于窗口: {e}")

    def eventFilter(self, watched, event):
        try:
            if watched is getattr(self, "_help_window", None):
                # 使用数值来避免某些静态类型检查器对 QEvent 枚举成员的误报
                ev_type = event.type()
                if ev_type in (19, 5):  # 19 = Close, 5 = Hide
                    try:
                        watched.removeEventFilter(self)
                    except Exception:
                        pass
                    self._help_window = None
        except Exception:
            pass

        return super().eventFilter(watched, event)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    ui = SportsUploaderUI()
    ui.show()
    sys.exit(app.exec())