# Backupper

Minecraft 基岩版服务器自动备份工具。

支持 **原生 BDS** / **LeviLamina** / **Endstone** 三种服务端，通过 `save hold` → `save query` → 压缩 `worlds` → `save resume` 流程实现安全热备份。

## 快速开始

1. 编辑 `config.json`（首次运行会自动生成）：

```json
{
  "server_type": "bds",
  "server_path": "D:/Servers/MyServer",
  "backup_interval_minutes": 1440,
  "backup_keep_count": 7,
  "backup_max_age_days": 14
}
```

2. 双击 `启动备份.bat` 或运行：

```bash
python backup_runner.py
```

3. 服务器启动后，脚本窗口中可直接输入 Minecraft 命令；输入 `stop` 或按 `Ctrl+C` 停止。

## 配置项

| 字段 | 说明 |
|---|---|
| `server_type` | `"bds"` / `"levilamina"` / `"endstone"` |
| `server_path` | 服务器根目录路径（支持 `/` 或 `\`） |
| `backup_interval_minutes` | 备份间隔（分钟），1440 = 每天 |
| `backup_keep_count` | 保留最近 N 个备份 |
| `backup_max_age_days` | 超过 N 天的备份自动删除 |

详见 `配置文件说明.md`。

## 备份流程

```
save hold → 轮询 save query → Data saved
→ 复制 worlds → save resume → 压缩 zip → 清理旧备份
```

## 三端差异

| 类型 | 启动命令 | worlds 位置 |
|---|---|---|
| bds | `bedrock_server.exe` | `worlds/` |
| levilamina | `bedrock_server_mod.exe` | `worlds/` |
| endstone | `endstone`（PATH） | `bedrock_server/worlds/` |

## 许可

MIT License
