# Changelog

## v1.0.0 (2026-07-19)

### Added
- 支持原生 BDS / LeviLamina / Endstone 三种基岩版服务端
- `save hold` → `save query` → 复制 → `save resume` 热备份流程
- 基于文件重定向的服务器日志监控
- 独立终端窗口运行服务器，脚本窗口转发命令
- 定时自动备份（可配置间隔）
- 备份保留策略（按数量 + 按天数双重清理）
- ANSI 颜色码保留
- Windows 路径自动转义修复
- 启动时自动清理残留进程
- 配置文件模板自动生成
- 双击 `启动备份.bat` 一键启动
