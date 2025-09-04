import os
import requests
import urllib.parse

# 定义文件路径
links_file = 'links.txt'
output_file = 'usb.txt'

# 设置请求超时时间（秒）
TIMEOUT = 30

# 设置请求头，模拟浏览器行为
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}

# 订阅转换后端列表（优先级从高到低）
SUB_CONVERTERS = [
    'https://url.v1.mk/sub',          # 主要后端
    'https://subapi.cmliussss.net',   # 备用后端1
    'https://subapi.140407.xyz'       # 备用后端2
]

def convert_subscription(subscription_urls):
    """使用多后端自动切换机制处理订阅链接转换"""
    # 构建转换参数（适用于所有后端）
    params = {
        'target': 'clash',
        'url': subscription_urls,
        'insert': 'false',
        'config': 'https://raw.githubusercontent.com/yuanzhou029/ACL4SSR/refs/heads/rm/yz029.ini',
        'emoji': 'true',
        'list': 'false',
        'xudp': 'false',
        'udp': 'false',
        'tfo': 'false',
        'expand': 'true',
        'scv': 'false',
        'fdn': 'false',
        'new_name': 'true'
    }
    query_string = urllib.parse.urlencode(params)
    
    # 依次尝试每个后端
    for index, converter in enumerate(SUB_CONVERTERS, 1):
        try:
            # 构建完整转换URL
            conversion_url = f"{converter}?{query_string}"
            print(f"  正在使用第{index}个转换后端: {converter}")
            print(f"  请求URL: {conversion_url}")
            
            # 发送请求
            response = requests.get(conversion_url, headers=HEADERS, timeout=TIMEOUT)
            response.raise_for_status()
            
            # 检查响应内容是否有效（非错误页面）
            if 'Invalid target' in response.text or len(response.text.strip()) == 0:
                raise Exception("无效的转换结果")
            
            print(f"  成功: 第{index}个转换后端可用")
            return response.text
            
        except requests.exceptions.RequestException as e:
            error_msg = f"第{index}个转换后端请求失败: {str(e)}"
            print(error_msg)
        except Exception as e:
            error_msg = f"第{index}个转换后端处理失败: {str(e)}"
            print(error_msg)
        
        # 如果不是最后一个后端，提示将尝试下一个
        if index < len(SUB_CONVERTERS):
            print(f"  将尝试第{index+1}个转换后端...")
    
    # 所有后端都失败时，尝试直接获取原始链接内容
    print("所有转换后端均失效，尝试直接获取原始链接内容...")
    try:
        combined_content = []
        for url in subscription_urls.split('|'):
            response = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
            response.raise_for_status()
            combined_content.append(response.text)
        return '\n'.join(combined_content)
    except requests.exceptions.RequestException as backup_e:
        print(f"  原始链接获取也失败: {backup_e}")
        return ""

def get_subscription_content():
    try:
        # 检查links.txt文件是否存在
        if not os.path.exists(links_file):
            print(f"错误: {links_file} 文件不存在")
            return
        
        # 读取links.txt中的订阅链接
        with open(links_file, 'r', encoding='utf-8') as f:
            links = [line.strip() for line in f if line.strip()]
        
        if not links:
            print(f"警告: {links_file} 文件中没有找到有效的订阅链接")
            return
        
        # 创建或清空usb.txt文件
        with open(output_file, 'w', encoding='utf-8') as f_out:
            
            # 合并所有链接，用|分隔
            combined_links = '|'.join(links)
            print(f"处理合并链接: {combined_links}")
            
            # 使用多后端转换订阅链接
            content = convert_subscription(combined_links)
            
            if content:
                # 写入转换后的内容
                f_out.write(f"# 订阅节点由“背锅的侠”提供\n")
                f_out.write(content)
                f_out.write('\n')
                print(f"  成功: 已获取并保存转换后的链接内容")
            else:
                print(f"  失败: 无法获取或转换链接内容")
        
        print(f"\n成功: 已处理所有 {len(links)} 个订阅链接，并将转换后的内容保存到 {output_file} 文件中")
        
    except Exception as e:
        print(f"发生错误: {e}")

if __name__ == "__main__":
    get_subscription_content()
