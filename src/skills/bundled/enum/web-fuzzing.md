---
name: web-fuzzing
description: Web 目录和参数模糊测试方法论
when_to_use: 当需要发现隐藏路径、文件或参数时
allowed-tools: [Bash, Read, Write]
argument-hint: "<target-url>"
arguments: [target]
user-invocable: true
context: inline
---

## Web 模糊测试

### 1. 目录扫描

```bash
# ffuf 目录扫描
ffuf -u $ARGUMENTS/FUZZ -w /usr/share/seclists/Discovery/Web-Content/raft-medium-directories.txt -mc 200,301,302,403

# feroxbuster 递归扫描
feroxbuster -u $ARGUMENTS -w /usr/share/seclists/Discovery/Web-Content/raft-medium-directories.txt

# gobuster
gobuster dir -u $ARGUMENTS -w /usr/share/seclists/Discovery/Web-Content/common.txt -x php,txt,html,js
```

### 2. 文件发现

```bash
# 备份文件
ffuf -u $ARGUMENTS/FUZZ -w /usr/share/seclists/Discovery/Web-Content/raft-medium-files.txt -e .bak,.old,.swp,.zip,.tar.gz

# 敏感文件
ffuf -u $ARGUMENTS/FUZZ -w /usr/share/seclists/Discovery/Web-Content/quickhits.txt
```

### 3. 参数发现

```bash
# GET 参数
ffuf -u "$ARGUMENTS?FUZZ=test" -w /usr/share/seclists/Discovery/Web-Content/burp-parameter-names.txt -mc 200 -fs <baseline-size>

# POST 参数
ffuf -u $ARGUMENTS -X POST -d "FUZZ=test" -w /usr/share/seclists/Discovery/Web-Content/burp-parameter-names.txt -mc 200
```

### 4. 虚拟主机发现

```bash
ffuf -u $ARGUMENTS -H "Host: FUZZ.target.com" -w /usr/share/seclists/Discovery/DNS/subdomains-top1million-5000.txt -fs <baseline-size>
```

### 5. 决策树

```
目标 URL
  ├── 先跑目录扫描 → 发现新路径
  │     ├── 403 → 尝试绕过（大小写、双编码、路径穿越）
  │     └── 200 → 继续递归 + 检查内容
  ├── 发现登录页 → 参数模糊 + 默认凭据
  ├── 发现 API → 枚举端点 + 方法
  └── 无结果 → 换字典、加扩展名、尝试虚拟主机
```
