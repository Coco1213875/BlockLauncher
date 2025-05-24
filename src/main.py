# main.py
import sys
import subprocess
import configparser
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QPushButton, QLabel, QScrollArea, QListWidget, QStatusBar, 
    QMenu, QAction, QMessageBox, QStackedWidget)
from PyQt5.QtGui import QIcon, QFont
from PyQt5.QtCore import Qt, QSize, QThread, pyqtSignal
from style_sheet import apply_theme
from LauncherGenerator import MinecraftLauncherGenerator, log

class DownloadThread(QThread):
    """用于后台执行下载安装的线程"""
    output_signal = pyqtSignal(str, str)  # (消息, 模式)
    
    def __init__(self, launcher):
        super().__init__()
        self.launcher = launcher
        
    def run(self):
        try:
            # 执行下载安装操作
            self.output_signal.emit("开始下载安装游戏文件...", "Info")
            self.launcher.generate_install_script()
            self.output_signal.emit("游戏文件下载安装完成", "Success")
        except Exception as e:
            self.output_signal.emit(f"下载安装失败：{str(e)}", "Error")

class LaunchThread(QThread):
    """用于后台执行启动命令的线程"""
    output_signal = pyqtSignal(str, str)  # (消息, 模式)
    
    def __init__(self, config):
        super().__init__()
        self.config = config
        
    def run(self):
        try:
            # 构建完整命令
            cmd = [
                self.config['java_path'],
                *self.config['jvm_args'],
                *self.config['game_args']
            ]
            
            # 启动游戏进程
            self.output_signal.emit("正在启动游戏...", "Info")
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True,
                bufsize=1,
                encoding='utf-8'
            )
            
            # 实时输出日志
            while True:
                line = process.stdout.readline()
                if not line:
                    break
                self.output_signal.emit(line.strip(), "GameLog")
            
            process.wait()
            self.output_signal.emit(f"游戏进程已退出，代码：{process.returncode}", "Info")
            
        except Exception as e:
            self.output_signal.emit(f"启动失败：{str(e)}", "Error")

class BlockLauncher(QMainWindow):
    def __init__(self):
        super().__init__()
        self.launch_thread = None  # 后台线程实例
        self.download_thread = None  # 下载线程实例
        self.scaling_factor = self.load_scaling_config()
        self.setWindowTitle("Block Launcher")
        self.setGeometry(100, 100, 1000, 600)
        self.init_ui()
    
    def load_scaling_config(self):
        """从 BL.ini 中读取缩放比例"""
        config = configparser.ConfigParser()
        try:
            # 添加 encoding='utf-8' 参数确保以 UTF-8 解码
            config.read('BL.ini', encoding='utf-8')
            return config.getfloat('UI', 'Scaling', fallback=1.0)
        except Exception as e:
            print(f"读取 BL.ini 失败: {e}")
            return 1.0
    
    def apply_scaling(self):
        """全局缩放：调整字体、按钮、列表项等"""
        font = self.font()
        font.setPointSize(int(font.pointSize() * self.scaling_factor))
        self.setFont(font)

        # 调整侧边栏按钮字体和高度
        for btn in self.findChildren(QPushButton):
            if btn.parent() and btn.parent().objectName() == "sidebar":
                sidebar_font = QFont("src/resources/fonts/NotoSansSC-Regular.ttf", 
                                   int(10 * self.scaling_factor))  # 字体大小随缩放
                btn.setFont(sidebar_font)
                btn.setFixedHeight(int(40 * self.scaling_factor))
        
        # 调整游戏列表项高度
        for item in self.findChildren(QWidget, name="game-item"):
            item.setFixedHeight(int(100 * self.scaling_factor))

    def init_ui(self):
        # 创建菜单栏
        self.create_menu()

        # 主界面布局
        main_widget = QWidget()
        main_layout = QHBoxLayout(main_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # 侧边栏
        sidebar = self.create_sidebar()
        main_layout.addWidget(sidebar, stretch=1)

        # 主内容区域
        self.stacked_widget = self.create_main_content()  # 替换为 QStackedWidget
        main_layout.addWidget(self.stacked_widget, stretch=4)

        # 状态栏
        status_bar = QStatusBar()
        status_bar.showMessage("就绪 | 当前账户：未登录")
        self.setStatusBar(status_bar)

        self.setCentralWidget(main_widget)
        self.apply_scaling()

    def create_menu(self):
        """创建顶部菜单栏"""
        menubar = self.menuBar()
        
        # 文件菜单
        file_menu = menubar.addMenu('文件')
        settings_action = QAction('设置', self)
        settings_action.triggered.connect(self.open_settings)
        file_menu.addAction(settings_action)
        
        # 帮助菜单
        help_menu = menubar.addMenu('帮助')
        about_action = QAction('关于', self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)

    def create_sidebar(self):
        sidebar = QWidget()
        sidebar.setObjectName("sidebar")
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(5, 10, 5, 10)
        layout.setSpacing(8)

        buttons = [
            ("开始游戏", "home.svg"),
            ("版本选择", "version.svg"),
            ("模组管理", "mods.svg"),
            ("资源下载", "download.svg"),
            ("联机游戏", "network.svg"),
            ("游戏设置", "settings.svg")
        ]

        for i, (text, icon) in enumerate(buttons):
            btn = QPushButton(text)
            btn.setIcon(QIcon(f"src/resources/icons/{icon}"))
            btn.setIconSize(QSize(24, 24))
            btn.setFont(QFont("src/resources/fonts/NotoSansSC-Regular.ttf", 10))
            btn.setFixedHeight(int(40 * self.scaling_factor)) 
            btn.clicked.connect(lambda _, idx=i: self.switch_page(idx))  # 绑定切换事件
            layout.addWidget(btn)

        layout.addStretch()
        return sidebar

    def create_main_content(self):
        stacked = QStackedWidget()

        # 页面 1：游戏列表
        game_list_page = QWidget()
        game_layout = QVBoxLayout(game_list_page)
        game_layout.setAlignment(Qt.AlignTop)

        # 标题栏
        title = QLabel("游戏列表")
        title.setFont(QFont("src/resources/fonts/NotoSansSC-Regular.ttf", 14, QFont.Bold))
        title.setStyleSheet("padding: 15px;")
        game_layout.addWidget(title)

        # 游戏列表
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)

        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setAlignment(Qt.AlignTop)

        for i in range(10):
            game_item = self.create_game_item(
                f"我的世界 1.{18+i}.2",
                f"Forge 36.2.0 | Java 8",
                "最近游玩：2023-08-20"
            )
            content_layout.addWidget(game_item)

        scroll_area.setWidget(content_widget)
        game_layout.addWidget(scroll_area)

        stacked.addWidget(game_list_page)

        # 页面 2：模组管理（占位）
        mod_page = QWidget()
        mod_layout = QVBoxLayout(mod_page)
        mod_layout.addWidget(QLabel("模组管理页面"))
        stacked.addWidget(mod_page)

        # 页面 3：资源下载（占位）
        download_page = QWidget()
        download_layout = QVBoxLayout(download_page)
        download_layout.addWidget(QLabel("资源下载页面"))
        stacked.addWidget(download_page)

        # 页面 4：联机游戏（占位）
        online_page = QWidget()
        online_layout = QVBoxLayout(online_page)
        online_layout.addWidget(QLabel("联机游戏页面"))
        stacked.addWidget(online_page)

        # 页面 5：游戏设置（占位）
        settings_page = QWidget()
        settings_layout = QVBoxLayout(settings_page)
        settings_layout.addWidget(QLabel("游戏设置页面"))
        stacked.addWidget(settings_page)

        # 页面 6：版本选择（占位）
        version_page = QWidget()
        version_layout = QVBoxLayout(version_page)
        version_layout.addWidget(QLabel("版本选择页面"))
        stacked.addWidget(version_page)

        return stacked

    def create_game_item(self, title, subtitle, info):
        item = QWidget()
        item.setObjectName("game-item")
        item.setFixedHeight(int(100 * self.scaling_factor))

        layout = QHBoxLayout(item)
        layout.setContentsMargins(20, 10, 20, 10)

        # 图标
        icon = QLabel()
        icon.setPixmap(QIcon("src/resources/icons/mc_icon.png").pixmap(64, 64))
        layout.addWidget(icon)

        # 文字信息
        text_layout = QVBoxLayout()
        title_label = QLabel(title)
        title_label.setProperty("class", "title")
        
        subtitle_label = QLabel(subtitle)
        subtitle_label.setProperty("class", "subtitle")
        
        info_label = QLabel(info)
        info_label.setProperty("class", "info")

        text_layout.addWidget(title_label)
        text_layout.addWidget(subtitle_label)
        text_layout.addWidget(info_label)
        text_layout.addStretch()
        layout.addLayout(text_layout, stretch=3)

        # 操作按钮
        btn_layout = QVBoxLayout()
        btn_layout.setSpacing(5)
        
        launch_btn = QPushButton("启动游戏")
        launch_btn.setProperty("class", "launch-btn")
        launch_btn.setFixedWidth(100)
        launch_btn.clicked.connect(lambda _, t=title: self.handle_launch(t))
        
        option_btn = QPushButton("版本设置")
        option_btn.setProperty("class", "option-btn")
        option_btn.setFixedWidth(100)

        btn_layout.addWidget(launch_btn)
        btn_layout.addWidget(option_btn)
        btn_layout.addStretch()
        layout.addLayout(btn_layout, stretch=1)

        return item

    def handle_launch(self, version_name):
        """处理启动游戏逻辑"""
        try:
            # 提取版本号（示例：从"我的世界 1.20.4"提取1.20.4）
            version = version_name.split()[-1]
            
            # 初始化启动器生成器
            launcher = MinecraftLauncherGenerator(
                version=version,
                loader_type="fabric",
                loader_version="0.15.11",
                player_name="Player"
            )
            
            # 生成安装脚本（首次启动需要下载）
            reply = QMessageBox.question(
                self, '确认', '需要先安装游戏文件，是否继续？',
                QMessageBox.Yes | QMessageBox.No
            )
            if reply == QMessageBox.Yes:
                # 启动下载线程
                self.download_thread = DownloadThread(launcher)
                self.download_thread.output_signal.connect(self.update_status)
                self.download_thread.start()
            
            # 生成启动配置（下载完成后才能执行）
            # 注：实际应在线程完成后触发，此处仅做代码示例
            config = launcher.generate_launch_script()
            
            # 启动后台线程执行命令
            self.launch_thread = LaunchThread(config)
            self.launch_thread.output_signal.connect(self.update_status)
            self.launch_thread.start()
            
        except Exception as e:
            self.statusBar().showMessage(f"错误：{str(e)}", 5000)
            log(f"启动失败: {str(e)}", "Error")
            QMessageBox.critical(self, "错误", str(e))

    def update_status(self, message, mode):
        """更新状态栏和日志"""
        if mode == "GameLog":
            print(f"[游戏日志] {message}")  # 可替换为日志窗口
        else:
            self.statusBar().showMessage(message, 5000)
        
        # 错误弹窗
        if mode == "Error":
            QMessageBox.critical(self, "错误", message)

    def open_settings(self):
        QMessageBox.information(self, "设置", "此功能暂未实现")

    def show_about(self):
        QMessageBox.about(self, "关于", "Block启动器\n版本 1.0.0")

    def closeEvent(self, event):
        if self.launch_thread and self.launch_thread.isRunning():
            reply = QMessageBox.question(
                self, '确认退出',
                '游戏正在运行，确定要退出启动器吗？',
                QMessageBox.Yes | QMessageBox.No
            )
            if reply == QMessageBox.Yes:
                self.launch_thread.terminate()
                event.accept()
            else:
                event.ignore()
        else:
            event.accept()

    def switch_page(self, index):
        """切换主内容区域的页面"""
        self.stacked_widget.setCurrentIndex(index)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    # 应用主题（light 或 dark）
    apply_theme("light", app)
    
    window = BlockLauncher()
    window.show()
    sys.exit(app.exec_())