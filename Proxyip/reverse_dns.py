import os
import requests

# ==================== 配置区 ====================

# 是否输出每个DNS记录的详细操作信息（设为False则只输出最终汇总True全部输出）
VERBOSE_OUTPUT = True

# ==================== 配置区结束 ====================

def mask_domain(domain):
    """隐藏域名敏感信息，只显示第一部分"""
    if not domain:
        return "***"
    parts = domain.split('.')
    if len(parts) > 1:
        return f"{parts[0]}.***"
    return "***"

def mask_record_name(record_name):
    """隐藏记录名中的域名部分，只显示子域名前缀"""
    if not record_name:
        return "***"
    parts = record_name.split('.')
    if len(parts) > 1:
        return f"{parts[0]}.***"
    return record_name

def delete_dns_record(cf_token, zone_id, record_id):
    """删除DNS记录"""
    url = f"https://api.cloudflare.com/client/v4/zones/{zone_id}/dns_records/{record_id}"
    headers = {
        "Authorization": f"Bearer {cf_token}",
        "Content-Type": "application/json"
    }
    
    try:
        response = requests.delete(url, headers=headers)
        return response.status_code == 200
    except:
        return False

def create_dns_record(cf_token, zone_id, name, content, record_type="A"):
    """创建DNS记录"""
    url = f"https://api.cloudflare.com/client/v4/zones/{zone_id}/dns_records"
    headers = {
        "Authorization": f"Bearer {cf_token}",
        "Content-Type": "application/json"
    }
    data = {
        "type": record_type,
        "name": name,
        "content": content,
        "ttl": 1,
        "proxied": False
    }
    
    try:
        response = requests.post(url, headers=headers, json=data)
        result = response.json()
        if result.get("success"):
            if VERBOSE_OUTPUT:
                print(f"✅ {mask_record_name(name)} -> {content}")
            return True
        else:
            errors = result.get('errors', [])
            if any('already exists' in str(e).lower() for e in errors):
                if VERBOSE_OUTPUT:
                    print(f"⚠️ 已存在: {mask_record_name(name)}")
                return True
            if VERBOSE_OUTPUT:
                print(f"❌ 失败: {mask_record_name(name)}")
            return False
    except Exception as e:
        if VERBOSE_OUTPUT:
            print(f"❌ 出错: {e}")
        return False

def delete_existing_records(cf_token, zone_id, record_name):
    """删除指定子域名的所有现有DNS记录"""
    url = f"https://api.cloudflare.com/client/v4/zones/{zone_id}/dns_records"
    headers = {
        "Authorization": f"Bearer {cf_token}",
        "Content-Type": "application/json"
    }
    params = {"name": record_name, "per_page": 100}
    
    try:
        response = requests.get(url, headers=headers, params=params)
        result = response.json()
        
        if result.get("success"):
            records = result.get("result", [])
            deleted_count = 0
            
            for record in records:
                record_id = record.get("id")
                if record_id and delete_dns_record(cf_token, zone_id, record_id):
                    deleted_count += 1
            
            if deleted_count > 0 and VERBOSE_OUTPUT:
                print(f"🗑️ 删除 {mask_record_name(record_name)} 的 {deleted_count} 条旧记录")
            return deleted_count
        return 0
    except:
        return 0

# 国家代码到中文名称的映射
COUNTRY_NAME_MAP = {
    "TW": "台湾",
    "JP": "日本",
    "HK": "香港",
    "SG": "新加坡",
    "US": "美国",
    "KR": "韩国",
    "UK": "英国",
    "DE": "德国",
    "FR": "法国",
    "AU": "澳大利亚",
    "CA": "加拿大",
    "RU": "俄罗斯",
    "IN": "印度",
    "BR": "巴西",
    "MX": "墨西哥",
    "IT": "意大利",
    "ES": "西班牙",
    "NL": "荷兰",
    "CH": "瑞士",
    "SE": "瑞典",
    "NO": "挪威",
    "DK": "丹麦",
    "FI": "芬兰",
    "PL": "波兰",
    "BE": "比利时",
    "AT": "奥地利",
    "TH": "泰国",
    "MY": "马来西亚",
    "ID": "印尼",
    "PH": "菲律宾",
    "VN": "越南",
    "AE": "阿联酋",
    "SA": "沙特",
    "TR": "土耳其",
    "ZA": "南非",
    "EG": "埃及",
    "IL": "以色列",
    "GR": "希腊",
    "PT": "葡萄牙",
    "CZ": "捷克",
    "HU": "匈牙利",
    "UA": "乌克兰",
    "CL": "智利",
    "AR": "阿根廷",
    "NZ": "新西兰",
}

def upload_ips_to_cf(input_dir, reverse_domain, cf_token, zone_id, max_ips=30):
    """将IP上传到Cloudflare DNS"""
    if not all([reverse_domain, cf_token, zone_id]):
        print("❌ 缺少必要配置（CF_API_TOKEN, CF_ZONE_ID, CF_REVERSE_DOMAIN）")
        return None
    
    if not os.path.exists(input_dir):
        print(f"❌ 目录不存在: {input_dir}")
        return None
    
    total_created = 0
    total_failed = 0
    total_deleted = 0
    processed_files = 0
    
    # 按国家统计
    country_stats = {}
    
    print(f"🔄 处理目录: {input_dir}")
    print(f"🎯 域名: {mask_domain(reverse_domain)}")
    print(f"🎯 Zone ID: {zone_id[:8]}***")
    print(f"🎯 每文件最多: {max_ips} 个IP")
    print(f"📝 详细输出: {'开启' if VERBOSE_OUTPUT else '关闭'}")
    
    for filename in os.listdir(input_dir):
        if not filename.endswith('.txt'):
            continue
            
        subdomain = filename.replace('.txt', '')
        filepath = os.path.join(input_dir, filename)
        
        with open(filepath, 'r', encoding='utf-8') as f:
            ips = [line.strip() for line in f if line.strip()][:max_ips]
        
        if not ips:
            continue
        
        if VERBOSE_OUTPUT:
            print(f"\n📂 {filename}")
        
        record_name = f"{subdomain}.{reverse_domain}"
        total_deleted += delete_existing_records(cf_token, zone_id, record_name)
        
        created = 0
        failed = 0
        for ip in ips:
            record_type = "AAAA" if ':' in ip else "A"
            if create_dns_record(cf_token, zone_id, record_name, ip, record_type):
                created += 1
            else:
                failed += 1
        
        total_created += created
        total_failed += failed
        processed_files += 1
        
        # 记录国家统计
        country_stats[subdomain] = {
            'success': created,
            'failed': failed,
            'total': len(ips)
        }
        
        if VERBOSE_OUTPUT:
            print(f"✅ {filename}: {created} 条记录")
    
    print(f"\n✅ 完成！文件: {processed_files}, 删除: {total_deleted}, 创建: {total_created}, 失败: {total_failed}")
    
    return {
        'total_created': total_created,
        'total_failed': total_failed,
        'total_deleted': total_deleted,
        'processed_files': processed_files,
        'country_stats': country_stats
    }

def main():
    print("🔄 Cloudflare DNS上传工具")
    print("=" * 40)
    
    # 从环境变量读取配置
    cf_token = os.environ.get("CF_API_TOKEN")
    zone_id = os.environ.get("CF_ZONE_ID")
    reverse_domain = os.environ.get("CF_REVERSE_DOMAIN")
    
    if not all([cf_token, zone_id, reverse_domain]):
        print("❌ 请设置环境变量:")
        print("   CF_API_TOKEN - Cloudflare API Token")
        print("   CF_ZONE_ID - Cloudflare Zone ID")
        print("   CF_REVERSE_DOMAIN - 反向DNS域名")
        return
    
    print(f"🎯 域名: {mask_domain(reverse_domain)}")
    
    result = upload_ips_to_cf(
        input_dir="valid_proxies",
        reverse_domain=reverse_domain,
        cf_token=cf_token,
        zone_id=zone_id
    )
    
    # 输出统计信息到 GitHub Actions
    if result:
        # 生成按国家分类的统计字符串（按成功数量降序排列）
        country_stats_lines = []
        sorted_countries = sorted(
            result['country_stats'].items(),
            key=lambda x: x[1]['success'],
            reverse=True
        )
        
        for country_code, stats in sorted_countries:
            country_name = COUNTRY_NAME_MAP.get(country_code, "")
            success = stats['success']
            failed = stats['failed']
            
            if country_name:
                if failed > 0:
                    country_stats_lines.append(f"{country_code}（{country_name}）: ✅{success} ❌{failed}")
                else:
                    country_stats_lines.append(f"{country_code}（{country_name}）: ✅{success}")
            else:
                if failed > 0:
                    country_stats_lines.append(f"{country_code}: ✅{success} ❌{failed}")
                else:
                    country_stats_lines.append(f"{country_code}: ✅{success}")
        
        country_stats_str = "\n".join(country_stats_lines) if country_stats_lines else "无数据"
        
        # 输出到 GitHub Actions
        github_output = os.environ.get('GITHUB_OUTPUT')
        if github_output:
            with open(github_output, 'a', encoding='utf-8') as f:
                f.write(f"cf_total_created={result['total_created']}\n")
                f.write(f"cf_total_failed={result['total_failed']}\n")
                f.write(f"cf_country_stats<<EOF\n{country_stats_str}\nEOF\n")
            print("✅ CF统计信息已写入GitHub Actions输出")
        else:
            # 本地运行时打印输出
            print(f"\n📤 GitHub Actions输出变量:")
            print(f"  cf_total_created={result['total_created']}")
            print(f"  cf_total_failed={result['total_failed']}")
            print(f"  cf_country_stats=\n{country_stats_str}")

if __name__ == "__main__":
    main()
