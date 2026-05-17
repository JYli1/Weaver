---
name: solve-challenge
description: 调度器 - 识别任务类型后路由到具体 skill
when_to_use: 当用户给出模糊任务或需要判断从哪里开始时
allowed-tools: [Bash, Read, Write, Glob, Grep, Skill, Agent]
user-invocable: true
context: inline
---

## 任务调度器

根据用户描述和当前信息，判断任务类型并路由到合适的 skill。

### 分类决策树

```
用户任务
  ├── 给了 IP/CIDR → 网络侦察
  │     └── 调用 /network-discovery
  ├── 给了域名 → 子域名枚举 + Web 指纹
  │     ├── 调用 /subdomain-enum
  │     └── 调用 /web-fingerprint
  ├── 给了 URL → Web 测试
  │     ├── 先调用 /web-fingerprint 识别技术栈
  │     ├── 再调用 /web-fuzzing 发现路径
  │     └── 最后调用 /web-vuln 测试漏洞
  ├── 已有 shell → 后渗透
  │     └── 调用 /privesc
  ├── 给了服务端口 → 服务枚举
  │     └── 调用 /service-enum
  └── 不确定 → 先收集信息再决定
```

### 执行策略

1. **分析输入** — 用户给了什么信息？IP？域名？URL？已有访问权限？
2. **确定阶段** — 当前处于渗透测试的哪个阶段？
3. **选择 skill** — 调用最合适的 skill
4. **并行执行** — 如果有多个独立任务，使用 Agent 工具并行执行
5. **汇总结果** — 整理发现，决定下一步

### 并行示例

对于大范围目标，可以并行执行：
- Agent A: 子域名枚举
- Agent B: 端口扫描
- Agent C: Web 指纹识别

结果汇总后再决定深入方向。
