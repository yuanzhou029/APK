import sys
import re
import os
import random
import time
from datetime import datetime, timedelta
from urllib.parse import urljoin
import requests
from bs4 import BeautifulSoup
from crawl4ai import AsyncWebCrawler
import asyncio

# 配置中文字符集
sys.stdout.reconfigure(encoding='utf-8')

# 扩展的User-Agent列表
USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/117.0'
]

# 热门网站Referer列表，模拟真实用户跳转
REFERERS = [
    'https://www.google.com/',
    'https://www.baidu.com/',
    'https://www.bing.com/',
    'https://www.zhihu.com/',
    'https://www.weibo.com/'
]

def create_session():
    session = requests.Session()
    # 随机请求头配置
    headers = {
        'User-Agent': random.choice(USER_AGENTS),
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'Cache-Control': 'max-age=0',
        'DNT': '1',  # 启用Do Not Track
        'Referer': random.choice(REFERERS)
    }
    session.headers.update(headers)
    return session

def request_with_retry(session, url, max_retries=5, base_delay=3):
    retries = 0
    is_github_actions = os.environ.get('GITHUB_ACTIONS') == 'true'
    while retries < max_retries:
        try:
            # GitHub环境使用更长延迟
            delay = random.uniform(base_delay*2, base_delay*4) if is_github_actions else random.uniform(base_delay, base_delay*2)
            print(f"等待 {delay:.2f} 秒后发送请求...")
            time.sleep(delay)

            response = session.get(url, timeout=20)

            # 处理Google验证页面
            if 'google.com/sorry' in response.url:
                print("检测到Google人机验证，尝试通过Cookie绕过...")
                session.cookies.clear()
                session.headers['User-Agent'] = random.choice(USER_AGENTS)
                session.headers['Referer'] = random.choice(REFERERS)
                continue

            if response.status_code == 429:
                print(f"429错误，第{retries+1}次重试...")
                retries += 1
                wait_time = random.uniform(base_delay*(2**retries), base_delay*(2**retries)+10)
                time.sleep(wait_time)
                # 更换关键指纹信息
                session.headers['User-Agent'] = random.choice(USER_AGENTS)
                session.headers['Referer'] = random.choice(REFERERS)
                continue

            response.raise_for_status()
            return response

        except Exception as e:
            retries += 1
            print(f"请求失败 ({retries}/{max_retries}): {str(e)}")
            if retries < max_retries:
                wait_time = random.uniform(base_delay*(2**retries), base_delay*(2**retries)+10)
                time.sleep(wait_time)
                session.headers['User-Agent'] = random.choice(USER_AGENTS)
    return None

def extract_subscription_links(page_content):
    # 正则匹配目标格式：https://mm.mibei77.com/YYYYMM/DD.随机字符.txt
    pattern = re.compile(r'(https?://mm\.mibei77\.com/\d{4}\.\d{2}/\d{2}\.[a-zA-Z0-9]+\.(?:txt|yaml))')
    return pattern.findall(page_content)

# 替换原create_session和request_with_retry函数
async def crawl_with_crawl4ai(url):
    # 初始化异步爬虫，启用代理和反爬策略
    crawler = AsyncWebCrawler(
        verbose=True,
        proxy="http://your_proxy_ip:port",  # 可选代理配置
        headers={
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'DNT': '1'
        }
    )
    
    # 使用Crawl4AI内置的智能抓取功能
    result = await crawler.fetch(url)
    
    # 内置的LLM友好格式输出
    if result.success:
        return result.markdown  # 或 result.html, result.json
    return None

# 修改find_recent_messages为异步函数
async def find_recent_messages(url):
    """获取当前日期及前两天（共三天）的消息"""
    # 生成三天的日期列表（格式：YYYY年MM月DD日）：今天、昨天、前天
    today = datetime.today()
    date_list = [
        (today - timedelta(days=i)).strftime("%Y年%m月%d日") 
        for i in range(0, 1)  # 0: 今天, 1: 昨天, 2: 前天（共3天）
    ]
    
    try:
        # 使用带重试机制的请求
        session = create_session()
        response = request_with_retry(session, url)
        if not response:
            return []
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        recent_messages = []
        
        a_elements = soup.find_all('a')
        for a_tag in a_elements:
            # 检查消息文本是否包含三天中任意一天的日期
            for date in date_list:
                if date in a_tag.text:
                    title = a_tag.text.strip()
                    link = urljoin(url, a_tag.get('href', ''))
                    
                    # 访问消息链接并提取订阅地址（逻辑不变）
                    try:
                        # 消息链接也使用重试机制
                        msg_response = request_with_retry(session, link)
                        if msg_response:
                            subscription_links = extract_subscription_links(msg_response.text)
                    except Exception as e:
                        print(f"访问消息链接 {link} 失败: {str(e)}")
                        subscription_links = []
                    
                    recent_messages.append({
                        "title": title,
                        "link": link,
                        "date": date,  # 记录匹配的具体日期
                        "subscription_links": subscription_links
                    })
                    break  # 避免重复匹配同一天的消息
        
        return recent_messages
    
    except Exception as e:
        print(f"访问或解析页面失败: {str(e)}")
        return []

# 修改主程序入口
if __name__ == "__main__":
    # 生成三天的日期范围（用于提示）
    today = datetime.today().strftime("%Y年%m月%d日")
    yesterday = (datetime.today() - timedelta(days=1)).strftime("%Y年%m月%d日")
    two_days_ago = (datetime.today() - timedelta(days=2)).strftime("%Y年%m月%d日")
    print(f"当前查询日期范围：{two_days_ago}、{yesterday}、{today}")
    
    target_url = "https://www.mibei77.com/"
    messages = asyncio.run(find_recent_messages(target_url))
    
    links_path = os.path.join(os.path.dirname(__file__), "links.txt")
    
    if messages:
        print(f"找到 {len(messages)} 条包含近三天日期的消息:")
        for idx, msg in enumerate(messages, 1):
            print(f"{idx}. 日期：{msg['date']} | 标题：{msg['title']}")
            print(f"   消息链接：{msg['link']}")
            if msg['subscription_links']:
                print(f"   提取到的目标订阅地址:")
                for sub_link in msg['subscription_links']:
                    print(f"   - {sub_link}")
                
                # 追加保存到links.txt（逻辑不变）
                try:
                    with open(links_path, "a", encoding="utf-8") as f:
                        for sub_link in msg['subscription_links']:
                            f.write(sub_link + "\n")
                    print(f"   已将 {len(msg['subscription_links'])} 条订阅地址追加到links.txt")
                except Exception as e:
                    print(f"   保存订阅地址到文件失败: {str(e)}")
            else:
                print("   未提取到目标格式的订阅地址（可能页面无相关内容或格式不匹配）")
            print()  # 空行分隔
    else:
        print("未找到包含近三天日期的消息（可能网站未更新、日期格式不匹配或链接标签不正确）")
