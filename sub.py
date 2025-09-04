import os
import requests
import urllib.parse
import hashlib
import time
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# 定义文件路径
links_file = 'links.txt'
output_file = 'usb.txt'
CACHE_DIR = 'cache'
CACHE_EXPIRE = 3600  # 缓存有效期(秒)

# 创建缓存目录
os.makedirs(CACHE_DIR, exist_ok=True)

def get_cache_key(url):
    """生成URL的缓存键"""
    return hashlib.md5(url.encode()).hexdigest()

def get_cached_content(url):
    """获取缓存内容，如果缓存有效"""
    cache_key = get_cache_key(url)
    cache_path = os.path.join(CACHE_DIR, cache_key)
    if os.path.exists(cache_path):
        modified_time = os.path.getmtime(cache_path)
        if time.time() - modified_time < CACHE_EXPIRE:
            with open(cache_path, 'r', encoding='utf-8') as f:
                return f.read()
    return None

def save_cache_content(url, content):
    """保存内容到缓存"""
    cache_key = get_cache_key(url)
    cache_path = os.path.join(CACHE_DIR, cache_key)
    with open(cache_path, 'w', encoding='utf-8') as f:
        f.write(content)

# 设置请求超时时间（秒）
TIMEOUT = 15  # 缩短超时时间，提高响应速度

# 创建带重试机制的Session
SESSION = requests.Session()
retry_strategy = Retry(
    total=2,  # 总重试次数
    backoff_factor=1,  # 重试间隔因子
    status_forcelist=[429, 500, 502, 503, 504]  # 需要重试的状态码
)
adapter = HTTPAdapter(max_retries=retry_strategy, pool_connections=10, pool_maxsize=10)
SESSION.mount('http://', adapter)
SESSION.mount('https://', adapter)

# 设置请求头，模拟浏览器行为
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}

# 订阅转换后端列表（优先级从高到低）
SUB_CONVERTERS = [
    'https://url.v1.mk/sub',          # 主要后端
    'https://subapi.cmliussss.net/sub',   # 备用后端1
    'https://sub.d1.mk/sub',       # 备用后端2
    'https://sub.xeton.dev/sub'# 备用后端3
]

def convert_subscription(subscription_urls):
    """使用多后端自动切换机制处理订阅链接转换"""
    # 构建转换参数（适用于所有后端）
    params = {
        'target': 'clash',          # 输出格式，这里设置为Clash配置文件格式
        'url': subscription_urls,   # 订阅链接（多个链接用|分隔）
        'insert': 'false',          # 是否插入额外内容到配置中，false表示不插入
        'config': 'https://raw.githubusercontent.com/yuanzhou029/ACL4SSR/refs/heads/rm/yz029.ini',  # ACL4SSR规则配置文件URL
        'emoji': 'true',            # 是否在节点名称中显示国旗emoji，true表示显示
        'list': 'false',            # 是否仅列出节点而不生成完整配置，false表示生成完整配置
        'xudp': 'false',            # 是否启用XTLS-UDP，false表示禁用
        'udp': 'false',             # 是否启用UDP支持，false表示禁用
        'tfo': 'false',             # 是否启用TCP Fast Open，false表示禁用
        'expand': 'true',           # 是否展开节点信息，true表示展开详细信息
        'scv': 'false',             # 是否启用服务器证书验证，false表示禁用
        'fdn': 'false',             # 是否使用完整域名，false表示不使用
        'new_name': 'true',         # 是否启用新的节点命名格式，true表示启用
        'rename': 'mibei77.com 米贝节点分享@yz'  # 节点名称前缀模板
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
            # response = requests.get(conversion_url, headers=HEADERS, timeout=TIMEOUT)
            response = SESSION.get(conversion_url, headers=HEADERS, timeout=TIMEOUT)
            response.raise_for_status()
            
            # 增强内容验证机制
            content_type = response.headers.get('Content-Type', '').lower()
            if 'text/html' in content_type or '<!doctype html>' in response.text[:100].lower():
                raise Exception(f"无效响应: HTML内容 (状态码{response.status_code})")
            
            # 验证Clash配置特征
            required_keywords = ['proxies:', 'proxy-groups:', 'rules:']
            if not all(keyword in response.text for keyword in required_keywords):
                raise Exception(f"无效Clash配置: 缺少必要字段")
            
            # 原有基础验证
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
