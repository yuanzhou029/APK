import os
import time
import sys
from reverse_dns import get_cf_domains_stats

def count_ips_by_country():
    """统计各地区IP数量"""
    country_counts = {}
    valid_proxies_dir = 'valid_proxies'
    
    if os.path.exists(valid_proxies_dir):
        for filename in os.listdir(valid_proxies_dir):
            if filename.endswith('.txt'):
                filepath = os.path.join(valid_proxies_dir, filename)
                with open(filepath, 'r', encoding='utf-8') as f:
                    lines = [line.strip() for line in f if line.strip()]
                    country_code = filename.replace('.txt', '')
                    country_counts[country_code.lower()] = len(lines)
    
    return country_counts

def main():
    start_time = time.time()
    stats, total_domains, total_ips = get_cf_domains_stats()
    execution_time = time.time() - start_time

    # 统计各地区IP数量
    country_counts = count_ips_by_country()
    
    # 保存统计信息到环境变量
    print(f'::set-output name=execution_time::{round(execution_time, 2)}')
    print(f'::set-output name=total_domains::{total_domains}')
    print(f'::set-output name=total_ips::{total_ips}')
    
    # 输出各地区IP数量
    print(f'::set-output name=tw_count::{country_counts.get("tw", 0)}')
    print(f'::set-output name=hk_count::{country_counts.get("hk", 0)}')
    print(f'::set-output name=jp_count::{country_counts.get("jp", 0)}')
    print(f'::set-output name=sg_count::{country_counts.get("sg", 0)}')

    # 生成详细报告
    report_lines = []
    for country, country_stats in stats.items():
        for domain, count in country_stats.items():
            report_lines.append(f'{domain}: {count} IPs')
            
    if report_lines:
        report = '\\n'.join(report_lines[:10])  # 只显示前10个
        print(f'::set-output name=report::{report}')
    else:
        print(f'::set-output name=report::无CF域名解析结果')

if __name__ == "__main__":
    main()
