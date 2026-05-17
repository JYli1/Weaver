# Weaver 设计文档

## 1. 项目定位

Weaver 是一个基于 Claude Code 架构的渗透测试 agent 框架。它是 Claude Code 的精简版，保留完整的代码能力和通用交互能力，同时在渗透测试方面做专精增强。

**核心定位：** 通用 AI 编程助手 + 渗透测试专精

**目标场景：** 授权渗透测试

**与 Claude Code 的关系：** 从 Claude Code 源码提取核心模块重组（方案 B: Core Extract），不跟随 Claude Code 后续更新，完全独立维护。

**启动方式：** 和 Claude Code 一样，终端输入 `weaver` 即启动 agent，直接给提示词开始工作。无需额外配置目标范围等前置步骤。

---

## 2. 整体架构

### 2.1 四层架构

```
┌──────────────────────────────────────────────┐
│  TUI 层 (React + Ink)                        │
│  - 消息流、输入框、确认弹窗                  │
│  - 状态面板、实时状态栏                      │
│  - 阶段颜色区分                              │
│  - 退出时触发报告生成                        │
├──────────────────────────────────────────────┤
│  执行内核                                    │
│  - QueryEngine (tool-calling 主循环)         │
│  - 协调者 + 子 agent 调度                    │
├──────────────────────────────────────────────┤
│  工具层                                      │
│  - BashTool (可配置执行后端)                 │
│  - AgentTool (spawn 子 agent)                │
│  - SkillTool (技能调用)                      │
│  - TokenTracker (token/上下文窗口显示)        │
│  - FileReadTool / FileWriteTool / FileEditTool│
│  - GlobTool / GrepTool                       │
│  - WebSearchTool / WebFetchTool              │
│  - NotebookEditTool                          │
├──────────────────────────────────────────────┤
│  持久层                                      │
│  - Session 记录                              │
│  - 报告生成 (退出时自动)                     │
│  - 统一目录按日期存储                        │
└──────────────────────────────────────────────┘
```

### 2.2 主链路

```
entrypoints/cli.ts → main.ts → init + setup
  → launchRepl() → REPL.tsx
  → 用户输入 → query()
    → Claude API → tool_use → runTools()
      → BashTool/AgentTool/SkillTool 执行
    → tool_result → 下一轮 query
  → 用户退出 → 自动生成报告 → 保存
```

---

## 3. BashTool 与执行后端

### 3.1 执行原理

复用 Claude Code 的 BashTool 核心：`child_process.spawn()` 起子进程，stdout/stderr 合并写入文件，每秒轮询文件尾部做进度展示。

### 3.2 可配置后端

在 `spawn()` 层加 backend 抽象，支持四种执行环境：

```typescript
type ExecBackend =
  | { type: 'local' }
  | { type: 'wsl'; distro: string }
  | { type: 'ssh'; host: string; port: number; user: string; authMethod: 'password' | 'key' | 'agent'; password?: string; passwordHelper?: string; keyFile?: string }
  | { type: 'docker'; container: string }
```

执行时根据 backend 类型构造不同的 spawn 参数：

| Backend | spawn 命令 |
|---------|-----------|
| local | `spawn('bash', ['-c', command])` |
| wsl | `spawn('wsl', ['-d', distro, '--', 'bash', '-c', command])` |
| ssh | `spawn('ssh', ['-p', port, 'user@host', command])` |
| docker | `spawn('docker', ['exec', container, 'bash', '-c', command])` |

其余机制（输出捕获、超时、进度轮询、tree-kill）全部复用，不改动。

### 3.3 SSH 认证

支持三种方式：
- `password` — 直接密码或 `passwordHelper` 脚本输出密码（避免明文存储）
- `key` — 私钥文件路径
- `agent` — SSH agent 转发

---

---

## 5. 多 Agent 协调

### 5.1 模式

协调者（主 agent）+ 子 agent 并行。复用 Claude Code 的 AgentTool。

```
主 Agent（协调者）
  ├── spawn 子 Agent A → 扫描子网 192.168.1.0/24
  ├── spawn 子 Agent B → 扫描子网 10.0.0.0/24
  └── spawn 子 Agent C → 对已发现服务做漏洞枚举
```

### 5.2 约束

- 各自有独立的 Bash 执行环境
- 结果汇报回主 agent
- 主 agent 通过 prompt 描述任务，子 agent 完成后返回结果文本

---

## 6. Skill 系统

### 6.1 机制

完整复用 Claude Code 的 skill 基础设施：
- SkillTool — LM 通过 tool call 调用 skill
- Inline 模式 — skill 内容注入为 user message
- Fork 模式 — 在子 agent 中执行
- `/skill` 命令 — 用户管理 skill

### 6.2 Skill 文件格式

目录结构 `skill-name/SKILL.md`，YAML frontmatter + markdown 内容：

```markdown
---
name: network-recon
description: 网络侦察与端口扫描方法论
when_to_use: 当需要对目标进行网络层面的侦察时
---

## 方法论
1. 存活探测: nmap -sn {target}
2. 全端口扫描: nmap -sV -sC -p- {target}
...
```

### 6.3 加载来源（三层）

| 来源 | 路径 | 说明 |
|------|------|------|
| 内置 skill | `src/skills/bundled/` | 随项目发布的渗透方法论 |
| 用户全局 skill | `~/.weaver/skills/` | 用户自定义，跨项目 |
| 项目级 skill | `.weaver/skills/` | 项目特定 |

优先级：项目级 > 用户全局 > 内置。同名时高优先级覆盖低优先级。

### 6.4 /skill 命令

```
/skill list              — 列出所有已加载 skill（内置 + 自定义）
/skill show <name>       — 查看某个 skill 内容
/skill add <name>        — 交互式创建新 skill 到 .weaver/skills/
/skill edit <name>       — 编辑已有 skill
/skill remove <name>     — 删除自定义 skill
/skill enable/disable    — 启用/禁用某个 skill
```

### 6.5 内置渗透 Skill 分类

```
skills/bundled/
  recon/                  # 侦察阶段
    network-discovery/    (nmap, masscan, arp-scan)
    subdomain-enum/       (subfinder, amass, dnsrecon)
    web-fingerprint/      (whatweb, wappalyzer, httpx)
  enum/                   # 枚举阶段
    service-enum/         (针对各服务的枚举方法)
    web-fuzzing/          (ffuf, gobuster, feroxbuster)
    credential-spray/     (hydra, crackmapexec)
  exploit/                # 利用阶段
    web-vuln/             (sqli, xss, ssti, ssrf)
    known-cve/            (searchsploit, metasploit)
    privesc/              (linpeas, winpeas, sudo abuse)
  post/                   # 后渗透
    lateral-movement/     (psexec, wmi, ssh pivot)
    persistence/          (cron, service, registry)
    data-exfil/           (安全的数据收集方法)
  report/                 # 报告
    session-summary/      (退出时自动整理模板)
```

---

## 7. MCP Client 支持

### 7.1 保留内容

保留 Claude Code 的 MCP **client** 能力：
- MCP client 连接（`services/mcp/client.ts`）
- MCP 工具注册和调用
- `/mcp` 命令管理连接

### 7.2 删除内容

- MCP server 模式（不需要把自己暴露为 MCP server）

### 7.3 配置方式

```jsonc
// .weaver/settings.json
{
  "mcpServers": {
    "burpsuite": {
      "command": "burp-mcp-server",
      "args": ["--port", "8080"]
    },
    "caido": {
      "command": "npx",
      "args": ["caido-mcp"]
    }
  }
}
```

---

## 8. Session 记录与退出报告

### 8.1 Session 记录

每次启动自动创建 session，所有交互和工具输出实时记录。复用 Claude Code 的 sessionStorage 机制。

### 8.2 退出时自动生成报告

正常退出流程（`/exit` 或 Ctrl+D）中插入报告生成步骤：

```
用户退出
  → 触发 report skill（内置 session-summary）
  → LM 总结本次 session 的关键发现
  → 生成结构化报告
  → 保存到统一目录
```

### 8.3 报告存储

```
~/.weaver/reports/
  2026-05-17_192.168.1.0-24_recon.md
  2026-05-17_example.com_full-pentest.md
```

命名格式：`{日期}_{目标}_{阶段或描述}.md`

### 8.4 报告内容模板

```markdown
# 渗透测试报告
- 目标: {scope}
- 时间: {start} ~ {end}
- 操作者: {user}

## 发现摘要
- 高危: X 个
- 中危: X 个
- 低危: X 个

## 详细发现
### [高危] {漏洞名称}
- 位置: ...
- 描述: ...
- 复现步骤: ...
- 建议修复: ...

## 执行的操作时间线
...
```

---

## 9. 配置系统

### 9.1 配置文件层级（优先级从高到低）

```
命令行参数 (--backend, --model)
  ↓
项目级 .weaver/settings.json
  ↓
用户级 ~/.weaver/settings.json
```

### 9.2 完整配置项

```jsonc
{
  // === API 配置（与 Claude Code 一致）===
  "apiKey": "",                       // 或 ANTHROPIC_API_KEY 环境变量
  "apiKeyHelper": "./get-key.sh",     // 脚本输出 key
  "model": "claude-sonnet-4-6",       // 或 ANTHROPIC_MODEL 环境变量
  "baseUrl": "",                      // 自定义 API 地址，或 ANTHROPIC_BASE_URL
  "customHeaders": "",                // 自定义请求头
  "timeout": 600000,                  // API 超时 ms

  // Provider 选择（环境变量控制）
  // CLAUDE_CODE_USE_BEDROCK=1 / CLAUDE_CODE_USE_VERTEX=1

  // === 执行后端 ===
  "backend": {
    "type": "local",                  // local | wsl | ssh | docker
    "distro": "kali-linux",           // wsl 时
    "host": "192.168.1.100",          // ssh/docker 时
    "port": 22,                       // ssh 端口
    "user": "kali",                   // ssh 用户
    "authMethod": "password",         // password | key | agent
    "password": "",                   // 密码（建议用 passwordHelper）
    "passwordHelper": "./get-pass.sh",// 脚本输出密码
    "keyFile": "~/.ssh/id_rsa",       // 私钥路径
    "container": "kali-pentest"       // docker 容器名
  },

  // === 报告 ===
  "reportsDir": "~/.weaver/reports/",

  // === MCP ===
  "mcpServers": {}
}
```

### 9.3 API Key 优先级（与 Claude Code 一致）

1. `ANTHROPIC_API_KEY` 环境变量
2. `apiKeyHelper` 脚本
3. settings.json 中的 `apiKey` 字段
4. `/login` 命令存储的 OAuth token

### 9.4 支持的环境变量

| 变量 | 用途 |
|------|------|
| `ANTHROPIC_API_KEY` | API key |
| `ANTHROPIC_BASE_URL` | 自定义 API 地址 |
| `ANTHROPIC_MODEL` | 模型覆盖 |
| `ANTHROPIC_CUSTOM_HEADERS` | 自定义请求头 |
| `API_TIMEOUT_MS` | 请求超时 |
| `WEAVER_USE_BEDROCK` | 启用 Bedrock |
| `WEAVER_USE_VERTEX` | 启用 Vertex |

注：`ANTHROPIC_` 前缀的变量保持不变（这是 Anthropic SDK 标准），只有原 `CLAUDE_CODE_` 前缀的变量改为 `WEAVER_` 前缀。

---

## 10. TUI 外观设计

### 10.1 品牌化

启动画面：

```
╔══════════════════════════════════════════════╗
║  ██╗    ██╗███████╗ █████╗ ██╗   ██╗███████╗██████╗  ║
║  ██║    ██║██╔════╝██╔══██╗██║   ██║██╔════╝██╔══██╗ ║
║  ██║ █╗ ██║█████╗  ███████║██║   ██║█████╗  ██████╔╝ ║
║  ██║███╗██║██╔══╝  ██╔══██║╚██╗ ██╔╝██╔══╝  ██╔══██╗ ║
║  ╚███╔███╔╝███████╗██║  ██║ ╚████╔╝ ███████╗██║  ██║ ║
║   ╚══╝╚══╝ ╚══════╝╚═╝  ╚═╝  ╚═══╝  ╚══════╝╚═╝  ╚═╝ ║
║                                                          ║
║  渗透测试 Agent 框架                         v0.1.0      ║
╚══════════════════════════════════════════════╝
```

配色方案：深色背景 + 绿色/红色/黄色为主色调（黑客风格）

### 10.2 阶段颜色区分

| 阶段 | 颜色 | 中文标签 |
|------|------|----------|
| Recon | 蓝色 | 侦察 |
| Enum | 青色 | 枚举 |
| Exploit | 红色 | 利用 |
| Post | 紫色 | 后渗透 |
| Report | 绿色 | 报告 |
| General | 白色 | 通用 |

消息流文本颜色随当前阶段变化，输入框边框也跟着变。

### 10.3 状态面板（顶部）

```
┌─ 状态 ──────────────────────────────────────┐
│ 后端: ssh://kali@192.168.1.100              │
│ 阶段: 侦察                                  │
│ 发现: 3 高危 / 2 中危 / 5 低危              │
│ Token: 12.5k / 200k (6%)                     │
└──────────────────────────────────────────────┘
```

### 10.4 实时状态栏（底部）

```
[侦察] ▶ 子任务-1: nmap 扫描中 (42%) │ 子任务-2: subfinder 运行中 │ 发现: 10 │ 12.5k/200k │ 00:15:32
```

显示内容：
- 当前阶段
- 子 agent 状态和正在执行的命令
- 累计发现数量
- Token 使用量 / 上下文窗口总量
- 运行时长

### 10.5 Token 与上下文窗口显示

实时状态栏中显示 token 消耗和上下文窗口使用情况：

```
Token: 12.5k / 200k (6%) │ 输入: 8.2k │ 输出: 4.3k
```

显示内容：
- 当前上下文已用 token / 总窗口大小（百分比）
- 输入/输出 token 分别统计

当上下文使用超过 80% 时，颜色变为黄色警告；超过 95% 时变为红色。

### 10.6 退出提示

```
正在生成本次任务报告...
报告已保存至: ~/.weaver/reports/2026-05-17_192.168.1.0-24.md
```

---

## 11. 通用能力与自我更新

### 11.1 保留的通用能力

Weaver 不只是渗透工具，保留 Claude Code 的通用能力：
- 文件读写编辑（FileRead/FileWrite/FileEdit）
- 代码搜索（Glob/Grep）
- 网页搜索和抓取（WebSearch/WebFetch）
- 环境检查、工具状态检查
- 代码编写和修改

### 11.2 自我更新

Weaver 可以读写自己的源码，支持：
- 修改自己的 skill 文件
- 修改自己的 system prompt
- 修改自己的 TUI 组件
- 写新的 skill 到 `.weaver/skills/`
- 修改自己的工具实现
- 修改自己的配置逻辑

### 11.3 内置命令

```
/status  — 显示当前状态（后端连接、skill 列表、MCP、API）
/env     — 检查执行环境（可用工具、网络、权限、环境变量）
/report  — 手动触发报告生成
/skill   — 管理 skill
/mcp     — 管理 MCP 连接
/config  — 配置管理
/compact — context 压缩
```

---

## 12. 项目文件结构

```
src/
  entrypoints/
    cli.ts                    # 入口分流
  main.ts                     # 主启动器
  setup.ts                    # 环境初始化

  query/
    query.ts                  # 核心主循环
    QueryEngine.ts            # 无UI执行引擎

  tools/
    BashTool/                 # Bash执行（加backend抽象）
    AgentTool/                # 子agent调度
    SkillTool/                # Skill调用
    FileReadTool/             # 文件读取
    FileWriteTool/            # 文件写入
    FileEditTool/             # 文件编辑
    GlobTool/                 # 文件查找
    GrepTool/                 # 内容搜索
    WebSearchTool/            # 网页搜索
    WebFetchTool/             # 网页抓取
    NotebookEditTool/         # Jupyter编辑

  services/
    api/                      # Claude API客户端
    mcp/                      # MCP client
    tools/
      toolOrchestration.ts    # 工具调度

  skills/
    bundled/                  # 内置渗透skill
      recon/
      enum/
      exploit/
      post/
      report/
    loadSkillsDir.ts          # skill加载机制

  screens/
    REPL.tsx                  # 主交互界面

  components/
    messages/                 # 消息流展示
    permissions/              # 确认弹窗
    input/                    # 输入框
    statusPanel/              # 状态面板（新增）
    statusBar/                # 实时状态栏（新增）

  state/
    AppState.ts               # 应用状态

  commands/
    skill/                    # /skill 命令
    config/                   # /config 命令
    compact/                  # /compact 命令
    report/                   # /report 命令（新增）
    status/                   # /status 命令（新增）
    env/                      # /env 命令（新增）
    mcp/                      # /mcp 命令

  utils/
    Shell.ts                  # 命令执行核心（加backend）
    ShellCommand.ts           # 进程生命周期
    auth.ts                   # API认证
    config.ts                 # 配置读取
    settings/                 # 配置系统
    sessionStorage.ts         # session记录
    messages.ts               # 消息构造
    compact.ts                # context压缩

  constants/                  # 常量
  types/                      # 类型定义

.weaver/                      # 用户项目级配置
  settings.json
  skills/                     # 用户自定义skill
```

---

## 13. 从 Claude Code 删除的模块

| 模块 | 原因 |
|------|------|
| `buddy/` | 装饰性精灵，无关 |
| `voice/` | 语音输入，无关 |
| `vim/` | vim模式，无关 |
| `keybindings/` | 快捷键自定义，无关 |
| `bridge/` | 远程桥接，不需要 |
| `remote/` | 远程会话，不需要 |
| `moreright/` | 内部功能 |
| `plugins/` | 插件市场，不需要 |
| `memdir/` | 复杂记忆系统，不需要 |
| `migrations/` | 数据迁移，不需要 |
| `coordinator/` | 内部协调模式 |
| `outputStyles/` | 多种输出风格 |
| `native-ts/` | 原生TS扩展 |
| `upstreamproxy/` | 代理 |
| `entrypoints/mcp.ts` | MCP server模式 |
| 大部分 `commands/` | 无关命令（review/pr/desktop/mobile等） |
| `TodoWriteTool` | 不需要 |
| `TeamCreate/TeamDelete/SendMessage` | 内部协作工具 |

---

## 14. 技术栈

| 项 | 选择 |
|----|------|
| 语言 | TypeScript |
| 运行时 | Bun |
| TUI 框架 | React + Ink |
| API | Anthropic Claude API |
| 进程管理 | child_process.spawn + tree-kill |
| 配色 | chalk |

---

## 15. 代码规范

- 全部使用中文注释
- TUI 状态文本使用中文显示
- 变量名/函数名使用英文
- 文件名使用英文

---

## 16. 实现参考原则

Weaver 的实现完全参考 Claude Code 源码，遵循以下流程：

1. **先看分析文档** — 位于 `D:\github_project\claude-code-main\claude-code-analysis-main\analysis\`，包含架构概览、工具实现、skill 机制、多 agent 等详细分析
2. **需要时再看源码** — 位于 `D:\github_project\claude-code-main\src\`，当分析文档不够详细或需要确认具体实现细节时，直接阅读源码
3. **提取而非 fork** — 不是直接复制粘贴，而是理解原理后在 Weaver 项目中重新实现，保持代码干净可控
4. **保持一致性** — 对于复用的模块（API 层、工具调度、skill 机制等），尽量保持与 Claude Code 相同的接口和行为，降低理解成本

**参考优先级：**
```
分析文档（快速理解架构和设计意图）
  ↓
源码（确认具体实现细节）
  ↓
重新实现（在 Weaver 中干净地实现）
```

---

## 17. 预估规模

- 文件数：~150-200
- 代码行数：~3-5万行
- 从 Claude Code 的 1900 文件 / 51万行大幅精简
