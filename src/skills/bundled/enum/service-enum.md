---
name: service-enum
description: 针对各服务的深入枚举方法
when_to_use: 当发现开放服务需要深入枚举时
allowed-tools: [Bash, Read, Write]
argument-hint: "<target-ip> <service>"
arguments: [target, service]
user-invocable: true
context: inline
---

## 服务枚举方法论

### SMB (445)

```bash
# 匿名枚举
smbclient -L //$ARGUMENTS -N
enum4linux -a $ARGUMENTS
crackmapexec smb $ARGUMENTS --shares

# 用户枚举
crackmapexec smb $ARGUMENTS --users
rpcclient -U "" -N $ARGUMENTS -c "enumdomusers"
```

### FTP (21)

```bash
# 匿名登录
ftp $ARGUMENTS
# 尝试 anonymous / anonymous

# nmap 脚本
nmap --script=ftp-anon,ftp-bounce,ftp-vuln* -p 21 $ARGUMENTS
```

### SSH (22)

```bash
# 版本信息
ssh -v $ARGUMENTS 2>&1 | head -5

# 用户枚举（CVE-2018-15473）
# 仅适用于 OpenSSH < 7.7
nmap --script=ssh-auth-methods -p 22 $ARGUMENTS
```

### SMTP (25)

```bash
# 用户枚举
smtp-user-enum -M VRFY -U /usr/share/wordlists/names.txt -t $ARGUMENTS

# nmap 脚本
nmap --script=smtp-commands,smtp-enum-users -p 25 $ARGUMENTS
```

### DNS (53)

```bash
# 区域传送
dig axfr @$ARGUMENTS <domain>

# 子域名枚举
dnsrecon -d <domain> -n $ARGUMENTS
```

### SNMP (161)

```bash
# 社区字符串爆破
onesixtyone -c /usr/share/seclists/Discovery/SNMP/common-snmp-community-strings.txt $ARGUMENTS

# 信息提取
snmpwalk -v2c -c public $ARGUMENTS
```

### 决策树

```
识别服务版本
  ├── 有已知漏洞 → searchsploit / exploit-db
  ├── 支持匿名访问 → 枚举可访问资源
  ├── 需要认证 → 尝试默认凭据 / 弱口令
  └── 无明显攻击面 → 记录，继续其他服务
```
