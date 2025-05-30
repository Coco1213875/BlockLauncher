from PyQt5.QtWidgets import QApplication, QMainWindow, QFileDialog, QMessageBox
from PyQt5.QtWebEngineWidgets import QWebEngineView, QWebEngineProfile
from PyQt5.QtCore import QUrl, Qt, QObject, pyqtSlot, QPoint, pyqtSignal, QSettings
from PyQt5.QtGui import QRegion, QPainterPath, QMouseEvent
import sys
import os
import json
import threading
from pathlib import Path
import subprocess
import webbrowser
from datetime import datetime

# 初始化日志
def init_log():
    log_path = Path("BL.log")
    with open(log_path, "w") as f:
        f.write(f"-----====***[{datetime.now().strftime('%H%M%S')}]开始记录log***====-----\n")

def log(message, mode="Info"):
    timestamp = datetime.now().strftime("%H%M%S")
    try :
        print(f"[{timestamp}] | [{mode}] {message}", flush=True)
        with open("BL.log", "a") as f:
            f.write(f"[{timestamp}] | [{mode}] {message}\n")
    except Exception as e:
        print(f"[{timestamp}] | [Error] 错误地引用log函数: {e}", flush=True)
        with open("BL.log", "a") as f:
            f.write(f"[{timestamp}] | [Error] 错误地引用log函数: {e}\n")

os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = "--use-gl=desktop"

# 全局设置
SETTINGS_FILE = "blocklauncher.ini"
GAMES_FILE = "games.json"
WORLDS_FILE = "worlds.json"

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        log("初始化主窗口...")
        self.setWindowTitle("BlockLauncher")
        self.setGeometry(100, 100, 1280, 800)
        self.setWindowFlags(self.windowFlags() | Qt.FramelessWindowHint)
        
        # 窗口拖动相关变量
        self.dragging = False
        self.drag_position = QPoint()
        
        # 设置User-Agent为Chrome
        profile = QWebEngineProfile.defaultProfile()
        profile.setHttpUserAgent("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")
        
        from PyQt5.QtWebEngineWidgets import QWebEnginePage
        page = QWebEnginePage(profile, self)
        self.browser = QWebEngineView()
        self.browser.setPage(page)
        self.browser.setZoomFactor(1.0)
        self.browser.setAttribute(Qt.WA_TransparentForMouseEvents, False)
        
        html_path = os.path.abspath(os.path.join(os.path.dirname(__file__), 'resources', 'pages', 'index.html'))
        self.browser.load(QUrl.fromLocalFile(html_path))
        self.setCentralWidget(self.browser)
        
        # 设置圆角窗口
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setStyleSheet('background: transparent;')
        
        # 创建圆角遮罩
        self.update_mask()
        
        # 绑定JS信号
        self.browser.page().javaScriptConsoleMessage = self.on_js_console_message
        
        # 安装事件过滤器
        self.browser.installEventFilter(self)
        
        # 加载设置
        self.settings = QSettings(SETTINGS_FILE, QSettings.IniFormat)
        self.installed_games = self.load_games()
        self.game_worlds = self.load_worlds()
        
        # 设置WebChannel用于关闭功能
        try:
            from PyQt5.QtWebChannel import QWebChannel
            
            class Bridge(QObject):
                downloadProgress = pyqtSignal(int, str)  # 进度百分比, 状态文本
                downloadFinished = pyqtSignal(str, str)  # 状态, 游戏ID
                launchStatus = pyqtSignal(str, str)      # 游戏ID, 状态
                worldsUpdated = pyqtSignal(str)          # 世界列表JSON
                
                def __init__(self, window):
                    super().__init__()
                    self.window = window

                @pyqtSlot()
                def closeApp(self):
                    self.window.close()

                @pyqtSlot(str, str, str)
                def downloadGame(self, version, player_name, loader_type="vanilla"):
                    import threading
                    from src.LauncherGenerator import MinecraftLauncherGenerator
                    
                    # 生成游戏ID
                    game_id = f"{version}_{loader_type}_{player_name}"
                    
                    def run_download():
                        try:
                            launcher = MinecraftLauncherGenerator(
                                version=version, 
                                player_name=player_name, 
                                loader_type=loader_type
                            )
                            
                            # 覆盖log函数，实时推送进度
                            def log_hook(msg, mode="Info"):
                                percent = 0
                                try:
                                    # 尝试从msg中提取百分比
                                    if isinstance(msg, str) and ("%" in msg or "进度" in msg):
                                        import re
                                        m = re.search(r"(\d{1,3})%", msg)
                                        if m:
                                            percent = int(m.group(1))
                                except Exception:
                                    percent = 0
                                self.downloadProgress.emit(int(percent), str(msg) if msg is not None else "")
                            
                            # 临时替换log函数
                            original_log = getattr(__import__('builtins'), 'log', None)
                            setattr(__import__('builtins'), 'log', log_hook)
                            
                            # 执行下载
                            launcher.generate_install_script()
                            
                            # 恢复原始log函数
                            if original_log:
                                setattr(__import__('builtins'), 'log', original_log)
                            
                            # 添加游戏到已安装列表
                            game_data = {
                                "id": game_id,
                                "version": version,
                                "player_name": player_name,
                                "loader_type": loader_type,
                                "last_played": "",
                                "play_count": 0
                            }
                            self.window.add_game(game_data)
                            
                            self.downloadProgress.emit(100, "下载完成")
                            self.downloadFinished.emit("success", game_id)
                        except Exception as e:
                            self.downloadProgress.emit(0, f"下载失败: {e}")
                            self.downloadFinished.emit("fail", game_id)
                    
                    threading.Thread(target=run_download, daemon=True).start()
                
                @pyqtSlot(str)
                def launchGame(self, game_id):
                    """启动指定的游戏"""
                    game = self.window.get_game(game_id)
                    if not game:
                        self.launchStatus.emit(game_id, "游戏未找到")
                        return
                    
                    def run_launch():
                        try:
                            from src.LauncherGenerator import MinecraftLauncherGenerator
                            launcher = MinecraftLauncherGenerator(
                                version=game["version"],
                                player_name=game["player_name"],
                                loader_type=game["loader_type"]
                            )
                            
                            # 更新游戏信息
                            game["last_played"] = "刚刚"
                            game["play_count"] = game.get("play_count", 0) + 1
                            self.window.update_game(game)
                            
                            # 生成启动命令
                            config = launcher.generate_launch_script()
                            
                            # 构建命令
                            command = [config['java_path']] 
                            command.extend(config['jvm_args'])
                            command.extend(config['game_args'])
                            
                            # 启动游戏
                            if sys.platform == "win32":
                                # Windows下创建新控制台窗口
                                subprocess.Popen(
                                    command, 
                                    creationflags=subprocess.CREATE_NEW_CONSOLE
                                )
                            else:
                                # Linux/MacOS
                                subprocess.Popen(command)
                            
                            self.launchStatus.emit(game_id, "success")
                        except Exception as e:
                            self.launchStatus.emit(game_id, f"启动失败: {e}")
                    
                    threading.Thread(target=run_launch, daemon=True).start()
                
                @pyqtSlot(str)
                def loadWorld(self, world_name):
                    """加载指定的游戏世界"""
                    try:
                        # 在实际实现中，这里会调用游戏启动命令并指定世界
                        print(f"加载世界: {world_name}")
                        # 这里只是模拟
                        QMessageBox.information(
                            self.window, 
                            "世界加载", 
                            f"正在加载世界: {world_name}"
                        )
                    except Exception as e:
                        print(f"加载世界失败: {e}")

                @pyqtSlot(str)
                def createWorld(self, world_name):
                    """创建新的游戏世界"""
                    try:
                        # 在实际实现中，这里会调用游戏命令创建新世界
                        print(f"创建世界: {world_name}")
                        # 添加到世界列表
                        world_data = {
                            "name": world_name,
                            "game_id": "current_game",  # 实际应关联到特定游戏
                            "created": "2023-10-15",
                            "last_played": ""
                        }
                        self.window.add_world(world_data)
                        
                        # 更新UI
                        self.worldsUpdated.emit(json.dumps(self.window.game_worlds))
                        
                        QMessageBox.information(
                            self.window, 
                            "世界创建", 
                            f"已创建世界: {world_name}"
                        )
                    except Exception as e:
                        print(f"创建世界失败: {e}")
                
                @pyqtSlot()
                def getInstalledGames(self):
                    """获取已安装的游戏列表"""
                    return json.dumps(self.window.installed_games)
                
                @pyqtSlot()
                def getGameWorlds(self):
                    """获取游戏世界列表"""
                    return json.dumps(self.window.game_worlds)
                
                @pyqtSlot(str, str, str)
                def setSetting(self, key, value, category="general"):
                    """保存设置"""
                    self.window.settings.setValue(f"{category}/{key}", value)
                
                @pyqtSlot(str, str)
                def getSetting(self, key, category="general", default=""):
                    """获取设置"""
                    return self.window.settings.value(f"{category}/{key}", default)
                
                @pyqtSlot()
                def openGameFolder(self):
                    """打开游戏文件夹"""
                    game_dir = Path(".minecraft")
                    if game_dir.exists():
                        if sys.platform == "win32":
                            os.startfile(game_dir)
                        elif sys.platform == "darwin":
                            subprocess.Popen(["open", str(game_dir)])
                        else:
                            subprocess.Popen(["xdg-open", str(game_dir)])
                
                @pyqtSlot(str)
                def openUrl(self, url):
                    """打开外部链接"""
                    webbrowser.open(url)

            self.channel = QWebChannel()
            self.bridge = Bridge(self)
            self.channel.registerObject('pyBridge', self.bridge)
            self.browser.page().setWebChannel(self.channel)
            
            # 注入JavaScript功能
            def inject_js():
                self.browser.page().runJavaScript('''
                    (function(){
                        if (typeof qt !== 'undefined' && qt.pyBridge) {
                            // 关闭功能
                            window.closeApp = function() { qt.pyBridge.closeApp(); };
                            
                            // 游戏功能
                            window.launchGame = function(gameId) { qt.pyBridge.launchGame(gameId); };
                            window.loadWorld = function(worldName) { qt.pyBridge.loadWorld(worldName); };
                            window.createWorld = function(worldName) { qt.pyBridge.createWorld(worldName); };
                            
                            // 设置功能
                            window.setSetting = function(key, value, category) { 
                                qt.pyBridge.setSetting(key, value, category); 
                            };
                            window.getSetting = function(key, category, defaultValue) { 
                                return qt.pyBridge.getSetting(key, category, defaultValue); 
                            };
                            
                            // 实用功能
                            window.openGameFolder = function() { qt.pyBridge.openGameFolder(); };
                            window.openUrl = function(url) { qt.pyBridge.openUrl(url); };
                            
                            // 获取数据
                            window.getInstalledGames = function() { 
                                return qt.pyBridge.getInstalledGames(); 
                            };
                            window.getGameWorlds = function() { 
                                return qt.pyBridge.getGameWorlds(); 
                            };
                        } else {
                            console.log("Python功能不可用");
                        }
                    })();
                ''')
            
            self.browser.loadFinished.connect(lambda ok: inject_js())
        except Exception as e:
            print(f"WebChannel初始化错误: {e}")
    
    def add_game(self, game_data):
        """添加游戏到已安装列表"""
        # 检查是否已存在
        if not any(game['id'] == game_data['id'] for game in self.installed_games):
            log(f"添加新游戏: {game_data['id']}")
            self.installed_games.append(game_data)
            self.save_games()
    
    def update_game(self, game_data):
        """更新游戏信息"""
        for i, game in enumerate(self.installed_games):
            if game['id'] == game_data['id']:
                log(f"更新游戏信息: {game_data['id']}")
                self.installed_games[i] = game_data
                self.save_games()
                break
    
    def get_game(self, game_id):
        """获取指定游戏"""
        for game in self.installed_games:
            if game['id'] == game_id:
                log(f"获取游戏信息: {game_id}")
                return game
        log(f"游戏未找到: {game_id}", "Warning")
        return None
    
    def add_world(self, world_data):
        """添加游戏世界"""
        log(f"添加新世界: {world_data['name']}")
        self.game_worlds.append(world_data)
        self.save_worlds()
    
    def load_games(self):
        """加载已安装游戏列表"""
        try:
            if Path(GAMES_FILE).exists():
                with open(GAMES_FILE, 'r') as f:
                    games = json.load(f)
                    log(f"已加载 {len(games)} 个游戏")
                    return games
        except Exception as e:
            log(f"加载游戏列表失败: {e}", "Error")
        return []
    
    def save_games(self):
        """保存游戏列表"""
        try:
            with open(GAMES_FILE, 'w') as f:
                json.dump(self.installed_games, f)
                log("游戏列表已保存")
        except Exception as e:
            log(f"保存游戏列表失败: {e}", "Error")
    
    def load_worlds(self):
        """加载游戏世界列表"""
        try:
            if Path(WORLDS_FILE).exists():
                with open(WORLDS_FILE, 'r') as f:
                    worlds = json.load(f)
                    log(f"已加载 {len(worlds)} 个世界")
                    return worlds
        except Exception as e:
            log(f"加载世界列表失败: {e}", "Error")
        return []
    
    def save_worlds(self):
        """保存世界列表"""
        try:
            with open(WORLDS_FILE, 'w') as f:
                json.dump(self.game_worlds, f)
                log("世界列表已保存")
        except Exception as e:
            log(f"保存世界列表失败: {e}", "Error")
    
    def update_mask(self):
        """更新窗口圆角遮罩"""
        path = QPainterPath()
        path.addRoundedRect(0, 0, self.width(), self.height(), 18, 18)
        region = QRegion(path.toFillPolygon().toPolygon())
        self.setMask(region)
    
    def resizeEvent(self, event):
        """窗口大小改变时更新遮罩"""
        self.update_mask()
        super().resizeEvent(event)
    
    def eventFilter(self, obj, event):
        """事件过滤器处理鼠标事件"""
        if obj == self.browser:
            # 处理鼠标按下事件
            if event.type() == QMouseEvent.MouseButtonPress:
                return self.handle_mouse_press(event)
            
            # 处理鼠标移动事件
            elif event.type() == QMouseEvent.MouseMove:
                return self.handle_mouse_move(event)
            
            # 处理鼠标释放事件
            elif event.type() == QMouseEvent.MouseButtonRelease:
                return self.handle_mouse_release(event)
        
        return super().eventFilter(obj, event)
    
    def handle_mouse_press(self, event):
        """处理鼠标按下事件"""
        if event.button() == Qt.LeftButton:
            # 获取鼠标在标题栏区域的位置
            element = self.browser.page().hitTestContent(event.pos())
            
            # 检查是否在标题栏区域
            if element.elementId() == "custom-titlebar" or element.parentElementId() == "custom-titlebar":
                # 排除关闭按钮
                if element.elementId() != "close-btn":
                    self.dragging = True
                    self.drag_position = event.globalPos() - self.frameGeometry().topLeft()
                    event.accept()
                    return True
        
        return False
    
    def handle_mouse_move(self, event):
        """处理鼠标移动事件"""
        if self.dragging and event.buttons() & Qt.LeftButton:
            self.move(event.globalPos() - self.drag_position)
            event.accept()
            return True
        
        return False
    
    def handle_mouse_release(self, event):
        """处理鼠标释放事件"""
        if event.button() == Qt.LeftButton and self.dragging:
            self.dragging = False
            event.accept()
            return True
        
        return False
    
    def on_js_console_message(self, level, message, line, sourceID):
        """处理JavaScript控制台消息"""
        if message == "__CLOSE_APP__":
            self.close()

if __name__ == "__main__":
    init_log()  # 初始化日志
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())