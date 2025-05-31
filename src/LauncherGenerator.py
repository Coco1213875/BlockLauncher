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
import logging

# 设置日志
logger = logging.getLogger(__name__)

def log(message, mode="Info"):
    """增强型日志记录函数，支持多线程安全和详细日志格式"""
    timestamp = datetime.now().strftime("%H:%M:%S")
    log_line = f"[{timestamp}] | [{mode}] {message}"
    
    # 控制台输出带颜色
    if mode.lower() == "error":
        print(f"\033[91m{log_line}\033[0m", flush=True)
        logger.error(message)
    elif mode.lower() == "warning":
        print(f"\033[93m{log_line}\033[0m", flush=True)
        logger.warning(message)
    else:
        print(log_line, flush=True)
        logger.info(message)

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
                version_response.raise_for_status()
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
        if not self.loader_version:
            # 获取最新的Fabric版本
            loader_url = "https://meta.fabricmc.net/v2/versions/loader"
            response = requests.get(loader_url)
            response.raise_for_status()
            self.loader_version = response.json()[0]["version"]
            log(f"使用最新Fabric版本: {self.loader_version}")
        
        fabric_url = f"https://meta.fabricmc.net/v2/versions/loader/{self.version}/{self.loader_version}/profile/json"
        response = requests.get(fabric_url)
        response.raise_for_status()
        return response.json()

    def _check_library_compatibility(self, lib):
        """检查库兼容性规则"""
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
        
        return allow if applicable else True  # 默认允许未匹配规则的库

    def _download_file(self, url, target_path, sha1=None):
        """通用文件下载方法"""
        target_path.parent.mkdir(parents=True, exist_ok=True)
        if target_path.exists():
            if sha1:
                existing_hash = hashlib.sha1(target_path.read_bytes()).hexdigest()
                if existing_hash == sha1:
                    return True
                log(f"文件已损坏, 正在删除: {target_path}", "Warning")
                target_path.unlink()  # 删除损坏的文件

        response = requests.get(url, stream=True)
        response.raise_for_status()
        
        # 分块写入文件
        with open(target_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
        
        # 哈希校验
        if sha1:
            file_hash = hashlib.sha1(target_path.read_bytes()).hexdigest()
            if file_hash != sha1:
                log(f"文件校验失败: {target_path} (预期: {sha1} 实际: {file_hash})", "Error")
                target_path.unlink()
                return False
        return True

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

    def generate_install_script(self, progress_callback=None):
        """生成安装脚本，带进度反馈"""
        log("开始安装 Minecraft 游戏文件...")
        # 创建基础目录
        (self.minecraft_dir / "versions" / self.version).mkdir(parents=True, exist_ok=True)
        (self.minecraft_dir / "assets" / "objects").mkdir(parents=True, exist_ok=True)
        
        # 更新进度
        if progress_callback:
            progress_callback(0, "创建目录结构")
        
        # 下载客户端JAR
        client_jar = self.minecraft_dir / "versions" / self.version / f"{self.version}.jar"
        if not self._download_file(
            self.client_download["url"],
            client_jar,
            self.client_download["sha1"]
        ):
            raise Exception("客户端JAR下载失败")
        
        # 更新进度
        if progress_callback:
            progress_callback(5, "下载客户端文件")
        
        # 下载资源索引
        asset_index_file = self.minecraft_dir / "assets" / "indexes" / f"{self.asset_index}.json"
        if not self._download_file(
            self.version_meta["assetIndex"]["url"],
            asset_index_file
        ):
            raise Exception("资源索引下载失败")
        
        # 更新进度
        if progress_callback:
            progress_callback(10, "下载资源索引")
        
        # 下载所有资源文件（带进度）
        with open(asset_index_file, "r", encoding="utf-8") as f:
            assets = json.load(f)["objects"]
            total = len(assets)
            for idx, (asset_name, asset) in enumerate(assets.items()):
                hash_ = asset["hash"]
                url = f"https://resources.download.minecraft.net/{hash_[:2]}/{hash_}"
                path = self.minecraft_dir / "assets" / "objects" / hash_[:2] / hash_
                
                # 跳过已存在且校验通过的文件
                if path.exists():
                    if hashlib.sha1(path.read_bytes()).hexdigest() == hash_:
                        continue
                
                if not self._download_file(url, path, hash_):
                    log(f"资源下载失败: {asset_name}", "Warning")
                
                # 更新进度
                if progress_callback and idx % 100 == 0:
                    percent = min(10 + int((idx + 1) / total * 80), 85)
                    progress_callback(percent, f"下载资源文件 ({idx+1}/{total})")
        
        # 更新进度
        if progress_callback:
            progress_callback(85, "资源文件下载完成")
        
        # 下载原生库文件（带进度）
        libs = [lib for lib in self.version_meta["libraries"] if self._check_library_compatibility(lib) and "downloads" in lib]
        total_libs = len(libs)
        for idx, lib in enumerate(libs):
            # 下载主库文件
            if "artifact" in lib["downloads"]:
                artifact = lib["downloads"]["artifact"]
                lib_path = self.minecraft_dir / "libraries" / artifact["path"]
                if not self._download_file(artifact["url"], lib_path, artifact["sha1"]):
                    log(f"库文件下载失败: {artifact['path']}", "Warning")
            
            # 下载原生库
            if "classifiers" in lib["downloads"]:
                natives = lib["natives"]
                platform_key = {"win32": "windows", "darwin": "osx", "linux": "linux"}.get(sys.platform)
                if platform_key in natives:
                    classifier = lib["downloads"]["classifiers"][natives[platform_key]]
                    native_path = self.minecraft_dir / "libraries" / classifier["path"]
                    if not self._download_file(classifier["url"], native_path, classifier["sha1"]):
                        log(f"原生库下载失败: {classifier['path']}", "Warning")
            
            # 更新进度
            if progress_callback and idx % 5 == 0:
                percent = min(85 + int((idx + 1) / total_libs * 10), 95)
                progress_callback(percent, f"下载库文件 ({idx+1}/{total_libs})")
        
        # 更新进度
        if progress_callback:
            progress_callback(95, "库文件下载完成")
        
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
                
                # 跳过已存在的文件
                if lib_path.exists():
                    continue
                    
                url = f"https://maven.fabricmc.net/{group.replace('.', '/')}/{artifact}/{version}/{jar_name}"
                if not self._download_file(url, lib_path, lib.get("sha1")):
                    log(f"Fabric库下载失败: {lib['name']}", "Warning")
                
                # 更新进度
                if progress_callback and idx % 5 == 0:
                    percent = min(95 + int((idx + 1) / total_fabric * 5), 100)
                    progress_callback(percent, f"下载Fabric文件 ({idx+1}/{total_fabric})")
        
        # 更新进度
        if progress_callback:
            progress_callback(100, "安装完成")
        
        log("安装脚本生成完成.")

    def _detect_java(self):
        """自动检测Java 17+路径"""
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
            search_paths = [
                Path("C:/Program Files/Java/jdk-17/bin/java.exe"),
                Path("C:/Program Files/Java/jdk-21/bin/java.exe"),
                Path("C:/Program Files (x86)/Java/jdk-17/bin/java.exe")
            ]
        elif sys.platform == "darwin":
            search_paths = [
                Path("/Library/Java/JavaVirtualMachines/jdk-17.jdk/Contents/Home/bin/java"),
                Path("/usr/local/opt/openjdk@17/bin/java")
            ]
        else:  # Linux
            search_paths = [
                Path("/usr/lib/jvm/java-17-openjdk/bin/java"),
                Path("/usr/lib/jvm/java-21-openjdk/bin/java")
            ]

        for path in search_paths:
            if path.exists():
                log(f"已自动检测到Java 17+路径：{path}")
                return path

        # 尝试PATH环境变量
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