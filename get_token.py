import requests
import re

def extract_unified_token():
    """提取统一为后面的token字符串"""
    issue_url = "https://github.com/wzdnzd/aggregator/issues/91"
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(issue_url, headers=headers, timeout=10)
        response.raise_for_status()
        
        # 精确匹配<td>统一为<code>格式的token
        match = re.search(r'<td>统一为<code class="notranslate">([a-z0-9]{16})</code></td>', response.text)
        if match:
            return match.group(1)
        return None
    except Exception as e:
        print(f"请求失败: {str(e)}")
        return None

def generate_subscribe_url(token):
    """生成订阅URL"""
    return f"https://ohayoo-distribute.hf.space/api/v1/subscribe?token={token}&target=v2ray&list=true"
    
def save_subscription_data(url, filename="v2ray.txt"):
    """保存订阅数据到文件"""
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(response.text)
        return True
    except Exception as e:
        print(f"保存订阅数据失败: {str(e)}")
        return False

if __name__ == "__main__":
    token = extract_unified_token()
    if token:
        subscribe_url = generate_subscribe_url(token)
        print("="*50)
        print(f"获取到的token: {token}")
        print(f"生成的订阅URL: {subscribe_url}")
        
        # 注释掉保存订阅数据的函数调用
        # if save_subscription_data(subscribe_url):
        #     print("订阅数据已保存到v2ray.txt")
        # else:
        #     print("⚠️ 订阅数据保存失败")
        print("="*50)
    else:
        print("⚠️ 未找到符合格式的token")
