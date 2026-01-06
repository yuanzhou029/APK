import os
import json
from datetime import datetime
import time

def get_proxy_stats():
    """获取代理检测统计信息"""
    stats = {
        'total_valid_proxies': 0,
        'countries': {},
        'subdomain_stats': {
            'total_files': 0,
            'total_subdomains': 0,
            'countries': {}
        },
        'execution_time': 0,
        'timestamp': datetime.now().isoformat()
    }
    
    # 统计valid_proxies目录下的代理数量
    valid_proxies_dir = 'valid_proxies'
    if os.path.exists(valid_proxies_dir):
        for filename in os.listdir(valid_proxies_dir):
            if filename.endswith('.txt'):
                file_path = os.path.join(valid_proxies_dir, filename)
                country_code = filename.replace('.txt', '')
                
                with open(file_path, 'r', encoding='utf-8') as f:
                    ips = [line.strip() for line in f if line.strip()]
                    count = len(ips)
                    stats['countries'][country_code] = count
                    stats['total_valid_proxies'] += count
    
    # 统计subdomain_domains目录下的子域名数量
    subdomain_dir = 'subdomain_domains'
    if os.path.exists(subdomain_dir):
        for filename in os.listdir(subdomain_dir):
            if filename.endswith('.txt'):
                file_path = os.path.join(subdomain_dir, filename)
                country_code = filename.replace('.txt', '')
                
                with open(file_path, 'r', encoding='utf-8') as f:
                    subdomains = [line.strip() for line in f if line.strip()]
                    count = len(subdomains)
                    stats['subdomain_stats']['countries'][country_code] = count
                    stats['subdomain_stats']['total_subdomains'] += count
                
                stats['subdomain_stats']['total_files'] += 1
    
    return stats

def print_stats(stats):
    """打印统计信息"""
    print("📊 代理检测统计报告")
    print("=" * 50)
    print(f"时间戳: {stats['timestamp']}")
    print(f"总有效代理数: {stats['total_valid_proxies']}")
    print(f"国家数量: {len(stats['countries'])}")
    
    print("\n各国家代理数量:")
    for country, count in sorted(stats['countries'].items()):
        print(f"  {country}: {count}")
    
    print(f"\n子域名统计:")
    print(f"  总文件数: {stats['subdomain_stats']['total_files']}")
    print(f"  总子域名数: {stats['subdomain_stats']['total_subdomains']}")
    
    print("\n各国家子域名数量:")
    for country, count in sorted(stats['subdomain_stats']['countries'].items()):
        print(f"  {country}: {count}")

def main():
    """主函数"""
    start_time = time.time()
    stats = get_proxy_stats()
    end_time = time.time()
    stats['execution_time'] = end_time - start_time
    
    print_stats(stats)
    
    # 生成按国家分类的统计字符串
    country_stats_lines = []
    for country, count in sorted(stats['countries'].items()):
        country_stats_lines.append(f"{country}: {count}")
    country_stats_str = "\n".join(country_stats_lines) if country_stats_lines else "无数据"
    
    # 将统计信息输出到GitHub Actions环境文件（新方式）
    github_output = os.environ.get('GITHUB_OUTPUT')
    if github_output:
        with open(github_output, 'a', encoding='utf-8') as f:
            f.write(f"RUN_TIME={stats['execution_time']:.2f}\n")
            f.write(f"total_proxies={stats['total_valid_proxies']}\n")
            f.write(f"total_countries={len(stats['countries'])}\n")
            # 使用 EOF 分隔符处理多行输出
            f.write(f"country_stats<<EOF\n{country_stats_str}\nEOF\n")
        print("✅ 统计信息已写入GitHub Actions输出")
    else:
        # 本地运行时打印输出
        print(f"\n📤 GitHub Actions输出变量:")
        print(f"  RUN_TIME={stats['execution_time']:.2f}")
        print(f"  total_proxies={stats['total_valid_proxies']}")
        print(f"  total_countries={len(stats['countries'])}")
        print(f"  country_stats=\n{country_stats_str}")
    
    # 保存统计信息到JSON文件
    with open('stats.json', 'w', encoding='utf-8') as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    main()
