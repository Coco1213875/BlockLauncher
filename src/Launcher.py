import os
import sys
import json
import time
import shutil
import requests
import platform
import threading
import subprocess
from pathlib import Path
from urllib.parse import urlparse
from concurrent.futures import ThreadPoolExecutor, as_completed

# 全局配置
VERSION = "1.1.0"
CONFIG_FILE = "blocklauncher_config.json"
DEFAULT_CONFIG = {
    "game_directory": str(Path.home() / "BlockLauncher"),
    "java_path": "",
    "selected_account": "",
    "accounts": {},
    "last_used_version": "",
    "selected_mirror": "官方",
    "max_memory": 2048,
    "download_threads": 8,
    "default_resource_source": "Modrinth"  # CurseForge 或 Modrinth
}

# 镜像源配置
MIRRORS = {
    "官方": {
        "base_url": "https://launchermeta.mojang.com",
        "versions_url": "https://launchermeta.mojang.com/mc/game/version_manifest.json",
        "assets_url": "https://resources.download.minecraft.net",
        "libraries_url": "https://libraries.minecraft.net",
        "forge_url": "https://files.minecraftforge.net/maven",
        "fabric_url": "https://meta.fabricmc.net",
        "quilt_url": "https://meta.quiltmc.org"
    },
    "BMCLAPI": {
        "base_url": "https://bmclapi2.bangbang93.com",
        "versions_url": "https://bmclapi2.bangbang93.com/mc/game/version_manifest.json",
        "assets_url": "https://bmclapi2.bangbang93.com/assets",
        "libraries_url": "https://bmclapi2.bangbang93.com/maven",
        "forge_url": "https://bmclapi2.bangbang93.com/maven",
        "fabric_url": "https://bmclapi2.bangbang93.com/fabric-meta",
        "quilt_url": "https://bmclapi2.bangbang93.com/quilt-meta"
    },
    "MCBBS": {
        "base_url": "https://download.mcbbs.net",
        "versions_url": "https://download.mcbbs.net/mc/game/version_manifest.json",
        "assets_url": "https://download.mcbbs.net/assets",
        "libraries_url": "https://download.mcbbs.net/maven",
        "forge_url": "https://download.mcbbs.net/maven",
        "fabric_url": "https://download.mcbbs.net/fabric-meta",
        "quilt_url": "https://download.mcbbs.net/quilt-meta"
    }
}

# 资源类型配置 - 添加Modrinth支持
RESOURCE_TYPES = {
    "mods": {
        "name": "模组 (Mods)",
        "sources": {
            "CurseForge": {
                "url": "https://api.curseforge.com/v1/mods/search?gameId=432&pageSize=20&searchFilter=",
                "headers": {"Accept": "application/json"}
            },
            "Modrinth": {
                "url": "https://api.modrinth.com/v2/search?facets=[[\"project_type:mod\"]]&limit=20&query=",
                "headers": {"User-Agent": "BlockLauncher/1.0.0 (by your_username)"}
            }
        }
    },
    "texture_packs": {
        "name": "材质包",
        "sources": {
            "CurseForge": {
                "url": "https://api.curseforge.com/v1/mods/search?gameId=432&categoryId=12&pageSize=20&searchFilter=",
                "headers": {"Accept": "application/json"}
            },
            "Modrinth": {
                "url": "https://api.modrinth.com/v2/search?facets=[[\"project_type:resourcepack\"]]&limit=20&query=",
                "headers": {"User-Agent": "BlockLauncher/1.0.0 (by your_username)"}
            }
        }
    },
    "shader_packs": {
        "name": "光影包",
        "sources": {
            "CurseForge": {
                "url": "https://api.curseforge.com/v1/mods/search?gameId=432&categoryId=6552&pageSize=20&searchFilter=",
                "headers": {"Accept": "application/json"}
            },
            "Modrinth": {
                "url": "https://api.modrinth.com/v2/search?facets=[[\"project_type:shader\"]]&limit=20&query=",
                "headers": {"User-Agent": "BlockLauncher/1.0.0 (by your_username)"}
            }
        }
    },
    "worlds": {
        "name": "世界存档",
        "sources": {
            "CurseForge": {
                "url": "https://api.curseforge.com/v1/mods/search?gameId=432&categoryId=17&pageSize=20&searchFilter=",
                "headers": {"Accept": "application/json"}
            },
            "Modrinth": {
                "url": "https://api.modrinth.com/v2/search?facets=[[\"project_type:world\"]]&limit=20&query=",
                "headers": {"User-Agent": "BlockLauncher/1.0.0 (by your_username)"}
            }
        }
    }
}

# 登录服务配置
AUTH_SERVICES = {
    "mojang": {
        "auth_url": "https://authserver.mojang.com/authenticate",
        "session_url": "https://sessionserver.mojang.com/session/minecraft/profile"
    },
    "ely": {
        "auth_url": "https://authserver.ely.by/auth/authenticate",
        "session_url": "https://authserver.ely.by/session/minecraft/profile"
    }
}

class BlockLauncher:
    def __init__(self):
        self.config = DEFAULT_CONFIG.copy()
        self.current_version = None
        self.versions = []
        self.resources = {}
        self.load_config()
        
        # 创建必要的目录
        os.makedirs(self.config["game_directory"], exist_ok=True)
        os.makedirs(os.path.join(self.config["game_directory"], "versions"), exist_ok=True)
        os.makedirs(os.path.join(self.config["game_directory"], "libraries"), exist_ok=True)
        os.makedirs(os.path.join(self.config["game_directory"], "assets"), exist_ok=True)
        os.makedirs(os.path.join(self.config["game_directory"], "mods"), exist_ok=True)
        os.makedirs(os.path.join(self.config["game_directory"], "resourcepacks"), exist_ok=True)
        os.makedirs(os.path.join(self.config["game_directory"], "shaderpacks"), exist_ok=True)
        os.makedirs(os.path.join(self.config["game_directory"], "saves"), exist_ok=True)
        
        # 检查Java安装
        self.check_java_installation()
        
        print(f"超级无敌吊炸天MC启动器 v{VERSION} 已初始化!")
        print(f"游戏目录: {self.config['game_directory']}")
        print(f"默认资源源: {self.config['default_resource_source']}")
    
    def load_config(self):
        try:
            if os.path.exists(CONFIG_FILE):
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    self.config = json.load(f)
        except:
            # 如果配置文件损坏，使用默认配置
            self.config = DEFAULT_CONFIG.copy()
            self.save_config()
    
    def save_config(self):
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(self.config, f, indent=2)
    
    def download_file(self, url, destination, show_progress=True):
        """下载单个文件，支持多线程下载"""
        try:
            # 确保目标目录存在
            os.makedirs(os.path.dirname(destination), exist_ok=True)
            
            # 发送HEAD请求获取文件大小
            response = requests.head(url, allow_redirects=True)
            total_size = int(response.headers.get('content-length', 0))
            
            # 如果文件已存在且大小匹配，跳过下载
            if os.path.exists(destination):
                if os.path.getsize(destination) == total_size:
                    if show_progress:
                        print(f"文件已存在，跳过下载: {destination}")
                    return True
            
            # 下载文件
            start_time = time.time()
            response = requests.get(url, stream=True)
            response.raise_for_status()
            
            with open(destination, 'wb') as f:
                downloaded = 0
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        
                        if show_progress and total_size > 0:
                            percent = downloaded / total_size * 100
                            speed = downloaded / (time.time() - start_time) / 1024
                            print(f"\r下载中: {os.path.basename(destination)} - {percent:.1f}% ({speed:.1f} KB/s)", end="")
            
            if show_progress:
                print(f"\n下载完成: {destination}")
            return True
        except Exception as e:
            print(f"\n下载失败: {url} -> {str(e)}")
            return False
    
    def download_files(self, file_list, max_workers=None):
        """多线程下载多个文件"""
        if not max_workers:
            max_workers = self.config["download_threads"]
        
        total = len(file_list)
        success = 0
        failed = 0
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(self.download_file, url, dest, False): (url, dest) for url, dest in file_list}
            
            for i, future in enumerate(as_completed(futures)):
                url, dest = futures[future]
                try:
                    if future.result():
                        success += 1
                        print(f"[{i+1}/{total}] 下载成功: {os.path.basename(dest)}")
                    else:
                        failed += 1
                        print(f"[{i+1}/{total}] 下载失败: {os.path.basename(dest)}")
                except Exception as e:
                    failed += 1
                    print(f"[{i+1}/{total}] 下载异常: {str(e)}")
        
        print(f"下载完成: 成功 {success}/{total}, 失败 {failed}/{total}")
        return success == total
    
    def get_mirror(self):
        """获取当前镜像配置"""
        return MIRRORS[self.config["selected_mirror"]]
    
    def load_versions(self):
        """加载可用版本列表"""
        mirror = self.get_mirror()
        
        try:
            print(f"正在从 {self.config['selected_mirror']} 镜像获取版本列表...")
            response = requests.get(mirror["versions_url"])
            response.raise_for_status()
            
            data = response.json()
            versions = data.get("versions", [])
            
            # 过滤出正式版和快照版
            release_versions = [v for v in versions if v["type"] == "release"]
            snapshot_versions = [v for v in versions if v["type"] == "snapshot"]
            
            # 只保留最新20个版本
            self.versions = release_versions[:20] + snapshot_versions[:20]
            
            print(f"成功加载 {len(self.versions)} 个版本")
            return True
        except Exception as e:
            print(f"无法获取版本列表: {str(e)}")
            return False
    
    def list_versions(self):
        """列出所有可用版本"""
        if not self.versions:
            self.load_versions()
        
        print("\n可用Minecraft版本:")
        for i, version in enumerate(self.versions):
            print(f"{i+1}. {version['id']} ({version['type']}) - {version['releaseTime']}")
    
    def download_version(self, version_index):
        """下载指定版本的Minecraft"""
        if not self.versions:
            self.load_versions()
        
        if version_index < 0 or version_index >= len(self.versions):
            print("无效的版本索引")
            return False
        
        version = self.versions[version_index]
        version_id = version["id"]
        version_url = version["url"]
        mirror = self.get_mirror()
        
        # 替换URL为镜像源
        if mirror["base_url"] != "https://launchermeta.mojang.com":
            parsed_url = urlparse(version_url)
            version_url = f"{mirror['base_url']}{parsed_url.path}"
        
        try:
            print(f"开始下载版本: {version_id}")
            
            # 下载版本元数据
            print("获取版本元数据...")
            response = requests.get(version_url)
            response.raise_for_status()
            version_data = response.json()
            
            # 创建版本目录
            version_dir = os.path.join(self.config["game_directory"], "versions", version_id)
            os.makedirs(version_dir, exist_ok=True)
            
            # 保存版本元数据
            with open(os.path.join(version_dir, f"{version_id}.json"), "w") as f:
                json.dump(version_data, f, indent=2)
            
            # 下载客户端JAR
            client_jar = version_data["downloads"]["client"]["url"]
            jar_path = os.path.join(version_dir, f"{version_id}.jar")
            
            print(f"下载客户端JAR文件...")
            self.download_file(client_jar, jar_path)
            
            # 下载资源文件
            assets_url = version_data["assetIndex"]["url"]
            assets_path = os.path.join(self.config["game_directory"], "assets", "indexes", f"{version_data['assetIndex']['id']}.json")
            
            print(f"下载资源索引...")
            self.download_file(assets_url, assets_path)
            
            # 下载资源文件
            assets_data = requests.get(assets_url).json()
            download_list = []
            
            for asset in assets_data["objects"].values():
                hash = asset["hash"]
                url = f"{mirror['assets_url']}/{hash[0:2]}/{hash}"
                dest = os.path.join(self.config["game_directory"], "assets", "objects", hash[0:2], hash)
                download_list.append((url, dest))
            
            print(f"需要下载 {len(download_list)} 个资源文件...")
            self.download_files(download_list)
            
            # 下载库文件
            libraries = version_data.get("libraries", [])
            download_list = []
            
            for lib in libraries:
                if "rules" in lib and not self.check_library_rules(lib["rules"]):
                    continue
                
                lib_data = lib["downloads"]["artifact"]
                url = lib_data["url"]
                
                # 替换为镜像源
                if mirror["libraries_url"] != "https://libraries.minecraft.net":
                    url = url.replace("https://libraries.minecraft.net", mirror["libraries_url"])
                
                path = lib_data["path"]
                dest = os.path.join(self.config["game_directory"], "libraries", path)
                download_list.append((url, dest))
            
            print(f"需要下载 {len(download_list)} 个库文件...")
            self.download_files(download_list)
            
            print(f"版本 {version_id} 下载完成!")
            return True
        except Exception as e:
            print(f"下载版本失败: {str(e)}")
            return False
    
    def check_library_rules(self, rules):
        """检查库文件规则是否适用于当前系统"""
        allow = False
        os_name = platform.system().lower()
        
        for rule in rules:
            if "action" not in rule:
                continue
                
            if rule["action"] == "allow":
                if "os" in rule:
                    if rule["os"]["name"] == os_name:
                        allow = True
                    else:
                        allow = False
                else:
                    allow = True
            elif rule["action"] == "disallow":
                if "os" in rule:
                    if rule["os"]["name"] == os_name:
                        allow = False
                else:
                    allow = False
                    
        return allow
    
    def download_mod_loader(self, loader_type, version, mc_version=None):
        """下载mod加载器"""
        mirror = self.get_mirror()
        
        try:
            if loader_type.lower() == "forge":
                print(f"下载Forge加载器 (Minecraft {mc_version})")
                
                # 获取Forge版本列表
                metadata_url = f"{mirror['forge_url']}/net/minecraftforge/forge/maven-metadata.xml"
                response = requests.get(metadata_url)
                response.raise_for_status()
                
                # 解析XML获取版本
                # 这里简化处理，实际需要解析XML
                forge_version = f"{mc_version}-recommended"
                installer_url = f"{mirror['forge_url']}/net/minecraftforge/forge/{forge_version}/forge-{forge_version}-installer.jar"
                
                # 下载安装器
                dest = os.path.join(self.config["game_directory"], "forge_installer.jar")
                self.download_file(installer_url, dest)
                
                # 运行安装器
                print("运行Forge安装器...")
                subprocess.run([self.config["java_path"], "-jar", dest, "--installServer"], check=True)
                print("Forge安装完成!")
                return True
            
            elif loader_type.lower() == "fabric":
                print(f"下载Fabric加载器 (Minecraft {mc_version})")
                
                # 获取Fabric加载器版本
                loader_url = f"{mirror['fabric_url']}/v2/versions/loader/{mc_version}"
                response = requests.get(loader_url)
                response.raise_for_status()
                loader_data = response.json()
                
                if not loader_data:
                    print("未找到Fabric加载器版本")
                    return False
                
                loader_version = loader_data[0]["loader"]["version"]
                installer_url = f"{mirror['fabric_url']}/v2/versions/loader/{mc_version}/{loader_version}/profile/json"
                
                # 下载安装配置文件
                profile_path = os.path.join(self.config["game_directory"], "versions", f"fabric-loader-{loader_version}-{mc_version}", f"fabric-loader-{loader_version}-{mc_version}.json")
                self.download_file(installer_url, profile_path)
                print("Fabric安装完成!")
                return True
            
            elif loader_type.lower() == "quilt":
                print(f"下载Quilt加载器 (Minecraft {mc_version})")
                
                # 获取Quilt加载器版本
                loader_url = f"{mirror['quilt_url']}/v3/versions/loader/{mc_version}"
                response = requests.get(loader_url)
                response.raise_for_status()
                loader_data = response.json()
                
                if not loader_data:
                    print("未找到Quilt加载器版本")
                    return False
                
                loader_version = loader_data[0]["loader"]["version"]
                installer_url = f"{mirror['quilt_url']}/v3/versions/loader/{mc_version}/{loader_version}/profile/json"
                
                # 下载安装配置文件
                profile_path = os.path.join(self.config["game_directory"], "versions", f"quilt-loader-{loader_version}-{mc_version}", f"quilt-loader-{loader_version}-{mc_version}.json")
                self.download_file(installer_url, profile_path)
                print("Quilt安装完成!")
                return True
            
            else:
                print(f"未知的mod加载器类型: {loader_type}")
                return False
        except Exception as e:
            print(f"下载mod加载器失败: {str(e)}")
            return False
    
    def download_resource(self, resource_type, resource_id, source=None):
        """下载资源（mod、材质包等），支持多来源"""
        if resource_type not in RESOURCE_TYPES:
            print(f"无效的资源类型: {resource_type}")
            return False
        
        if not source:
            source = self.config["default_resource_source"]
        
        resource_cfg = RESOURCE_TYPES[resource_type]
        
        if source not in resource_cfg["sources"]:
            print(f"资源源 '{source}' 不支持资源类型 '{resource_type}'")
            return False
        
        source_cfg = resource_cfg["sources"][source]
        
        try:
            if source == "CurseForge":
                return self._download_curseforge_resource(resource_type, resource_id, source_cfg)
            elif source == "Modrinth":
                return self._download_modrinth_resource(resource_type, resource_id, source_cfg)
            else:
                print(f"不支持的资源源: {source}")
                return False
        except Exception as e:
            print(f"下载资源失败: {str(e)}")
            return False
    
    def _download_curseforge_resource(self, resource_type, resource_id, source_cfg):
        """从CurseForge下载资源"""
        print(f"获取CurseForge资源信息 (ID: {resource_id})...")
        url = source_cfg["url"] + resource_id
        headers = source_cfg.get("headers", {})
        
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        
        data = response.json()
        if not data.get("data") or not data["data"]:
            print("未找到资源")
            return False
        
        item = data["data"][0]
        if not item.get("latestFiles"):
            print("资源没有可用文件")
            return False
            
        latest_file = item["latestFiles"][0]
        download_url = latest_file["downloadUrl"]
        
        if not download_url:
            print("资源没有下载链接")
            return False
            
        # 确定保存路径
        if resource_type == "mods":
            dest_dir = os.path.join(self.config["game_directory"], "mods")
        elif resource_type == "texture_packs":
            dest_dir = os.path.join(self.config["game_directory"], "resourcepacks")
        elif resource_type == "shader_packs":
            dest_dir = os.path.join(self.config["game_directory"], "shaderpacks")
        elif resource_type == "worlds":
            dest_dir = os.path.join(self.config["game_directory"], "saves")
        else:
            dest_dir = self.config["game_directory"]
        
        os.makedirs(dest_dir, exist_ok=True)
        dest_path = os.path.join(dest_dir, latest_file["fileName"])
        
        print(f"下载资源: {item['name']} ({latest_file['fileLength']//1024} KB)")
        return self.download_file(download_url, dest_path)
    
    def _download_modrinth_resource(self, resource_type, resource_id, source_cfg):
        """从Modrinth下载资源"""
        print(f"获取Modrinth资源信息 (ID: {resource_id})...")
        
        # 第一步：获取项目信息
        project_url = f"https://api.modrinth.com/v2/project/{resource_id}"
        headers = source_cfg.get("headers", {})
        
        project_response = requests.get(project_url, headers=headers)
        project_response.raise_for_status()
        project_data = project_response.json()
        
        if not project_data:
            print("未找到项目")
            return False
        
        project_id = project_data["id"]
        project_name = project_data["title"]
        
        # 第二步：获取项目版本
        versions_url = f"https://api.modrinth.com/v2/project/{project_id}/version"
        versions_response = requests.get(versions_url, headers=headers)
        versions_response.raise_for_status()
        versions_data = versions_response.json()
        
        if not versions_data:
            print("项目没有可用版本")
            return False
        
        # 选择最新版本
        latest_version = versions_data[0]
        
        # 选择适合当前系统的文件
        game_files = []
        os_name = platform.system().lower()
        
        for file in latest_version["files"]:
            # 检查平台兼容性
            if "platforms" in file:
                if os_name == "windows" and "windows" not in file["platforms"]:
                    continue
                elif os_name == "linux" and "linux" not in file["platforms"]:
                    continue
                elif os_name == "darwin" and "macos" not in file["platforms"]:
                    continue
            
            # 检查是否为主要文件（不是额外文件）
            if file["primary"]:
                game_files.append(file)
        
        if not game_files:
            print("没有找到适合当前平台的文件")
            return False
        
        # 选择第一个主要文件
        game_file = game_files[0]
        download_url = game_file["url"]
        file_name = game_file["filename"]
        
        # 确定保存路径
        if resource_type == "mods":
            dest_dir = os.path.join(self.config["game_directory"], "mods")
        elif resource_type == "texture_packs":
            dest_dir = os.path.join(self.config["game_directory"], "resourcepacks")
        elif resource_type == "shader_packs":
            dest_dir = os.path.join(self.config["game_directory"], "shaderpacks")
        elif resource_type == "worlds":
            dest_dir = os.path.join(self.config["game_directory"], "saves")
        else:
            dest_dir = self.config["game_directory"]
        
        os.makedirs(dest_dir, exist_ok=True)
        dest_path = os.path.join(dest_dir, file_name)
        
        print(f"下载资源: {project_name} ({file_name}, {game_file['size']//1024} KB)")
        return self.download_file(download_url, dest_path)
    
    def download_java(self, version_id=None):
        """根据版本自动下载并安装合适的Java版本"""
        os_name = platform.system().lower()
        arch = platform.machine().lower()

        # 确定系统架构
        if arch in ["x86_64", "amd64"]:
            arch = "x64"
        elif arch in ["i386", "i686", "x86"]:
            arch = "x86"
        elif arch.startswith("arm") or arch.startswith("aarch"):
            arch = "arm" if "64" not in arch else "arm64"
        else:
            print(f"不支持的架构: {arch}")
            return False

        # 确定Java版本
        java_version = "17"
        if version_id:
            try:
                parts = version_id.split('.')
                if len(parts) >= 2:
                    major = parts[0]
                    minor = parts[1]
                    if major == "1" and minor.isdigit():
                        minor_num = int(minor)
                        if minor_num <= 16:
                            java_version = "8"
                        elif minor_num == 17:
                            java_version = "16"
                        elif 18 <= minor_num <= 20:
                            java_version = "17"
                        else:  # 1.21+
                            java_version = "21"
                    elif major == "2":  # 未来版本
                        java_version = "21"
            except:
                print("版本解析失败，使用默认Java版本")

        # 使用Adoptium的OpenJDK
        # 主下载源：GitHub
        # 镜像源：华为云镜像
        adoptium_version = {
            "8": "jdk8u392-b08",
            "16": "jdk-16.0.2+7",
            "17": "jdk-17.0.9+9",
            "21": "jdk-21.0.1+12"
        }.get(java_version, "jdk-17.0.9+9")
        
        # 构建下载URL
        base_urls = [
            f"https://github.com/adoptium/temurin{java_version}-binaries/releases/download/{adoptium_version}",
            f"https://mirrors.huaweicloud.com/java/jdk/{adoptium_version}"
        ]
        
        # 文件后缀
        if os_name == "windows":
            suffix = "zip"
            os_str = "windows"
        elif os_name == "linux":
            suffix = "tar.gz"
            os_str = "linux"
        elif os_name == "darwin":
            suffix = "tar.gz"
            os_str = "mac"
        else:
            print(f"不支持的操作系统: {os_name}")
            return False

        # 文件名模板
        file_template = {
            "windows": {
                "x64": f"OpenJDK{java_version}U-jdk_x64_{os_str}_hotspot_{adoptium_version.split('+')[0]}.{suffix}",
                "x86": f"OpenJDK{java_version}U-jdk_x86-32_{os_str}_hotspot_{adoptium_version.split('+')[0]}.{suffix}",
                "arm64": f"OpenJDK{java_version}U-jdk_aarch64_{os_str}_hotspot_{adoptium_version.split('+')[0]}.{suffix}"
            },
            "linux": {
                "x64": f"OpenJDK{java_version}U-jdk_x64_{os_str}_hotspot_{adoptium_version.split('+')[0]}.{suffix}",
                "arm": f"OpenJDK{java_version}U-jdk_arm_{os_str}_hotspot_{adoptium_version.split('+')[0]}.{suffix}",
                "arm64": f"OpenJDK{java_version}U-jdk_aarch64_{os_str}_hotspot_{adoptium_version.split('+')[0]}.{suffix}"
            },
            "darwin": {
                "x64": f"OpenJDK{java_version}U-jdk_x64_{os_str}_hotspot_{adoptium_version.split('+')[0]}.{suffix}",
                "arm64": f"OpenJDK{java_version}U-jdk_aarch64_{os_str}_hotspot_{adoptium_version.split('+')[0]}.{suffix}"
            }
        }

        if os_name not in file_template:
            print(f"不支持的操作系统: {os_name}")
            return False

        if arch not in file_template[os_name]:
            print(f"不支持的架构: {arch} for {os_name}")
            return False

        file_name = file_template[os_name][arch]
        print(f"下载Java运行时 {java_version} ({os_name}-{arch})...")
        
        # 尝试多个源直到成功
        downloaded = False
        java_zip = None
        for base_url in base_urls:
            java_url = f"{base_url}/{file_name}"
            print(f"尝试从 {base_url} 下载...")
            
            java_dir = os.path.join(self.config["game_directory"], "java")
            os.makedirs(java_dir, exist_ok=True)
            java_zip = os.path.join(java_dir, file_name)
            
            if self.download_file(java_url, java_zip):
                downloaded = True
                break
            else:
                print(f"从 {base_url} 下载失败")
        
        if not downloaded:
            print("所有下载源均失败")
            return False

        # 解压Java
        print("解压Java运行时...")
        try:
            shutil.unpack_archive(java_zip, java_dir)
            print("解压成功")
        except Exception as e:
            print(f"解压失败: {str(e)}")
            return False

        # 删除压缩包
        try:
            os.remove(java_zip)
        except Exception as e:
            print(f"删除压缩包失败: {str(e)}")

        # 设置Java路径
        java_bin = "java"
        if os_name == "windows":
            java_bin = "java.exe"

        # 查找Java可执行文件 - 在解压目录中搜索
        java_path = None
        for root, dirs, files in os.walk(java_dir):
            if java_bin in files:
                java_path = os.path.join(root, java_bin)
                break
        
        if java_path:
            self.config["java_path"] = java_path
            self.save_config()
            print(f"Java安装完成: {java_path}")
            return True

        print("未找到Java可执行文件")
        return False
    
    def check_java_installation(self, version_id=None):
        """检查Java安装状态和版本"""
        required_version = self._get_java_version_for_mc(version_id)
        
        # 如果Java路径存在，检查其版本
        if self.config["java_path"] and os.path.exists(self.config["java_path"]):
            try:
                # 检查Java版本
                result = subprocess.run(
                    [self.config["java_path"], "-version"],
                    capture_output=True,
                    text=True,
                    check=True
                )
                
                # 解析版本信息
                version_info = result.stderr.splitlines()[0]
                if "version" in version_info:
                    # 提取Java版本号
                    version_str = version_info.split()[2].replace('"', '')
                    installed_version = int(version_str.split('.')[0])
                    
                    # 检查版本是否满足要求
                    if installed_version >= required_version:
                        print(f"Java状态: 已安装 ({version_info.strip()}), 满足版本要求 (需要 >= {required_version})")
                        return True
                    else:
                        print(f"Java版本过低: 已安装 {installed_version}, 需要 {required_version} 或更高")
                else:
                    print("无法解析Java版本信息")
            except Exception as e:
                print(f"检查Java版本失败: {str(e)}")
        
        # 如果Java不存在或版本不匹配，下载合适的版本
        print(f"Java未安装或版本不匹配，正在尝试自动下载Java {required_version}...")
        if self.download_java(version_id=version_id):
            return True
        print("无法自动下载Java，请手动安装Java并设置路径")
        return False
    
    def _get_java_version_for_mc(self, version_id):
        """根据Minecraft版本确定所需的Java版本"""
        if version_id:
            try:
                parts = version_id.split('.')
                if len(parts) >= 2:
                    major = parts[0]
                    minor = parts[1]
                    if major == "1" and minor.isdigit():
                        minor_num = int(minor)
                        if minor_num <= 16:
                            return 8
                        elif minor_num == 17:
                            return 16
                        elif 18 <= minor_num <= 20:
                            return 17
                        else:  # 1.21+
                            return 21
                    elif major == "2":  # 未来版本
                        return 21
            except:
                pass
        return 17  # 默认值
    
    def authenticate(self, username, password, service="mojang"):
        """账户认证"""
        if service not in AUTH_SERVICES:
            print(f"不支持的登录服务: {service}")
            return None
        
        auth_url = AUTH_SERVICES[service]["auth_url"]
        session_url = AUTH_SERVICES[service]["session_url"]
        
        try:
            # 认证请求
            payload = {
                "username": username,
                "password": password,
                "requestUser": True,
                "agent": {
                    "name": "Minecraft",
                    "version": 1
                }
            }
            
            print(f"正在通过 {service} 认证...")
            response = requests.post(auth_url, json=payload)
            response.raise_for_status()
            auth_data = response.json()
            
            # 获取会话
            access_token = auth_data["accessToken"]
            uuid = auth_data["selectedProfile"]["id"]
            username = auth_data["selectedProfile"]["name"]
            
            print(f"认证成功: {username} ({uuid})")
            
            # 获取皮肤信息
            skin_data = self.get_skin_data(uuid, access_token, service)
            
            return {
                "username": username,
                "uuid": uuid,
                "access_token": access_token,
                "skin_data": skin_data
            }
        except Exception as e:
            print(f"认证失败: {str(e)}")
            return None
    
    def get_skin_data(self, uuid, access_token, service="mojang"):
        """获取皮肤数据"""
        session_url = AUTH_SERVICES[service]["session_url"]
        
        try:
            headers = {"Authorization": f"Bearer {access_token}"}
            response = requests.get(f"{session_url}/{uuid}", headers=headers)
            response.raise_for_status()
            
            profile_data = response.json()
            textures = profile_data.get("textures", {})
            skin_url = textures.get("SKIN", {}).get("url")
            cape_url = textures.get("CAPE", {}).get("url")
            
            skin_path = None
            if skin_url:
                skin_dir = os.path.join(self.config["game_directory"], "skins")
                os.makedirs(skin_dir, exist_ok=True)
                skin_path = os.path.join(skin_dir, f"{uuid}_skin.png")
                self.download_file(skin_url, skin_path, False)
                print(f"皮肤已下载: {skin_path}")
            
            cape_path = None
            if cape_url:
                cape_dir = os.path.join(self.config["game_directory"], "capes")
                os.makedirs(cape_dir, exist_ok=True)
                cape_path = os.path.join(cape_dir, f"{uuid}_cape.png")
                self.download_file(cape_url, cape_path, False)
                print(f"披风已下载: {cape_path}")
            
            return {
                "skin": skin_path,
                "cape": cape_path
            }
        except Exception as e:
            print(f"获取皮肤信息失败: {str(e)}")
            return {}
    
    def generate_launch_command(self, version_id, username, uuid=None, access_token=None):
        """生成启动命令"""
        version_dir = os.path.join(self.config["game_directory"], "versions", version_id)
        version_json = os.path.join(version_dir, f"{version_id}.json")
        
        if not os.path.exists(version_json):
            print(f"版本 {version_id} 未安装")
            return None
        
        try:
            # 加载版本数据
            with open(version_json, "r") as f:
                version_data = json.load(f)
            
            # 基本参数
            main_class = version_data["mainClass"]
            game_args = [
                "--username", username,
                "--version", version_id,
                "--gameDir", self.config["game_directory"],
                "--assetsDir", os.path.join(self.config["game_directory"], "assets"),
                "--assetIndex", version_data["assetIndex"]["id"],
                "--uuid", uuid if uuid else "11451400-cnm0-rnm0-gggg-000000sb0cjr",
                "--accessToken", access_token if access_token else "0",
                "--userType", "mojang" if access_token else "legacy",
                "--versionType", "BlockLauncher"
            ]
            
            # JVM参数
            jvm_args = [
                self.config["java_path"],
                f"-Xmx{self.config['max_memory']}M",
                f"-Djava.library.path={os.path.join(self.config['game_directory'], 'natives')}",
                "-Dfml.ignoreInvalidMinecraftCertificates=true",
                "-Dfml.ignorePatchDiscrepancies=true"
            ]
            
            # 添加库文件
            libraries = version_data.get("libraries", [])
            classpath = []
            
            for lib in libraries:
                if "rules" in lib and not self.check_library_rules(lib["rules"]):
                    continue
                
                lib_data = lib["downloads"]["artifact"]
                path = lib_data["path"]
                lib_path = os.path.join(self.config["game_directory"], "libraries", path)
                
                if os.path.exists(lib_path):
                    classpath.append(lib_path)
            
            # 添加主JAR
            main_jar = os.path.join(version_dir, f"{version_id}.jar")
            classpath.append(main_jar)
            
            # 设置classpath
            jvm_args.append("-cp")
            jvm_args.append(os.pathsep.join(classpath))
            
            # 添加主类
            jvm_args.append(main_class)
            
            # 合并所有参数
            command = jvm_args + game_args
            return command
        except Exception as e:
            print(f"生成启动命令失败: {str(e)}")
            return None
    
    def launch_game(self, version_id, account):
        """启动游戏"""
        # 检查Java安装
        if not self.check_java_installation(version_id=version_id):
            print("Java安装失败或版本不匹配，无法启动游戏")
            return False
        
        # 生成启动命令
        command = self.generate_launch_command(
            version_id, 
            account["username"], 
            account.get("uuid"), 
            account.get("access_token")
        )
        
        if not command:
            return False
        
        try:
            print("启动Minecraft...")
            print("命令: " + " ".join(command))
            
            # 启动游戏
            process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True
            )
            
            # 实时输出游戏日志
            while True:
                output = process.stdout.readline()
                if output == '' and process.poll() is not None:
                    break
                if output:
                    print(output.strip())
            
            print("游戏进程已退出")
            return True
        except Exception as e:
            print(f"启动游戏失败: {str(e)}")
            return False

# 示例用法
if __name__ == "__main__":
    launcher = BlockLauncher()
    
    # 加载版本列表
    launcher.load_versions()
    
    # 列出可用版本
    launcher.list_versions()
    
    # 下载版本（示例：下载第一个版本）
    launcher.download_version(0)
    
    # 下载mod加载器（示例：下载Fabric）
    # launcher.download_mod_loader("fabric", "1.20.1")
    
    # 下载资源（示例：从Modrinth下载一个mod）
    # launcher.download_resource("mods", "sodium", "Modrinth")
    
    # 账户认证（示例：离线登录）
    offline_account = {
        "username": "BlockLauncherPlayer",
        "uuid": None,
        "access_token": None
    }
    
    # 启动游戏（示例：启动第一个版本）
    if launcher.versions:
        version_id = launcher.versions[0]["id"]
        launcher.launch_game(version_id, offline_account)