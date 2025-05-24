# style_sheet.py
"""
样式表模块，提供两种主题：'light'和'dark'
使用apply_theme(theme_name)函数应用主题
主题资源文件需存放在src/resources/icons目录下
"""

light = """
    /* 基础样式 */
    QMainWindow {{
        background-color: #f5f5f5;
    }}
    
    QStatusBar {{
        background-color: #e0e0e0;
        color: #333333;
        font-family: "微软雅黑";
        font-size: 9pt;
    }}

    /* 侧边栏样式 */
    QWidget#sidebar {{
        background-color: #f0f0f0;
        border-right: 1px solid #cccccc;
    }}
    
    QPushButton {{
        text-align: left; 
        padding-left: 15px;
        border: none;
        border-radius: 4px;
        background-color: transparent;
        color: #333333;
        font-family: "微软雅黑";
        font-size: 13px;
    }}
    
    QPushButton:hover {{
        background-color: #e6e6e6;
    }}
    
    QPushButton:pressed {{
        background-color: #d9d9d9;
    }}

    /* 游戏列表项 */
    QWidget[class="game-item"] {{
        background-color: white;
        border-radius: 8px;
        border: 1px solid #e0e0e0;
    }}
    
    QLabel[class="title"] {{
        font-family: "微软雅黑";
        font-size: 14px;
        font-weight: bold;
        color: #333333;
    }}
    
    QLabel[class="subtitle"] {{
        font-family: "微软雅黑";
        font-size: 12px;
        color: #666666;
    }}
    
    QLabel[class="info"] {{
        font-family: "微软雅黑";
        font-size: 11px;
        color: #999999;
    }}

    /* 滚动区域 */
    QScrollArea {{
        border: none;
        border-radius: 5px;
        background: transparent;
    }}
    
    /* 按钮样式 */
    QPushButton[class="launch-btn"] {{
        background-color: #4CAF50;
        color: white;
        padding: 8px 16px;
        border-radius: 5px;
        font-family: "微软雅黑";
        font-size: 12px;
    }}
    
    QPushButton[class="option-btn"] {{
        background-color: #f0f0f0;
        color: #666666;
        padding: 6px 12px;
        border: 1px solid #cccccc;
        border-radius: 4px;
        font-family: "微软雅黑";
        font-size: 11px;
    }}
    
    /* 菜单样式 */
    QMenuBar {{
        background-color: #f5f5f5;
        border-bottom: 1px solid #e0e0e0;
        font-family: "微软雅黑";
    }}
    
    QMenu {{
        background-color: white;
        border: 1px solid #e0e0e0;
        padding: 8px 0;
        font-family: "微软雅黑";
    }}
    
    QMenu::item {{
        padding: 6px 24px;
    }}
    
    /* 列表样式 */
    QListWidget {{
        background-color: white;
        border: 1px solid #e0e0e0;
        border-radius: 6px;
        font-family: "微软雅黑";
    }}
"""

dark = """
    /* 基础样式 */
    QMainWindow {{
        background-color: #2d2d2d;
    }}
    
    QStatusBar {{
        background-color: #383838;
        color: #cccccc;
        font-family: "微软雅黑";
        font-size: 9pt;
    }}

    /* 侧边栏样式 */
    QWidget#sidebar {{
        background-color: #333333;
        border-right: 1px solid #404040;
    }}
    
    QPushButton {{
        text-align: left;
        padding-left: 15px;
        border: none;
        border-radius: 4px;
        background-color: transparent;
        color: #cccccc;
        font-family: "微软雅黑";
        font-size: 13px;
    }}
    
    QPushButton:hover {{
        background-color: #404040;
    }}
    
    QPushButton:pressed {{
        background-color: #4d4d4d;
    }}

    /* 游戏列表项 */
    QWidget[class="game-item"] {{
        background-color: #383838;
        border-radius: 8px;
        border: 1px solid #404040;
    }}
    
    QLabel[class="title"] {{
        color: #ffffff;
        font-family: "微软雅黑";
        font-size: 14px;
        font-weight: bold;
    }}
    
    QLabel[class="subtitle"] {{
        color: #aaaaaa;
        font-family: "微软雅黑";
        font-size: 12px;
    }}
    
    QLabel[class="info"] {{
        color: #888888;
        font-family: "微软雅黑";
        font-size: 11px;
    }}

    /* 滚动区域 */
    QScrollArea {{
        border: none;
        border-radius: 5px;
        background: transparent;
    }}
    
    /* 按钮样式 */
    QPushButton[class="launch-btn"] {{
        background-color: #4CAF50;
        color: white;
        padding: 8px 16px;
        border-radius: 5px;
        font-family: "微软雅黑";
        font-size: 12px;
    }}
    
    QPushButton[class="option-btn"] {{
        background-color: #404040;
        color: #cccccc;
        padding: 6px 12px;
        border: 1px solid #555555;
        border-radius: 4px;
        font-family: "微软雅黑";
        font-size: 11px;
    }}
    
    /* 菜单样式 */
    QMenuBar {{
        background-color: #333333;
        border-bottom: 1px solid #404040;
        font-family: "微软雅黑";
    }}
    
    QMenu {{
        background-color: #383838;
        border: 1px solid #404040;
        padding: 8px 0;
        font-family: "微软雅黑";
    }}
    
    QMenu::item {{
        padding: 6px 24px;
        color: #cccccc;
    }}
    
    /* 列表样式 */
    QListWidget {{
        background-color: #383838;
        border: 1px solid #404040;
        border-radius: 6px;
        font-family: "微软雅黑";
    }}
"""

def apply_theme(theme_name, app):
    """应用主题到应用程序"""
    theme_map = {
        "light": light,
        "dark": dark
    }
    
    if theme_name in theme_map:
        style_sheet = theme_map[theme_name].format(
            check_mark="src/resources/icons/check_mark.svg",
            drop_down_arrow="src/resources/icons/arrow_down.svg",
            scroll_bar_top="src/resources/icons/scroll_top.svg",
            scroll_bar_bottom="src/resources/icons/scroll_bottom.svg",
            scroll_bar_left="src/resources/icons/scroll_left.svg",
            scroll_bar_right="src/resources/icons/scroll_right.svg"
        )
        app.setStyleSheet(style_sheet)