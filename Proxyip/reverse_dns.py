import dns.resolver
import requests
import socket
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import defaultdict
import os

def is_cloudflare_domain(domain):
    """判断是否为Cloudflare相关域名"""
    cloudflare_patterns = [
        'cloudflaressl.com',
        'cloudflare.com',
        'cloudflare.net',
        'cloudflare-dns.com',
        'cloudflare-ipfs.com',
        'cloudflare.app',
        'trycloudflare.com'
    ]
    domain_lower = domain.lower()
    return any(pattern in domain_lower for pattern in cloudflare_patterns)

def reverse_dns_lookup(ip):
    """对IP进行反向DNS解析"""
    try:
        result = socket.gethostbyaddr(ip)
        return result[0]
    except:
        return None

def get_ip_from_domain(domain):
    """获取域名的IP地址"""
    try:
        resolver = dns.resolver.Resolver()
        resolver.timeout = 5
        resolver.lifetime = 5
        answers = resolver.resolve(domain, 'A')
        return [str(rdata) for rdata in answers]
    except:
        return []

def is_cloudflare_ip(ip):
    """检查IP是否属于Cloudflare"""
    try:
        # 获取IP的反向DNS
        hostname = reverse_dns_lookup(ip)
        if hostname and is_cloudflare_domain(hostname):
            return True
        
        # 检查常见的Cloudflare域名模式
        domain_ips = get_ip_from_domain(f"{ip.replace('.', '-')}.ip4.cf-ip.net")
        if domain_ips:
            return True
            
        return False
    except:
        return False

def process_country_file(file_path, max_ips_per_domain=30):
    """处理单个国家文件，返回CF域名统计"""
    if not os.path.exists(file_path):
        return {}
    
    with open(file_path, 'r', encoding='utf-8') as f:
        ips = [line.strip() for line in f if line.strip()]
    
    # 统计每个域名的IP数量
    domain_ip_count = defaultdict(int)
    
    for ip in ips:
        try:
            hostname = reverse_dns_lookup(ip)
            if hostname and is_cloudflare_domain(hostname):
                domain_ip_count[hostname] += 1
        except:
            continue
    
    # 限制每个域名最多30个IP，按数量排序保留前30个
    limited_domain_ip_count = {}
    for domain, count in domain_ip_count.items():
        limited_domain_ip_count[domain] = min(count, max_ips_per_domain)
    
    return dict(limited_domain_ip_count)

def get_cf_domains_stats(valid_proxies_dir='valid_proxies'):
    """获取所有国家文件的CF域名统计"""
    if not os.path.exists(valid_proxies_dir):
        return {}
    
    all_stats = {}
    total_domains = 0
    total_ips = 0
    
    for filename in os.listdir(valid_proxies_dir):
        if filename.endswith('.txt'):
            file_path = os.path.join(valid_proxies_dir, filename)
            country_stats = process_country_file(file_path)
            
            if country_stats:
                country_code = filename.replace('.txt', '')
                all_stats[country_code] = country_stats
                
                for domain, count in country_stats.items():
                    total_domains += 1
                    total_ips += count
    
    return all_stats, total_domains, total_ips

def main():
    """主函数，返回统计信息用于通知"""
    print("🔄 开始反向DNS解析...")
    
    start_time = time.time()
    stats, total_domains, total_ips = get_cf_domains_stats()
    end_time = time.time()
    
    execution_time = end_time - start_time
    
    # 生成统计报告
    report = {
        'execution_time': execution_time,
        'stats': stats,
        'total_domains': total_domains,
        'total_ips': total_ips
    }
    
    print(f"✅ 反向DNS解析完成！")
    print(f"🕐 执行时长: {execution_time:.2f}秒")
    print(f"🌍 CF域名数量: {total_domains}")
    print(f"🌐 CF域名IP总数: {total_ips}")
    
    return report

if __name__ == "__main__":
    main()
