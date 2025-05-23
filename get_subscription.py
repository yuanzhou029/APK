import requests
import base64
from datetime import datetime, timedelta
import logging
import re
import os  

logging.basicConfig(level=logging.DEBUG)

def count_nodes(subscription_links):
    """统计节点数量"""
    try:
        # 解码base64并统计节点数量
        decoded = base64.b64decode(subscription_links).decode('utf-8')
        return len(re.findall(r'vmess://|vless://|trojan://|ss://|hysteria2', decoded))
    except:
        return 0

def get_subscription_links():
    # 删除 base64.txt 文件（如果存在）
    if os.path.exists("base64.txt"):
        os.remove("base64.txt")
        print("已删除 base64.txt 文件")
    
    # 获取当前日期，手动去掉月份前面的0
    today = datetime.now()
    days_back = 0
    min_nodes = 1000
    max_attempts = 10  # 最大尝试次数
    
    while days_back < max_attempts:
        # 计算当前日期
        target_date = today - timedelta(days=days_back)
        month = target_date.month
        day = target_date.day
        current_date = f"{month if month >= 10 else month}{day}"  # 手动去掉月份前面的0
        
        # 动态生成当前日期的URL
        url_current = f"https://shz.al/~{current_date}-TG@pgkj666"
        
        # 打印动态生成的URL
        print(f"当前日期URL: {url_current}")
        
        # 尝试获取当前日期的订阅链接
        try:
            response_current = requests.get(url_current, timeout=10)
            response_current.raise_for_status()
            subscription_links_current = response_current.text
            print("获取当前日期订阅链接成功")
            
            # 转换为Base64编码并保存到文件
            base64_links_current = base64.b64encode(subscription_links_current.encode('utf-8')).decode('utf-8')
            with open("base64.txt", "a") as file:  # 使用追加模式
                file.write(base64_links_current + "\n")  # 追加并换行
            
            # 统计当前URL的节点数量
            node_count = count_nodes(base64_links_current)
            print(f"当前URL节点数量: {node_count}")
            
            # 读取 base64.txt 文件并统计总结点数
            with open("base64.txt", "r") as file:
                total_nodes = sum(count_nodes(line.strip()) for line in file)
            print(f"总节点数量: {total_nodes}")
            
            if total_nodes >= min_nodes:
                print(f"节点数量满足要求，停止查找")
                break
            else:
                print(f"节点数量不足 {min_nodes} 个，继续查找前一天...")
                days_back += 1
                
        except requests.exceptions.RequestException as e:
            print(f"获取当前日期订阅链接失败: {e}")
            days_back += 1

if __name__ == "__main__":
    get_subscription_links()
