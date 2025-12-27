import requests
import re
import os
import time
from urllib.parse import urlparse
from pathlib import Path

# ================= 配置区域 =================
# 项目配置
github_issue_url = "https://github.com/wzdnzd/aggregator/issues/91"
default_domain = "https://proxy-manager-ggeu.onrender.com"
output_file = "links.txt"

# 网络请求配置
request_timeout = 10
max_retries = 3
retry_delay = 2  # 重试间隔秒数
# ===========================================


def _fetch_url_content(url: str, description: str) -> str | None:
    """
    辅助函数：从指定URL获取内容，并处理重试逻辑。

    参数:
        url (str): 要请求的URL。
        description (str): 请求的描述，用于日志输出。

    返回:
        str: 页面内容，如果请求失败则返回None。
    """
    print(f"开始{description}，请求URL: {url}")
    headers = {'User-Agent': 'Mozilla/5.0'}
    for retries in range(1, max_retries + 1):
        try:
            response = requests.get(url, headers=headers, timeout=request_timeout)
            response.raise_for_status()
            return response.text
        except requests.exceptions.RequestException as e:
            error_msg = f"{description}请求失败 (尝试 {retries}/{max_retries}): {e}"
            if retries < max_retries:
                print(f"{error_msg}, {retry_delay}秒后重试...")
                time.sleep(retry_delay)
            else:
                print(f"{error_msg}")
                return None


def extract_unified_token() -> str | None:
    """
    从GitHub Issue提取统一token字符串

    返回:
        str: 提取到的token，如果提取失败则返回None
    """
    html_content = _fetch_url_content(github_issue_url, "获取token")
    if not html_content:
        return None

    # 直接查找具有class="notranslate"属性的<code>标签中的16位字母数字token
    match = re.search(r'<td><code class="notranslate">([a-z0-9]{16,20})</code></td>', html_content)
    if match:
        token = match.group(1)
        #print(f"成功提取到token: {token[:4]}****{token[-4:]}")  # 隐藏中间部分
        return token
    print("未找到符合格式的token")
    return None


def extract_service_url() -> str:
    """
    从GitHub Issue提取在线服务接口的域名（只提取第一个/之前的部分）

    返回:
        str: 提取到的域名，如果提取失败则返回默认域名
    """
    html_content = _fetch_url_content(github_issue_url, "获取服务URL")
    if not html_content:
        return default_domain

    # 匹配 a 标签中的 href 属性
    match = re.search(r'<strong>在线服务接口地址</strong>：<a href="(https?://[^"]+)"', html_content)
    if match:
        full_url = match.group(1)
        # 替换 HTML 实体编码 & 为 &
        full_url = full_url.replace('&', '&')

        # 解析URL，提取协议和域名部分（第一个/之前的部分）
        parsed_url = urlparse(full_url)
        domain = f"{parsed_url.scheme}://{parsed_url.netloc}"

        #print(f"成功提取到域名: {domain}")
        return domain

    # 如果没有匹配到，则打印一次默认值信息
    print(f"未找到符合格式的域名，使用默认值: {default_domain}")
    return default_domain


def generate_subscribe_url(token: str) -> str:
    """
    生成订阅URL

    参数:
        token: 用于订阅的token

    返回:
        str: 完整的订阅URL
    """
    if not token:
        raise ValueError("token不能为空")

    base_url = extract_service_url()
    # 固定的后半部分
    fixed_path = "/api/v1/subscribe?token={}&target=v2ray&list=true"
    subscribe_url = base_url + fixed_path.format(token)
    #sprint(f"生成订阅URL: {subscribe_url}")
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

    # 提取token
    token = extract_unified_token()
    if token:
        try:
            subscribe_url = generate_subscribe_url(token)
            print("=" * 50)
            print(f"获取到的token: {token[:4]}****{token[-4:]}")  # 隐藏中间部分
            print(f"生成的订阅URL: {subscribe_url}")

            # 保存订阅URL到文件
            with links_path.open("a", encoding="utf-8") as f:
                f.write(subscribe_url + "\n")
            print(f"订阅URL已成功追加到{output_file}")
        except ValueError as e:
            print(f"生成订阅URL失败: {e}")
        except Exception as e:
            print(f"处理订阅URL时发生未知错误: {e}")
        finally:
            print("=" * 50)
    else:
        print("⚠️ 未找到符合格式的token")


if __name__ == "__main__":
    print("===== 程序开始执行 =====")
    main()
