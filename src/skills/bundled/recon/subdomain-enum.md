---
name: subdomain-enum
description: 子域名枚举与发现方法论
when_to_use: 当需要发现目标的子域名时
allowed-tools: [Bash, Read, Write]
argument-hint: "<domain>"
arguments: [target]
user-invocable: true
context: inline
---

## 子域名枚举

### 1. 被动收集

```bash
# subfinder（多源聚合）
subfinder -d $ARGUMENTS -o subdomains.txt

# amass 被动模式
amass enum -passive -d $ARGUMENTS -o amass_subs.txt

# crt.sh 证书透明度
curl -s "https://crt.sh/?q=%25.$ARGUMENTS&output=json" | jq -r '.[].name_value' | sort -u
```

### 2. 主动枚举

```bash
# DNS 暴力
gobuster dns -d $ARGUMENTS -w /usr/share/seclists/Discovery/DNS/subdomains-top1million-5000.txt

# puredns 带解析验证
puredns bruteforce /usr/share/seclists/Discovery/DNS/subdomains-top1million-5000.txt $ARGUMENTS
```

### 3. 存活验证

```bash
# httpx 批量验证
cat subdomains.txt | httpx -status-code -title -tech-detect -o alive.txt

# 端口扫描关键子域
nmap -sV -p 80,443,8080,8443 -iL subdomains.txt
```

### 4. 决策树

```
目标域名
  ├── 被动收集（subfinder + crt.sh + amass）
  │     └── 合并去重
  ├── 主动枚举（DNS 暴力）
  │     └── 合并到总列表
  ├── 存活验证（httpx）
  │     ├── Web 服务 → 转 web-fingerprint
  │     └── 其他服务 → 转 service-enum
  └── 持续监控（新子域名告警）
```
