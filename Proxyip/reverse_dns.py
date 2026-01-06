import os
import requests

# ==================== 配置区 ====================

# 是否输出每个DNS记录的详细操作信息（设为False则只输出最终汇总True全部输出）
VERBOSE_OUTPUT = False

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

def upload_ips_to_cf(input_dir, reverse_domain, cf_token, zone_id, max_ips=30):
    """将IP上传到Cloudflare DNS"""
    if not all([reverse_domain, cf_token, zone_id]):
        print("❌ 缺少必要配置（CF_API_TOKEN, CF_ZONE_ID, CF_REVERSE_DOMAIN）")
        return False
    
    if not os.path.exists(input_dir):
        print(f"❌ 目录不存在: {input_dir}")
        return False
    
    total_created = 0
    total_deleted = 0
    processed_files = 0
    
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
        for ip in ips:
            record_type = "AAAA" if ':' in ip else "A"
            if create_dns_record(cf_token, zone_id, record_name, ip, record_type):
                created += 1
        
        total_created += created
        processed_files += 1
        
        if VERBOSE_OUTPUT:
            print(f"✅ {filename}: {created} 条记录")
    
    print(f"\n✅ 完成！文件: {processed_files}, 删除: {total_deleted}, 创建: {total_created}")
    return True

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
    
    upload_ips_to_cf(
        input_dir="valid_proxies",
        reverse_domain=reverse_domain,
        cf_token=cf_token,
        zone_id=zone_id
    )

if __name__ == "__main__":
    main()
