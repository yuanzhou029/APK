import os
import json
import requests
from pathlib import Path

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
            print(f"✅ DNS记录创建成功: {name} -> {content}")
            return True
        else:
            errors = result.get('errors', [])
            # 如果记录已存在，尝试更新
            if any('already exists' in str(e).lower() for e in errors):
                print(f"⚠️ 记录已存在，跳过: {name}")
                return True
            print(f"❌ DNS记录创建失败: {errors}")
            return False
    except Exception as e:
        print(f"❌ 创建DNS记录时出错: {e}")
        return False

def upload_ips_to_cf(input_dir="valid_proxies", reverse_domain="5.a.9.f.0.7.4.0.1.0.0.2.ip6.arpa", cf_token=None, zone_id=None):
    """
    将valid_proxies目录下的txt文件中的IP上传到Cloudflare的反向DNS域名下
    使用文件名作为子域名前缀
    
    例如：
    - 日本.txt 中的IP 192.168.1.1 -> 日本.5.a.9.f.0.7.4.0.1.0.0.2.ip6.arpa 指向 192.168.1.1
    
    Args:
        input_dir: 输入目录，包含以国家代码命名的txt文件
        reverse_domain: 反向DNS根域名
        cf_token: Cloudflare API token
        zone_id: Cloudflare Zone ID
    """
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
            print(f"❌ 无法获取域名 {root_domain} 的Zone ID，请手动提供")
            return False
        print(f"🎯 自动获取Zone ID: {zone_id}")
    
    total_records_created = 0
    processed_files = 0
    
    print(f"🔄 开始处理 {input_dir} 目录下的文件...")
    print(f"🎯 反向DNS域名: {reverse_domain}")
    print(f"🎯 Cloudflare Zone ID: {zone_id}")
    
    for filename in os.listdir(input_dir):
        if filename.endswith('.txt'):
            # 获取文件名（不含扩展名）作为子域名前缀
            subdomain_prefix = filename.replace('.txt', '')
            
            input_file_path = os.path.join(input_dir, filename)
            
            # 读取文件中的IP列表
            with open(input_file_path, 'r', encoding='utf-8') as f:
                lines = [line.strip() for line in f if line.strip()]
            
            # 为每个IP创建DNS记录
            records_created = 0
            for ip in lines:
                if ip and ('.' in ip or ':' in ip):  # 检查是否为IP地址
                    try:
                        # 确定IP类型
                        if ':' in ip:  # IPv6
                            record_type = "AAAA"
                        else:  # IPv4
                            record_type = "A"
                        
                        # 生成子域名: 文件名.主域名
                        # 例如: 日本.5.a.9.f.0.7.4.0.1.0.0.2.ip6.arpa
                        record_name = f"{subdomain_prefix}.{reverse_domain}"
                        
                        # 创建DNS记录
                        if create_dns_record(cf_token, zone_id, record_name, ip, record_type, 1, False):
                            records_created += 1
                            total_records_created += 1
                            
                    except Exception as e:
                        print(f"⚠️ 处理IP {ip} 时出错: {e}")
                        continue
            
            print(f"✅ {filename}: 成功创建 {records_created} 个DNS记录")
            processed_files += 1
    
    print(f"\n✅ DNS记录上传完成！")
    print(f"🌍 总共处理文件: {processed_files}")
    print(f"🔗 总共创建记录: {total_records_created}")
    return True

def main():
    """主函数"""
    print("🔄 Cloudflare DNS记录上传工具")
    print("=" * 50)
    print("功能: 将valid_proxies目录下的txt文件中的IP解析到CF上")
    print("子域名格式: {文件名}.5.a.9.f.0.7.4.0.1.0.0.2.ip6.arpa")
    print("=" * 50)
    
    # 从配置文件读取配置
    config = load_config()
    
    cf_token = None
    zone_id = None
    reverse_domain = "5.a.9.f.0.7.4.0.1.0.0.2.ip6.arpa"
    
    # 从环境变量读取（用于GitHub Actions）
    cf_token = os.environ.get("CF_API_TOKEN")
    zone_id = os.environ.get("CF_ZONE_ID")
    
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
    
    print(f"\n🎯 反向DNS域名: {reverse_domain}")
    
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
