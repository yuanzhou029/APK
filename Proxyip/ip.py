import requests
import socket
import os
import json
import shutil
import threading
import dns.resolver
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from collections import defaultdict

# ==================== 配置区 ====================

# 输入源：可以是本地文件路径，也可以是远程 URL
# 示例：
#   INPUT_SOURCE = "Proxyip.txt"                           # 本地文件
#   INPUT_SOURCE = "https://example.com/proxy_list.txt"    # 远程 URL
INPUT_SOURCE = "Proxyip.txt"

# 域名输入文件
DOMAINS_SOURCE = "domains.txt"

# 临时IP文件
TEMP_IP_FILE = "temp_ips.txt"

# 输出目录
OUTPUT_DIR = "valid_proxies"

# 需要筛选的国家列表（留空则保留所有国家）
# 示例：FILTER_COUNTRIES = ["台湾", "日本", "美国", "新加坡"]
# 留空表示不筛选：FILTER_COUNTRIES = []
FILTER_COUNTRIES = ["台湾", "日本", "香港", "新加坡"]

# API 配置
CHECK_API = "https://cf.090227.xyz/check"

# 性能配置
MAX_THREADS = 30                  # 并发线程数
TCP_TIMEOUT = 2                   # TCP 握手超时秒数
API_TIMEOUT = 5                   # API 响应超时秒数

# 是否进行二次验证
ENABLE_SECOND_VERIFY = True

# ==================== 配置区结束 ====================

# 线程安全的锁
print_lock = threading.Lock()

def get_timestamp():
    return datetime.now().strftime("%H:%M:%S")

def dns_resolve_domain(domain):
    """DNS解析域名获取IP列表"""
    try:
        resolver = dns.resolver.Resolver()
        resolver.timeout = 5
        resolver.lifetime = 5
        answers = resolver.resolve(domain, 'A')
        ips = [str(rdata) for rdata in answers]
        print(f"[{get_timestamp()}] 🌐 {domain} -> {len(ips)} IPs")
        return ips
    except Exception as e:
        print(f"[{get_timestamp()}] ❌ DNS解析失败 {domain}: {str(e)}")
        return []

def load_domains_from_file(filename):
    """从文件加载域名列表"""
    if not os.path.exists(filename):
        return []
    
    with open(filename, "r", encoding="utf-8") as f:
        domains = [line.strip() for line in f if line.strip() and not line.strip().startswith('#')]
    return domains

def load_mixed_input(source):
    """加载混合输入（IP、域名、URL）"""
    print(f"[{get_timestamp()}] 📥 正在加载混合输入...")
    
    raw_items = []
    domain_list = []
    
    if source.startswith("http://") or source.startswith("https://"):
        # 远程 URL
        try:
            print(f"[{get_timestamp()}] 🌐 从远程 URL 获取: {source}")
            response = requests.get(source, timeout=30)
            response.raise_for_status()
            raw_items = response.text.strip().split("\n")
            print(f"[{get_timestamp()}] ✅ 远程获取成功")
        except Exception as e:
            print(f"[{get_timestamp()}] ❌ 远程获取失败: {str(e)}")
            return [], []
    else:
        # 本地文件
        if not os.path.exists(source):
            print(f"[{get_timestamp()}] ❌ 错误: 找不到文件 {source}")
            return [], []
        
        print(f"[{get_timestamp()}] 📂 从本地文件读取: {source}")
        with open(source, "r", encoding="utf-8") as f:
            raw_items = f.readlines()
    
    # 分类处理：IP、域名、URL
    ips = []
    urls = []
    domains = []
    
    for item in raw_items:
        item = item.strip()
        if not item:
            continue
            
        if item.startswith("http://") or item.startswith("https://"):
            urls.append(item)
        elif ":" in item:
            ip_part = item.split(":")[0]
            if is_valid_ip(ip_part):
                ips.append(item)
            else:
                domains.append(item)
        else:
            if is_valid_ip(item):
                ips.append(item)
            else:
                domains.append(item)
    
    # 处理URL列表
    for url in urls:
        try:
            print(f"[{get_timestamp()}] 🌐 从URL获取IP: {url}")
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            url_ips = response.text.strip().split("\n")
            for url_ip in url_ips:
                url_ip = url_ip.strip()
                if url_ip and is_valid_ip(url_ip.split(":")[0] if ":" in url_ip else url_ip):
                    ips.append(url_ip)
        except Exception as e:
            print(f"[{get_timestamp()}] ❌ URL获取失败 {url}: {str(e)}")
    
    # 从domains.txt加载额外域名
    additional_domains = load_domains_from_file(DOMAINS_SOURCE)
    domains.extend(additional_domains)
    
    # DNS解析域名
    for domain in set(domains):
        domain_ips = dns_resolve_domain(domain)
        for ip in domain_ips:
            full_ip = f"{ip}:443" if ":" not in domain else domain
            ips.append(full_ip)
    
    # 去重
    unique_ips = list(set([ip for ip in ips if ip.strip()]))
    print(f"[{get_timestamp()}] 📊 读取总数: {len(raw_items)} | 去重后IP: {len(unique_ips)} | 解析域名数: {len(set(domains))}")
    
    return unique_ips, domains

def is_valid_ip(ip_str):
    """验证IP地址格式"""
    try:
        socket.inet_aton(ip_str.split(":")[0])
        return True
    except:
        return False

def tcp_ping(ip, port=443):
    """极速预检端口是否开放"""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(TCP_TIMEOUT)
            s.connect((ip, int(port)))
            return True
    except:
        return False

def get_ip_location(ip):
    """获取 IP 地理位置信息"""
    try:
        response = requests.get(f"http://ip-api.com/json/{ip}?lang=zh-CN", timeout=API_TIMEOUT)
        response.raise_for_status()
        data = response.json()
        if data.get("status") == "success":
            return {
                "city": data.get("city") or "未知城市",
                "country": data.get("country") or "未知国家",
                "region": data.get("regionName") or "未知地区",
                "isp": data.get("isp") or "未知ISP"
            }
    except:
        pass
    return {"city": "未知城市", "country": "未知国家", "region": "未知地区", "isp": "未知ISP"}

def check_proxy(proxy_str):
    """检测单个代理 IP"""
    proxy_str = proxy_str.strip()
    if not proxy_str:
        return None

    # 格式化处理
    if ":" in proxy_str:
        ip, port = proxy_str.split(":")
    else:
        ip, port = proxy_str, "443"

    # TCP 预检
    if not tcp_ping(ip, port):
        return None

    # API 验证
    try:
        params = {"proxyip": f"{ip}:{port}"}
        response = requests.get(CHECK_API, params=params, timeout=API_TIMEOUT)
        data = response.json()

        if data.get("success"):
            colo = data.get("colo", "UNKNOWN")
            resp_time = data.get("responseTime", -1)
            
            # 获取地理位置
            location_info = get_ip_location(ip)
            country = location_info["country"]
            
            # 如果设置了国家筛选，检查是否在筛选列表中
            if FILTER_COUNTRIES:
                # 检查国家名称是否包含筛选关键词
                matched = any(fc in country for fc in FILTER_COUNTRIES)
                if not matched:
                    return None
            
            result = {
                "ip": ip,
                "port": port,
                "colo": colo,
                "responseTime": resp_time,
                "city": location_info["city"],
                "country": country,
                "region": location_info["region"],
                "isp": location_info["isp"]
            }
            
            with print_lock:
                print(f"[{get_timestamp()}] ✅ {ip}:{port} | {country} - {location_info['city']} ({colo}) | 延迟: {resp_time}ms")
            
            return result
    except Exception as e:
        pass
    
    return None

def verify_proxy(proxy_info):
    """二次验证"""
    ip = proxy_info["ip"]
    port = proxy_info["port"]
    
    # TCP 预检
    if not tcp_ping(ip, port):
        with print_lock:
            print(f"[{get_timestamp()}] ❌ {ip}:{port} - 二次验证失败")
        return None

    # API 验证
    try:
        params = {"proxyip": f"{ip}:{port}"}
        response = requests.get(CHECK_API, params=params, timeout=API_TIMEOUT)
        data = response.json()

        if data.get("success"):
            proxy_info["responseTime"] = data.get("responseTime", proxy_info["responseTime"])
            with print_lock:
                print(f"[{get_timestamp()}] ✅ {ip}:{port} - 二次验证通过 | 延迟: {proxy_info['responseTime']}ms")
            return proxy_info
    except:
        pass
    
    with print_lock:
        print(f"[{get_timestamp()}] ❌ {ip}:{port} - 二次验证失败")
    return None

def clear_output_dir():
    """清空输出目录"""
    if os.path.exists(OUTPUT_DIR):
        shutil.rmtree(OUTPUT_DIR)
        print(f"[{get_timestamp()}] 🗑️  已清空 {OUTPUT_DIR} 目录")
    os.makedirs(OUTPUT_DIR)

def save_by_country(valid_ips):
    """按国家保存有效 IP（不带端口号）"""
    country_groups = defaultdict(list)
    
    # 国家代码映射
    country_code_map = {
        "台湾": "TW", "台湾省": "TW", "中国台湾": "TW",
        "香港": "HK", "香港特别行政区": "HK", "中国香港": "HK", 
        "日本": "JP", "日本国": "JP", "日本列岛": "JP",
        "新加坡": "SG", "新加坡共和国": "SG", "狮城": "SG",
        "美国": "US", "美利坚": "US", "USA": "US",
        "韩国": "KR", "大韩民国": "KR", "韩国": "KR",
        "英国": "UK", "联合王国": "UK", "英国": "UK",
        "德国": "DE", "德意志": "DE", "德国": "DE",
        "法国": "FR", "法兰西": "FR", "法国": "FR",
        "澳大利亚": "AU", "澳洲": "AU", "Australia": "AU",
        "加拿大": "CA", "Canada": "CA", "加拿大": "CA",
        "俄罗斯": "RU", "俄联邦": "RU", "俄罗斯": "RU",
        "印度": "IN", "印度共和国": "IN", "India": "IN",
        "巴西": "BR", "巴西联邦共和国": "BR", "Brazil": "BR",
        "墨西哥": "MX", "墨西哥合众国": "MX", "Mexico": "MX",
        "意大利": "IT", "意大利共和国": "IT", "Italy": "IT",
        "西班牙": "ES", "西班牙王国": "ES", "Spain": "ES",
        "荷兰": "NL", "荷兰王国": "NL", "Netherlands": "NL",
        "瑞士": "CH", "瑞士联邦": "CH", "Switzerland": "CH",
        "瑞典": "SE", "瑞典王国": "SE", "Sweden": "SE",
        "挪威": "NO", "挪威王国": "NO", "Norway": "NO",
        "丹麦": "DK", "丹麦王国": "DK", "Denmark": "DK",
        "芬兰": "FI", "芬兰共和国": "FI", "Finland": "FI",
        "波兰": "PL", "波兰共和国": "PL", "Poland": "PL",
        "比利时": "BE", "比利时王国": "BE", "Belgium": "BE",
        "奥地利": "AT", "奥地利共和国": "AT", "Austria": "AT",
        "泰国": "TH", "泰王国": "TH", "Thailand": "TH",
        "马来西亚": "MY", "马来西亚联邦": "MY", "Malaysia": "MY",
        "印度尼西亚": "ID", "印尼": "ID", "Indonesia": "ID",
        "菲律宾": "PH", "菲律宾共和国": "PH", "Philippines": "PH",
        "越南": "VN", "越南社会主义共和国": "VN", "Vietnam": "VN",
        "阿联酋": "AE", "阿拉伯联合酋长国": "AE", "UAE": "AE",
        "沙特阿拉伯": "SA", "沙特": "SA", "Saudi Arabia": "SA",
        "土耳其": "TR", "土耳其共和国": "TR", "Turkey": "TR",
        "南非": "ZA", "南非共和国": "ZA", "South Africa": "ZA",
        "埃及": "EG", "阿拉伯埃及共和国": "EG", "Egypt": "EG",
        "以色列": "IL", "以色列国": "IL", "Israel": "IL",
        "希腊": "GR", "希腊共和国": "GR", "Greece": "GR",
        "葡萄牙": "PT", "葡萄牙共和国": "PT", "Portugal": "PT",
        "捷克": "CZ", "捷克共和国": "CZ", "Czech Republic": "CZ",
        "匈牙利": "HU", "匈牙利": "HU", "Hungary": "HU",
        "乌克兰": "UA", "乌克兰": "UA", "Ukraine": "UA",
        "智利": "CL", "智利共和国": "CL", "Chile": "CL",
        "阿根廷": "AR", "阿根廷共和国": "AR", "Argentina": "AR",
        "新西兰": "NZ", "新西兰": "NZ", "New Zealand": "NZ"
    }
    
    for ip_info in valid_ips:
        country = ip_info["country"]
        # 使用国家代码映射
        country_code = country_code_map.get(country, country)
        country_groups[country_code].append(ip_info)
    
    for country_code, ips in country_groups.items():
        filename = os.path.join(OUTPUT_DIR, f"{country_code}.txt")
        with open(filename, "w", encoding="utf-8") as f:
            for ip_info in ips:
                f.write(f"{ip_info['ip']}\n")
        print(f"[{get_timestamp()}] 💾 {country_code}: {len(ips)} 个 IP 已保存")

def display_statistics(valid_ips):
    """显示统计信息"""
    print("\n" + "=" * 60)
    print("📊 有效 IP 统计信息")
    print("=" * 60)
    print(f"总有效 IP 数量: {len(valid_ips)}")
    
    # 按国家统计
    country_stats = defaultdict(int)
    for ip_info in valid_ips:
        country = ip_info["country"]
        country_code_map = {
            "台湾": "TW", "台湾省": "TW", "中国台湾": "TW",
            "香港": "HK", "香港特别行政区": "HK", "中国香港": "HK", 
            "日本": "JP", "日本国": "JP", "日本列岛": "JP",
            "新加坡": "SG", "新加坡共和国": "SG", "狮城": "SG"
        }
        country_code = country_code_map.get(country, country)
        country_stats[country_code] += 1
    
    print("\n🌍 按国家分布:")
    for country, count in sorted(country_stats.items(), key=lambda x: -x[1]):
        print(f"   {country}: {count} 个")
    
    # 延迟统计
    response_times = [ip["responseTime"] for ip in valid_ips if ip["responseTime"] > 0]
    if response_times:
        print(f"\n⏱️  延迟统计:")
        print(f"   最小: {min(response_times)}ms")
        print(f"   最大: {max(response_times)}ms")
        print(f"   平均: {sum(response_times) // len(response_times)}ms")
    
    print("=" * 60)

def main():
    print("=" * 60)
    print("🚀 ProxyIP 批量检测工具 v4.0")
    print("=" * 60)
    
    # 显示配置信息
    print(f"📂 输入源: {INPUT_SOURCE}")
    print(f"🌐 域名源: {DOMAINS_SOURCE}")
    print(f"📁 输出目录: {OUTPUT_DIR}")
    if FILTER_COUNTRIES:
        print(f"🔍 筛选国家: {', '.join(FILTER_COUNTRIES)}")
    else:
        print(f"🔍 筛选国家: 全部保留")
    print(f"⚡ 并发线程: {MAX_THREADS}")
    print(f"🔄 二次验证: {'开启' if ENABLE_SECOND_VERIFY else '关闭'}")
    
    # ========== 阶段 1: 加载混合输入（IP、域名、URL） ==========
    unique_ips, domains = load_mixed_input(INPUT_SOURCE)
    if not unique_ips:
        print("❌ 未加载到任何 IP，任务结束。")
        return
    
    # ========== 阶段 2: 批量检测 ==========
    print("\n" + "=" * 60)
    print("🔍 阶段 1: 批量检测")
    print("=" * 60)
    
    valid_ips = []
    with ThreadPoolExecutor(max_workers=MAX_THREADS) as executor:
        futures = {executor.submit(check_proxy, ip): ip for ip in unique_ips}
        for future in as_completed(futures):
            result = future.result()
            if result:
                valid_ips.append(result)
    
    print(f"\n✅ 阶段 1 完成！共发现 {len(valid_ips)} 个有效 IP")
    
    if not valid_ips:
        print("❌ 未发现任何有效 IP，任务结束。")
        return
    
    # ========== 阶段 3: 二次验证（可选）==========
    if ENABLE_SECOND_VERIFY:
        print("\n" + "=" * 60)
        print("🔄 阶段 2: 二次验证")
        print("=" * 60)
        
        verified_ips = []
        with ThreadPoolExecutor(max_workers=MAX_THREADS) as executor:
            futures = {executor.submit(verify_proxy, ip): ip for ip in valid_ips}
            for future in as_completed(futures):
                result = future.result()
                if result:
                    verified_ips.append(result)
        
        print(f"\n✅ 阶段 2 完成！二次验证通过: {len(verified_ips)} 个 IP")
        valid_ips = verified_ips
    
    if not valid_ips:
        print("❌ 二次验证后无有效 IP，任务结束。")
        return
    
    # ========== 阶段 4: 统计与保存 ==========
    display_statistics(valid_ips)
    
    print("\n" + "=" * 60)
    print("💾 阶段 3: 保存结果")
    print("=" * 60)
    
    clear_output_dir()
    save_by_country(valid_ips)
    
    print("\n" + "=" * 60)
    print(f"🎉 任务完成！最终有效 IP: {len(valid_ips)} 个")
    print(f"📁 结果已保存至: {OUTPUT_DIR}/")
    print("=" * 60)

if __name__ == "__main__":
    main()
