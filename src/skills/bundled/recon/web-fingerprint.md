---
name: web-fingerprint
description: Web 应用指纹识别与技术栈探测
when_to_use: 当发现 Web 服务需要识别技术栈时
allowed-tools: [Bash, Read, Write]
argument-hint: "<target-url>"
arguments: [target]
user-invocable: true
context: inline
---

## Web 指纹识别

### 1. 基础探测

```bash
# HTTP 响应头分析
curl -sI $ARGUMENTS

# whatweb 指纹
whatweb $ARGUMENTS

# httpx 批量探测
echo "$ARGUMENTS" | httpx -tech-detect -status-code -title
```

### 2. 技术栈识别

```bash
# Wappalyzer CLI
wappalyzer $ARGUMENTS

# 检查常见路径
curl -s $ARGUMENTS/robots.txt
curl -s $ARGUMENTS/sitemap.xml
curl -s $ARGUMENTS/.well-known/security.txt
```

### 3. CMS 识别

```bash
# WordPress
curl -s $ARGUMENTS/wp-login.php | head -5
wpscan --url $ARGUMENTS --enumerate vp,vt,u

# Joomla
curl -s $ARGUMENTS/administrator/ | head -5

# Drupal
curl -s $ARGUMENTS/CHANGELOG.txt | head -5
```

### 4. 决策树

```
识别技术栈
  ├── WordPress → wpscan 深入
  ├── Java (Tomcat/Spring) → 检查已知 CVE
  ├── PHP → 检查版本漏洞 + 常见框架漏洞
  ├── Node.js → 检查 package.json 泄露
  └── 自定义应用 → 转 web-fuzzing skill
```
