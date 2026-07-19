#!/usr/bin/env python3
"""
Minecraft Bedrock Server Backup Runner

Double-click or run:  python backup_runner.py

Reads config.json for server configuration and backup settings.
Starts the server in a visible console, tails output, and performs
scheduled backups automatically.
"""

import json
import logging
import os
import re
import shutil
import subprocess
import sys
import threading
import time
import zipfile
from datetime import datetime, timedelta
from pathlib import Path

# Enable ANSI escape codes on Windows terminal
if sys.platform == "win32":
    import ctypes
    kernel32 = ctypes.windll.kernel32
    for handle in (-11, -12):
        mode = ctypes.c_uint32()
        kernel32.GetConsoleMode(kernel32.GetStdHandle(handle), ctypes.byref(mode))
        kernel32.SetConsoleMode(kernel32.GetStdHandle(handle), mode.value | 0x0004)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
SCRIPT_DIR = Path(__file__).parent.resolve()
CONFIG_PATH = SCRIPT_DIR / "config.json"

DEFAULT_CONFIG = {
    "server_type": "bds",
    "server_path": "D:/Servers/BDS-test",
    "backup_interval_minutes": 1440,
    "backup_keep_count": 7,
    "backup_max_age_days": 14,
}

SERVER_TYPES = {
    "bds": {
        "name": "原生 BDS",
        "command": "bedrock_server.exe",
        "worlds_subdir": "worlds",
    },
    "levilamina": {
        "name": "LeviLamina",
        "command": "bedrock_server_mod.exe",
        "worlds_subdir": "worlds",
    },
    "endstone": {
        "name": "Endstone",
        "command": "endstone",
        "worlds_subdir": "bedrock_server/worlds",
    },
}

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger("backup_runner")

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
SAVE_MARKER = "Data saved. Files are now ready to be copied."
ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")


def strip_ansi(text: str) -> str:
    return ANSI_RE.sub("", text)


def load_config():
    if CONFIG_PATH.exists():
        data = _read_config_robust()
        merged = DEFAULT_CONFIG.copy()
        merged.update(data)
        sp = merged.get("server_path", "")
        if sp:
            merged["server_path"] = sp.replace("\\", "/")
        return merged
    # First run: generate a config template
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(DEFAULT_CONFIG, f, indent=2, ensure_ascii=False)
    log.info("已生成配置文件: %s", CONFIG_PATH)
    log.info("请编辑 %s 后重新运行", CONFIG_PATH.name)
    return DEFAULT_CONFIG.copy()


def _read_config_robust():
    """Read config.json, auto-fix Windows backslash paths like D:\path."""
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        raw = f.read()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        # Replace lone backslashes (not valid JSON escapes) with /
        fixed = []
        i = 0
        while i < len(raw):
            if raw[i] == "\\" and i + 1 < len(raw):
                nxt = raw[i + 1]
                if nxt in '"\\/bfnrtu':
                    fixed.append(raw[i])  # valid escape, keep
                else:
                    fixed.append("/")  # replace with forward slash
                    i += 1
                    continue
            fixed.append(raw[i])
            i += 1
        return json.loads("".join(fixed))


# ---------------------------------------------------------------------------
# Server manager
# ---------------------------------------------------------------------------
class ServerManager:
    def __init__(self):
        self.process = None
        self._running = False
        self._save_ready = threading.Event()
        self._log_path = None

    @property
    def running(self):
        return self._running

    def start(self, server_path: str, exe_name: str):
        # Resolve command: PATH commands (like 'endstone') are used as-is;
        # relative paths (like './bedrock_server.exe') are resolved to absolute.
        if "/" in exe_name or "\\" in exe_name or exe_name.startswith("."):
            exe_path = Path(server_path) / exe_name.lstrip("./")
            if not exe_path.exists():
                raise FileNotFoundError(f"找不到服务器程序: {exe_path}")
            cmd = f'"{exe_path}"'
        else:
            cmd = exe_name

        # Kill leftover processes from previous runs
        self._cleanup_orphans(Path(exe_name).name)

        log_name = f"server_output_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        self._log_path = Path(server_path) / log_name

        cmd = f'{cmd} > "{log_name}" 2>&1'
        kwargs = {
            "cwd": server_path,
            "stdin": subprocess.PIPE,
            "shell": True,
            "text": True,
            "encoding": "utf-8",
        }
        if sys.platform == "win32":
            kwargs["creationflags"] = subprocess.CREATE_NEW_CONSOLE

        self.process = subprocess.Popen(cmd, **kwargs)
        self._running = True
        self._save_ready.clear()

        threading.Thread(target=self._watch_log, daemon=True).start()

    def stop(self):
        if not self._running:
            return
        try:
            self.send_command("stop")
            time.sleep(3)
        except Exception:
            pass
        try:
            if self.process and self.process.poll() is None:
                self.process.terminate()
                self.process.wait(timeout=5)
        except Exception:
            if self.process and self.process.poll() is None:
                self.process.kill()
        self._running = False

    def send_command(self, cmd: str):
        if self.process and self.process.stdin:
            self.process.stdin.write(cmd + "\n")
            self.process.stdin.flush()

    def wait_for_save_ready(self, timeout: float = 30.0) -> bool:
        return self._save_ready.wait(timeout)

    def clear_save_ready(self):
        self._save_ready.clear()

    @staticmethod
    def _cleanup_orphans(exe_name: str):
        """Kill lingering server processes from previous runs."""
        try:
            subprocess.run(
                ["taskkill", "/F", "/IM", exe_name],
                capture_output=True,
            )
        except Exception:
            pass

    def _watch_log(self):
        pos = 0
        while self._running:
            try:
                if not self._log_path or not self._log_path.exists():
                    time.sleep(0.5)
                    continue
                with open(self._log_path, "r", encoding="utf-8", errors="replace") as f:
                    f.seek(pos)
                    for line in f:
                        raw = line.rstrip("\n\r")
                        if not raw:
                            continue
                        log.info("[SERVER] %s", raw)
                        if SAVE_MARKER in strip_ansi(raw):
                            self._save_ready.set()
                    pos = f.tell()
            except (IOError, OSError):
                pass

            if self.process and self.process.poll() is not None:
                self._running = False
                log.info("服务器进程已退出")
                break
            time.sleep(0.3)


# ---------------------------------------------------------------------------
# Backup logic
# ---------------------------------------------------------------------------
def perform_backup(server: ServerManager, config: dict) -> bool:
    server_path = config["server_path"]
    st = SERVER_TYPES[config["server_type"]]
    worlds = Path(server_path) / st["worlds_subdir"]
    backups = worlds.parent / "backups"
    keep_count = config.get("backup_keep_count", 7)
    max_age_days = config.get("backup_max_age_days", 14)

    if not worlds.exists():
        log.error("worlds 文件夹不存在: %s", worlds)
        return False

    backups.mkdir(parents=True, exist_ok=True)

    tag = datetime.now().strftime("%Y%m%d_%H%M%S")
    archive_name = f"worlds_backup_{tag}.zip"
    tmp_copy = backups / f"_tmp_worlds_copy_{tag}"
    archive_path = backups / archive_name

    log.info("=== 备份开始: %s ===", tag)

    # 1. save hold
    server.clear_save_ready()
    server.send_command("save hold")
    log.info("发送 save hold")

    # 2. poll save query
    log.info("轮询 save query ...")
    deadline = time.time() + 60
    while time.time() < deadline:
        server.send_command("save query")
        if server.wait_for_save_ready(timeout=1.0):
            log.info("Data saved!")
            break
    else:
        server.send_command("save resume")
        log.error("等待 save 完成超时")
        return False

    # 3. copy
    try:
        log.info("复制 worlds ...")
        shutil.copytree(worlds, tmp_copy)
    except Exception as e:
        server.send_command("save resume")
        log.error("复制失败: %s", e)
        return False

    # 4. resume
    server.send_command("save resume")
    log.info("发送 save resume")

    # 5. compress
    try:
        log.info("压缩中 ...")
        with zipfile.ZipFile(archive_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for root, dirs, files in os.walk(tmp_copy):
                for fn in files:
                    full = os.path.join(root, fn)
                    zf.write(full, os.path.relpath(full, tmp_copy))
    except Exception as e:
        shutil.rmtree(tmp_copy, ignore_errors=True)
        log.error("压缩失败: %s", e)
        return False

    shutil.rmtree(tmp_copy, ignore_errors=True)

    # 6. cleanup
    cleanup_backups(backups, keep_count, max_age_days)

    size_mb = archive_path.stat().st_size / (1024 * 1024)
    log.info("=== 备份完成: %s (%.1f MB) ===", archive_name, size_mb)
    return True


def cleanup_backups(backups_dir: Path, keep_count: int, max_age_days: int):
    if not backups_dir.exists():
        return
    archives = sorted(
        backups_dir.glob("worlds_backup_*.zip"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    cutoff = datetime.now() - timedelta(days=max_age_days)
    for i, archive in enumerate(archives):
        mtime = datetime.fromtimestamp(archive.stat().st_mtime)
        if i >= keep_count or mtime < cutoff:
            log.info("清理旧备份: %s", archive.name)
            archive.unlink()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    config = load_config()

    server_type = config.get("server_type", "bds")
    if server_type not in SERVER_TYPES:
        log.error("无效的服务器类型: %s (可选: bds / levilamina / endstone)", server_type)
        sys.exit(1)

    st = SERVER_TYPES[server_type]
    server_path = config.get("server_path", "")
    if not server_path or not Path(server_path).is_dir():
        log.error("服务器路径无效: %s", server_path)
        log.error("请编辑 %s 设置正确的 server_path", CONFIG_PATH.name)
        sys.exit(1)

    interval = config.get("backup_interval_minutes", 1440)
    keep = config.get("backup_keep_count", 7)
    age = config.get("backup_max_age_days", 14)

    log.info("=" * 50)
    log.info("Minecraft 基岩版备份工具")
    log.info("  服务器类型: %s", st["name"])
    log.info("  服务器路径: %s", server_path)
    log.info("  备份间隔:   %d 分钟", interval)
    log.info("  保留数量:   %d 个", keep)
    log.info("  最大保存:   %d 天", age)
    log.info("=" * 50)

    server = ServerManager()
    log.info("启动服务器...")
    try:
        server.start(server_path, st["command"])
    except Exception as e:
        log.error("启动失败: %s", e)
        sys.exit(1)

    log.info("等待服务器就绪...")
    deadline = time.time() + 120
    ready = False
    log_path = server._log_path
    while time.time() < deadline:
        if log_path.exists():
            with open(log_path, "r", encoding="utf-8", errors="replace") as f:
                if "Server started" in f.read():
                    ready = True
                    break
        if not server.running:
            log.error("服务器进程已退出")
            sys.exit(1)
        time.sleep(2)

    if not ready:
        log.error("服务器启动超时")
        server.stop()
        sys.exit(1)

    log.info("服务器已就绪！定时备份将在 %d 分钟后首次执行", interval)
    log.info("在此窗口输入命令将发送到服务器，输入 stop / Ctrl+C 停止")
    log.info("=" * 50)

    # Relay user input to the server
    def _relay_input():
        while server.running:
            try:
                line = sys.stdin.readline()
                if not line:
                    break
                cmd = line.strip()
                if not cmd:
                    continue
                if cmd.lower() in ("stop", "quit", "exit"):
                    log.info("收到 %s，正在停止服务器...", cmd)
                    server.stop()
                    break
                server.send_command(cmd)
            except (IOError, OSError):
                break

    relay_thread = threading.Thread(target=_relay_input, daemon=True)
    relay_thread.start()

    last_backup = time.time()
    try:
        while server.running:
            elapsed = time.time() - last_backup
            if elapsed >= interval * 60:
                perform_backup(server, config)
                last_backup = time.time()
            time.sleep(1)
    except KeyboardInterrupt:
        log.info("收到中断信号，正在停止...")
    finally:
        server.stop()
        log.info("已退出")


if __name__ == "__main__":
    main()
