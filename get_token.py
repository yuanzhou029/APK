import requests
import re
import os  # 新增：导入os模块用于文件操作

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
    return f"https://pm.enjoy.cloudns.biz/api/v1/subscribe?token={token}&target=v2ray&list=true"

if __name__ == "__main__":
    # 新增：检查links.txt是否存在（同脚本目录）
    links_path = os.path.join(os.path.dirname(__file__), "links.txt")
    if not os.path.exists(links_path):
        # 不存在则创建空文件（避免后续追加时报错）
        with open(links_path, "w", encoding="utf-8") as f:
            pass
        print("links.txt 文件不存在，已创建新文件")
    else:
        print("links.txt 文件已存在")

    token = extract_unified_token()
    if token:
        subscribe_url = generate_subscribe_url(token)
        print("="*50)
        print(f"获取到的token: {token}")
        print(f"生成的订阅URL: {subscribe_url}")
        
        # 新增：将订阅URL追加保存到links.txt（不覆盖原有数据）
        try:
            with open(links_path, "a", encoding="utf-8") as f:
                f.write(subscribe_url + "\n")  # 每个URL占一行
            print("订阅URL已成功追加到links.txt")
        except Exception as e:
            print(f"保存订阅URL失败: {str(e)}")
        
        print("="*50)
    else:
        print("⚠️ 未找到符合格式的token")

