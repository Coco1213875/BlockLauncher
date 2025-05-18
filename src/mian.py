from LauncherGenerator import MinecraftLauncherGenerator



launcher = MinecraftLauncherGenerator(
    version="1.20.4"
    # loader_type="fabric",
    # loader_version="0.15.11"
)
launcher.generate_install_script()
config = launcher.generate_launch_script()

with open("launch.bat", "w") as f:
    f.write(f"{config['java_path']} {' '.join(config['jvm_args'])} {' '.join(config['game_args'])}")
