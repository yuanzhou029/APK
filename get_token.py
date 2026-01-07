import requests
import re
import os
import time
from urllib.parse import urlparse
from pathlib import Path

# ================= 配置区域 =================
# 项目配置
github_issue_url = "https://github.com/wzdnzd/aggregator/issues/91"
github_api_url = "https://api.github.com/repos/wzdnzd/aggregator/issues/91"
default_domain = "https://proxy-manager-ggeu.onrender.com"
output_file = "links.txt"

# 网络请求配置
request_timeout = 15
max_retries = 3
retry_delay = 2  # 重试间隔秒数
# ===========================================


def _fetch_url_content(url: str, description: str, is_api: bool = False) -> str | None:
    """
    辅助函数：从指定URL获取内容，并处理重试逻辑。

    参数:
        url (str): 要请求的URL。
        description (str): 请求的描述，用于日志输出。
        is_api (bool): 是否为API请求，如果是则返回JSON格式。

    返回:
        str: 页面内容，如果请求失败则返回None。
    """
    print(f"开始{description}，请求URL: {url}")
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': 'application/vnd.github.v3+json' if is_api else 'text/html'
    }
    
    for retries in range(1, max_retries + 1):
        try:
            response = requests.get(url, headers=headers, timeout=request_timeout)
            response.raise_for_status()
            if is_api:
                return response.json()
            return response.text
        except requests.exceptions.RequestException as e:
            error_msg = f"{description}请求失败 (尝试 {retries}/{max_retries}): {e}"
            if retries < max_retries:
                print(f"{error_msg}, {retry_delay}秒后重试...")
                time.sleep(retry_delay)
            else:
                print(f"{error_msg}")
                return None


def extract_from_github_api() -> tuple[str | None, str]:
    """
    从GitHub API提取token和服务地址（更可靠的方式）

    返回:
        tuple: (token, service_url)
    """
    data = _fetch_url_content(github_api_url, "获取Issue数据(API)", is_api=True)
    if not data:
        return None, default_domain
    
    body = data.get('body', '')
    if not body:
        print("Issue body为空")
        return None, default_domain
    
    token = None
    service_url = default_domain
    
    # 从Markdown表格中提取token
    # 匹配格式: |  token  |  鉴权  |  是  |  -  |  -  |  `xxxxx`  |
    token_match = re.search(r'\|\s*token\s*\|[^|]*\|[^|]*\|[^|]*\|[^|]*\|\s*`([a-z0-9]{16,40})`\s*\|', body)
    if token_match:
        token = token_match.group(1)
        print(f"✅ 成功从表格提取到token: {token[:4]}****{token[-4:]}")
    else:
        # 备用方案：直接搜索反引号包裹的32位token
        backup_match = re.search(r'`([a-z0-9]{32})`', body)
        if backup_match:
            token = backup_match.group(1)
            print(f"✅ 成功从备用方案提取到token: {token[:4]}****{token[-4:]}")
        else:
            print("❌ 未找到符合格式的token")
    
    # 提取服务地址
    # 匹配格式: **在线服务接口地址**：https://xxx.xxx/api/v1/subscribe?token=xxx
    url_match = re.search(r'\*\*在线服务接口地址\*\*[：:]\s*(https?://[^\s\n]+)', body)
    if url_match:
        full_url = url_match.group(1)
        # 解析URL，提取协议和域名部分
        parsed_url = urlparse(full_url)
        service_url = f"{parsed_url.scheme}://{parsed_url.netloc}"
        print(f"✅ 成功提取到服务地址: {service_url}")
    else:
        print(f"⚠️ 未找到服务地址，使用默认值: {default_domain}")
    
    return token, service_url


def extract_unified_token() -> str | None:
    """
    从GitHub Issue提取统一token字符串（HTML方式，作为备用）

    返回:
        str: 提取到的token，如果提取失败则返回None
    """
    html_content = _fetch_url_content(github_issue_url, "获取token(HTML)")
    if not html_content:
        return None

    # 方案1：查找具有class="notranslate"属性的<code>标签中的token
    match = re.search(r'<code[^>]*>([a-z0-9]{32})</code>', html_content)
    if match:
        token = match.group(1)
        return token
    
    # 方案2：从表格单元格中提取
    match = re.search(r'<td[^>]*>\s*<code[^>]*>([a-z0-9]{16,40})</code>\s*</td>', html_content)
    if match:
        token = match.group(1)
        return token
    
    print("未找到符合格式的token")
    return None


def extract_service_url() -> str:
    """
    从GitHub Issue提取在线服务接口的域名（HTML方式，作为备用）

    返回:
        str: 提取到的域名，如果提取失败则返回默认域名
    """
    html_content = _fetch_url_content(github_issue_url, "获取服务URL(HTML)")
    if not html_content:
        return default_domain

    # 匹配 a 标签中的 href 属性
    match = re.search(r'<strong>在线服务接口地址</strong>[：:]\s*<a href="(https?://[^"]+)"', html_content)
    if match:
        full_url = match.group(1)
        full_url = full_url.replace('&amp;', '&')
        parsed_url = urlparse(full_url)
        domain = f"{parsed_url.scheme}://{parsed_url.netloc}"
        return domain

    print(f"未找到符合格式的域名，使用默认值: {default_domain}")
    return default_domain


def generate_subscribe_url(token: str, base_url: str) -> str:
    """
    生成订阅URL

    参数:
        token: 用于订阅的token
        base_url: 服务基础地址

    返回:
        str: 完整的订阅URL
    """
    if not token:
        raise ValueError("token不能为空")

    # 固定的后半部分
    fixed_path = "/api/v1/subscribe?token={}&target=v2ray&list=true"
    subscribe_url = base_url + fixed_path.format(token)
    return subscribe_url


def main():
    """主函数，执行脚本主要逻辑"""
    # 检查并创建输出文件
    links_path = Path(__file__).parent / output_file
    if not links_path.exists():
        try:
            links_path.touch()
            print(f"{output_file} 文件不存在，已创建新文件")
        except OSError as e:
            print(f"创建{output_file}文件失败: {e}")
            return
    else:
        print(f"{output_file} 文件已存在")

    # 优先使用GitHub API提取（更可靠）
    print("\n" + "=" * 50)
    print("📡 尝试通过GitHub API获取数据...")
    print("=" * 50)
    
    token, service_url = extract_from_github_api()
    
    # 如果API方式失败，尝试HTML方式
    if not token:
        print("\n" + "=" * 50)
        print("📡 API方式失败，尝试HTML方式...")
        print("=" * 50)
        token = extract_unified_token()
        if token:
            service_url = extract_service_url()
    
    if token:
        try:
            subscribe_url = generate_subscribe_url(token, service_url)
            print("\n" + "=" * 50)
            print("🎉 获取成功！")
            print("=" * 50)
            print(f"Token: {token[:4]}****{token[-4:]}")
            print(f"服务地址: {service_url}")
            print(f"订阅URL: {subscribe_url}")

            # 读取现有内容，检查是否已存在相同URL
            existing_urls = set()
            if links_path.exists():
                with links_path.open("r", encoding="utf-8") as f:
                    existing_urls = set(line.strip() for line in f if line.strip())
            
            if subscribe_url in existing_urls:
                print(f"\n⚠️ 该订阅URL已存在于{output_file}中，跳过写入")
            else:
                # 保存订阅URL到文件
                with links_path.open("a", encoding="utf-8") as f:
                    f.write(subscribe_url + "\n")
                print(f"\n✅ 订阅URL已成功追加到{output_file}")
            print("=" * 50)
        except ValueError as e:
            print(f"❌ 生成订阅URL失败: {e}")
        except Exception as e:
            print(f"❌ 处理订阅URL时发生未知错误: {e}")
    else:
        print("\n" + "=" * 50)
        print("❌ 未能获取到token，请检查：")
        print("   1. 网络连接是否正常")
        print("   2. GitHub Issue是否可访问")
        print("   3. Issue内容格式是否有变化")
        print("=" * 50)


if __name__ == "__main__":
    print("=" * 50)
    print("🚀 GitHub Token 提取工具 v2.0")
    print("=" * 50)
    main()
