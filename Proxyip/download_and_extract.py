#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
IP源数据获取与分类工具（增强高鲁棒性版）
"""

import os
import sys
import re
import random
import shutil
import logging
import subprocess
from pathlib import Path
from collections import defaultdict
from typing import Dict, Set, Tuple, Optional

# 导入共享配置
try:
    from config import (
        DOWNLOAD_URL,
        IP_SOURCE_DIR,
        PROXY_PORTS,
        COUNTRY_CODES,
        COUNTRY_CONFIG
    )
except ImportError:
    print("错误：无法导入 config.py，请确保配置文件存在")
    sys.exit(1)

# 第三方库检测与安装
try:
    import requests
    from requests.adapters import HTTPAdapter
    from urllib3.util.retry import Retry
except ImportError:
    print("正在安装 requests 库...")
    os.system(f"{sys.executable} -m pip install requests")
    import requests
    from requests.adapters import HTTPAdapter
    from urllib3.util.retry import Retry

# 禁用SSL警告
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


# 常见桌面端真实浏览器 User-Agent 库
USER_AGENTS = [
    # Chrome on Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    # Edge on Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36 Edg/124.0.0.0",
    # Firefox on Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
    # Chrome on macOS
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    # Safari on macOS
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
]

# 质询特征识别关键字（防误将错误页或验证码页当作数据解析）
CHALLENGE_SIGNATURES = [
    "just a moment...",
    "checking your browser",
    "cf-browser-verification",
    "turnstile",
    "cloudflare-static/email-decode",
    "<title>attention required! | cloudflare</title>",
    "challenge-platform",
    "ray id:"
]


class IPFetcher:
    """高鲁棒性 IP 源数据拉取器"""

    def __init__(self,
                 url: str,
                 timeout: int = 30,
                 max_retries: int = 3,
                 verify_ssl: bool = False):
        self.url = url
        self.timeout = timeout
        self.max_retries = max_retries
        self.verify_ssl = verify_ssl

    def _get_random_headers(self) -> dict:
        """生成随机拟真浏览器请求头"""
        ua = random.choice(USER_AGENTS)
        headers = {
            'User-Agent': ua,
            'Accept': 'text/plain,text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7',
            'Cache-Control': 'no-cache',
            'Pragma': 'no-cache',
            'Connection': 'keep-alive',
            'Sec-Ch-Ua-Mobile': '?0',
            'Sec-Ch-Ua-Platform': '"Windows"',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
            'Upgrade-Insecure-Requests': '1'
        }
        return headers

    def _is_challenge_page(self, content: str) -> bool:
        """检测返回的内容是否为 Cloudflare 拦截质询页"""
        if not content:
            return False
        content_lower = content[:2000].lower()
        if content_lower.startswith("<!doctype html") or "<html" in content_lower:
            for sig in CHALLENGE_SIGNATURES:
                if sig in content_lower:
                    return True
        return False

    def _fetch_by_requests(self) -> Optional[str]:
        """第一梯队：使用 requests 配合重试策略"""
        logger.info(f"[梯队1] 尝试 requests 获取: {self.url}")
        session = requests.Session()
        retry_strategy = Retry(
            total=self.max_retries,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["HEAD", "GET"]
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)

        response = session.get(
            self.url,
            headers=self._get_random_headers(),
            timeout=self.timeout,
            verify=self.verify_ssl
        )
        if response.status_code == 200:
            if not self._is_challenge_page(response.text):
                return response.text
            logger.warning("[梯队1] 遭遇疑似 Cloudflare 验证拦截页面 (HTML/Challenge)")
        else:
            logger.warning(f"[梯队1] 请求状态码异常: {response.status_code}")
        return None

    def _fetch_by_cloudscraper(self) -> Optional[str]:
        """第二梯队：尝试使用 cloudscraper 绕过 CF 质询（若已安装）"""
        try:
            import cloudscraper
            logger.info(f"[梯队2] 检测到 cloudscraper 库，尝试绕过 Cloudflare 验证: {self.url}")
            scraper = cloudscraper.create_scraper(
                browser={
                    'browser': 'chrome',
                    'platform': 'windows',
                    'desktop': True
                }
            )
            resp = scraper.get(self.url, timeout=self.timeout, verify=self.verify_ssl)
            if resp.status_code == 200 and not self._is_challenge_page(resp.text):
                return resp.text
        except ImportError:
            pass
        except Exception as e:
            logger.warning(f"[梯队2] cloudscraper 尝试失败: {e}")
        return None

    def _fetch_by_curl_cli(self) -> Optional[str]:
        """第三梯队：尝试调用系统原生 curl 命令（Linux/macOS/Windows 10+ 均内置）"""
        logger.info(f"[梯队3] 尝试使用系统 curl 命令获取...")
        ua = random.choice(USER_AGENTS)
        cmd = [
            "curl",
            "-k",               # 忽略证书
            "-s",               # 静默输出
            "-L",               # 跟随重定向
            "--max-time", str(self.timeout),
            "-A", ua,
            "-H", "Accept: text/plain,*/*",
            self.url
        ]
        try:
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=self.timeout + 5)
            if result.returncode == 0 and result.stdout:
                if not self._is_challenge_page(result.stdout):
                    return result.stdout
                logger.warning("[梯队3] curl 获取结果包含质询特征")
        except Exception as e:
            logger.warning(f"[梯队3] curl 命令行调用失败: {e}")
        return None

    def fetch_text(self) -> str:
        """按优先级降级执行拉取任务"""
        # 1. 优先标准 requests
        try:
            content = self._fetch_by_requests()
            if content:
                return content
        except Exception as e:
            logger.warning(f"[梯队1] requests 异常: {e}")

        # 2. 尝试反混淆库
        content = self._fetch_by_cloudscraper()
        if content:
            return content

        # 3. 尝试系统原生 curl
        content = self._fetch_by_curl_cli()
        if content:
            return content

        raise RuntimeError("所有拉取机制均未成功，请检查目标地址是否在线或已开启严格的人机验证")


def parse_and_group_ips(text: str, allowed_ports: list, allowed_countries: list) -> Tuple[Dict[str, Set[str]], dict]:
    """
    解析文本内容并按国家分组纯IP

    数据行格式支持:
      - 101.142.129.72:443#JP
      - 101.142.129.72:443#日本
      - 101.142.129.72:443
      - 101.142.129.72
    """
    stats = {
        'total_lines': 0,
        'matched_ips': 0,
        'unique_ips': 0,
        'by_country': {}
    }

    country_ips: Dict[str, Set[str]] = defaultdict(set)
    allowed_ports_set = {int(p) for p in allowed_ports} if allowed_ports else set()
    allowed_countries_upper = {c.upper() for c in allowed_countries}

    # 构建中文名称到国家代码的反向映射
    cn_to_code = {v: k for k, v in COUNTRY_CONFIG.items()}

    # 匹配模式：IP[:PORT][#TAG]
    line_pattern = re.compile(r'^\s*([0-9a-fA-F\.:]+?)(?::(\d+))?(?:#(.*))?\s*$')

    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("//"):
            continue

        stats['total_lines'] += 1
        m = line_pattern.match(line)
        if not m:
            continue

        ip_part, port_part, tag_part = m.groups()
        ip_part = ip_part.strip()
        port = int(port_part) if port_part else None
        tag = tag_part.strip() if tag_part else ""

        # 端口筛选（如果有配置且数据中含有端口）
        if allowed_ports_set and port is not None and port not in allowed_ports_set:
            continue

        # 识别国家
        matched_country_code = None
        tag_upper = tag.upper()

        if tag_upper in allowed_countries_upper:
            matched_country_code = tag_upper
        elif tag in cn_to_code:
            matched_country_code = cn_to_code[tag]
        else:
            for code in allowed_countries_upper:
                cn_name = COUNTRY_CONFIG.get(code, "")
                if code in tag_upper or (cn_name and cn_name in tag):
                    matched_country_code = code
                    break

        if matched_country_code:
            stats['matched_ips'] += 1
            country_ips[matched_country_code].add(ip_part)

    stats['unique_ips'] = sum(len(ips) for ips in country_ips.values())
    return country_ips, stats


def save_country_ips(country_ips: Dict[str, Set[str]], output_dir: Path) -> dict:
    """将按国家归类的IP保存为文件，带熔断保护（数据为空不覆盖）"""
    total_new_ips = sum(len(ips) for ips in country_ips.values())
    if total_new_ips == 0:
        logger.error("安全熔断: 本次解析出的有效 IP 数量为 0，放弃覆盖本地目录以避免历史数据被清空！")
        return {}

    if output_dir.exists():
        logger.info(f"清空输出目录: {output_dir}")
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    summary = {}
    for country_code, ips in country_ips.items():
        file_path = output_dir / f"{country_code}.txt"
        sorted_ips = sorted(ips)
        with open(file_path, 'w', encoding='utf-8') as f:
            for ip in sorted_ips:
                f.write(f"{ip}\n")

        summary[country_code] = {
            'count': len(ips),
            'name': COUNTRY_CONFIG.get(country_code, country_code)
        }
        logger.info(f"  {country_code} ({COUNTRY_CONFIG.get(country_code, country_code)}): {len(ips)} 个IP -> {file_path.name}")

    return summary


def main():
    """主函数"""
    script_dir = Path(__file__).parent
    output_dir = script_dir / IP_SOURCE_DIR

    print("=" * 60)
    print("🚀 IP源数据获取与分类工具（增强高鲁棒性版）")
    print("=" * 60)
    print(f"📥 数据源URL: {DOWNLOAD_URL}")
    print(f"📁 输出目录: {output_dir}")
    print(f"🔌 端口过滤: {PROXY_PORTS}")
    print(f"🌍 目标国家: {', '.join([f'{k}({v})' for k, v in COUNTRY_CONFIG.items()])}")
    print("=" * 60)

    try:
        fetcher = IPFetcher(
            url=DOWNLOAD_URL,
            timeout=60,
            max_retries=3,
            verify_ssl=False
        )
        content = fetcher.fetch_text()
        logger.info(f"成功获取数据，文本大小: {len(content) / 1024:.2f} KB")

        country_ips, stats = parse_and_group_ips(
            text=content,
            allowed_ports=PROXY_PORTS,
            allowed_countries=COUNTRY_CODES
        )

        print("\n" + "=" * 60)
        print("📊 写入国家IP文件")
        print("=" * 60)

        saved_summary = save_country_ips(country_ips, output_dir)
        stats['by_country'] = saved_summary

        print("\n" + "=" * 60)
        print("✅ 操作完成!")
        print("=" * 60)
        print(f"📊 总数据行数: {stats['total_lines']}")
        print(f"📊 匹配目标国家行数: {stats['matched_ips']}")
        print(f"📊 去重后纯IP总数: {stats['unique_ips']}")
        print(f"📂 输出目录: {output_dir}")

        print("\n🌍 各国家IP统计:")
        for code, info in stats['by_country'].items():
            print(f"   {code} ({info['name']}): {info['count']} 个IP")

    except Exception as e:
        print(f"\n❌ 错误: {e}")
        logger.exception("详细错误信息:")
        sys.exit(1)


if __name__ == "__main__":
    main()
