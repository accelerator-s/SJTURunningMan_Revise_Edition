# --- START OF FILE src/help_dialog.py ---
import os
import markdown
import re
from PySide6.QtWidgets import QDialog, QVBoxLayout, QTextBrowser, QPushButton, QSizePolicy
from PySide6.QtGui import QIcon, QColor, QPalette
from PySide6.QtCore import Qt, QUrl
from src.utils import get_base_path

# 构建资源目录的完整路径
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

        # 构建完整的 markdown 文件路径
        full_markdown_path = os.path.join(get_base_path(), markdown_relative_path)
        help_content = self.load_markdown_content(full_markdown_path)

        if help_content:
            html_content = markdown.markdown(help_content)

            # --- 最终图片处理逻辑：包裹 <div> 并设置样式 ---
            image_src_pattern = r'(<img[^>]*?src=")(\.?/?([^"/\\<>]+\.(?:png|jpg|jpeg|gif|bmp|svg)))("[^>]*?>)'

            def replace_and_resize_image_path(match):
                image_filename = match.group(3)
                absolute_image_path = os.path.join(RESOURCES_FULL_PATH, image_filename)
                file_url = QUrl.fromLocalFile(absolute_image_path).toString()

                # 构建图片本身的内联样式，确保它在 div 内部正确显示
                # 使用 display: block 和 margin: auto 来确保图片在 div 内居中
                image_internal_styles = "max-width: 100%; height: auto; display: block; margin: 0 auto; border: 1px solid rgb(230, 230, 230); border-radius: 5px;"

                # 原始的 img 标签，我们将修改它的 src 和 style
                original_img_tag = match.group(0)  # 整个 img 标签

                # 替换 src 属性
                modified_img_tag = re.sub(r'src="[^"]+"', f'src="{file_url}"', original_img_tag, flags=re.IGNORECASE)

                # 如果 style 属性已经存在，则追加，否则添加
                if 'style="' in modified_img_tag:
                    modified_img_tag = re.sub(r'(style="[^"]*)(")', rf'\1; {image_internal_styles}\2', modified_img_tag,
                                              flags=re.IGNORECASE, count=1)
                else:
                    # 在第一个属性后添加 style 属性，例如：<img alt="..." style="...">
                    modified_img_tag = re.sub(r'(<img)', r'\1 style="' + image_internal_styles + '"', modified_img_tag,
                                              flags=re.IGNORECASE, count=1)

                # 包裹在一个 div 内部，并设置 div 的样式
                # div 的样式用来控制图片块的整体布局和间距
                div_wrapper_styles = "margin: 20px 0; text-align: center;"  # 增加上下 margin，居中

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

        # 移除 QSS 中所有针对 img 的样式，因为现在所有样式都通过内联方式设置
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