# main_window.py
import sys
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                            QLabel, QLineEdit, QComboBox, QPushButton,
                            QStatusBar, QTabWidget, QFrame, QMessageBox)
from PyQt5.QtCore import Qt
from style_sheet import white, black
from LauncherGenerator import MinecraftLauncherGenerator

class BlockLaunchUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("BlockLaunch")
        self.setMinimumSize(800, 500)
        self.launcher = MinecraftLauncherGenerator(version="", player_name="")
        self.init_ui()
        self.apply_style('dark')

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
            self.loader_version_combo.setEnabled(False)

    def apply_style(self, theme='light'):
        style = white if theme == 'light' else black
        self.setStyleSheet(style)

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
            if loader_type != "无" and not loader_version:
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

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = BlockLaunchUI()
    window.show()
    sys.exit(app.exec_())