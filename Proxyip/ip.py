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
from pathlib import Path

# ==================== 导入共享配置 ====================
try:
    from config import (
        PROXY_PORTS,
        COUNTRY_CONFIG,
        FILTER_COUNTRIES,
        COUNTRY_CODES,
        IP_SOURCE_DIR,
        OUTPUT_DIR,
        CHECK_API,
        MAX_THREADS,
        TCP_TIMEOUT,
        API_TIMEOUT,
        ENABLE_SECOND_VERIFY,
        VERBOSE_OUTPUT
    )
    USE_CONFIG = True
except ImportError:
    print("⚠️ 未找到 config.py，使用默认配置")
    USE_CONFIG = False
    # 默认配置
    PROXY_PORTS = [443]
    COUNTRY_CONFIG = {"TW": "台湾", "JP": "日本", "HK": "香港", "SG": "新加坡"}
    FILTER_COUNTRIES = ["台湾", "日本", "香港", "新加坡"]
    COUNTRY_CODES = ["TW", "JP", "HK", "SG"]
    IP_SOURCE_DIR = "source_ips"
    OUTPUT_DIR = "valid_proxies"
    CHECK_API = "https://cf.090227.xyz/check"
    MAX_THREADS = 30
    TCP_TIMEOUT = 2
    API_TIMEOUT = 5
    ENABLE_SECOND_VERIFY = True
    VERBOSE_OUTPUT = False

# ==================== 本地配置（可覆盖共享配置） ====================

# 输入源模式：
#   "source_ips" - 从 source_ips 目录读取（download_and_extract.py 生成的文件）
#   "file" - 从本地文件读取（使用 INPUT_SOURCE 指定的文件）
#   "url" - 从远程URL读取（使用 INPUT_SOURCE 指定的URL）
#   "auto" - 自动检测：优先使用 INPUT_SOURCE 文件，如果不存在则使用 source_ips 目录   现在 auto 模式会合并两个来源的IP
INPUT_MODE = "auto"

# 输入源文件或URL（当 INPUT_MODE 为 "file"、"url" 或 "auto" 时使用）
INPUT_SOURCE = "Proxyip.txt"

# 域名输入文件
DOMAINS_SOURCE = "domains.txt"

# 临时IP文件
TEMP_IP_FILE = "temp_ips.txt"

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

def load_from_source_ips():
    """从 source_ips 目录加载IP（使用配置的端口和国家）"""
    print(f"[{get_timestamp()}] 📥 从 {IP_SOURCE_DIR} 目录加载IP...")
    
    script_dir = Path(__file__).parent
    source_dir = script_dir / IP_SOURCE_DIR
    
    if not source_dir.exists():
        print(f"[{get_timestamp()}] ❌ 错误: {IP_SOURCE_DIR} 目录不存在")
        print(f"[{get_timestamp()}] 💡 请先运行 download_and_extract.py 下载IP源数据")
        return []
    
    all_ips = set()
    files_loaded = 0
    
    # 遍历配置的国家代码文件
    for country_code in COUNTRY_CODES:
        file_path = source_dir / f"{country_code}.txt"
        if not file_path.exists():
            continue
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                for line in f:
                    ip = line.strip()
                    if ip and is_valid_ip(ip):
                        # 为每个配置的端口添加IP
                        for port in PROXY_PORTS:
                            all_ips.add(f"{ip}:{port}")
            files_loaded += 1
            country_name = COUNTRY_CONFIG.get(country_code, country_code)
            print(f"[{get_timestamp()}] 📂 已加载 {country_code} ({country_name})")
        except Exception as e:
            print(f"[{get_timestamp()}] ❌ 读取文件失败 {file_path}: {e}")
    
    unique_ips = list(all_ips)
    print(f"[{get_timestamp()}] 📊 加载文件数: {files_loaded} | 端口数: {len(PROXY_PORTS)} | 总IP数: {len(unique_ips)}")
    
    return unique_ips

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
        
        # 跳过注释行
        if item.startswith("#"):
            continue
            
        if item.startswith("http://") or item.startswith("https://"):
            urls.append(item)
        elif ":" in item:
            ip_part = item.split(":")[0]
            if is_valid_ip(ip_part):
                ips.append(item)
            else:
                # 确保不是注释或无效内容
                if not item.startswith("#") and "." in item:
                    domains.append(item)
        else:
            if is_valid_ip(item):
                ips.append(item)
            else:
                # 确保是有效域名格式
                if "." in item and not item.startswith("#"):
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
            
            if VERBOSE_OUTPUT:
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
        if VERBOSE_OUTPUT:
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
            if VERBOSE_OUTPUT:
                with print_lock:
                    print(f"[{get_timestamp()}] ✅ {ip}:{port} - 二次验证通过 | 延迟: {proxy_info['responseTime']}ms")
            return proxy_info
    except:
        pass
    
    if VERBOSE_OUTPUT:
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
    """按国家保存有效 IP（不带端口号），按延时排序"""
    # 先按延时排序（延时低的在前）
    valid_ips_sorted = sorted(valid_ips, key=lambda x: x.get("responseTime", 9999))
    
    country_groups = defaultdict(list)
    
    # 国家代码映射（中文名称 -> 国家代码）
    country_code_map = {
        "台湾": "TW", "台湾省": "TW", "中国台湾": "TW",
        "香港": "HK", "香港特别行政区": "HK", "中国香港": "HK", 
        "日本": "JP", "日本国": "JP", "日本列岛": "JP",
        "新加坡": "SG", "新加坡共和国": "SG", "狮城": "SG",
        "美国": "US", "美利坚": "US", "USA": "US",
        "韩国": "KR", "大韩民国": "KR",
        "英国": "UK", "联合王国": "UK",
        "德国": "DE", "德意志": "DE",
        "法国": "FR", "法兰西": "FR",
        "澳大利亚": "AU", "澳洲": "AU", "Australia": "AU",
        "加拿大": "CA", "Canada": "CA",
        "俄罗斯": "RU", "俄联邦": "RU",
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
        "匈牙利": "HU", "Hungary": "HU",
        "乌克兰": "UA", "Ukraine": "UA",
        "智利": "CL", "智利共和国": "CL", "Chile": "CL",
        "阿根廷": "AR", "阿根廷共和国": "AR", "Argentina": "AR",
        "新西兰": "NZ", "New Zealand": "NZ"
    }
    
    for ip_info in valid_ips_sorted:
        country = ip_info["country"]
        # 使用国家代码映射
        country_code = country_code_map.get(country, country)
        country_groups[country_code].append(ip_info)
    
    for country_code, ips in country_groups.items():
        filename = os.path.join(OUTPUT_DIR, f"{country_code}.txt")
        with open(filename, "w", encoding="utf-8") as f:
            for ip_info in ips:
                f.write(f"{ip_info['ip']}\n")
        print(f"[{get_timestamp()}] 💾 {country_code}: {len(ips)} 个 IP 已保存（按延时排序）")
    
    # 同时保存到临时文件（所有IP按延时排序）
    with open(TEMP_IP_FILE, "w", encoding="utf-8") as f:
        for ip_info in valid_ips_sorted:
            f.write(f"{ip_info['ip']}:{ip_info['port']}\n")
    print(f"[{get_timestamp()}] 💾 临时文件: {len(valid_ips_sorted)} 个 IP 已保存到 {TEMP_IP_FILE}（按延时排序）")

def display_statistics(valid_ips):
    """显示统计信息"""
    print("\n" + "=" * 60)
    print("📊 有效 IP 统计信息")
    print("=" * 60)
    print(f"总有效 IP 数量: {len(valid_ips)}")
    
    # 按国家统计
    country_stats = defaultdict(int)
    country_code_map = {
        "台湾": "TW", "台湾省": "TW", "中国台湾": "TW",
        "香港": "HK", "香港特别行政区": "HK", "中国香港": "HK", 
        "日本": "JP", "日本国": "JP", "日本列岛": "JP",
        "新加坡": "SG", "新加坡共和国": "SG", "狮城": "SG"
    }
    
    for ip_info in valid_ips:
        country = ip_info["country"]
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
    print("🚀 ProxyIP 批量检测工具 v5.0")
    print("=" * 60)
    
    # 显示配置信息
    print(f"📂 输入模式: {INPUT_MODE}")
    if INPUT_MODE == "source_ips":
        print(f"📁 IP源目录: {IP_SOURCE_DIR}")
        print(f"🔌 检测端口: {PROXY_PORTS}")
        print(f"🌍 检测国家: {', '.join([f'{k}({v})' for k, v in COUNTRY_CONFIG.items()])}")
    else:
        print(f"📂 输入源: {INPUT_SOURCE}")
        print(f"🌐 域名源: {DOMAINS_SOURCE}")
    print(f"📁 输出目录: {OUTPUT_DIR}")
    if FILTER_COUNTRIES:
        print(f"🔍 筛选国家: {', '.join(FILTER_COUNTRIES)}")
    else:
        print(f"🔍 筛选国家: 全部保留")
    print(f"⚡ 并发线程: {MAX_THREADS}")
    print(f"🔄 二次验证: {'开启' if ENABLE_SECOND_VERIFY else '关闭'}")
    print(f"📝 详细输出: {'开启' if VERBOSE_OUTPUT else '关闭'}")
    
    # ========== 阶段 1: 加载IP ==========
    if INPUT_MODE == "auto":
        # 自动模式：合并 INPUT_SOURCE 文件和 source_ips 目录的IP
        all_ips = set()
        domains = []
        
        # 1. 尝试从 INPUT_SOURCE 文件加载
        if os.path.exists(INPUT_SOURCE):
            print(f"[{get_timestamp()}] 🔄 自动模式: 检测到 {INPUT_SOURCE} 文件")
            file_ips, file_domains = load_mixed_input(INPUT_SOURCE)
            all_ips.update(file_ips)
            domains.extend(file_domains)
            print(f"[{get_timestamp()}] 📊 从文件加载: {len(file_ips)} 个IP")
        
        # 2. 尝试从 source_ips 目录加载
        script_dir = Path(__file__).parent
        source_dir = script_dir / IP_SOURCE_DIR
        if source_dir.exists():
            print(f"[{get_timestamp()}] 🔄 自动模式: 检测到 {IP_SOURCE_DIR} 目录")
            source_ips = load_from_source_ips()
            all_ips.update(source_ips)
            print(f"[{get_timestamp()}] 📊 从目录加载: {len(source_ips)} 个IP")
        
        unique_ips = list(all_ips)
        print(f"[{get_timestamp()}] 📊 合并去重后总IP数: {len(unique_ips)}")
        
    elif INPUT_MODE == "source_ips":
        unique_ips = load_from_source_ips()
        domains = []
    else:
        # file 或 url 模式
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
