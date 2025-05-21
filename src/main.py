# main_window.py
import sys
import subprocess  # 新增导入
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                            QLabel, QLineEdit, QComboBox, QPushButton,
                            QStatusBar, QTabWidget, QFrame, QMessageBox)
from PyQt5.QtCore import Qt
from style_sheet import apply_theme  # 修改导入方式
from LauncherGenerator import MinecraftLauncherGenerator

class BlockLaunchUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("BlockLaunch")
        self.setMinimumSize(800, 500)
        self.launcher = MinecraftLauncherGenerator(
            version="1.20.1",
            player_name=""
        )
        self.init_ui()
        apply_theme('white')  # 使用新的主题应用方式