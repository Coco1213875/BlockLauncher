# BlockLauncher

BlockLauncher 是一个功能强大的 Minecraft 启动器，支持多种加载器类型（如 Vanilla 和 Fabric），并提供用户友好的界面和丰富的功能。

## 功能

- **游戏管理**：支持多版本 Minecraft 游戏的添加、更新和管理。
- **世界管理**：轻松管理 Minecraft 世界，包括生存模式和创造模式。
- **自定义界面**：提供可定制的主题和颜色。
- **多语言支持**：支持多种语言的游戏规则和生成器描述。
- **日志记录**：增强型日志记录功能，确保线程安全。

## 文件结构

```
BlockLauncher/
├── BL.ini                # 配置文件
├── BL.log                # 日志文件
├── launch.bat            # 启动脚本
├── logs/                 # 日志文件夹
├── src/                  # 源代码文件夹
│   ├── games.json        # 游戏数据
│   ├── worlds.json       # 世界数据
│   ├── LauncherGenerator.py # 启动器生成器
│   ├── main.py           # 主程序入口
│   ├── resources/        # 资源文件夹
│   │   ├── fonts/        # 字体文件
│   │   ├── icons/        # 图标文件
│   │   ├── pages/        # HTML 页面和样式
│   │   │   ├── custom-colors.css
│   │   │   ├── downloads.html
│   │   │   ├── games.html
│   │   │   ├── home.html
│   │   │   ├── index.html
│   │   │   ├── settings.html
│   │   │   ├── theme.css
```

## 安装

1. 克隆此仓库：
   ```bash
   git clone https://github.com/Coco1213875/BlockLauncher.git
   ```
2. 安装依赖：
   ```bash
   pip install -r requirements.txt
   ```
3. 运行启动器：
   ```bash
   python src/main.py
   ```

## 使用方法

1. 启动程序后，您可以通过界面管理游戏和世界。
2. 在 `settings.html` 页面中自定义界面主题和颜色。
3. 查看 `logs/` 文件夹中的日志以排查问题。

## 贡献

欢迎贡献代码！请遵循以下步骤：

1. Fork 此仓库。
2. 创建一个新分支：
   ```bash
   git checkout -b feature-branch
   ```
3. 提交更改：
   ```bash
   git commit -m "添加新功能"
   ```
4. 推送到您的分支：
   ```bash
   git push origin feature-branch
   ```
5. 创建 Pull Request。

## 许可证

此项目使用 [MIT 许可证](LICENSE)。
