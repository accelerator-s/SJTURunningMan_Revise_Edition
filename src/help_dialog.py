import os
import markdown
import re
from PySide6.QtWidgets import QDialog, QVBoxLayout, QTextBrowser, QPushButton, QSizePolicy
from PySide6.QtGui import QIcon, QColor, QPalette
from PySide6.QtCore import Qt, QUrl
from src.utils import get_base_path

RESOURCES_SUB_DIR = "assets"
RESOURCES_FULL_PATH = os.path.join(get_base_path(), RESOURCES_SUB_DIR)


class HelpDialog(QDialog):
    def __init__(self, parent=None, markdown_relative_path="assets/help.md"):
        super().__init__(parent)
        self.setWindowTitle("帮助 - SJTU 体育跑步上传工具")
        self.setWindowIcon(QIcon(os.path.join(RESOURCES_FULL_PATH, "SJTURM.png")))
        self.resize(600, 700)

        self.init_ui(markdown_relative_path)
        self.apply_style()

    def init_ui(self, markdown_relative_path):
        main_layout = QVBoxLayout(self)

        self.text_browser = QTextBrowser()
        self.text_browser.setOpenExternalLinks(True)
        self.text_browser.setReadOnly(True)
        self.text_browser.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        full_markdown_path = os.path.join(get_base_path(), markdown_relative_path)
        help_content = self.load_markdown_content(full_markdown_path)

        if help_content:
            html_content = markdown.markdown(help_content)

            image_src_pattern = r'(<img[^>]*?src=")(\.?/?([^"/\\<>]+\.(?:png|jpg|jpeg|gif|bmp|svg)))("[^>]*?>)'

            def replace_and_resize_image_path(match):
                image_filename = match.group(3)
                absolute_image_path = os.path.join(RESOURCES_FULL_PATH, image_filename)
                file_url = QUrl.fromLocalFile(absolute_image_path).toString()

                image_internal_styles = "max-width: 100%; height: auto; display: block; margin: 0 auto; border: 1px solid rgb(230, 230, 230); border-radius: 5px;"

                original_img_tag = match.group(0)

                modified_img_tag = re.sub(r'src="[^"]+"', f'src="{file_url}"', original_img_tag, flags=re.IGNORECASE)

                if 'style="' in modified_img_tag:
                    modified_img_tag = re.sub(r'(style="[^"]*)(")', rf'\1; {image_internal_styles}\2', modified_img_tag,
                                              flags=re.IGNORECASE, count=1)
                else:
                    modified_img_tag = re.sub(r'(<img)', r'\1 style="' + image_internal_styles + '"', modified_img_tag,
                                              flags=re.IGNORECASE, count=1)

                div_wrapper_styles = "margin: 20px 0; text-align: center;"

                return f'<div style="{div_wrapper_styles}">{modified_img_tag}</div>'

            html_content = re.sub(image_src_pattern, replace_and_resize_image_path, html_content, flags=re.IGNORECASE)

            self.text_browser.setHtml(html_content)

        else:
            self.text_browser.setPlainText(
                f"无法加载帮助内容。请确保 '{os.path.basename(markdown_relative_path)}' 文件存在且可读。")

        main_layout.addWidget(self.text_browser)

        close_button = QPushButton("关闭")
        close_button.clicked.connect(self.accept)
        main_layout.addWidget(close_button, alignment=Qt.AlignCenter)

    def load_markdown_content(self, path):
        """从文件加载Markdown内容"""
        if os.path.exists(path):
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    return f.read()
            except Exception as e:
                print(f"Error loading {os.path.basename(path)}: {e}")
                return None
        return None

    def apply_style(self):
        """为帮助对话框应用浅色样式，与主窗口保持一致"""
        palette = self.palette()
        palette.setColor(QPalette.Window, QColor(255, 255, 255))
        palette.setColor(QPalette.WindowText, QColor(30, 30, 30))
        palette.setColor(QPalette.Base, QColor(255, 255, 255))
        palette.setColor(QPalette.Text, QColor(30, 30, 30))
        palette.setColor(QPalette.Button, QColor(0, 120, 212))
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
                image-rendering: auto;
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