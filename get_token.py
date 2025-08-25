import requests
import re
import os
import time
from urllib.parse import urlparse

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


def extract_unified_token():
    """
    从GitHub Issue提取统一token字符串

    返回:
        str: 提取到的token，如果提取失败则返回None
    """
    print(f"开始提取token，请求URL: {github_issue_url}")
    retries = 0
    while retries < max_retries:
        try:
            headers = {'User-Agent': 'Mozilla/5.0'}
            response = requests.get(github_issue_url, headers=headers, timeout=request_timeout)
            response.raise_for_status()

            # 精确匹配<td>统一为<code>格式的token
            match = re.search(r'<td>统一为<code class="notranslate">([a-z0-9]{16})</code></td>', response.text)
            if match:
                token = match.group(1)
                print(f"成功提取到token: {token[:4]}****{token[-4:]}")  # 隐藏中间部分
                return token
            print("未找到符合格式的token")
            return None
        except requests.exceptions.RequestException as e:
            retries += 1
            error_msg = f"提取token请求失败 (尝试 {retries}/{max_retries}): {str(e)}"
            if retries < max_retries:
                error_msg += f", {retry_delay}秒后重试..."
                print(error_msg)
                time.sleep(retry_delay)
            else:
                print(error_msg)
                print(f"请求失败: {str(e)}")
                return None


def extract_service_url():
    """
    从GitHub Issue提取在线服务接口的域名（只提取第一个/之前的部分）

    返回:
        str: 提取到的域名，如果提取失败则返回默认域名
    """
    print(f"开始提取域名，请求URL: {github_issue_url}")
    retries = 0
    while retries < max_retries:
        try:
            headers = {'User-Agent': 'Mozilla/5.0'}
            response = requests.get(github_issue_url, headers=headers, timeout=request_timeout)
            response.raise_for_status()

            # 匹配 a 标签中的 href 属性
            match = re.search(r'<strong>在线服务接口地址</strong>：<a href="(https?://[^"]+)"', response.text)
            if match:
                full_url = match.group(1)
                # 替换 HTML 实体编码 &amp; 为 &
                full_url = full_url.replace('&amp;', '&')

                # 解析URL，提取协议和域名部分（第一个/之前的部分）
                parsed_url = urlparse(full_url)
                domain = f"{parsed_url.scheme}://{parsed_url.netloc}"

                print(f"成功提取到域名: {domain}")
                return domain

            print("无法提取域名，使用默认值")
            print(f"无法提取域名，使用默认值: {default_domain}")
            return default_domain
        except requests.exceptions.RequestException as e:
            retries += 1
            error_msg = f"提取域名请求失败 (尝试 {retries}/{max_retries}): {str(e)}"
            if retries < max_retries:
                error_msg += f", {retry_delay}秒后重试..."
                print(error_msg)
                time.sleep(retry_delay)
            else:
                print(error_msg)
                print(f"请求失败: {str(e)}")
                # 发生错误时使用默认值
                print(f"发生错误，使用默认域名: {default_domain}")
                return default_domain


def generate_subscribe_url(token):
    """
    生成订阅URL

    参数:
        token: 用于订阅的token

    返回:
        str: 完整的订阅URL
    """
    if not token:
        print("无法生成订阅URL: token为空")
        raise ValueError("token不能为空")

    base_url = extract_service_url()
    # 固定的后半部分
    fixed_path = "/api/v1/subscribe?token={}&target=v2ray&list=true"
    subscribe_url = base_url + fixed_path.format(token)
    print(f"生成订阅URL: {subscribe_url}")
    return subscribe_url


def main():
    """主函数，执行脚本主要逻辑"""
    # 检查输出文件是否存在
    links_path = os.path.join(os.path.dirname(__file__), output_file)
    if not os.path.exists(links_path):
        # 不存在则创建空文件
        try:
            with open(links_path, "w", encoding="utf-8") as f:
                pass
            print(f"{output_file} 文件不存在，已创建新文件")
        except Exception as e:
            print(f"创建{output_file}文件失败: {str(e)}")
            return
    else:
        print(f"{output_file} 文件已存在")

    # 提取token
    token = extract_unified_token()
    if token:
        try:
            subscribe_url = generate_subscribe_url(token)
            print("="*50)
            print(f"获取到的token: {token[:4]}****{token[-4:]}")  # 隐藏中间部分
            print(f"生成的订阅URL: {subscribe_url}")

            # 保存订阅URL到文件
            with open(links_path, "a", encoding="utf-8") as f:
                f.write(subscribe_url + "\n")
            print(f"订阅URL已成功追加到{output_file}")
        except Exception as e:
            print(f"生成或保存订阅URL失败: {str(e)}")
        finally:
            print("="*50)
    else:
        print("⚠️ 未找到符合格式的token")


if __name__ == "__main__":
    print("===== 程序开始执行 =====")
    main()


