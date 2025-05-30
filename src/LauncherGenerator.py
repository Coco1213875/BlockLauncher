import json
import requests
import hashlib
import sys
import platform
import subprocess
import os
from pathlib import Path
from datetime import datetime
import threading

# 创建日志锁确保线程安全
log_lock = threading.Lock()

def log(message, mode="Info"):
    """增强型日志记录函数，支持多线程安全和详细日志格式"""
    timestamp = datetime.now().strftime("%H%M%S")
    try:
        # 统一日志格式
        log_line = f"[{timestamp}] | [{mode}] {message}"
        
        # 控制台输出带颜色
        if mode.lower() == "error":
            print(f"\033[91m{log_line}\033[0m", flush=True)
        elif mode.lower() == "warning":
            print(f"\033[93m{log_line}\033[0m", flush=True)
        else:
            print(log_line, flush=True)
            
        # 文件写入（线程安全）
        with log_lock:
            with open("BL.log", "a", encoding="utf-8") as f:
                f.write(log_line + "\n")
    except Exception as e:
        # 失败回退到基础输出
        print(f"[ERROR] 日志记录失败: {str(e)}", flush=True)
        print(f"原始消息: {message}", flush=True)

class MinecraftLauncherGenerator:
    def __init__(self, version, loader_type="vanilla", player_name="Steve", loader_version=None):
        self.version = version
        self.loader_type = loader_type
        self.player_name = player_name
        self.loader_version = loader_version
        self.minecraft_dir = Path(".minecraft")
        self.java_path = self._detect_java()
        
        # 动态获取版本元数据
        self.version_meta = self._fetch_version_manifest()
        self.asset_index = self.version_meta["assetIndex"]["id"]
        self.main_class = self.version_meta["mainClass"]
        self.client_download = self.version_meta["downloads"]["client"]

    def _fetch_version_manifest(self):
        """从Mojang API获取版本元数据"""
        log("正在获取版本元数据...")
        manifest_url = "https://piston-meta.mojang.com/mc/game/version_manifest_v2.json"
        response = requests.get(manifest_url)
        response.raise_for_status()
        
        for entry in response.json()["versions"]:
            if entry["id"] == self.version:
                version_url = entry["url"]
                version_response = requests.get(version_url)
                log(f"获取完成: {version_response.json}")
                return version_response.json()
        log(f"版本 {self.version} 不存在", "Error")
        raise ValueError(f"版本 {self.version} 不存在")

    def _generate_classpath(self):
        """构建动态类路径"""
        log("正在生成动态类路径...")
        libraries = []
        # 原生库处理
        libraries.extend([
            str(self.minecraft_dir / "libraries" / lib["downloads"]["artifact"]["path"])
            for lib in self.version_meta["libraries"]
            if self._check_library_compatibility(lib)
        ])
        
        # 客户端JAR
        client_jar = self.minecraft_dir / "versions" / self.version / f"{self.version}.jar"
        libraries.append(str(client_jar))
        
        # 加载器特殊处理
        if self.loader_type == "fabric":
            fabric_meta = self._fetch_fabric_metadata()
            libraries.extend([
                str(self.minecraft_dir / "libraries" / lib["name"].replace(":", "/")) 
                for lib in fabric_meta["libraries"]
            ])
        
        log(f"动态类路径生成完成: {';'.join(libraries)}")
        
        return ";".join(libraries)

    def _fetch_fabric_metadata(self):
        """获取Fabric加载器元数据"""
        log(f"正在获取 Fabric 加载器元数据...")
        fabric_url = f"https://meta.fabricmc.net/v2/versions/loader/{self.version}/{self.loader_version}/profile/json"
        response = requests.get(fabric_url)
        response.raise_for_status()
        log(f"获取完成: {response.json}")
        return response.json()

    def _check_library_compatibility(self, lib):
        """检查库兼容性规则"""
        log(f"正在检查库 {lib['name']} 的兼容性规则...")
        rules = lib.get("rules", [])
        if not rules:
            return True

        current_os = {"win32": "windows", "darwin": "osx", "linux": "linux"}.get(sys.platform)
        current_arch = platform.machine().lower()
        arch_map = {"x86_64": "x64", "amd64": "x64", "i386": "x86", "i686": "x86"}
        current_arch = arch_map.get(current_arch, current_arch)

        allow = False
        applicable = False
        for rule in rules:
            os_match = True
            arch_match = True
            
            # 检查操作系统条件
            if "os" in rule:
                os_rule = rule["os"]
                if "name" in os_rule and os_rule["name"] != current_os:
                    os_match = False
                if "arch" in os_rule and os_rule["arch"] != current_arch:
                    arch_match = False

            # 当所有条件满足时才应用规则
            if os_match and arch_match:
                applicable = True
                allow = (rule["action"] == "allow")
        
        log(f"库 {lib['name']} 的兼容性规则结果: {allow}")

        return allow if applicable else True  # 默认允许未匹配规则的库

    def _download_file(self, url, target_path, sha1=None):
        """通用文件下载方法"""
        log(f"正在下载 {url} 到 {target_path}")
        target_path.parent.mkdir(parents=True, exist_ok=True)
        if target_path.exists():
            if sha1:
                existing_hash = hashlib.sha1(target_path.read_bytes()).hexdigest()
                if existing_hash == sha1:
                    return
                log(f"文件已损坏, 正在删除: {target_path}", "Warning")
                target_path.unlink()  # 删除损坏的文件

        response = requests.get(url)
        response.raise_for_status()
        content = response.content
        
        # 哈希校验
        if sha1:
            log(f"正在校验 {target_path} 的哈希值...")
            file_hash = hashlib.sha1(content).hexdigest()
            if file_hash != sha1:
                log(f"文件校验失败: {target_path} (预期: {sha1} 实际: {file_hash})", "Error")
                raise ValueError(f"文件校验失败: {target_path} (预期: {sha1} 实际: {file_hash})")

        target_path.write_bytes(content)
        log(f"下载完成: {target_path}")

    def generate_launch_script(self):
        """生成启动命令"""
        log("开始生成 Minecraft 启动脚本...")
        uuid = hashlib.md5(self.player_name.encode()).hexdigest()
        uuid = f"{uuid[:8]}-{uuid[8:12]}-{uuid[12:16]}-{uuid[16:20]}-{uuid[20:]}"

        jvm_args = [
            f"-Xmx4G", 
            f"-Xms2G",
            f"-Djava.library.path={self.minecraft_dir / 'natives'}",
            f"-cp {self._generate_classpath()}"
        ]

        game_args = [
            self.main_class,
            "--username", self.player_name,
            "--version", self.version,
            "--gameDir", str(self.minecraft_dir),
            "--assetsDir", str(self.minecraft_dir / "assets"),
            "--assetIndex", self.asset_index,
            "--uuid", uuid,
            "--accessToken", "114514henghengaaa"
        ]

        if self.loader_type == "fabric":
            game_args.extend(["--launchTarget", "fabric-client"])

        log("生成完成！")

        return {
            "java_path": str(self.java_path),
            "jvm_args": jvm_args,
            "game_args": game_args
        }

    def generate_install_script(self):
        """生成安装脚本，带进度反馈"""
        log("开始安装 Minecraft 游戏文件...")
        # 创建基础目录
        (self.minecraft_dir / "versions" / self.version).mkdir(parents=True, exist_ok=True)
        (self.minecraft_dir / "assets" / "objects").mkdir(parents=True, exist_ok=True)
        log("基础目录创建完成.")
        # 下载客户端JAR
        client_jar = self.minecraft_dir / "versions" / self.version / f"{self.version}.jar"
        self._download_file(
            self.client_download["url"],
            client_jar,
            self.client_download["sha1"]
        )
        log("客户端JAR文件下载完成.")
        # 下载资源索引
        asset_index_file = self.minecraft_dir / "assets" / "indexes" / f"{self.asset_index}.json"
        self._download_file(
            self.version_meta["assetIndex"]["url"],
            asset_index_file
        )
        log("资源索引文件下载完成.")
        # 下载所有资源文件（带进度）
        with open(asset_index_file, "r", encoding="utf-8") as f:
            assets = json.load(f)["objects"]
            total = len(assets)
            for idx, asset in enumerate(assets.values()):
                hash_ = asset["hash"]
                url = f"https://resources.download.minecraft.net/{hash_[:2]}/{hash_}"
                path = self.minecraft_dir / "assets" / "objects" / hash_[:2] / hash_
                self._download_file(url, path, hash_)
                percent = int((idx + 1) / total * 100)
                log(f"资源下载进度: {percent}%")
        log("所有资源文件下载完成.")
        # 下载原生库文件（带进度）
        libs = [lib for lib in self.version_meta["libraries"] if self._check_library_compatibility(lib) and "downloads" in lib]
        total_libs = len(libs)
        for idx, lib in enumerate(libs):
            # 下载主库文件
            if "artifact" in lib["downloads"]:
                artifact = lib["downloads"]["artifact"]
                lib_path = self.minecraft_dir / "libraries" / artifact["path"]
                self._download_file(artifact["url"], lib_path, artifact["sha1"])
            # 下载原生库
            if "classifiers" in lib["downloads"]:
                natives = lib["natives"]
                platform_key = {"win32": "windows", "darwin": "osx", "linux": "linux"}.get(sys.platform)
                if platform_key in natives:
                    classifier = lib["downloads"]["classifiers"][natives[platform_key]]
                    native_path = self.minecraft_dir / "libraries" / classifier["path"]
                    self._download_file(classifier["url"], native_path, classifier["sha1"])
            percent = int((idx + 1) / total_libs * 100)
            log(f"库下载进度: {percent}%")
        log("所有库文件下载完成.")
        # 处理Fabric加载器
        if self.loader_type == "fabric":
            fabric_meta = self._fetch_fabric_metadata()
            total_fabric = len(fabric_meta["libraries"])
            for idx, lib in enumerate(fabric_meta["libraries"]):
                parts = lib["name"].split(":")
                group, artifact, version = parts[0], parts[1], parts[2]
                jar_name = f"{artifact}-{version}.jar"
                lib_path = self.minecraft_dir / "libraries" / \
                    group.replace(".", "/") / artifact / version / jar_name
                url = f"https://maven.fabricmc.net/{group.replace('.', '/')}/{artifact}/{version}/{jar_name}"
                self._download_file(url, lib_path, lib.get("sha1"))
                percent = int((idx + 1) / total_fabric * 100)
                log(f"Fabric库下载进度: {percent}%")
        log("Fabric加载器处理完成.")
        log("安装脚本生成完成.")

    def _detect_java(self):
        """自动检测Java 17+路径"""
        log("正在自动检测Java 17+路径...")
        # 检查JAVA_HOME
        if java_home := os.environ.get("JAVA_HOME"):
            possible_paths = [
                Path(java_home) / "bin" / "java",
                Path(java_home) / "bin" / "java.exe"
            ]
            for path in possible_paths:
                if path.exists():
                    log(f"已自动检测到Java 17+路径：{path}")
                    return path

        # 平台特定搜索
        if sys.platform == "win32":
            log("正在使用Windows平台特定搜索...")
            search_paths = [
                Path("C:/Program Files/Java/jdk-17/bin/java.exe"),
                Path("C:/Program Files/Java/jdk-21/bin/java.exe"),
                Path("C:/Program Files (x86)/Java/jdk-17/bin/java.exe")
            ]
        elif sys.platform == "darwin":
            log("正在使用macOS平台特定搜索...")
            search_paths = [
                Path("/Library/Java/JavaVirtualMachines/jdk-17.jdk/Contents/Home/bin/java"),
                Path("/usr/local/opt/openjdk@17/bin/java")
            ]
        else:  # Linux
            log("正在使用Linux平台特定搜索...")
            search_paths = [
                Path("/usr/lib/jvm/java-17-openjdk/bin/java"),
                Path("/usr/lib/jvm/java-21-openjdk/bin/java")
            ]

        for path in search_paths:
            if path.exists():
                log(f"已自动检测到Java 17+路径：{path}")
                return path

        # 尝试PATH环境变量
        log("正在尝试PATH环境变量...")
        try:
            result = subprocess.run(
                ["java", "-version"],
                stderr=subprocess.PIPE,
                stdout=subprocess.DEVNULL
            )
            if "17" in result.stderr.decode() or "21" in result.stderr.decode():
                log("已自动检测到Java 17+路径：java")
                return Path("java")
        except Exception:
            pass
        
        log("未找到Java 17或更高版本, 请安装JDK并设置JAVA_HOME", "Error")
        raise RuntimeError("未找到Java 17或更高版本, 请安装JDK并设置JAVA_HOME")

if __name__ == "__main__":
    log("正在启动Minecraft启动器生成器...")
    # 使用示例：生成1.20.4 Vanilla启动配置
    launcher = MinecraftLauncherGenerator(
        version="1.20.1",
        player_name="Steve"
    )
    log("开始生成安装Minecraft...")
    launcher.generate_install_script()
    log("安装Minecraft完成, 开始生成启动脚本...")
    config = launcher.generate_launch_script()
    print("启动命令：")
    print(f"{config['java_path']} {' '.join(config['jvm_args'])} {' '.join(config['game_args'])}")
    with open("launch.bat", "w") as f:
        f.write(f"{config['java_path']} {' '.join(config['jvm_args'])} {' '.join(config['game_args'])}")
    log("启动脚本生成完成.")

