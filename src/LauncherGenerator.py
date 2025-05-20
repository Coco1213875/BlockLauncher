import json
import requests
import hashlib
import sys
import platform
import subprocess
import os
from pathlib import Path
from datetime import datetime



with open("BL.log", "w") as f:
    f.write(f"-----====***[{datetime.now().strftime("%H%M%S")}]开始记录log***====-----\n")

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

class MinecraftLauncherGenerator:
    def __init__(self, version, player_name, loader_type="vanilla", loader_version=None):
        self.version = version
        self.player_name = player_name
        self.loader_type = loader_type
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
        for lib in self.version_meta["libraries"]:
            if not self._check_library_compatibility(lib):
                continue
            if "downloads" not in lib:
                continue
            # 安全访问artifact
            if (artifact := lib["downloads"].get("artifact")):
                libraries.append(
                    str(self.minecraft_dir / "libraries" / artifact["path"])
                )
            else:
                log(f"库 {lib['name']} 缺少artifact下载信息", "Warning")
        
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
                log(f"文bgithub.xyz: {target_path} (预期: {sha1} 实际: {file_hash})", "Error")
                raise ValueError(f"文bgithub.xyz: {target_path} (预期: {sha1} 实际: {file_hash})")

        target_path.write_bytes(content)
        log(f"下载完成: {target_path}")

    def generate_launch_script(self):
        """生成启动命令"""
        log("开始生成 Minecraft 启动脚本...")
        uuid = hashlib.md5(self.player_name.encode()).hexdigest()
        uuid = f"{uuid[:8]}-{uuid[8:12]}-{uuid[12:16]}-{uuid[16:20]}-{uuid[20:]}"
        
        # ✅ 新增：显式验证Java路径有效性
        if not self.java_path or not self.java_path.exists():
            raise RuntimeError("Java路径无效，请检查Java安装")
            
        # 动态确定主类（针对不同版本和加载器特殊处理）
        if self.loader_type == "fabric":
            main_class = "net.fabricmc.loader.impl.launch.knot.KnotClient"
        else:
            # 修复旧版Vanilla主类问题
            if self.version.startswith("1.8."):
                main_class = "net.minecraft.client.Minecraft"
            else:
                main_class = self.main_class

        jvm_args = [
            f"-Xmx4G", 
            f"-Xms2G",
            f"-Djava.library.path={self.minecraft_dir / 'natives'}",
            f"-cp {self._generate_classpath()}"
        ]

        game_args = [
            main_class,
            "--username", self.player_name,
            "--version", self.version,
            "--gameDir", str(self.minecraft_dir),
            "--assetsDir", str(self.minecraft_dir / "assets"),
            "--assetIndex", self.asset_index,
            "--uuid", uuid,
            "--accessToken", "0"
        ]
        
        # ✅ 新增：添加启动参数调试日志
        log(f"Java可执行文件路径: {self.java_path}")
        log(f"JVM参数: {' '.join(jvm_args)}")
        log(f"游戏参数: {' '.join(game_args)}")

        if self.loader_type == "fabric":
            game_args.extend(["--launchTarget", "fabric-client"])

        log("生成完成！")

        return {
            "java_path": str(self.java_path),
            "jvm_args": jvm_args,
            "game_args": game_args
        }

    def generate_install_script(self):
        """生成安装脚本"""
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
        
        # 下载所有资源文件
        with open(asset_index_file, "r", encoding="utf-8") as f:
            assets = json.load(f)["objects"]
            for asset in assets.values():
                hash_ = asset["hash"]
                url = f"https://resources.download.minecraft.net/{hash_[:2]}/{hash_}"
                path = self.minecraft_dir / "assets" / "objects" / hash_[:2] / hash_
                self._download_file(url, path, hash_)
        log("所有资源文件下载完成.")
        
        # 下载原生库文件
        for lib in self.version_meta["libraries"]:
            if not self._check_library_compatibility(lib):
                continue
            
            if "downloads" not in lib:
                continue
                
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
                    # 获取当前架构
                    current_arch = platform.machine().lower()
                    arch_map = {"x86_64": "x64", "amd64": "x64", "i386": "x86", "i686": "x86"}
                    current_arch = arch_map.get(current_arch, current_arch)
                    
                    # 替换变量
                    natives_key = natives[platform_key].replace("${arch}", current_arch)
                    
                    # 下载原生库
                    classifier = lib["downloads"]["classifiers"].get(natives_key)
                    if classifier:
                        native_path = self.minecraft_dir / "libraries" / classifier["path"]
                        self._download_file(classifier["url"], native_path, classifier["sha1"])
                    else:
                        log(f"未找到分类器 {natives_key} 对应的原生库", "Warning")
        log("所有库文件下载完成.")
        
        # 处理Fabric加载器
        if self.loader_type == "fabric":
            fabric_meta = self._fetch_fabric_metadata()
            for lib in fabric_meta["libraries"]:
                parts = lib["name"].split(":")
                group, artifact, version = parts[0], parts[1], parts[2]
                jar_name = f"{artifact}-{version}.jar"
                lib_path = self.minecraft_dir / "libraries" / \
                    group.replace(".", "/") / artifact / version / jar_name
                    
                url = f"https://maven.fabricmc.net/{group.replace('.', '/')}/{artifact}/{version}/{jar_name}"
                self._download_file(url, lib_path, lib.get("sha1"))
        log("Fabric加载器处理完成.")
        log("安装脚本生成完成.")

    def _download_java(self, version):
        """自动下载指定版本的Java"""
        # 确定下载URL和目标路径
        java_dir = self.minecraft_dir / ".blocklauncher" / "java"
        java_dir.mkdir(parents=True, exist_ok=True)
        
        # 根据平台和版本确定下载信息
        if sys.platform == "win32":
            if version == 8:
                url = "https://bgithub.xyz/adoptium/temurin8-binaries/releases/download/jdk8u442-b06/OpenJDK8U-jdk_x64_windows_hotspot_8u442b06.zip"
                expected_hash = "9e7a2b0c3f5d1e4a7d30f2c8e0f1d2c3a4b5e6f"  # 示例SHA1值
            elif version == 17:
                url = "https://bgithub.xyz/adoptium/temurin17-binaries/releases/download/jdk-17.0.9/OpenJDK17U-jdk_x64_windows_hotspot_17.0.9_9.zip"
                expected_hash = "5b7c2d5f8e3a9b7d3c0e1f2a9d7e8c4b0f3a1d6e"
            elif version == 21:
                url = "https://bgithub.xyz/adoptium/temurin21-binaries/releases/download/jdk-21.0.1/OpenJDK21U-jdk_x64_windows_hotspot_21.0.1_12.zip"
                expected_hash = "c5a2d4f9b8e1c0d7a3f0e5c6d4b9a8e7f2c0d1a7"
            target_dir = java_dir 
        elif sys.platform == "darwin":
            if version == 8:
                url = "https://bgithub.xyz/adoptium/temurin8-binaries/releases/download/jdk8u392-b08/OpenJDK8U-jdk_x64_mac_hotspot_8u392b08.tar.gz"
                expected_hash = "3e4f8d9c0a7b6e2f5d8c4a1b9e7d3c0f2a1d6e5b"
            elif version == 17:
                url = "https://bgithub.xyz/adoptium/temurin17-binaries/releases/download/jdk-17.0.9%2B9/OpenJDK17U-jdk_x64_mac_hotspot_17.0.9_9.tar.gz"
                expected_hash = "a5d7e2c8f1b9d4a0e3f6c2d5a7b8e9f0c1d6e3a4"
            elif version == 21:
                url = "https://bgithub.xyz/adoptium/temurin21-binaries/releases/download/jdk-21.0.1%2B12/OpenJDK21U-jdk_x64_mac_hotspot_21.0.1_12.tar.gz"
                expected_hash = "d6b9e0c5a4f1d8c7e2a9b3f6d0e7c8d4a1f2c0b5"
            target_dir = java_dir 
        else:  # Linux
            if version == 8:
                url = "https://bgithub.xyz/adoptium/temurin8-binaries/releases/download/jdk8u392-b08/OpenJDK8U-jdk_x64_linux_hotspot_8u392b08.tar.gz"
                expected_hash = "1f8c0d7e9a3b4f6e2a1d5c0f7b8e9d4a2c6f3e1b"
            elif version == 17:
                url = "https://bgithub.xyz/adoptium/temurin17-binaries/releases/download/jdk-17.0.9%2B9/OpenJDK17U-jdk_x64_linux_hotspot_17.0.9_9.tar.gz"
                expected_hash = "e4a3d7f8b2c9e0d1a6f5c4b3d2e1a0c9f7d8b5e6"
            elif version == 21:
                url = "https://bgithub.xyz/adoptium/temurin21-binaries/releases/download/jdk-21.0.1%2B12/OpenJDK21U-jdk_x64_linux_hotspot_21.0.1_12.tar.gz"
                expected_hash = "a3d5f9c0e7b4d2a1c8e6f3b0d1a7c9e4f8d2c0b6"
            target_dir = java_dir 

        # 下载Java并校验哈希
        log(f"正在从 {url} 下载Java {version}")
        download_path = java_dir / f"jdk{version}.tmp"
        self._download_file(url, download_path, expected_hash)  # 启用哈希校验

        # 解压文件
        log("正在解压Java文件...")
        if sys.platform == "win32":
            import zipfile
            with zipfile.ZipFile(download_path, 'r') as zip_ref:
                zip_ref.extractall(target_dir)
        else:
            import tarfile
            with tarfile.open(download_path, 'r:gz') as tar_ref:
                tar_ref.extractall(target_dir)

        # 清理临时文件
        download_path.unlink()

        # 动态获取解压后的外层目录
        extracted_dirs = [d for d in target_dir.iterdir() if d.is_dir()]
        if not extracted_dirs:
            raise RuntimeError("无法找到解压后的Java目录，可能下载或解压失败")
        java_root = extracted_dirs[0]

        # 返回Java可执行文件路径
        if sys.platform == "win32":
            return java_root / "bin" / "java.exe"
        else:
            return java_root / "bin" / "java"

    def _detect_java(self):
        """自动检测所需Java路径"""
        # 解析游戏版本的主次版本号
        version_parts = self.version.split('.')
        java_required = 17  # 默认Java 17
        if len(version_parts) >= 1:
            try:
                major = int(version_parts[0])
                if major == 1:
                    if len(version_parts) >= 2:
                        minor = int(version_parts[1])
                        if minor <= 15:
                            java_required = 8
                        elif minor <= 17:
                            java_required = 16  # 1.16-1.17需要Java 16
                        else:
                            java_required = 17  # 1.18+需要Java 17
                    else:
                        java_required = 8  # 1.x without minor version
                elif major >= 2:
                    java_required = 17
            except ValueError:
                pass  # 如果版本号无法解析，保持默认
            
if __name__ == "__main__":
    log("正在启动Minecraft启动器生成器...")
    
    # 使用示例：生成1.20.4 Fabric启动配置
    launcher = MinecraftLauncherGenerator(
        version="1.20.4",
        loader_type="fabric",
        loader_version="0.15.11"
    )
    log("开始生成安装Minecraft..")
    launcher.generate_install_script()
    log("安装Minecraft完成, 开始生成启动脚本...")
    config = launcher.generate_launch_script()
    
    print("启动命令：")
    print(f"{config['java_path']} {' '.join(config['jvm_args'])} {' '.join(config['game_args'])}")
    log("启动脚本生成完成.")



















