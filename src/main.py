import os
import sys
import json
import time
import logging
import platform
import subprocess
import threading
import datetime
import psutil
from pathlib import Path

# 设置环境变量以修复编码问题
os.environ['PYTHONIOENCODING'] = 'utf-8'

# 如果是Windows系统，设置控制台代码页
if sys.platform == 'win32':
    os.system('chcp 65001')

# 设置Qt WebEngine相关环境变量
os.environ['QTWEBENGINE_CHROMIUM_FLAGS'] = '--disable-logging --log-level=3'
os.environ['QTWEBENGINE_REMOTE_DEBUGGING'] = '9222'

from PyQt5.QtWidgets import QApplication, QMainWindow
from PyQt5.QtWebEngineWidgets import QWebEngineView, QWebEngineProfile, QWebEnginePage, QWebEngineScript
from PyQt5.QtCore import QUrl, QObject, pyqtSlot, QPoint, pyqtSignal, QSettings, Qt
from PyQt5.QtGui import QRegion, QPainterPath, QMouseEvent, QIcon
from PyQt5.QtWebChannel import QWebChannel
from LauncherGenerator import MinecraftLauncherGenerator

# Windows API 定义
if sys.platform == "win32":
    import ctypes
    from ctypes import wintypes

    kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
    
    PROCESS_TERMINATE = 0x0001
    PROCESS_QUERY_INFORMATION = 0x0400
    
    kernel32.OpenProcess.argtypes = [
        wintypes.DWORD,
        wintypes.BOOL,
        wintypes.DWORD
    ]
    kernel32.OpenProcess.restype = wintypes.HANDLE
    
    kernel32.TerminateProcess.argtypes = [
        wintypes.HANDLE,
        wintypes.UINT
    ]
    kernel32.TerminateProcess.restype = wintypes.BOOL
    
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.CloseHandle.restype = wintypes.BOOL

# 日志系统优化
LOG_DIR = Path("logs")
LOG_MAX_SIZE = 5 * 1024 * 1024  # 5MB
LOG_MAX_DAYS = 7

def rotate_logs():
    """优化的日志轮转功能"""
    try:
        latest_log = LOG_DIR / "BL.log"
        if latest_log.exists() and latest_log.stat().st_size > LOG_MAX_SIZE:
            today = datetime.datetime.now().strftime("%Y-%m-%d")
            new_log = LOG_DIR / f"BL-{today}-{len(list(LOG_DIR.glob(f'BL-{today}-*.log'))) + 1}.log"
            latest_log.rename(new_log)
            latest_log.touch()
            logger.info(f"日志已轮转至: {new_log.name}")
    except Exception as e:
        logger.error(f"日志轮转失败: {str(e)}")

def clean_old_logs(days=LOG_MAX_DAYS):
    """优化的日志清理功能"""
    try:
        now = datetime.datetime.now()
        deleted = 0
        for log_file in LOG_DIR.glob("BL-*.log"):
            try:
                if (now - datetime.datetime.fromtimestamp(log_file.stat().st_mtime)).days > days:
                    log_file.unlink()
                    deleted += 1
            except Exception as e:
                logger.error(f"清理日志失败 {log_file.name}: {str(e)}")
        logger.info(f"已清理 {deleted} 个过期日志文件")
    except Exception as e:
        logger.error(f"日志清理失败: {str(e)}")

# 确保日志目录存在
LOG_DIR.mkdir(exist_ok=True)

# 配置日志处理器
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# 清理现有处理器
for handler in logger.handlers[:]:
    logger.removeHandler(handler)

# 文件处理器
file_handler = logging.FileHandler(LOG_DIR / "BL.log", encoding='utf-8')
file_handler.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(message)s', '%H:%M:%S'))

# 控制台处理器
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(message)s', '%H:%M:%S'))
console_handler.setStream(sys.stdout)

# 将处理器添加到日志记录器
logger.addHandler(file_handler)
logger.addHandler(console_handler)

logger.info("日志系统初始化完成，使用UTF-8编码")

class Bridge(QObject):
    """用于和JavaScript通信的桥接对象"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        logger.info("Bridge对象初始化")
    
    @pyqtSlot(result=str)
    def ping(self):
        """测试WebChannel连接是否正常"""
        logger.info("收到ping请求")
        return "pong"
    
    @pyqtSlot()
    def minimizeWindow(self):
        """最小化窗口"""
        logger.info("收到最小化窗口请求")
        if self.parent():
            self.parent().showMinimized()
            logger.info("窗口已最小化")
        else:
            logger.error("无法最小化窗口：找不到父窗口")
    
    @pyqtSlot()
    def closeApp(self):
        """关闭应用程序"""
        logger.info("收到关闭应用程序请求")
        if self.parent():
            self.parent().close()
            logger.info("应用程序正在关闭")
        else:
            logger.error("无法关闭应用程序：找不到父窗口")
            
    @pyqtSlot(result=str)
    def getGamesList(self):
        """获取游戏列表"""
        try:
            logger.info("收到获取游戏列表请求")
            if self.parent():
                games = self.parent().installed_games
                return json.dumps(games, ensure_ascii=False)
            else:
                logger.error("无法获取游戏列表：找不到父窗口")
                return "[]"
        except Exception as e:
            logger.error(f"获取游戏列表失败: {str(e)}")
            return "[]"
    
    @pyqtSlot(str, result=bool)
    def launchGame(self, game_id):
        """启动游戏"""
        try:
            logger.info(f"收到启动游戏请求: {game_id}")
            if self.parent():
                return self.parent().launch_game(game_id)
            else:
                logger.error("无法启动游戏：找不到父窗口")
                return False
        except Exception as e:
            logger.error(f"启动游戏失败: {str(e)}")
            return False
            
    @pyqtSlot(str, str, str, str, result=bool)
    def downloadGame(self, version, player_name, loader_type, loader_version=None):
        """下载游戏"""
        try:
            logger.info(f"收到下载游戏请求: {version} {loader_type}")
            if self.parent():
                self.parent().download_game(version, player_name, loader_type, loader_version)
                return True
            else:
                logger.error("无法下载游戏：找不到父窗口")
                return False
        except Exception as e:
            logger.error(f"下载游戏失败: {str(e)}")
            return False
    
    @pyqtSlot(str, result=bool)
    def removeGame(self, game_id):
        """删除游戏"""
        try:
            logger.info(f"收到删除游戏请求: {game_id}")
            if self.parent():
                return self.parent().remove_game(game_id)
            else:
                logger.error("无法删除游戏：找不到父窗口")
                return False
        except Exception as e:
            logger.error(f"删除游戏失败: {str(e)}")
            return False

class MainWindow(QMainWindow):
    downloadProgress = pyqtSignal(str, int, str)  # game_id, progress, message
    downloadFinished = pyqtSignal(str, str, str)   # game_id, status, message
    launchStatus = pyqtSignal(str, str)            # game_id, status
    logMessage = pyqtSignal(str, str, str)  # game_id, level, message

    def __init__(self):
        super().__init__()
        logger.info("初始化主窗口...")
        
        try:
            # 设置文件路径
            self.app_dir = os.path.dirname(os.path.abspath(__file__))
            self.resources_dir = os.path.join(self.app_dir, "resources")
            self.pages_dir = os.path.join(self.resources_dir, "pages")
            self.icons_dir = os.path.join(self.resources_dir, "icons")
            self.fonts_dir = os.path.join(self.resources_dir, "fonts")
            logger.info(f"应用目录: {self.app_dir}")
            
            # 加载自定义字体
            self._load_custom_fonts()
            
            # 设置基本窗口属性
            self.setWindowTitle("BlockLauncher")
            self.setGeometry(100, 100, 1280, 800)
            self.setMinimumSize(800, 600)
            logger.info(f"设置窗口大小: {self.width()}x{self.height()}")
            
            # 设置应用图标
            icon_path = os.path.join(self.icons_dir, "rocket.svg")
            if os.path.exists(icon_path):
                self.setWindowIcon(QIcon(icon_path))
                logger.info("已设置应用图标")
            else:
                logger.warning(f"图标文件不存在: {icon_path}")
            
            # 设置无边框窗口
            self.setWindowFlags(Qt.FramelessWindowHint | Qt.Window)
            self.setAttribute(Qt.WA_TranslucentBackground, True)
            logger.info("设置窗口样式完成")
            
            # 初始化游戏数据
            self._load_config()
            
            # 初始化浏览器组件
            self._init_browser()
            
            # 确保窗口可见
            self.show()
            logger.info("窗口初始化完成，已显示")
            
        except Exception as e:
            logger.error(f"窗口初始化失败: {str(e)}")
            raise

    def _load_custom_fonts(self):
        """加载自定义字体"""
        try:
            from PyQt5.QtGui import QFontDatabase
            fonts_loaded = []
            
            # 遍历字体目录加载所有字体文件
            for font_file in os.listdir(self.fonts_dir):
                if font_file.endswith(('.ttf', '.otf')):
                    font_path = os.path.join(self.fonts_dir, font_file)
                    font_id = QFontDatabase.addApplicationFont(font_path)
                    if font_id != -1:
                        fonts_loaded.append(font_file)
                        logger.info(f"已加载字体: {font_file}")
                    else:
                        logger.warning(f"加载字体失败: {font_file}")
            
            if fonts_loaded:
                logger.info(f"成功加载 {len(fonts_loaded)} 个字体")
            else:
                logger.warning("未加载任何字体")
                
        except Exception as e:
            logger.error(f"加载自定义字体失败: {str(e)}")

    def _init_browser(self):
        """初始化浏览器组件"""
        try:
            logger.info("初始化浏览器组件...")
            
            # 创建WebView和Page
            self.view = QWebEngineView(self)
            self.page = QWebEnginePage(self)
            self.view.setPage(self.page)
            logger.info("WebView和Page创建成功")
            
            # 初始化WebChannel
            self.channel = QWebChannel(self)
            self.bridge = Bridge(self)
            self.channel.registerObject('pyBridge', self.bridge)
            self.page.setWebChannel(self.channel)
            logger.info("WebChannel初始化成功")
            
            # 连接信号
            self.downloadProgress.connect(self._on_download_progress)
            self.downloadFinished.connect(self._on_download_finished)
            self.launchStatus.connect(self._on_launch_status)
            self.logMessage.connect(self._on_log_message)
            
            # 加载主页
            index_path = os.path.join(self.pages_dir, "index.html")
            if not os.path.exists(index_path):
                raise FileNotFoundError(f"找不到主页文件: {index_path}")
                
            index_url = QUrl.fromLocalFile(index_path)
            logger.info(f"加载页面: {index_url.toString()}")
            
            # 设置页面加载信号
            self.page.loadFinished.connect(self._on_page_load_finished)
            self.page.loadStarted.connect(lambda: logger.info("页面开始加载"))
            
            # 设置JavaScript控制台消息处理
            def handle_js_message(level, message, line_number, source_id):
                self._handle_console_message(level, message, line_number, source_id)
            self.page.javaScriptConsoleMessage = handle_js_message
            
            # 加载页面
            self.page.load(index_url)
            
            # 设置视图属性
            self.view.setContextMenuPolicy(Qt.NoContextMenu)
            self.view.resize(self.width(), self.height())
            self.setCentralWidget(self.view)
            
            logger.info("浏览器组件初始化完成")
            
        except Exception as e:
            logger.error(f"浏览器组件初始化失败: {str(e)}")
            raise
            
    def _on_download_progress(self, game_id, progress, message):
        """处理下载进度"""
        js_code = f"""
            if (typeof updateDownloadProgress === 'function') {{
                updateDownloadProgress('{game_id}', {progress}, '{message}');
            }}
        """
        self.page.runJavaScript(js_code)
        
    def _on_download_finished(self, game_id, status, message):
        """处理下载完成"""
        js_code = f"""
            if (typeof onDownloadFinished === 'function') {{
                onDownloadFinished('{game_id}', '{status}', '{message}');
            }}
        """
        self.page.runJavaScript(js_code)
        
    def _on_launch_status(self, game_id, status):
        """处理游戏启动状态"""
        js_code = f"""
            if (typeof updateLaunchStatus === 'function') {{
                updateLaunchStatus('{game_id}', '{status}');
            }}
        """
        self.page.runJavaScript(js_code)
        
    def _on_log_message(self, game_id, level, message):
        """处理日志消息"""
        js_code = f"""
            if (typeof appendLogMessage === 'function') {{
                appendLogMessage('{game_id}', '{level}', '{message}');
            }}
        """
        self.page.runJavaScript(js_code)

    def _on_page_load_finished(self, ok):
        """页面加载完成回调"""
        if ok:
            logger.info("页面加载成功")
            # 检查页面是否正确加载
            self.page.runJavaScript(
                "document.body.innerHTML.length",
                lambda result: logger.info(f"页面内容长度: {result}")
            )
        else:
            logger.error("页面加载失败")

    def _handle_console_message(self, level, message, line, source_id):
        """处理JavaScript控制台消息"""
        level_str = {
            0: "INFO",
            1: "WARNING",
            2: "ERROR"
        }.get(level, "INFO")
        logger.debug(f"JS [{level_str}] {message} (行 {line} in {source_id})")

    def _init_web_channel(self):
        """初始化WebChannel通信"""
        try:
            logger.info("初始化WebChannel...")
            self.channel = QWebChannel()
            self.bridge = Bridge(self)
            self.channel.registerObject('pyBridge', self.bridge)
            if hasattr(self, 'browser') and self.browser.page():
                self.browser.page().setWebChannel(self.channel)
                logger.info("WebChannel初始化成功")
            else:
                logger.error("WebChannel初始化失败：browser或page未就绪")
        except Exception as e:
            logger.error(f"WebChannel初始化失败: {str(e)}")

    def _load_config(self):
        """优化的配置加载方法"""
        logger.info("加载配置文件...")
        
        # 批量确保配置文件存在
        for file_name, default_content in {
            "settings.ini": "",
            "games.json": "[]",
            "worlds.json": "[]"
        }.items():
            path = Path(file_name)
            if not path.exists():
                path.write_text(default_content, encoding='utf-8')
                logger.info(f"创建配置文件: {file_name}")
        
        # 加载设置和游戏数据
        self.settings = QSettings("settings.ini", QSettings.IniFormat)
        self.installed_games = self.load_games()
        self.game_worlds = self.load_worlds()
        
        logger.info(f"已加载 {len(self.installed_games)} 个游戏和 {len(self.game_worlds)} 个世界")
        
    def load_games(self):
        """优化的游戏列表加载方法"""
        try:
            games_file = Path("games.json")
            if games_file.exists():
                with games_file.open('r', encoding='utf-8') as f:
                    games = json.load(f)
                    return games if isinstance(games, list) else []
        except Exception as e:
            logger.error(f"加载游戏列表失败: {str(e)}")
        return []
            
    def save_games(self):
        """优化的游戏列表保存方法"""
        try:
            games_file = Path("games.json")
            temp_file = games_file.with_suffix('.tmp')
            
            # 先写入临时文件
            with temp_file.open('w', encoding='utf-8') as f:
                json.dump(self.installed_games, f, indent=2, ensure_ascii=False)
                
            # 然后替换原文件
            temp_file.replace(games_file)
            logger.info(f"成功保存游戏列表: {len(self.installed_games)} 个游戏")
            
        except Exception as e:
            logger.error(f"保存游戏列表失败: {str(e)}")
            if temp_file.exists():
                temp_file.unlink()
                
    def load_worlds(self):
        """优化的世界列表加载方法"""
        try:
            worlds_file = Path("worlds.json")
            if worlds_file.exists():
                with worlds_file.open('r', encoding='utf-8') as f:
                    worlds = json.load(f)
                    return worlds if isinstance(worlds, list) else []
        except Exception as e:
            logger.error(f"加载世界列表失败: {str(e)}")
        return []
    
    def update_mask(self):
        """更新窗口圆角遮罩"""
        try:
            if self.width() <= 0 or self.height() <= 0:
                return
                
            # 创建一个QPainterPath来绘制圆角矩形
            path = QPainterPath()
            path.addRoundedRect(0, 0, self.width(), self.height(), 12, 12)
            
            # 创建一个QRegion作为窗口遮罩
            region = QRegion(path.toFillPolygon().toPolygon())
            
            # 应用遮罩
            if not region.isEmpty():
                self.setMask(region)
                logger.debug("已更新窗口遮罩")
        except Exception as e:
            logger.error(f"更新窗口遮罩失败: {str(e)}")

    def resizeEvent(self, event):
        """窗口大小改变时更新遮罩"""
        try:
            super().resizeEvent(event)
            self.update_mask()
            # 确保视图大小跟随窗口
            if hasattr(self, 'view'):
                self.view.resize(self.width(), self.height())
        except Exception as e:
            logger.error(f"处理窗口大小改变事件失败: {str(e)}")
            super().resizeEvent(event)

    def eventFilter(self, obj, event):
        """优化的事件过滤器"""
        if obj is self.browser:
            if event.type() == QMouseEvent.MouseButtonPress and event.button() == Qt.LeftButton:
                self.dragging = True
                self.drag_position = event.globalPos() - self.frameGeometry().topLeft()
                event.accept()
                return True
            
            if event.type() == QMouseEvent.MouseMove and self.dragging:
                self.move(event.globalPos() - self.drag_position)
                event.accept()
                return True
                
            if event.type() == QMouseEvent.MouseButtonRelease and event.button() == Qt.LeftButton:
                self.dragging = False
                event.accept()
                return True
                
        return super().eventFilter(obj, event)

    def add_game(self, game_data):
        """优化的游戏添加方法"""
        if not any(g['id'] == game_data['id'] for g in self.installed_games):
            self.installed_games.append(game_data)
            self.save_games()
            logger.info(f"已添加游戏: {game_data['id']}")

    def get_game(self, game_id):
        """优化的游戏获取方法"""
        try:
            return next(g for g in self.installed_games if g['id'] == game_id)
        except StopIteration:
            return None
            
    def update_game(self, game_data):
        """优化的游戏更新方法"""
        try:
            game_id = game_data['id']
            for i, game in enumerate(self.installed_games):
                if game['id'] == game_id:
                    self.installed_games[i] = {**game, **game_data}
                    self.save_games()
                    logger.info(f"已更新游戏: {game_id}")
                    return
            logger.warning(f"未找到游戏: {game_id}")
        except Exception as e:
            logger.error(f"更新游戏失败: {str(e)}")

    def remove_game(self, game_id):
        """优化的游戏删除方法"""
        try:
            initial_count = len(self.installed_games)
            self.installed_games = [g for g in self.installed_games if g['id'] != game_id]
            if len(self.installed_games) < initial_count:
                self.save_games()
                logger.info(f"已删除游戏: {game_id}")
                return True
            logger.warning(f"未找到游戏: {game_id}")
            return False
        except Exception as e:
            logger.error(f"删除游戏失败: {str(e)}")
            return False

    def on_js_console_message(self, level, message, lineNumber, sourceID):
        """处理JS控制台消息"""
        try:
            source = sourceID if sourceID else "未知来源"
            if level == 0:  # INFO
                logger.info(f"JS消息 [{source}:{lineNumber}]: {message}")
            elif level == 1:  # WARNING
                logger.warning(f"JS警告 [{source}:{lineNumber}]: {message}")
            elif level == 2:  # ERROR
                logger.error(f"JS错误 [{source}:{lineNumber}]: {message}")
            else:
                logger.debug(f"JS调试 [{source}:{lineNumber}]: {message}")
        except Exception as e:
            logger.error(f"处理JS控制台消息失败: {str(e)}")
    
    def force_terminate_process(self):
        """使用 Windows API 强制终止进程"""
        try:
            import ctypes
            from ctypes import wintypes
            
            kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
            PROCESS_TERMINATE = 0x0001
            
            pid = os.getpid()
            handle = kernel32.OpenProcess(PROCESS_TERMINATE, False, pid)
            if handle:
                kernel32.TerminateProcess(handle, 1)
                kernel32.CloseHandle(handle)
        except:
            os._exit(0)

    def closeEvent(self, event):
        """重写关闭事件"""
        logger.info("应用关闭中...")
        try:
            # 保存必要的数据
            self.save_games()
            self.settings.sync()
            
            # 隐藏窗口
            self.hide()
            
            # 停止事件循环
            QApplication.instance().quit()
            
            # 强制终止进程
            self.force_terminate_process()
        except:
            # 如果上面的方法失败，使用最后的备选方案
            os._exit(0)

    def download_game(self, version, player_name, loader_type, loader_version=None):
        """优化的游戏下载方法"""
        game_id = f"{version}_{loader_type}_{player_name}"
        logger.info(f"准备下载游戏: {game_id}")
        
        # 检查是否已存在
        if self.get_game(game_id):
            self.downloadFinished.emit(game_id, "failed", "游戏已存在")
            return
            
        try:
            game_data = {
                "id": game_id,
                "version": version,
                "player_name": player_name,
                "loader_type": loader_type,
                "loader_version": loader_version,
                "status": "downloading",
                "progress": 0,
                "last_played": "",
                "play_count": 0
            }
            
            with self.download_lock:
                self.current_downloads[game_id] = game_data
                self.add_game(game_data)
            
            def progress_callback(progress, message):
                """下载进度回调"""
                self.downloadProgress.emit(game_id, progress, message)
            
            launcher = MinecraftLauncherGenerator(
                version=version,
                loader_type=loader_type,
                player_name=player_name,
                loader_version=loader_version
            )
            
            launcher.generate_install_script(progress_callback=progress_callback)
            self.downloadFinished.emit(game_id, "success", "下载完成")
            
        except Exception as e:
            logger.error(f"下载失败 [{game_id}]: {str(e)}")
            self.downloadFinished.emit(game_id, "failed", str(e))
        finally:
            with self.download_lock:
                if game_id in self.current_downloads:
                    del self.current_downloads[game_id]
                    
    def launch_game(self, game_id):
        """优化的游戏启动方法"""
        try:
            game = self.get_game(game_id)
            if not game:
                logger.error(f"游戏未找到: {game_id}")
                return False
                
            launcher = MinecraftLauncherGenerator(
                version=game["version"],
                loader_type=game["loader_type"],
                player_name=game["player_name"],
                loader_version=game.get("loader_version")
            )
            
            config = launcher.generate_launch_script()
            command = f'"{config["java_path"]}" {" ".join(config["jvm_args"])} {" ".join(config["game_args"])}'
            
            # 使用subprocess.Popen启动游戏
            subprocess.Popen(
                command,
                shell=True,
                start_new_session=True,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
            )
            
            # 更新游戏状态
            game.update({
                "last_played": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
                "play_count": game.get("play_count", 0) + 1
            })
            self.update_game(game)
            
            return True
            
        except Exception as e:
            logger.error(f"启动游戏失败 [{game_id}]: {str(e)}")
            return False

    def changeEvent(self, event):
        """处理窗口状态改变事件"""
        # 窗口状态改变事件的类型值是105
        if event.type() == 105:  # WindowStateChange event type
            # 通知前端更新窗口状态
            if hasattr(self, 'page'):
                self.page.runJavaScript("window.dispatchEvent(new Event('windowStateChanged'));")
        super().changeEvent(event)

if __name__ == "__main__":
    try:
        # 确保只创建一个QApplication实例
        app = QApplication.instance()
        if app is None:
            app = QApplication(sys.argv)
            logger.info("创建QApplication实例")
        else:
            logger.info("使用现有QApplication实例")
        
        # 设置应用程序属性
        app.setApplicationName("BlockLauncher")
        app.setApplicationVersion("1.0.0")
        app.setOrganizationName("BlockLauncher")
        app.setOrganizationDomain("blocklauncher.org")
        
        # 设置高DPI支持
        if hasattr(Qt, 'AA_EnableHighDpiScaling'):
            app.setAttribute(Qt.AA_EnableHighDpiScaling)
            logger.info("已启用高DPI缩放")
        if hasattr(Qt, 'AA_UseHighDpiPixmaps'):
            app.setAttribute(Qt.AA_UseHighDpiPixmaps)
            logger.info("已启用高DPI图标")
        
        # 确保资源目录存在
        resources_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "resources")
        if not os.path.exists(resources_dir):
            logger.error(f"资源目录不存在: {resources_dir}")
            sys.exit(1)
        
        # 创建并显示主窗口
        logger.info("正在创建主窗口...")
        window = MainWindow()
        
        # 进入事件循环
        logger.info("进入应用程序事件循环")
        exit_code = app.exec_()
        
        # 清理资源
        logger.info(f"应用程序退出，退出码: {exit_code}")
        sys.exit(exit_code)
        
    except Exception as e:
        logger.error(f"应用程序发生错误: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        sys.exit(1)