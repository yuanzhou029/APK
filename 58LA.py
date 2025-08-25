import os
import time
import random
import json
import logging
from datetime import datetime, timedelta
import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

# 配置日志
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

class BrowserSimulator:
    """浏览器模拟器类，用于模拟真实浏览器行为"""
    # 多样化的User-Agent列表
    USER_AGENTS = [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2.1 Safari/605.1.15',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0',
        'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
        'Mozilla/5.0 (iPhone; CPU iPhone OS 17_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Mobile/15E148 Safari/604.1'
    ]

    def __init__(self, proxy_config=None):
        self.session = self._create_session()
        self.proxy = proxy_config
        self.headers_history = []  # 记录历史请求头，避免重复
        self.cookies_updated = False

    def _create_session(self):
        """创建带重试机制的session"""
        session = requests.Session()
        retry = Retry(total=10, backoff_factor=2, status_forcelist=[403, 429, 500, 502, 503, 504])
        adapter = HTTPAdapter(max_retries=retry)
        session.mount('http://', adapter)
        session.mount('https://', adapter)
        return session

    def get_random_headers(self, referer=None):
        """生成随机请求头，模拟不同浏览器和用户"""
        # 确保获取不同的User-Agent
        user_agent = random.choice(self.USER_AGENTS)
        while len(self.headers_history) >= 3 and user_agent in self.headers_history[-3:]:
            user_agent = random.choice(self.USER_AGENTS)

        # 更新历史记录
        self.headers_history.append(user_agent)
        if len(self.headers_history) > 10:
            self.headers_history.pop(0)

        headers = {
            'User-Agent': user_agent,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'same-origin',
            'Sec-Fetch-User': '?1',
            'DNT': '1',
            'Cache-Control': 'max-age=0',
            'TE': 'Trailers',
            'Accept-Encoding': 'gzip, deflate, br'
        }

        # 如果提供了referer，则添加到请求头
        if referer:
            headers['Referer'] = referer

        # 随机添加一些额外的头部字段，增加请求的多样性
        if random.random() > 0.5:
            headers['X-Forwarded-For'] = f'{random.randint(1, 255)}.{random.randint(0, 255)}.{random.randint(0, 255)}.{random.randint(1, 255)}'
        if random.random() > 0.3:
            headers['X-Requested-With'] = 'XMLHttpRequest'

        return headers

    def update_cookies(self, domain):
        """更新特定域名的cookies"""
        if self.cookies_updated:
            return True

        try:
            # 访问首页获取cookies
            home_url = f'https://{domain}/'
            headers = self.get_random_headers()
            response = self.session.get(home_url, headers=headers, proxies=self.proxy, timeout=10)

            if response.status_code == 200:
                logging.info(f'成功获取{domain}的cookies')
                self.cookies_updated = True
                return True
            else:
                logging.warning(f'获取{domain}的cookies失败，状态码: {response.status_code}')
                return False
        except Exception as e:
            logging.error(f'更新cookies时出错: {e}')
            return False

class PageVisitor:
    """页面访问类，模拟用户浏览行为"""
    def __init__(self, browser_simulator):
        self.browser = browser_simulator
        self.domain = 'www.85la.com'
        self.visited_urls = set()  # 记录已访问的URL

    def simulate_user_browsing(self):
        """模拟用户浏览行为"""
        # 确保已获取cookies
        if not self.browser.cookies_updated:
            self.browser.update_cookies(self.domain)

        # 随机访问一些页面，模拟用户浏览
        nav_pages = [
            'https://www.85la.com/',
            'https://www.85la.com/about',
            'https://www.85la.com/contact',
            'https://www.85la.com/news'
        ]

        # 随机选择1-3个页面访问
        pages_to_visit = random.sample(nav_pages, random.randint(1, 3))
        referer = None

        for page in pages_to_visit:
            if page in self.visited_urls:
                continue

            try:
                # 随机延迟2-5秒
                time.sleep(random.uniform(2, 5))
                headers = self.browser.get_random_headers(referer)
                response = self.browser.session.get(page, headers=headers, proxies=self.browser.proxy, timeout=10)

                if response.status_code == 200:
                    logging.info(f'模拟访问页面: {page}')
                    self.visited_urls.add(page)
                    referer = page  # 更新referer为当前页面

                    # 随机滚动页面（模拟用户行为）
                    if random.random() > 0.5:
                        time.sleep(random.uniform(1, 3))
            except Exception as e:
                logging.error(f'模拟访问{page}时出错: {e}')

        return referer

    def visit_target_page(self, url, referer=None):
        """访问目标页面"""
        try:
            # 随机延迟3-7秒
            time.sleep(random.uniform(3, 7))
            headers = self.browser.get_random_headers(referer)
            response = self.browser.session.get(url, headers=headers, proxies=self.browser.proxy, timeout=15)

            if response.status_code == 200:
                logging.info(f'成功访问目标页面: {url}')
                self.visited_urls.add(url)
                return response.text
            else:
                logging.error(f'访问目标页面{url}失败，状态码: {response.status_code}')
                return None
        except Exception as e:
            logging.error(f'访问目标页面{url}时出错: {e}')
            return None

class DataExtractor:
    """数据提取类，负责从页面中提取所需信息"""
    def __init__(self):
        pass

    def extract_recent_links(self, html, days=3):
        """提取最近几天内的链接"""
        if not html:
            return []

        soup = BeautifulSoup(html, 'html.parser')
        h2_tags = soup.find_all('h2')
        links = []
        current_date = datetime.now()

        for h2 in h2_tags:
            link = h2.find('a')
            if link and link.get('href'):
                try:
                    title = h2.get_text(strip=True)
                    date_str = title.split(' ')[0]
                    if self._is_recent_date(date_str, current_date, days):
                        href = link['href']
                        if not href.startswith('http'):
                            href = f"https://www.85la.com{href}"
                        links.append(href)
                except (ValueError, IndexError):
                    logging.warning(f"跳过无效标题: {h2.get_text(strip=True)}")
                    continue

        return links

    def _is_recent_date(self, date_str, current_date, days=3):
        """检查日期是否在指定天数内"""
        try:
            date_obj = datetime.strptime(date_str, '%Y年%m月%d日')
            return (current_date - date_obj).days <= days
        except ValueError:
            return False

    def extract_subscription_links(self, html):
        """提取订阅链接"""
        if not html:
            return []

        soup = BeautifulSoup(html, 'html.parser')
        subscription_links = []

        # 查找所有包含"Base64 订阅地址"的三级标题
        h3_tags = soup.find_all('h3', string=lambda text: text and "Base64 订阅地址" in text)
        for h3 in h3_tags:
            logging.info(f"找到三级标题: {h3.get_text(strip=True)}")
            h3_link = h3.find_next('a')  # 查找紧随其后的链接
            if h3_link and h3_link.get('href'):
                link_url = h3_link['href']
                subscription_links.append(link_url)

        return subscription_links

class SubscriptionCrawler:
    """主爬虫类，协调各组件工作"""
    def __init__(self, proxy_env=None):
        # 解析代理配置
        self.proxy = self._parse_proxy_config(proxy_env)
        # 创建浏览器模拟器
        self.browser = BrowserSimulator(self.proxy)
        # 创建页面访问器
        self.visitor = PageVisitor(self.browser)
        # 创建数据提取器
        self.extractor = DataExtractor()

    def _parse_proxy_config(self, proxy_env):
        """解析代理配置"""
        if not proxy_env:
            proxy_env = os.environ.get('PROXY')

        if proxy_env:
            try:
                # 尝试JSON格式解析
                return json.loads(proxy_env)
            except json.JSONDecodeError:
                # 尝试分号分隔格式
                if ';' in proxy_env:
                    proxy_parts = proxy_env.split(';')
                    proxy_dict = {}
                    for part in proxy_parts:
                        if part.strip():
                            if part.startswith('http://'):
                                proxy_dict['http'] = part
                            elif part.startswith('https://'):
                                proxy_dict['https'] = part
                    if proxy_dict:
                        logging.info('使用分号分隔格式的代理配置')
                        return proxy_dict
                logging.warning('代理配置格式无效，将不使用代理')
        return None

    def run(self, target_url, backup_url=None, output_file='links.txt'):
        """运行爬虫"""
        try:
            # 1. 模拟用户浏览行为
            referer = self.visitor.simulate_user_browsing()

            # 2. 访问目标页面
            html = self.visitor.visit_target_page(target_url, referer)

            # 3. 如果主URL失败，尝试备用URL
            if not html and backup_url:
                logging.warning(f"主URL {target_url} 访问失败，尝试备用URL {backup_url}")
                html = self.visitor.visit_target_page(backup_url, referer)

            if not html:
                logging.error("未能获取页面内容，爬虫终止")
                return False

            # 4. 提取最近的链接
            recent_links = self.extractor.extract_recent_links(html)
            if not recent_links:
                logging.info("未找到符合条件的链接")
                return True

            for link in recent_links:
                logging.info(f"提取的链接: {link}")

            # 5. 访问链接并提取订阅地址
            subscription_links = []
            for link in recent_links:
                # 随机延迟2-5秒
                time.sleep(random.uniform(2, 5))
                # 访问链接
                page_html = self.visitor.visit_target_page(link, target_url)
                # 提取订阅链接
                links = self.extractor.extract_subscription_links(page_html)
                subscription_links.extend(links)

            # 6. 保存订阅链接
            if subscription_links:
                with open(output_file, 'a', encoding='utf-8') as f:
                    for link in subscription_links:
                        f.write(link + '\n')
                        logging.info(f"保存订阅链接: {link}")
                logging.info(f"共保存 {len(subscription_links)} 个订阅链接到 {output_file}")
            else:
                logging.info("未找到订阅链接")

            return True
        except Exception as e:
            logging.error(f"爬虫运行时出错: {e}")
            return False

if __name__ == '__main__':
    # 目标URL
    target_url = "https://www.85la.com/internet-access/free-network-nodes"
    backup_url = "https://www.85la.com/internet-access"

    # 创建并运行爬虫
    crawler = SubscriptionCrawler()
    success = crawler.run(target_url, backup_url)

    if success:
        logging.info("爬虫运行成功")
    else:
        logging.info("爬虫运行失败")
