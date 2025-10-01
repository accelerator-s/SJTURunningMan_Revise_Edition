import os
import markdown
from PySide6.QtWidgets import QDialog, QVBoxLayout, QTextBrowser, QPushButton, QSizePolicy
from PySide6.QtGui import QIcon, QColor, QPalette
from PySide6.QtCore import Qt

class HelpDialog(QDialog):
    def __init__(self, parent=None, markdown_path="assets/help.md"):
        super().__init__(parent)
        self.setWindowTitle("帮助 - SJTU 体育跑步上传工具")
        self.setWindowIcon(QIcon("assets/SJTURM.png"))
        self.resize(600, 700) # 设定一个默认的帮助窗口大小

        self.init_ui(markdown_path)
        self.apply_style()

    def init_ui(self, markdown_path):
        main_layout = QVBoxLayout(self)

        self.text_browser = QTextBrowser()
        self.text_browser.setOpenExternalLinks(True) # 允许打开外部链接
        self.text_browser.setReadOnly(True)
        self.text_browser.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        help_content = self.load_markdown_content(markdown_path)
        if help_content:
            # 使用markdown库将Markdown文本转换为HTML
            html_content = markdown.markdown(help_content)
            self.text_browser.setHtml(html_content)
        else:
            self.text_browser.setPlainText("无法加载帮助内容。请确保 assets/help.md 文件存在且可读。")

        main_layout.addWidget(self.text_browser)

        close_button = QPushButton("关闭")
        close_button.clicked.connect(self.accept) # 连接到 accept 槽，关闭对话框
        main_layout.addWidget(close_button, alignment=Qt.AlignCenter) # 按钮居中

    def load_markdown_content(self, path):
        """从文件加载Markdown内容"""
        if os.path.exists(path):
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    return f.read()
            except Exception as e:
                print(f"Error loading help.md: {e}")
                return None
        return None

    def apply_style(self):
        """为帮助对话框应用浅色样式，与主窗口保持一致"""
        palette = self.palette()
        palette.setColor(QPalette.Window, QColor(255, 255, 255))
        palette.setColor(QPalette.WindowText, QColor(30, 30, 30))
        palette.setColor(QPalette.Base, QColor(255, 255, 255)) # QTextBrowser背景
        palette.setColor(QPalette.Text, QColor(30, 30, 30))
        palette.setColor(QPalette.Button, QColor(0, 120, 212)) # 蓝色按钮
        palette.setColor(QPalette.ButtonText, QColor(255, 255, 255))
        self.setPalette(palette)

        self.setStyleSheet("""
            QDialog {
                background-color: rgb(255, 255, 255);
            }
            QTextBrowser {
                border: 1px solid rgb(220, 220, 220);
                border-radius: 5px;
                padding: 10px;
                font-family: "Segoe UI", "Microsoft YaHei", sans-serif;
                font-size: 10pt;
            }
            QPushButton {
                background-color: rgb(0, 120, 212);
                color: white;
                border-radius: 5px;
                padding: 8px 15px;
                font-weight: bold;
                min-width: 80px;
            }
            QPushButton:hover {
                background-color: rgb(0, 96, 173);
            }
        """)