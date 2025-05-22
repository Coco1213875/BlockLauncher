import sys
import requests
import os
from PyQt5.QtWidgets import *
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QFont, QIcon
from LauncherGenerator import MinecraftLauncherGenerator, log
import style_sheet
import subprocess

class DownloadThread(QThread):
    progress = pyqtSignal(str)
    finished = pyqtSignal(dict)

    def __init__(self, version, loader_type, loader_version, player_name):
        super().__init__()
        self.version = version
        self.loader_type = loader_type
        self.loader_version = loader_version
        self.player_name = player_name

    def run(self):
        try:
            launcher = MinecraftLauncherGenerator(
                version=self.version,
                loader_type=self.loader_type,
                loader_version=self.loader_version,
                player_name=self.player_name
            )
            self.progress.emit("开始安装游戏文件...")
            launcher.generate_install_script()
            self.progress.emit("生成启动配置...")
            config = launcher.generate_launch_script()
            self.finished.emit(config)
        except Exception as e:
            self.progress.emit(f"错误: {str(e)}")

class BlockLauncher(QMainWindow):
    def __init__(self):
        super().__init__()
        self.download_thread = None
        self.current_config = None
        self.init_ui()
        self.load_versions()

    def init_ui(self):
        # 窗口设置
        self.setWindowTitle('Block Launcher')
        self.setGeometry(300, 300, 1000, 700)
        self.apply_theme('white')

        # 主布局
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QVBoxLayout(main_widget)

        # 顶部栏
        top_bar = QWidget()
        top_layout = QHBoxLayout(top_bar)
        
        # 主题切换
        self.theme_btn = QPushButton("切换主题")
        self.theme_btn.clicked.connect(self.toggle_theme)
        top_layout.addWidget(self.theme_btn)

        # 账户设置
        self.player_input = QLineEdit("Steve")
        self.player_input.setPlaceholderText("玩家名称")
        self.player_input.setFixedWidth(150)
        top_layout.addWidget(QLabel("玩家名称:"))
        top_layout.addWidget(self.player_input)

        top_layout.addStretch()

        # 加载器设置
        self.loader_combo = QComboBox()
        self.loader_combo.addItems(["vanilla", "fabric"])
        self.loader_version_input = QLineEdit()
        self.loader_version_input.setPlaceholderText("加载器版本")
        self.loader_version_input.setFixedWidth(100)
        top_layout.addWidget(QLabel("加载器类型:"))
        top_layout.addWidget(self.loader_combo)
        top_layout.addWidget(QLabel("加载器版本:"))
        top_layout.addWidget(self.loader_version_input)

        main_layout.addWidget(top_bar)

        # 主内容区域
        content_widget = QWidget()
        content_layout = QHBoxLayout(content_widget)

        # 左侧游戏列表
        self.game_list = QListWidget()
        self.game_list.setFixedWidth(250)
        content_layout.addWidget(self.game_list)

        # 右侧面板
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)

        # 版本信息
        version_widget = QWidget()
        version_layout = QHBoxLayout(version_widget)
        version_layout.addWidget(QLabel("游戏版本:"))
        self.version_combo = QComboBox()
        version_layout.addWidget(self.version_combo)
        right_layout.addWidget(version_widget)

        # 控制按钮
        self.install_btn = QPushButton("安装游戏")
        self.install_btn.clicked.connect(self.start_installation)
        right_layout.addWidget(self.install_btn)

        # 日志显示
        self.log_browser = QTextBrowser()
        right_layout.addWidget(self.log_browser)

        content_layout.addWidget(right_panel)
        main_layout.addWidget(content_widget)

        # 底部栏
        bottom_bar = QWidget()
        bottom_layout = QHBoxLayout(bottom_bar)
        
        self.java_label = QLabel("Java路径: 自动检测")
        bottom_layout.addWidget(self.java_label)

        bottom_layout.addStretch()

        self.launch_btn = QPushButton("启动游戏")
        self.launch_btn.setFixedSize(120, 40)
        self.launch_btn.clicked.connect(self.launch_game)
        bottom_layout.addWidget(self.launch_btn)

        main_layout.addWidget(bottom_bar)

    def apply_theme(self, theme_name):
        theme = style_sheet.white if theme_name == 'white' else style_sheet.black
        icons = {
            'check_mark': 'resources/checkmark.png',
            'drop_down_arrow': 'resources/dropdown.png',
            'scroll_bar_top': 'resources/scroll_top.png',
            'scroll_bar_bottom': 'resources/scroll_bottom.png',
            'scroll_bar_left': 'resources/scroll_left.png',
            'scroll_bar_right': 'resources/scroll_right.png'
        }
        self.setStyleSheet(theme.format(**icons))

    def toggle_theme(self):
        current_theme = 'black' if 'background-color: #1c1c1c' in self.styleSheet() else 'white'
        self.apply_theme('black' if current_theme == 'white' else 'white')

    def load_versions(self):
        try:
            manifest_url = "https://piston-meta.mojang.com/mc/game/version_manifest_v2.json"
            response = requests.get(manifest_url)
            versions = [v['id'] for v in response.json()['versions'] if v['type'] == 'release']
            self.version_combo.addItems(versions)  # 显示最新20个版本
        except Exception as e:
            self.log_browser.append(f"无法获取版本列表: {str(e)}")

    def start_installation(self):
        if not self.version_combo.currentText():
            QMessageBox.warning(self, "警告", "请先选择游戏版本")
            return

        self.log_browser.clear()
        self.download_thread = DownloadThread(
            version=self.version_combo.currentText(),
            loader_type=self.loader_combo.currentText(),
            loader_version=self.loader_version_input.text(),
            player_name=self.player_input.text()
        )
        self.download_thread.progress.connect(self.update_log)
        self.download_thread.finished.connect(self.on_download_finished)
        self.download_thread.start()

    def update_log(self, message):
        self.log_browser.append(message)
        self.log_browser.verticalScrollBar().setValue(
            self.log_browser.verticalScrollBar().maximum()
        )

    def on_download_finished(self, config):
        self.current_config = config
        self.java_label.setText(f"Java路径: {config['java_path']}")
        QMessageBox.information(self, "完成", "游戏安装完成！")

    def launch_game(self):
        if not self.current_config:
            QMessageBox.warning(self, "警告", "请先安装游戏")
            return

        command = [
            self.current_config['java_path'],
            *self.current_config['jvm_args'],
            *self.current_config['game_args']
        ]
        try:
            subprocess.Popen(command, creationflags=subprocess.CREATE_NEW_CONSOLE)
            self.log_browser.append("游戏已启动！")
        except Exception as e:
            self.log_browser.append(f"启动失败: {str(e)}")

if __name__ == '__main__':
    app = QApplication(sys.argv)
    
    # 确保资源目录存在
    if not os.path.exists('resources'):
        os.makedirs('resources')

    launcher = BlockLauncher()
    launcher.show()
    sys.exit(app.exec_())