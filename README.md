# Weaver

渗透测试 Agent 框架，基于 Claude Code 架构。

## 安装

```bash
# 前置条件：Node.js >= 18, Bun
npm install -g bun   # 如果还没装 bun

# 克隆并安装依赖
cd D:\github_project\Weaver
bun install

# 配置 API Key（二选一）
# 方式 1: 环境变量
export ANTHROPIC_API_KEY="sk-ant-..."

# 方式 2: 配置文件
mkdir -p ~/.weaver
echo '{"apiKey": "sk-ant-..."}' > ~/.weaver/settings.json
```

## 运行

```bash
# 启动（Ink TUI 模式，需要真实终端）
bun run dev

# 经典 readline 模式（管道/非 TTY 环境）
bun run dev -- --classic
```

## 内置命令

| 命令 | 说明 |
|------|------|
| `/status` | 显示当前状态（模型、后端、token、skills） |
| `/env` | 显示执行环境 |
| `/skill` | 列出/查看已加载的 skill |
| `/mcp` | 查看 MCP 连接状态 |
| `/report` | 手动生成渗透测试报告 |
| `/compact` | 压缩对话上下文 |
| `/exit` | 退出（自动生成报告） |

## 执行后端

在 `.weaver/settings.json` 或 `~/.weaver/settings.json` 中配置：

```jsonc
{
  "backend": { "type": "local" }                    // 本地执行
  // "backend": { "type": "wsl", "distro": "kali-linux" }
  // "backend": { "type": "ssh", "host": "192.168.1.100", "port": 22, "user": "kali", "authMethod": "key", "keyFile": "~/.ssh/id_rsa" }
  // "backend": { "type": "docker", "container": "kali-pentest" }
}
```

## 测试

```bash
bun test
```

## 技术栈

TypeScript + Bun + React/Ink + Anthropic Claude API
