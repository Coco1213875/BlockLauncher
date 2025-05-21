import sys
import os
import subprocess
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                            QLabel, QLineEdit, QComboBox, QPushButton,
                            QStatusBar, QTabWidget, QFrame, QMessageBox)
from PyQt5.QtCore import Qt
from style_sheet import *
from LauncherGenerator import MinecraftLauncherGenerator

class BlockLauncherUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("BlockLauncher")
        self.setMinimumSize(800, 500)
        self.launcher = MinecraftLauncherGenerator(
            version="1.20.1",
            player_name=""
        )
        self.init_ui()
        self.apply_theme('white') 

    def init_ui(self):
        # 主容器
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QVBoxLayout(main_widget)
        main_layout.setContentsMargins(10, 10, 10, 10)

        # 选项卡
        self.tab_widget = QTabWidget()
        main_layout.addWidget(self.tab_widget)

        # 基本设置选项卡
        self.setup_basic_tab()
        # 高级设置选项卡
        self.setup_advanced_tab()

        # 生成按钮
        self.generate_btn = QPushButton("生成启动脚本")
        self.generate_btn.clicked.connect(self.generate_script)
        main_layout.addWidget(self.generate_btn, 0, Qt.AlignBottom)
        
        # 新增：启动游戏按钮
        self.run_btn = QPushButton("启动游戏")
        self.run_btn.clicked.connect(self.run_game)
        main_layout.addWidget(self.run_btn, 0, Qt.AlignBottom)  # 并列放置

        # 状态栏
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)

    def setup_basic_tab(self):
        tab = QWidget()
        self.tab_widget.addTab(tab, "基本设置")
        layout = QVBoxLayout(tab)
        
        # 玩家名称
        name_frame = QFrame()
        name_layout = QVBoxLayout(name_frame)
        name_layout.addWidget(QLabel("玩家名称："))
        self.player_name_input = QLineEdit()
        self.player_name_input.setPlaceholderText("请输入游戏ID")
        name_layout.addWidget(self.player_name_input)
        layout.addWidget(name_frame)

        # 游戏版本
        version_frame = QFrame()
        version_layout = QVBoxLayout(version_frame)
        version_layout.addWidget(QLabel("游戏版本："))
        self.version_combo = QComboBox()
        self.version_combo.addItems(["1.8.9", "1.12.2", "1.16.5", "1.19.4", "1.20.1"])
        version_layout.addWidget(self.version_combo)
        layout.addWidget(version_frame)

    def setup_advanced_tab(self):
        tab = QWidget()
        self.tab_widget.addTab(tab, "高级设置")
        layout = QVBoxLayout(tab)
        
        # 模组加载器
        loader_frame = QFrame()
        loader_layout = QVBoxLayout(loader_frame)
        loader_layout.addWidget(QLabel("模组加载器："))
        
        self.loader_type_combo = QComboBox()
        self.loader_type_combo.addItems(["原版", "Fabric", "Forge"])
        self.loader_type_combo.currentIndexChanged.connect(self.update_loader_versions)
        loader_layout.addWidget(self.loader_type_combo)

        self.loader_version_combo = QComboBox()
        self.loader_version_combo.setPlaceholderText("请选择加载器版本")
        loader_layout.addWidget(self.loader_version_combo)
        
        layout.addWidget(loader_frame)

    def update_loader_versions(self):
        loader_type = self.loader_type_combo.currentText()
        self.loader_version_combo.clear()
        
        if loader_type == "Fabric":
            self.loader_version_combo.addItems(["0.15.11", "0.14.22", "0.13.3"])
        elif loader_type == "Forge":
            self.loader_version_combo.addItems(["47.1.3", "43.2.0", "40.2.9"])
        else:
            # self.loader_version_combo.setEnabled(False)
            self.loader_version_combo.addItems(["无"])

    def generate_script(self):
        try:
            # 获取用户输入
            version = self.version_combo.currentText()
            player_name = self.player_name_input.text().strip()
            loader_type = self.loader_type_combo.currentText()
            loader_version = self.loader_version_combo.currentText()

            # 验证输入
            if not player_name:
                raise ValueError("玩家名称不能为空")
            if loader_type != "无" and not loader_version and loader_type != "原版":
                raise ValueError("请选择加载器版本")

            # 配置启动器
            self.launcher.version = version
            self.launcher.player_name = player_name
            if loader_type != "无":
                self.launcher.loader_type = loader_type.lower()
                self.launcher.loader_version = loader_version

            # 生成脚本
            self.launcher.generate_install_script()
            config = self.launcher.generate_launch_script()

            # 写入文件
            with open("launch.bat", "w", encoding="utf-8") as f:
                f.write(f"{config['java_path']} {' '.join(config['jvm_args'])} {' '.join(config['game_args'])}")

            self.status_bar.showMessage("✅ 启动脚本已成功生成！", 5000)
            QMessageBox.information(self, "成功", "启动脚本已生成！")

        except Exception as e:
            self.status_bar.showMessage(f"❌ 错误：{str(e)}", 5000)
            QMessageBox.critical(self, "错误", str(e))
    
    def apply_theme(self, theme_name='white'):
        # 获取资源目录（基于应用程序运行目录）
        icon_path = os.path.join(QApplication.applicationDirPath(), 'resources', 'icons')
        
        # 验证主题有效性
        if theme_name not in ['white', 'black']:
            raise ValueError(f"Unsupported theme: {theme_name}. Available themes: 'white', 'black'")
        
        # 定义主题资源映射
        theme_resources = {
            'white': {
                'check_mark': os.path.join(icon_path, 'checkmark_white.png'),
                'drop_down_arrow': os.path.join(icon_path, 'dropdown_arrow_white.png'),
                'scroll_bar_top': os.path.join(icon_path, 'scroll_up_white.png'),
                'scroll_bar_bottom': os.path.join(icon_path, 'scroll_down_white.png'),
                'scroll_bar_left': os.path.join(icon_path, 'scroll_left_white.png'),
                'scroll_bar_right': os.path.join(icon_path, 'scroll_right_white.png')
            },
            'black': {
                'check_mark': os.path.join(icon_path, 'checkmark_black.png'),
                'drop_down_arrow': os.path.join(icon_path, 'dropdown_arrow_black.png'),
                'scroll_bar_top': os.path.join(icon_path, 'scroll_up_black.png'),
                'scroll_bar_bottom': os.path.join(icon_path, 'scroll_down_black.png'),
                'scroll_bar_left': os.path.join(icon_path, 'scroll_left_black.png'),
                'scroll_bar_right': os.path.join(icon_path, 'scroll_right_black.png')
            }
        }
        
        # 获取对应样式模板
        style_templates = {
            'white': white,
            'black': black
        }
        
        try:
            # 生成样式表并应用
            theme_style = style_templates[theme_name].format(**theme_resources[theme_name])
            self.setStyleSheet(theme_style)
        except KeyError as e:
            raise RuntimeError(f"Missing resource for {theme_name} theme: {e}") from e

    def run_game(self):
        """生成并执行启动脚本"""
        try:
            # 先生成脚本
            self.generate_script()
            # 执行脚本
            subprocess.Popen(["launch.bat"], shell=True)
        except Exception as e:
            # 复用原有错误处理机制
            pass  # generate_script已处理异常

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = BlockLaunchUI()
    window.show()
    sys.exit(app.exec_())