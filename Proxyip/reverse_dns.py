import os
import json
import requests
from pathlib import Path

# ==================== 配置区 ====================

# 是否输出每个DNS记录的详细操作信息（设为False则只输出最终汇总）
VERBOSE_OUTPUT = True

# 默认反向DNS域名（留空，必须通过环境变量 CF_REVERSE_DOMAIN 或配置文件设置）
DEFAULT_REVERSE_DOMAIN = ""

# ==================== 配置区结束 ====================

def mask_domain(domain):
    """隐藏域名敏感信息，只显示子域名前缀"""
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

def load_config():
    """从配置文件加载配置"""
    config_file = "example_config.json"
    if os.path.exists(config_file):
        with open(config_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    return None

def get_zone_id(cf_token, domain):
    """获取域名的Zone ID"""
    url = "https://api.cloudflare.com/client/v4/zones"
    headers = {
        "Authorization": f"Bearer {cf_token}",
        "Content-Type": "application/json"
    }
    params = {"name": domain}
    
    try:
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()
        result = response.json()
        if result.get("success") and result.get("result"):
            return result["result"][0]["id"]
        return None
    except Exception as e:
        print(f"❌ 获取Zone ID失败: {e}")
        return None

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

def get_existing_records(cf_token, zone_id, name_pattern=None):
    """获取现有的DNS记录"""
    url = f"https://api.cloudflare.com/client/v4/zones/{zone_id}/dns_records"
    headers = {
        "Authorization": f"Bearer {cf_token}",
        "Content-Type": "application/json"
    }
    params = {"per_page": 100}
    if name_pattern:
        params["name"] = name_pattern
    
    try:
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()
        result = response.json()
        if result.get("success"):
            return result.get("result", [])
        return []
    except Exception as e:
        print(f"❌ 获取DNS记录失败: {e}")
        return []

def create_dns_record(cf_token, zone_id, name, content, record_type="A", ttl=1, proxied=False):
    """
    通过Cloudflare API创建DNS记录
    """
    url = f"https://api.cloudflare.com/client/v4/zones/{zone_id}/dns_records"
    headers = {
        "Authorization": f"Bearer {cf_token}",
        "Content-Type": "application/json"
    }
    data = {
        "type": record_type,
        "name": name,
        "content": content,
        "ttl": ttl,
        "proxied": proxied
    }
    
    try:
        response = requests.post(url, headers=headers, json=data)
        result = response.json()
        if result.get("success"):
            if VERBOSE_OUTPUT:
                print(f"✅ DNS记录创建成功: {mask_record_name(name)} -> {content}")
            return True
        else:
            errors = result.get('errors', [])
            # 如果记录已存在，尝试更新
            if any('already exists' in str(e).lower() for e in errors):
                if VERBOSE_OUTPUT:
                    print(f"⚠️ 记录已存在，跳过: {mask_record_name(name)}")
                return True
            if VERBOSE_OUTPUT:
                print(f"❌ DNS记录创建失败: {mask_record_name(name)}")
            return False
    except Exception as e:
        if VERBOSE_OUTPUT:
            print(f"❌ 创建DNS记录时出错: {e}")
        return False

def delete_existing_records_for_subdomain(cf_token, zone_id, subdomain_name, reverse_domain):
    """
    删除指定子域名的所有现有DNS记录
    
    Args:
        cf_token: Cloudflare API token
        zone_id: Cloudflare Zone ID
        subdomain_name: 子域名前缀（如：日本）
        reverse_domain: 反向DNS根域名
    """
    record_name = f"{subdomain_name}.{reverse_domain}"
    
    # 获取该子域名的所有记录
    url = f"https://api.cloudflare.com/client/v4/zones/{zone_id}/dns_records"
    headers = {
        "Authorization": f"Bearer {cf_token}",
        "Content-Type": "application/json"
    }
    params = {"name": record_name, "per_page": 100}
    
    try:
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()
        result = response.json()
        
        if result.get("success"):
            records = result.get("result", [])
            deleted_count = 0
            
            for record in records:
                record_id = record.get("id")
                if record_id:
                    if delete_dns_record(cf_token, zone_id, record_id):
                        deleted_count += 1
            
            if deleted_count > 0 and VERBOSE_OUTPUT:
                print(f"🗑️ 已删除 {mask_record_name(record_name)} 的 {deleted_count} 条旧记录")
            return deleted_count
        return 0
    except Exception as e:
        if VERBOSE_OUTPUT:
            print(f"⚠️ 删除旧记录时出错: {e}")
        return 0

def upload_ips_to_cf(input_dir="valid_proxies", reverse_domain=None, cf_token=None, zone_id=None, max_ips_per_file=30):
    """
    将valid_proxies目录下的txt文件中的IP上传到Cloudflare的反向DNS域名下
    使用文件名作为子域名前缀
    
    例如：
    - 日本.txt 中的IP 192.168.1.1 -> 日本.{反向DNS域名} 指向 192.168.1.1
    
    Args:
        input_dir: 输入目录，包含以国家代码命名的txt文件
        reverse_domain: 反向DNS根域名（必须通过环境变量或配置文件提供）
        cf_token: Cloudflare API token
        zone_id: Cloudflare Zone ID
        max_ips_per_file: 每个文件最多解析的IP数量（默认30）
    """
    if not reverse_domain:
        print("❌ 请提供反向DNS域名（通过环境变量 CF_REVERSE_DOMAIN 或配置文件）")
        return False
    
    if not cf_token:
        print("❌ 请提供有效的Cloudflare API token")
        return False
    
    if not os.path.exists(input_dir):
        print(f"❌ 输入目录 {input_dir} 不存在")
        return False
    
    # 如果没有提供zone_id，尝试获取
    if not zone_id:
        # 从反向域名中提取根域名
        root_domain = reverse_domain
        zone_id = get_zone_id(cf_token, root_domain)
        if not zone_id:
            print("❌ 无法自动获取Zone ID，请手动提供")
            return False
        print(f"🎯 自动获取Zone ID: {zone_id}")
    
    total_records_created = 0
    total_records_deleted = 0
    processed_files = 0
    
    print(f"🔄 开始处理 {input_dir} 目录下的文件...")
    print(f"🎯 反向DNS域名: {mask_domain(reverse_domain)}")
    print(f"🎯 Cloudflare Zone ID: {zone_id[:8]}***" if zone_id and len(zone_id) > 8 else "***")
    print(f"🎯 每个文件最多解析: {max_ips_per_file} 个IP")
    print(f"📝 详细输出: {'开启' if VERBOSE_OUTPUT else '关闭'}")
    
    for filename in os.listdir(input_dir):
        if filename.endswith('.txt'):
            # 获取文件名（不含扩展名）作为子域名前缀
            subdomain_prefix = filename.replace('.txt', '')
            
            input_file_path = os.path.join(input_dir, filename)
            
            # 读取文件中的IP列表
            with open(input_file_path, 'r', encoding='utf-8') as f:
                lines = [line.strip() for line in f if line.strip()]
            
            # 先删除该子域名的所有旧记录
            if VERBOSE_OUTPUT:
                print(f"\n📂 处理文件: {filename}")
            deleted = delete_existing_records_for_subdomain(cf_token, zone_id, subdomain_prefix, reverse_domain)
            total_records_deleted += deleted
            
            # 限制IP数量为最多max_ips_per_file个
            ips_to_process = []
            for line in lines:
                if line and ('.' in line or ':' in line):  # 检查是否为IP地址
                    ips_to_process.append(line)
                    if len(ips_to_process) >= max_ips_per_file:
                        break
            
            if len(lines) > max_ips_per_file and VERBOSE_OUTPUT:
                print(f"⚠️ 文件包含 {len(lines)} 个IP，只处理前 {max_ips_per_file} 个")
            
            # 为每个IP创建DNS记录
            records_created = 0
            for ip in ips_to_process:
                try:
                    # 确定IP类型
                    if ':' in ip:  # IPv6
                        record_type = "AAAA"
                    else:  # IPv4
                        record_type = "A"
                    
                    # 生成子域名: 文件名.主域名
                    record_name = f"{subdomain_prefix}.{reverse_domain}"
                    
                    # 创建DNS记录
                    if create_dns_record(cf_token, zone_id, record_name, ip, record_type, 1, False):
                        records_created += 1
                        total_records_created += 1
                        
                except Exception as e:
                    print(f"⚠️ 处理IP {ip} 时出错: {e}")
                    continue
            
            if VERBOSE_OUTPUT:
                print(f"✅ {filename}: 成功创建 {records_created} 个DNS记录")
            processed_files += 1
    
    print(f"\n✅ DNS记录上传完成！")
    print(f"🌍 总共处理文件: {processed_files}")
    print(f"🗑️ 总共删除旧记录: {total_records_deleted}")
    print(f"🔗 总共创建新记录: {total_records_created}")
    return True

def main():
    """主函数"""
    print("🔄 Cloudflare DNS记录上传工具")
    print("=" * 50)
    print("功能: 将valid_proxies目录下的txt文件中的IP解析到CF上")
    print("子域名格式: {文件名}.{反向DNS域名}")
    print("=" * 50)
    
    # 从配置文件读取配置
    config = load_config()
    
    cf_token = None
    zone_id = None
    reverse_domain = DEFAULT_REVERSE_DOMAIN
    
    # 从环境变量读取（用于GitHub Actions）
    cf_token = os.environ.get("CF_API_TOKEN")
    zone_id = os.environ.get("CF_ZONE_ID")
    reverse_domain_env = os.environ.get("CF_REVERSE_DOMAIN")
    if reverse_domain_env:
        reverse_domain = reverse_domain_env
    
    # 如果环境变量没有，从配置文件读取
    if not cf_token and config and "cloudflare" in config:
        cf_token = config["cloudflare"].get("api_token")
        zone_id = config["cloudflare"].get("zone_id")
        print("🎯 从配置文件读取Cloudflare配置")
    
    if config and "reverse_dns" in config:
        reverse_domain = config["reverse_dns"].get("reverse_domain", reverse_domain)
    
    # 如果还是没有，提示用户输入
    if not cf_token:
        print("🎯 请提供Cloudflare配置信息:")
        cf_token = input("请输入Cloudflare API Token: ").strip()
    
    if not zone_id:
        zone_id = input("请输入Cloudflare Zone ID (可选，直接回车自动获取): ").strip()
        if not zone_id:
            zone_id = None
    
    if not cf_token:
        print("❌ 请提供Cloudflare API Token")
        return
    
    print(f"\n🎯 反向DNS域名: {mask_domain(reverse_domain)}")
    
    success = upload_ips_to_cf(
        input_dir="valid_proxies",
        reverse_domain=reverse_domain,
        cf_token=cf_token,
        zone_id=zone_id
    )
    
    if success:
        print("\n🎉 DNS记录上传完成！")
    else:
        print("\n❌ DNS记录上传失败，请检查配置信息。")

if __name__ == "__main__":
    main()
