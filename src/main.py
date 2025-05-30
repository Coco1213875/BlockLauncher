from PyQt5.QtWidgets import QApplication, QMainWindow
from PyQt5.QtWebEngineWidgets import QWebEngineView, QWebEngineProfile
from PyQt5.QtCore import QUrl, Qt, QPoint, QObject, pyqtSlot
import sys
import os


os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = "--use-gl=desktop"
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("BlockLauncher")
        self.setGeometry(100, 100, 1280, 800)
        self.setWindowFlags(self.windowFlags() | Qt.FramelessWindowHint)
        self._is_dragging = False
        self._drag_pos = QPoint()

        # 设置User-Agent为Chrome
        profile = QWebEngineProfile.defaultProfile()
        profile.setHttpUserAgent("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")
        from PyQt5.QtWebEngineWidgets import QWebEnginePage
        page = QWebEnginePage(profile, self)
        self.browser = QWebEngineView()
        self.browser.setPage(page)
        # 设置缩放比例为100%
        self.browser.setZoomFactor(1.0)
        # 确保 QWebEngineView 能接收鼠标事件
        self.browser.setAttribute(Qt.WA_TransparentForMouseEvents, False)
        html_path = os.path.abspath(os.path.join(os.path.dirname(__file__), 'resources', 'pages', 'index.html'))
        self.browser.load(QUrl.fromLocalFile(html_path))
        self.setCentralWidget(self.browser)

        # 绑定JS信号（新版 PyQt5 需用 installEventFilter 或自定义 QWebEnginePage）
        self.browser.page().javaScriptConsoleMessage = self.on_js_console_message
        # 兼容性更强的关闭实现：直接注入 PyQt5 的 QWebChannel
        try:
            from PyQt5.QtWebChannel import QWebChannel
            class Bridge(QObject):
                @pyqtSlot()
                def closeApp(self):
                    self.parent().close()
                @pyqtSlot(int, int)
                def moveWindow(self, x, y):
                    self.parent().move(x, y)
                @pyqtSlot(result='QVariant')
                def getWindowPos(self):
                    pos = self.parent().pos()
                    return [pos.x(), pos.y()]
            self.channel = QWebChannel()
            self.bridge = Bridge(self)
            self.channel.registerObject('pyBridge', self.bridge)
            self.browser.page().setWebChannel(self.channel)
            # 必须在页面加载完成后再注入JS，且保证window.moveWindow可用
            def inject_js():
                self.browser.page().runJavaScript('''
                    (function(){
                        if (typeof qt !== 'undefined' && qt.pyBridge) {
                            window.closeApp = function() { qt.pyBridge.closeApp(); };
                            window.moveWindow = function(x, y) { qt.pyBridge.moveWindow(x, y); };
                            window.getWindowPos = function(cb) { qt.pyBridge.getWindowPos().then(cb); };
                        } else {
                            window.closeApp = function() { console.log("__CLOSE_APP__"); };
                            window.moveWindow = function(x, y) {};
                            window.getWindowPos = function(cb) { cb([0,0]); };
                        }
                        window._pyBridgeReady = true;
                    })();
                ''')
            self.browser.loadFinished.connect(lambda ok: inject_js())
        except Exception as e:
            pass

        # 设置圆角窗口
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setStyleSheet('background: transparent;')
        # 设置WebEngineView圆角遮罩
        from PyQt5.QtGui import QRegion, QPainterPath
        path = QPainterPath()
        path.addRoundedRect(0, 0, self.width(), self.height(), 18, 18)
        region = QRegion(path.toFillPolygon().toPolygon())
        self.setMask(region)

    def on_js_console_message(self, level, message, line, sourceID):
        if message == "__CLOSE_APP__":
            self.close()

    def resizeEvent(self, event):
        # 动态更新圆角遮罩
        from PyQt5.QtGui import QRegion, QPainterPath
        path = QPainterPath()
        path.addRoundedRect(0, 0, self.width(), self.height(), 18, 18)
        region = QRegion(path.toFillPolygon().toPolygon())
        self.setMask(region)
        super().resizeEvent(event)

    def mousePressEvent(self, event):
        # 只要不是点到自定义HTML按钮区域就允许拖动
        if event.button() == Qt.LeftButton:
            # 获取鼠标在全局的绝对位置
            global_pos = event.globalPos()
            # 获取窗口左上角的全局坐标
            top_left = self.frameGeometry().topLeft()
            # 计算鼠标在窗口内的相对坐标
            x, y = global_pos.x() - top_left.x(), global_pos.y() - top_left.y()
            print(f"Mouse Pressed at: ({x}, {y})")
            # 判断是否在自定义HTML按钮区域（如40px顶部且右侧40px内）
            if not (y < 40 and x > self.width() - 56):
                self._is_dragging = True
                self._drag_pos = global_pos - top_left
                event.accept()
                return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._is_dragging:
            self.move(event.globalPos() - self._drag_pos)
            event.accept()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self._is_dragging = False
        super().mouseReleaseEvent(event)

    def showEvent(self, event):
        # 不再需要事件过滤器
        super().showEvent(event)

    def eventFilter(self, obj, event):
        # 不再需要事件过滤器，直接返回父类实现
        return super().eventFilter(obj, event)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
