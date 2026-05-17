---
name: network-discovery
description: 网络侦察与端口扫描方法论
when_to_use: 当需要对目标进行网络层面的侦察时
allowed-tools: [Bash, Read, Write, Glob, Grep]
argument-hint: "<target-ip-or-cidr>"
arguments: [target]
user-invocable: true
context: inline
---

## 网络侦察方法论

### 1. 主机发现

```bash
# ARP 扫描（局域网最快）
arp-scan -l

# Ping 扫描
nmap -sn $ARGUMENTS

# 无 ping 扫描（绕过防火墙）
nmap -Pn -sn $ARGUMENTS
```

### 2. 端口扫描

```bash
# 快速 TCP 全端口扫描
nmap -p- --min-rate 10000 $ARGUMENTS

# 精确扫描（top 1000）
nmap -sC -sV $ARGUMENTS

# UDP 扫描（常见端口）
nmap -sU --top-ports 50 $ARGUMENTS
```

### 3. 服务识别

```bash
# 版本探测 + 默认脚本
nmap -sV -sC -p <ports> $ARGUMENTS

# 特定服务深入
nmap --script=<service>-* -p <port> $ARGUMENTS
```

### 4. 决策树

```
发现主机 → 快速全端口 → 识别开放端口
  ├── Web (80/443/8080) → 转 web-fingerprint skill
  ├── SSH (22) → 尝试弱口令 / 版本漏洞
  ├── SMB (445) → 转 service-enum skill
  ├── RDP (3389) → 检查 BlueKeep / 弱口令
  └── 其他 → 版本探测 + searchsploit
```

### 5. 输出整理

扫描完成后，整理为结构化格式：
- IP / 主机名
- 开放端口列表
- 服务版本
- 潜在攻击面
