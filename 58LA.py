import os
import requests
from bs4 import BeautifulSoup
import datetime
import logging
import time
import random
import json
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# 配置日志
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# 轮换User-Agent列表
USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2.1 Safari/605.1.15',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
    'Mozilla/5.0 (iPhone; CPU iPhone OS 17_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Mobile/15E148 Safari/604.1'
]

# 随机生成请求头
def get_random_headers():
    headers = {
        'User-Agent': random.choice(USER_AGENTS),
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
        'Accept-Language': 'zh-CN,zh;q=0.9',
        'Referer': 'https://www.85la.com/',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'same-origin',
        'Sec-Fetch-User': '?1',
    }
    return headers

# 创建带重试机制的session
def create_session():
    session = requests.Session()
    # 配置重试策略，增加总重试次数和回退因子
    retry = Retry(total=8, backoff_factor=2, status_forcelist=[403, 429, 500, 502, 503, 504])
    adapter = HTTPAdapter(max_retries=retry)
    session.mount('http://', adapter)
    session.mount('https://', adapter)
    return session

session = create_session()

# 尝试从环境变量获取代理配置
def get_proxy_config():
    # 从环境变量获取代理信息
    # 格式1: JSON字符串: {'http': 'http://proxy:port', 'https': 'https://proxy:port'}
    # 格式2: 分号分隔: http://proxy:port;https://proxy:port
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

proxy = get_proxy_config()

# 模拟访问首页以获取Cookies
def setup_cookies():
    try:
        # 先访问首页获取Cookies
        home_url = 'https://www.85la.com/'
        headers = get_random_headers()
        response = session.get(home_url, headers=headers, proxies=proxy)
        if response.status_code == 200:
            logging.info('成功获取Cookies')
            return True
        else:
            logging.warning(f'获取Cookies失败，状态码: {response.status_code}')
            return False
    except Exception as e:
        logging.error(f'获取Cookies时出错: {e}')
        return False

def fetch_page(url):
    """发送 HTTP 请求并返回页面内容"""
    try:
        # 每次请求使用不同的请求头
        headers = get_random_headers()
        # 添加随机延迟，范围增大
        time.sleep(random.uniform(2, 5))
        # 发送请求，使用代理（如果有）
        response = session.get(url, headers=headers, proxies=proxy)
        if response.status_code == 200:
            logging.info(f"成功访问页面: {url}")
            # 添加随机延迟
            time.sleep(random.uniform(1, 3))
            return response.text
        else:
            logging.error(f"无法访问页面，状态码: {response.status_code}")
            return None
    except Exception as e:
        logging.error(f"请求页面时出错: {e}")
        return None

def parse_links(html, current_date):
    """解析 HTML 并提取符合条件的链接"""
    soup = BeautifulSoup(html, 'html.parser')
    h2_tags = soup.find_all('h2')
    links = []

    for h2 in h2_tags:
        link = h2.find('a')
        if link and link.get('href'):
            try:
                title = h2.get_text(strip=True)
                date_str = title.split(' ')[0]
                if is_recent_date(date_str, current_date):
                    # 确保链接是完整的
                    href = link['href']
                    if not href.startswith('http'):
                        href = f"https://www.85la.com{href}"
                    links.append(href)
            except ValueError:
                logging.warning(f"跳过无效标题: {h2.get_text(strip=True)}")
                continue
    return links

def is_recent_date(date_str, current_date):
    """检查日期是否在最近三天内"""
    try:
        date_obj = datetime.datetime.strptime(date_str, '%Y年%m月%d日')
        return (current_date - date_obj).days <= 3
    except ValueError:
        return False

def fetch_subscriptions(links):
    """访问链接并提取页面中的三级标题 Base64 订阅地址及其链接"""
    with open("links.txt", "a", encoding="utf-8") as file:
        for link in links:
            try:
                logging.info(f"访问链接: {link}")
                # 每次请求使用不同的请求头
                headers = get_random_headers()
                # 添加随机延迟，范围增大
                time.sleep(random.uniform(3, 7))
                # 发送请求，使用代理（如果有）
                response = session.get(link, headers=headers, proxies=proxy)
                if response.status_code == 200:
                    soup = BeautifulSoup(response.text, 'html.parser')
                    # 查找三级标题为“Base64 订阅地址”
                    h3_tags = soup.find_all('h3', string=lambda text: text and "Base64 订阅地址" in text)
                    for h3 in h3_tags:
                        logging.info(f"找到三级标题: {h3.get_text(strip=True)}")
                        h3_link = h3.find_next('a')  # 查找紧随其后的链接
                        if h3_link and h3_link.get('href'):
                            link_url = h3_link['href']
                            logging.info(f"链接地址: {link_url}")
                            file.write(link_url + "\n")  # 将链接写入文件
                else:
                    logging.error(f"无法访问链接 {link}，状态码: {response.status_code}")
            except Exception as e:
                logging.error(f"处理链接 {link} 时出错: {e}")
                # 出错时也添加延迟
                time.sleep(random.uniform(2, 4))


def main():
    url = "https://www.85la.com/internet-access/free-network-nodes"
    current_date = datetime.datetime.now()

    # 尝试获取Cookies
    setup_cookies()

    # 获取页面内容
    html = fetch_page(url)
    if html:
        # 解析链接
        links = parse_links(html, current_date)
        for link in links:
            logging.info(f"提取的链接: {link}")
        # 访问链接并提取订阅地址
        fetch_subscriptions(links)
    else:
        logging.error("未能获取页面内容，脚本终止")
        # 尝试使用备用URL（如果有）
        alternative_url = "https://www.85la.com/internet-access"
        logging.info(f"尝试使用备用URL: {alternative_url}")
        html = fetch_page(alternative_url)
        if html:
            links = parse_links(html, current_date)
            fetch_subscriptions(links)

if __name__ == "__main__":
    main()
