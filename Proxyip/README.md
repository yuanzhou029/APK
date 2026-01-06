# ProxyIP 检测工具

一个自动化的代理IP检测和Cloudflare域名解析工具，支持GitHub Actions定时运行和Telegram通知。

## 功能特性

- **多源输入支持**：支持IP地址、域名、远程URL混合输入
- **DNS解析**：自动解析域名获取IP地址
- **远程URL处理**：从远程链接下载IP列表
- **代理检测**：并发检测代理IP可用性
- **地区筛选**：按国家/地区筛选IP
- **二次验证**：确保IP稳定性
- **Cloudflare解析**：反向解析IP到Cloudflare域名
- **Telegram通知**：运行结果实时推送
- **定时执行**：GitHub Actions自动运行

## 文件结构

```
Proxyip/
├── ip.py                 # 主检测脚本
├── reverse_dns.py        # CF域名解析脚本
├── Proxyip.txt           # 输入文件（IP/域名/URL混合）
├── domains.txt           # 域名输入文件
├── temp_ips.txt          # 临时IP存储
├── requirements.txt      # 依赖包
├── .github/workflows/
│   └── proxy-workflow.yml # GitHub Actions工作流
├── valid_proxies/        # 检测结果目录
│   ├── TW.txt           # 台湾IP
│   ├── HK.txt           # 香港IP
│   ├── JP.txt           # 日本IP
│   └── SG.txt           # 新加坡IP
└── README.md
```

## 配置说明

### 主要配置 (ip.py)

```python
INPUT_SOURCE = "Proxyip.txt"           # 输入源文件
DOMAINS_SOURCE = "domains.txt"         # 域名源文件
FILTER_COUNTRIES = ["台湾", "日本", "香港", "新加坡"]  # 筛选国家
MAX_THREADS = 30                       # 并发线程数
CHECK_API = "https://cf.090227.xyz/check"  # 检测API
```

### 输入文件格式

**Proxyip.txt** (支持混合格式):
```
# IP地址
1.2.3.4:8080
5.6.7.8:3128

# 远程URL
https://raw.githubusercontent.com/user/proxy-list/main/ips.txt
http://example.com/proxies.txt

# 域名
proxy.example.com:3128
```

**domains.txt**:
```
example.com
google.com
github.com
```

## GitHub Actions 配置

工作流支持：
- **定时运行**：每天UTC时间0点自动运行
- **手动触发**：可通过GitHub界面手动运行
- **Telegram通知**：运行结果推送到Telegram

### 需要设置的Secrets

在GitHub仓库设置中添加：
- `TELEGRAM_BOT_TOKEN` - Telegram机器人Token
- `TELEGRAM_CHAT_ID` - Telegram聊天ID

## 使用方法

### 本地运行

1. 安装依赖：
```bash
pip install -r requirements.txt
```

2. 运行主检测：
```bash
python ip.py
```

3. 运行CF域名解析：
```bash
python reverse_dns.py
```

### GitHub Actions部署

1. 将代码推送到GitHub仓库
2. 在仓库设置中配置Telegram相关Secrets
3. Actions会自动定时运行

## Telegram通知内容

通知包含：
- 运行时长
- 各地区有效IP数量
- Cloudflare域名解析统计
- 详细IP数量信息

## 技术栈

- Python 3.9+
- GitHub Actions
- DNS解析 (dnspython)
- HTTP请求 (requests)
- 并发处理 (ThreadPoolExecutor)

## 许可证

MIT License
