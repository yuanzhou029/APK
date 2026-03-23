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
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0'
]

# 热门网站Referer列表，模拟真实用户跳转
REFERERS = [
    'https://www.google.com/',
    'https://www.baidu.com/',
    'https://www.bing.com/'
]

def create_session():
    session = requests.Session()
    headers = {
        'User-Agent': random.choice(USER_AGENTS),
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'Cache-Control': 'max-age=0',
        'DNT': '1',
        'Referer': random.choice(REFERERS)
    }
    session.headers.update(headers)
    return session

def request_with_retry(session, url, max_retries=3, base_delay=2):
    retries = 0
    is_github_actions = os.environ.get('GITHUB_ACTIONS') == 'true'
    while retries < max_retries:
        try:
            delay = random.uniform(base_delay*2, base_delay*3) if is_github_actions else random.uniform(base_delay, base_delay*1.5)
            print(f"等待 {delay:.2f} 秒后发送请求...")
            time.sleep(delay)

            response = session.get(url, timeout=20)

            if response.status_code == 429:
                print(f"429错误，第{retries+1}次重试...")
                retries += 1
                wait_time = random.uniform(base_delay*(2**retries), base_delay*(2**retries)+5)
                time.sleep(wait_time)
                session.headers['User-Agent'] = random.choice(USER_AGENTS)
                continue

            response.raise_for_status()
            return response

        except Exception as e:
            retries += 1
            print(f"请求失败 ({retries}/{max_retries}): {str(e)}")
            if retries < max_retries:
                wait_time = random.uniform(base_delay*(2**retries), base_delay*(2**retries)+5)
                time.sleep(wait_time)
                session.headers['User-Agent'] = random.choice(USER_AGENTS)
    return None

def extract_subscription_links(page_content):
    """
    提取订阅链接
    实际格式示例：
    - https://mm.mibei77.com/202601/01.0564bafre.txt
    - https://mm.mibei77.com/202601/01.05Clasholryaml
    """
    # 更新正则表达式以匹配实际格式：年月/月.日+随机字符.扩展名
    pattern = re.compile(r'(https?://mm\.mibei77\.com/\d{6}/\d{2}\.\d{2}[a-zA-Z0-9]+\.(?:yaml))') #  ?:txt|yaml
    links = pattern.findall(page_content)
    
    # 备用方案：更宽松的匹配
    if not links:
        pattern2 = re.compile(r'(https?://mm\.mibei77\.com/[^\s"\'<>]+\.(?:yaml))')  # ?:txt|yaml
        links = pattern2.findall(page_content)
    
    return links

def generate_date_formats(date_obj):
    """
    生成多种日期格式用于匹配
    """
    formats = []
    
    # 格式1: 2026年01月07日
    formats.append(date_obj.strftime("%Y年%m月%d日"))
    
    # 格式2: 一月 07, 2026 (网站实际使用的格式)
    month_names = ['一月', '二月', '三月', '四月', '五月', '六月', 
                   '七月', '八月', '九月', '十月', '十一月', '十二月']
    month_name = month_names[date_obj.month - 1]
    formats.append(f"{month_name} {date_obj.day:02d}, {date_obj.year}")
    
    # 格式3: 01月07日
    formats.append(date_obj.strftime("%m月%d日"))
    
    # 格式4: 2026-01-07
    formats.append(date_obj.strftime("%Y-%m-%d"))
    
    # 格式5: 01-07 (月-日)
    formats.append(date_obj.strftime("%m-%d"))
    
    return formats

def find_recent_messages(url):
    """获取当前日期及前两天（共三天）的消息"""
    today = datetime.today()
    
    # 生成三天的日期列表和对应的多种格式
    date_formats_list = []
    for i in range(3):  # 今天、昨天、前天
        date_obj = today - timedelta(days=i)
        formats = generate_date_formats(date_obj)
        date_formats_list.append({
            'date_obj': date_obj,
            'formats': formats,
            'display': date_obj.strftime("%Y年%m月%d日")
        })
    
    try:
        session = create_session()
        response = request_with_retry(session, url)
        if not response:
            print("❌ 无法获取主页内容")
            return []
        
        soup = BeautifulSoup(response.text, 'html.parser')
        recent_messages = []
        found_dates = set()
        
        # 查找所有文章链接
        # 方案1: 查找包含日期的标题链接
        a_elements = soup.find_all('a')
        
        for a_tag in a_elements:
            text = a_tag.get_text(strip=True)
            href = a_tag.get('href', '')
            
            # 跳过空链接或非文章链接
            if not href or not text or len(text) < 10:
                continue
            
            # 检查是否包含任意一天的日期格式
            matched_date = None
            for date_info in date_formats_list:
                for fmt in date_info['formats']:
                    if fmt in text:
                        matched_date = date_info
                        break
                if matched_date:
                    break
            
            if matched_date:
                # 避免重复处理同一天的消息
                date_key = matched_date['display']
                if date_key in found_dates:
                    continue
                found_dates.add(date_key)
                
                title = text
                link = urljoin(url, href)
                
                print(f"📰 找到文章: {title[:50]}...")
                print(f"   链接: {link}")
                
                # 访问文章详情页提取订阅链接
                subscription_links = []
                try:
                    msg_response = request_with_retry(session, link)
                    if msg_response:
                        subscription_links = extract_subscription_links(msg_response.text)
                        if subscription_links:
                            print(f"   ✅ 找到 {len(subscription_links)} 个订阅链接")
                        else:
                            print(f"   ⚠️ 未找到订阅链接")
                except Exception as e:
                    print(f"   ❌ 访问文章失败: {str(e)}")
                
                recent_messages.append({
                    "title": title,
                    "link": link,
                    "date": date_key,
                    "subscription_links": subscription_links
                })
        
        return recent_messages
    
    except Exception as e:
        print(f"❌ 访问或解析页面失败: {str(e)}")
        return []

def main():
    """主函数"""
    print("=" * 60)
    print("🚀 米贝分享订阅链接提取工具 v2.0")
    print("=" * 60)
    
    # 显示查询日期范围
    today = datetime.today()
    dates = [(today - timedelta(days=i)).strftime("%Y年%m月%d日") for i in range(3)]
    print(f"📅 查询日期范围：{dates[2]}、{dates[1]}、{dates[0]}")
    print()
    
    target_url = "https://www.mibei77.com/"
    print(f"🌐 目标网站: {target_url}")
    print()
    
    messages = find_recent_messages(target_url)
    
    links_path = os.path.join(os.path.dirname(__file__), "links.txt")
    
    if messages:
        print()
        print("=" * 60)
        print(f"🎉 找到 {len(messages)} 条包含近三天日期的消息:")
        print("=" * 60)
        
        all_subscription_links = []
        
        for idx, msg in enumerate(messages, 1):
            print(f"\n{idx}. 📅 日期：{msg['date']}")
            print(f"   📰 标题：{msg['title'][:60]}...")
            print(f"   🔗 链接：{msg['link']}")
            
            if msg['subscription_links']:
                print(f"   📥 订阅地址:")
                for sub_link in msg['subscription_links']:
                    print(f"      - {sub_link}")
                    all_subscription_links.append(sub_link)
            else:
                print("   ⚠️ 未提取到订阅地址")
        
        # 保存到文件
        if all_subscription_links:
            try:
                # 读取现有链接，避免重复
                existing_links = set()
                if os.path.exists(links_path):
                    with open(links_path, "r", encoding="utf-8") as f:
                        existing_links = set(line.strip() for line in f if line.strip())
                
                # 过滤出新链接
                new_links = [link for link in all_subscription_links if link not in existing_links]
                
                if new_links:
                    with open(links_path, "a", encoding="utf-8") as f:
                        for link in new_links:
                            f.write(link + "\n")
                    print(f"\n✅ 已将 {len(new_links)} 条新订阅地址追加到 {links_path}")
                else:
                    print(f"\n⚠️ 所有订阅地址已存在于 {links_path}，跳过写入")
                    
            except Exception as e:
                print(f"\n❌ 保存订阅地址失败: {str(e)}")
    else:
        print()
        print("=" * 60)
        print("❌ 未找到包含近三天日期的消息")
        print("   可能原因：")
        print("   1. 网站尚未更新今日内容")
        print("   2. 日期格式不匹配")
        print("   3. 网络请求被拦截")
        print("=" * 60)

if __name__ == "__main__":
    main()
