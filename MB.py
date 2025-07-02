import sys
import re
import os
from datetime import datetime, timedelta  # 新增：timedelta用于日期偏移
from urllib.parse import urljoin
sys.stdout.reconfigure(encoding='utf-8')
import requests
from bs4 import BeautifulSoup

def extract_subscription_links(page_content):
    # 正则匹配目标格式：https://mm.mibei77.com/YYYYMM/DD.随机字符.txt
    # 解释：https?:// 匹配 http/https 协议；mm\.mibei77\.com 固定域名；\d{6} 匹配 YYYYMM（如202506）；\d{2} 匹配 DD（如06）；[a-zA-Z0-9]+ 匹配随机字符串；\.txt 固定后缀
    pattern = re.compile(r'https?://mm\.mibei77\.com/\d{6}|fs\.v2rayse\.com/\d+/\d+\.[a-zA-Z0-9]+\.txt')
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
