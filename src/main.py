from PyQt5.QtWidgets import QApplication, QMainWindow
from PyQt5.QtWebEngineWidgets import QWebEngineView, QWebEngineProfile
from PyQt5.QtCore import QUrl, Qt, QObject, pyqtSlot, QPoint, pyqtSignal, QSettings, QTimer
from PyQt5.QtGui import QRegion, QPainterPath, QMouseEvent
from LauncherGenerator import *
import sys
import os
import webbrowser
import json
import threading
from pathlib import Path
import subprocess

# 定义全局变量
GAMES_FILE = None
WORLDS_FILE = None

os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = "--use-gl=desktop"

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        log("初始化主窗口...", "Info")
        self.setWindowTitle("BlockLauncher")
        self.setGeometry(100, 100, 1280, 800)
        log("设置无边框窗口样式", "Info")
        self.setWindowFlags(Qt.FramelessWindowHint)
        
        # 窗口拖动相关变量
        self.dragging = False
        self.drag_position = QPoint()
        
        log("初始化浏览器组件...", "WebPages/Info")
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
        log(f"加载本地HTML文件: {html_path}", "WebPages/Info")
        self.browser.load(QUrl.fromLocalFile(html_path))
        self.setCentralWidget(self.browser)
        
        # 设置圆角窗口
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setStyleSheet('background: transparent;')
        
        log("初始化窗口遮罩", "WebPages/Info")
        # 创建圆角遮罩
        self.update_mask()
        
        log("绑定JS信号处理", "WebPages/Info")
        # 绑定JS信号
        self.browser.page().javaScriptConsoleMessage = self.on_js_console_message
        
        log("安装事件过滤器", "WebPages/Info")
        # 安装事件过滤器
        self.browser.installEventFilter(self)
        
        log("加载配置设置", "Info")
        # 加载设置
        SETTINGS_FILE = os.path.abspath(os.path.join(os.path.dirname(__file__), 'settings.ini'))
        self.settings = QSettings(SETTINGS_FILE, QSettings.IniFormat)
        
        # 定义游戏列表和世界列表文件路径
        global GAMES_FILE, WORLDS_FILE
        GAMES_FILE = os.path.abspath(os.path.join(os.path.dirname(__file__), 'games.json'))
        WORLDS_FILE = os.path.abspath(os.path.join(os.path.dirname(__file__), 'worlds.json'))
        
        # 加载游戏和世界列表
        self.installed_games = self.load_games()
        self.game_worlds = self.load_worlds()
        
        log("初始化WebChannel通信", "Info")
        # 设置WebChannel用于关闭功能
        try:
            from PyQt5.QtWebChannel import QWebChannel
            
            class Bridge(QObject):
                downloadProgress = pyqtSignal(int, str)  # 进度百分比, 状态文本
                downloadFinished = pyqtSignal(str, str)  # 下载完成，附带状态和游戏ID
                launchStatus = pyqtSignal(str, str)     # 启动状态
                gamesListChanged = pyqtSignal(str)      # 游戏列表更新信号
                
                def __init__(self, window):
                    super().__init__()
                    self.window = window

                @pyqtSlot()
                def closeApp(self):
                    self.window.close()

                @pyqtSlot(str, str, str)
                def downloadGame(self, version, player_name, loader_type="vanilla"):
                    log(f"开始下载游戏: {version}, 玩家: {player_name}, 类型: {loader_type}", "Info")
                    # 生成游戏ID
                    game_id = f"{version}_{loader_type}_{player_name}"
                    
                    def run_download():
                        try:
                            log(f"创建启动器生成器实例: {game_id}", "WebPages/Info")
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
                                except Exception as e:
                                    log(f"解析进度百分比失败: {e}", "WebPages/Warning")
                                    percent = 0
                                self.downloadProgress.emit(int(percent), str(msg) if msg is not None else "")
                            
                            # 临时替换log函数
                            original_log = getattr(__import__('builtins'), 'log', None)
                            setattr(__import__('builtins'), 'log', log_hook)
                            
                            # 执行下载
                            log(f"生成安装脚本: {game_id}", "Info")
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
                            log(f"添加新游戏到列表: {game_id}", "WebPages/Info")
                            self.window.add_game(game_data)
                            
                            # 发送游戏列表更新信号
                            self.gamesListChanged.emit(self.getGamesList())
                            
                            self.downloadProgress.emit(100, "下载完成")
                            self.downloadFinished.emit("success", game_id)
                        except Exception as e:
                            log(f"下载游戏失败: {e}", "Error")
                            self.downloadProgress.emit(0, f"下载失败: {e}")
                            self.downloadFinished.emit("fail", game_id)
                    
                    threading.Thread(target=run_download, daemon=True).start()
                
                @pyqtSlot(str)
                def launchGame(self, game_id):
                    """启动指定的游戏"""
                    log(f"启动游戏请求: {game_id}", "WebPages/Info")
                    game = self.window.get_game(game_id)
                    if not game:
                        log(f"游戏未找到: {game_id}", "WebPages/Warning")
                        self.launchStatus.emit(game_id, "游戏未找到")
                        return
                    
                    def run_launch():
                        try:
                            log(f"创建启动器实例: {game_id}", "WebPages/Info")
                            from src.LauncherGenerator import MinecraftLauncherGenerator
                            launcher = MinecraftLauncherGenerator(
                                version=game["version"],
                                player_name=game["player_name"],
                                loader_type=game["loader_type"]
                            )
                            
                            # 更新游戏信息
                            game["last_played"] = "刚刚"
                            game["play_count"] = game.get("play_count", 0) + 1
                            log(f"更新游戏信息: {game_id} (第{game['play_count']}次游玩)", "Info")
                            self.window.update_game(game)
                            
                            # 生成启动命令
                            log(f"生成启动脚本: {game_id}", "WebPages/Info")
                            config = launcher.generate_launch_script()
                            
                            # 构建命令
                            command = [config['java_path']] 
                            command.extend(config['jvm_args'])
                            command.extend(config['game_args'])
                            
                            log(f"执行启动命令: {' '.join(command)}", "Info")
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
                            
                            log(f"游戏启动成功: {game_id}", "Info")
                            self.launchStatus.emit(game_id, "success")
                        except Exception as e:
                            log(f"启动游戏失败: {e}", "Error")
                            self.launchStatus.emit(game_id, f"启动失败: {e}")
                    
                    threading.Thread(target=run_launch, daemon=True).start()
                
                @pyqtSlot()
                def openGameFolder(self):
                    """打开游戏文件夹"""
                    log("用户请求打开游戏文件夹", "WebPages/Info")
                    game_dir = Path(".minecraft")
                    if game_dir.exists():
                        try:
                            if sys.platform == "win32":
                                os.startfile(game_dir)
                            elif sys.platform == "darwin":
                                subprocess.Popen(["open", str(game_dir)])
                            else:
                                subprocess.Popen(["xdg-open", str(game_dir)])
                            log(f"成功打开游戏文件夹: {game_dir}", "WebPages/Info")
                        except Exception as e:
                            log(f"打开游戏文件夹失败: {e}", "Error")
                    else:
                        log(f"游戏文件夹不存在: {game_dir}", "WebPages/Warning")
                
                @pyqtSlot(str)
                def openUrl(self, url):
                    """打开外部链接"""
                    log(f"用户请求打开链接: {url}", "WebPages/Info")
                    webbrowser.open(url)

                @pyqtSlot(result=str)
                def getGamesList(self):
                    """获取游戏列表"""
                    log("前端请求获取游戏列表", "WebPages/Info")
                    try:
                        if not hasattr(self.window, 'installed_games'):
                            log("游戏列表未初始化", "WebPages/Warning")
                            return "[]"
                        
                        if self.window.installed_games is None:
                            log("游戏列表为空", "WebPages/Warning")
                            return "[]"
                        
                        games_list = json.dumps(self.window.installed_games, ensure_ascii=False)
                        log(f"返回游戏列表: {len(self.window.installed_games)}个游戏", "WebPages/Info")
                        return games_list
                    except Exception as e:
                        log(f"获取游戏列表失败: {e}", "Error")
                        return "[]"

            self.channel = QWebChannel()
            self.bridge = Bridge(self)
            self.channel.registerObject('pyBridge', self.bridge)
            self.browser.page().setWebChannel(self.channel)
            
            # 注入JavaScript关闭功能
            def inject_js():
                # 先注入 qwebchannel.js
                js_code = '''
                    (function() {
                        if (!window.QWebChannel) {
                            var script = document.createElement('script');
                            script.src = 'qrc:///qtwebchannel/qwebchannel.js';
                            script.onload = function() {
                                // QWebChannel加载完成后初始化
                                new QWebChannel(qt.webChannelTransport, function(channel) {
                                    window.pyBridge = channel.objects.pyBridge;

                                    // 初始化功能
                                    window.closeApp = function() { 
                                        try {
                                            window.pyBridge.closeApp(); 
                                        } catch (e) {
                                            console.error('关闭应用失败:', e);
                                            console.log("__CLOSE_APP__");
                                        }
                                    };

                                    // 获取游戏列表功能
                                    window.getGamesList = function() {
                                        try {
                                            return JSON.parse(window.pyBridge.getGamesList());
                                        } catch (e) {
                                            console.error('获取游戏列表失败:', e);
                                            return [];
                                        }
                                    };

                                    // 监听游戏列表更新
                                    window.pyBridge.gamesListChanged.connect(function(gamesList) {
                                        try {
                                            const games = JSON.parse(gamesList);
                                            window.dispatchEvent(new CustomEvent('gamesListUpdated', { 
                                                detail: games,
                                                bubbles: true,
                                                cancelable: true 
                                            }));
                                        } catch (e) {
                                            console.error('处理游戏列表更新失败:', e);
                                        }
                                    });

                                    // 触发初始化完成事件
                                    window.dispatchEvent(new CustomEvent('pyBridgeReady', { 
                                        bubbles: true,
                                        cancelable: true 
                                    }));

                                    console.log('PyBridge 初始化完成');
                                });
                            };
                            document.head.appendChild(script);
                        }
                    })();
                '''
                self.browser.page().runJavaScript(js_code)
            
            def delayed_inject():
                # 延迟200ms执行注入，确保页面完全加载
                QTimer.singleShot(200, inject_js)
            
            self.browser.loadFinished.connect(lambda ok: delayed_inject() if ok else log("页面加载失败", "Error"))
        except Exception as e:
            log(f"WebChannel初始化错误: {e}", "Error")
    
    def add_game(self, game_data):
        """添加游戏到已安装列表"""
        log(f"开始添加游戏: {game_data['id']}", "WebPages/Info")
        # 检查是否已存在
        if not any(game['id'] == game_data['id'] for game in self.installed_games):
            log(f"添加新游戏: {game_data['id']}", "WebPages/Info")
            self.installed_games.append(game_data)
            self.save_games()
        else:
            log(f"游戏已存在，跳过添加: {game_data['id']}", "WebPages/Info")

    def update_game(self, game_data):
        """更新游戏信息"""
        log(f"更新游戏信息: {game_data['id']}", "WebPages/Info")
        for i, game in enumerate(self.installed_games):
            if game['id'] == game_data['id']:
                log(f"更新游戏信息: {game_data['id']}", "WebPages/Info")
                self.installed_games[i] = game_data
                self.save_games()
                break
        else:
            log(f"未找到要更新的游戏: {game_data['id']}", "WebPages/Warning")

    def get_game(self, game_id):
        """获取指定游戏"""
        game = next((game for game in self.installed_games if game['id'] == game_id), None)
        if game:
            log(f"找到游戏: {game_id}", "WebPages/Info")
        else:
            log(f"未找到游戏: {game_id}", "WebPages/Warning")
        return game

    def load_games(self):
        """加载已安装游戏列表"""
        log("开始加载游戏列表", "WebPages/Info")
        try:
            if not Path(GAMES_FILE).exists():
                # 如果文件不存在，创建一个空的游戏列表文件
                log(f"创建新的游戏列表文件: {GAMES_FILE}", "WebPages/Info")
                with open(GAMES_FILE, 'w', encoding='utf-8') as f:
                    json.dump([], f, ensure_ascii=False, indent=4)
                return []
            
            with open(GAMES_FILE, 'r', encoding='utf-8') as f:
                games = json.load(f)
                log(f"已加载 {len(games)} 个游戏", "WebPages/Info")
                return games
        except Exception as e:
            log(f"加载游戏列表失败: {e}", "Error")
            return []

    def save_games(self):
        """保存游戏列表"""
        log("开始保存游戏列表", "WebPages/Info")
        try:
            with open(GAMES_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.installed_games, f, ensure_ascii=False, indent=4)
                log("游戏列表已保存", "WebPages/Info")
        except Exception as e:
            log(f"保存游戏列表失败: {e}", "Error")

    def load_worlds(self):
        """加载游戏世界列表"""
        log("开始加载世界列表", "WebPages/Info")
        try:
            if not Path(WORLDS_FILE).exists():
                # 如果文件不存在，创建一个空的世界列表文件
                log(f"创建新的世界列表文件: {WORLDS_FILE}", "WebPages/Info")
                with open(WORLDS_FILE, 'w', encoding='utf-8') as f:
                    json.dump([], f, ensure_ascii=False, indent=4)
                return []
            
            with open(WORLDS_FILE, 'r', encoding='utf-8') as f:
                worlds = json.load(f)
                log(f"已加载 {len(worlds)} 个世界", "WebPages/Info")
                return worlds
        except Exception as e:
            log(f"加载世界列表失败: {e}", "Error")
            return []

    def save_worlds(self):
        """保存世界列表"""
        log("开始保存世界列表", "WebPages/Info")
        try:
            with open(WORLDS_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.game_worlds, f, ensure_ascii=False, indent=4)
                log("世界列表已保存", "WebPages/Info")
        except Exception as e:
            log(f"保存世界列表失败: {e}", "Error")

    def update_mask(self):
        """更新窗口圆角遮罩"""
        log("更新窗口遮罩", "Info")
        path = QPainterPath()
        path.addRoundedRect(0, 0, self.width(), self.height(), 18, 18)
        region = QRegion(path.toFillPolygon().toPolygon())
        self.setMask(region)

    def resizeEvent(self, event):
        """窗口大小改变时更新遮罩"""
        log(f"窗口大小调整: {self.width()}x{self.height()}", "Info")
        self.update_mask()
        super().resizeEvent(event)

    def handle_mouse_press(self, event):
        """处理鼠标按下事件"""
        if event.button() == Qt.LeftButton:
            log(f"鼠标按下位置: {event.pos()}", "WebPages/Info")
            # 获取鼠标在标题栏区域的位置
            element = self.browser.page().hitTestContent(event.pos())
            
            # 检查是否在标题栏区域
            if element.elementId() == "custom-titlebar" or element.parentElementId() == "custom-titlebar":
                # 排除关闭按钮
                if element.elementId() != "close-btn":
                    log("检测到标题栏拖拽开始", "WebPages/Info")
                    self.dragging = True
                    self.drag_position = event.globalPos() - self.frameGeometry().topLeft()
                    event.accept()
                    return True
        
        return False

    def handle_mouse_move(self, event):
        """处理鼠标移动事件"""
        if self.dragging and event.buttons() & Qt.LeftButton:
            log(f"窗口拖拽移动: {event.globalPos()}", "WebPages/Info")
            self.move(event.globalPos() - self.drag_position)
            event.accept()
            return True
        
        return False

    def handle_mouse_release(self, event):
        """处理鼠标释放事件"""
        if event.button() == Qt.LeftButton and self.dragging:
            log("检测到标题栏拖拽结束", "WebPages/Info")
            self.dragging = False
            event.accept()
            return True
        
        return False

    def on_js_console_message(self, level, message, line, sourceID):
        """处理JavaScript控制台消息"""
        if message == "__CLOSE_APP__":
            log("收到JS关闭请求", "WebPages/Info")
            self.close()
        else:
            log(f"JS控制台消息: {message} (行{line})", "WebPages/Info")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())