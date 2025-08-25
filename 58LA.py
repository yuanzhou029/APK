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
    'Mozilla/5.0 (iPhone; CPU iPhone OS 17_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Mobile/15E148 Safari/604.1',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Edge/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Linux; Android 13; SM-G998B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Mobile Safari/537.36',
    'Mozilla/5.0 (iPad; CPU OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1',
    'Mozilla/5.0 (Windows NT 10.0; rv:109.0) Gecko/20100101 Firefox/115.0',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36'
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
        'DNT': '1',
        'Cache-Control': 'max-age=0',
        'TE': 'Trailers',
        'Accept-Encoding': 'gzip, deflate, br'
    }
    return headers

# 创建带重试机制的session
def create_session():
    session = requests.Session()
    retry = Retry(total=8, backoff_factor=2, status_forcelist=[403, 429, 500, 502, 503, 504])
    adapter = HTTPAdapter(max_retries=retry)
    session.mount('http://', adapter)
    session.mount('https://', adapter)
    return session

# 尝试从环境变量获取代理配置
def get_proxy_config():
    proxy_env = os.environ.get('PROXY')
    if proxy_env:
        try:
            return json.loads(proxy_env)
        except json.JSONDecodeError:
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

# 模拟访问首页以获取Cookies和建立会话
def setup_cookies_and_session(session, proxy):
    try:
        home_url = 'https://www.85la.com/'
        headers = get_random_headers()
        response = session.get(home_url, headers=headers, proxies=proxy)
        if response.status_code == 200:
            logging.info('成功获取Cookies和建立会话')
            
            if random.random() > 0.5:
                nav_links = ['https://www.85la.com/about', 'https://www.85la.com/contact', 'https://www.85la.com/news']
                random_nav_url = random.choice(nav_links)
                time.sleep(random.uniform(2, 4))
                session.get(random_nav_url, headers=get_random_headers(), proxies=proxy)
                logging.info(f'模拟用户浏览: {random_nav_url}')
                
            return True
        else:
            logging.warning(f'获取Cookies失败，状态码: {response.status_code}')
            return False
    except Exception as e:
        logging.error(f'获取Cookies时出错: {e}')
        return False

# 获取页面内容
def fetch_page(session, url, proxy):
    try:
        logging.info(f'访问页面: {url}')
        headers = get_random_headers()
        time.sleep(random.uniform(2, 5))
        response = session.get(url, headers=headers, proxies=proxy, timeout=10)
        if response.status_code == 200:
            return response.text
        else:
            logging.error(f'无法访问页面 {url}，状态码: {response.status_code}')
            return None
    except Exception as e:
        logging.error(f'获取页面 {url} 时出错: {e}')
        return None

# 解析HTML并提取符合条件的链接
def parse_links(html, current_date):
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
                    href = link['href']
                    if not href.startswith('http'):
                        href = f"https://www.85la.com{href}"
                    links.append(href)
            except (ValueError, IndexError):
                logging.warning(f"跳过无效标题: {h2.get_text(strip=True)}")
                continue
    return links

# 检查日期是否在最近三天内
def is_recent_date(date_str, current_date):
    try:
        date_obj = datetime.datetime.strptime(date_str, '%Y年%m月%d日')
        return (current_date - date_obj).days <= 3
    except ValueError:
        return False

# 访问链接并提取页面中的三级标题 Base64 订阅地址及其链接
def fetch_subscriptions(session, links, proxy):
    with open("links.txt", "a", encoding="utf-8") as file:
        for link in links:
            try:
                logging.info(f"访问链接: {link}")
                headers = get_random_headers()
                time.sleep(random.uniform(3, 7))
                response = session.get(link, headers=headers, proxies=proxy, timeout=10)
                if response.status_code == 200:
                    soup = BeautifulSoup(response.text, 'html.parser')
                    h3_tags = soup.find_all('h3', string=lambda text: text and "Base64 订阅地址" in text)
                    for h3 in h3_tags:
                        logging.info(f"找到三级标题: {h3.get_text(strip=True)}")
                        h3_link = h3.find_next('a')
                        if h3_link and h3_link.get('href'):
                            link_url = h3_link['href']
                            logging.info(f"链接地址: {link_url}")
                            file.write(link_url + "\n")
                else:
                    logging.error(f"无法访问链接 {link}，状态码: {response.status_code}")
            except Exception as e:
                logging.error(f"处理链接 {link} 时出错: {e}")
                time.sleep(random.uniform(2, 4))

# 主函数
def main():
    url = "https://www.85la.com/internet-access/free-network-nodes"
    backup_url = "https://www.85la.com/internet-access"
    current_date = datetime.datetime.now()

    # 创建session和获取代理
    session = create_session()
    proxy = get_proxy_config()

    # 尝试获取Cookies
    setup_cookies_and_session(session, proxy)

    # 获取页面内容
    html = fetch_page(session, url, proxy)
    
    # 如果主URL失败，尝试备用URL
    if not html:
        logging.warning(f"主URL {url} 访问失败，尝试备用URL {backup_url}")
        html = fetch_page(session, backup_url, proxy)

    if html:
        # 解析链接
        links = parse_links(html, current_date)
        if links:
            for link in links:
                logging.info(f"提取的链接: {link}")
            # 访问链接并提取订阅地址
            fetch_subscriptions(session, links, proxy)
        else:
            logging.info("未找到符合条件的链接")
    else:
        logging.error("未能获取页面内容，脚本终止")

if __name__ == "__main__":
    main()
