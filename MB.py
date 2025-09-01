import sys
import re
import os
import random
import time
from datetime import datetime, timedelta
from urllib.parse import urljoin
import requests
from bs4 import BeautifulSoup

# 配置中文字符集
sys.stdout.reconfigure(encoding='utf-8')

# 扩展的User-Agent列表
USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/117.0',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Safari/605.1.15',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.0.0 Edge/116.0.1938.76',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.0.0 Safari/537.36',
    'Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1',
    'Mozilla/5.0 (iPad; CPU OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1'
]

# 创建会话对象
def create_session():
    session = requests.Session()
    # 随机选择User-Agent
    headers = {
        'User-Agent': random.choice(USER_AGENTS),
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
        'Accept-Language': 'zh-CN,zh;q=0.9',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'Cache-Control': 'max-age=0',
        'TE': 'Trailers',
    }
    session.headers.update(headers)
    return session

# 带重试机制的请求函数，特别优化了GitHub Actions环境
def request_with_retry(session, url, max_retries=5, base_delay=3):
    retries = 0
    while retries < max_retries:
        try:
            # 在GitHub Actions环境中使用更长的随机延迟
            is_github_actions = os.environ.get('GITHUB_ACTIONS') == 'true'
            if is_github_actions:
                delay = random.uniform(base_delay * 2, base_delay * 3)
            else:
                delay = random.uniform(base_delay, base_delay * 2)
            
            print(f"等待 {delay:.2f} 秒后发送请求...")
            time.sleep(delay)
            
            response = session.get(url, timeout=20)
            
            # 检测到429错误时的特殊处理
            if response.status_code == 429:
                print(f"收到429 Too Many Requests错误，正在应用特殊处理...")
                retries += 1
                # 增加等待时间并更换User-Agent
                wait_time = random.uniform(base_delay * (2 ** retries), base_delay * (2 ** retries) + 5)
                print(f"等待 {wait_time:.2f} 秒后重试，更换User-Agent...")
                session.headers['User-Agent'] = random.choice(USER_AGENTS)
                time.sleep(wait_time)
                continue
            
            response.raise_for_status()
            return response
            
        except requests.exceptions.RequestException as e:
            retries += 1
            print(f"请求失败 ({retries}/{max_retries}): {str(e)}")
            
            if retries < max_retries:
                # 指数退避策略，GitHub Actions环境中使用更长的等待时间
                if is_github_actions:
                    wait_time = random.uniform(base_delay * (2 ** retries), base_delay * (2 ** retries) + 10)
                else:
                    wait_time = random.uniform(base_delay * (2 ** retries), base_delay * (2 ** retries) + 5)
                
                print(f"等待 {wait_time:.2f} 秒后重试...")
                # 重试前更换User-Agent
                session.headers['User-Agent'] = random.choice(USER_AGENTS)
                time.sleep(wait_time)
    return None

def extract_subscription_links(page_content):
    # 正则匹配目标格式：https://mm.mibei77.com/YYYYMM/DD.随机字符.txt
    pattern = re.compile(r'https?://(?:mm\.mibei77\.com/\d+/\d+\.[a-zA-Z0-9]+|fs\.v2rayse\.com/share/\d+/[a-zA-Z0-9]+)\.txt')
    return pattern.findall(page_content)

def find_recent_messages(url):
    """获取当前日期及前两天（共三天）的消息"""
    # 生成三天的日期列表（格式：YYYY年MM月DD日）：今天、昨天、前天
    today = datetime.today()
    date_list = [
        (today - timedelta(days=i)).strftime("%Y年%m月%d日") 
        for i in range(0, 3)  # 0: 今天, 1: 昨天, 2: 前天（共3天）
    ]
    
    try:
        response = requests.get(url, timeout=10)
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
                        msg_response = requests.get(link, timeout=10)
                        msg_response.raise_for_status()
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

if __name__ == "__main__":
    # 生成三天的日期范围（用于提示）
    today = datetime.today().strftime("%Y年%m月%d日")
    yesterday = (datetime.today() - timedelta(days=1)).strftime("%Y年%m月%d日")
    two_days_ago = (datetime.today() - timedelta(days=2)).strftime("%Y年%m月%d日")
    print(f"当前查询日期范围：{two_days_ago}、{yesterday}、{today}")
    
    target_url = "https://www.mibei77.com/"
    messages = find_recent_messages(target_url)
    
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
