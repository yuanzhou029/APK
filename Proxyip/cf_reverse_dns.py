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

def ip_to_reverse_format(ip):
    """将IPv6地址转换为反向DNS格式"""
    # 移除IPv6中的冒号并转换为小写
    ip_hex = ip.replace(':', '').lower()
    # 将每个字符用点分隔并反转
    reversed_ip = '.'.join(reversed(ip_hex))
    return reversed_ip

def ipv4_to_reverse_format(ip):
    """将IPv4地址转换为反向DNS格式 (in-addr.arpa)"""
    parts = ip.split('.')
    reversed_ip = '.'.join(reversed(parts))
    return reversed_ip

def create_dns_record(cf_token, zone_id, name, content, record_type="A", ttl=1):
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
        "proxied": False
    }
    
    try:
        response = requests.post(url, headers=headers, json=data)
        response.raise_for_status()
        result = response.json()
        if result.get("success"):
            print(f"✅ DNS记录创建成功: {name} -> {content}")
            return True
        else:
            print(f"❌ DNS记录创建失败: {result.get('errors', 'Unknown error')}")
            return False
    except Exception as e:
        print(f"❌ 创建DNS记录时出错: {e}")
        return False

def upload_ips_to_cf_reverse_dns(input_dir="valid_proxies", reverse_domain="5.a.9.f.0.7.4.0.1.0.0.2.ip6.arpa", cf_token=None, zone_id=None):
    """
    将valid_proxies目录下的txt文件中的IP上传到Cloudflare的反向DNS域名下
    使用文件名作为子域名
    
    Args:
        input_dir: 输入目录，包含以国家代码命名的txt文件
        reverse_domain: 反向DNS根域名
        cf_token: Cloudflare API token
        zone_id: Cloudflare Zone ID
    """
    if not cf_token or not zone_id:
        print("❌ 请提供有效的Cloudflare API token和Zone ID")
        return False
    
    if not os.path.exists(input_dir):
        print(f"❌ 输入目录 {input_dir} 不存在")
        return False
    
    total_records_created = 0
    processed_files = 0
    
    print(f"🔄 开始处理 {input_dir} 目录下的文件...")
    print(f"🎯 反向DNS域名: {reverse_domain}")
    print(f"🎯 Cloudflare Zone ID: {zone_id}")
    
    for filename in os.listdir(input_dir):
        if filename.endswith('.txt'):
            # 获取文件名（不含扩展名）作为子域名
            subdomain_name = filename.replace('.txt', '')
            
            input_file_path = os.path.join(input_dir, filename)
            
            # 读取文件中的IP列表
            with open(input_file_path, 'r', encoding='utf-8') as f:
                lines = [line.strip() for line in f if line.strip()]
            
            # 为每个IP创建DNS记录
            records_created = 0
            for line in lines:
                if line and (':' in line or '.' in line):  # 检查是否为IP地址
                    try:
                        # 确定IP类型并转换为反向格式
                        if ':' in line:  # IPv6
                            reversed_ip = ip_to_reverse_format(line)
                            record_type = "AAAA"
                        else:  # IPv4
                            reversed_ip = ipv4_to_reverse_format(line)
                            record_type = "A"
                        
                        # 生成完整的反向DNS记录名称
                        record_name = f"{subdomain_name}.{reversed_ip}.{reverse_domain}"
                        
                        # 创建DNS记录
                        if create_dns_record(cf_token, zone_id, record_name, line, record_type, 1):
                            records_created += 1
                            total_records_created += 1
                        else:
                            print(f"⚠️ 跳过记录: {record_name}")
                            
                    except Exception as e:
                        print(f"⚠️ 处理IP {line} 时出错: {e}")
                        continue
            
            print(f"✅ {filename}: 成功创建 {records_created} 个DNS记录")
            processed_files += 1
    
    print(f"\n✅ DNS记录上传完成！")
    print(f"🌍 总共处理文件: {processed_files}")
    print(f"🔗 总共创建记录: {total_records_created}")
    return True

def main():
    """主函数"""
    print("🔄 Cloudflare反向DNS记录上传工具")
    print("=" * 50)
    
    # 从配置文件读取配置
    config = load_config()
    
    cf_token = None
    zone_id = None
    reverse_domain = "5.a.9.f.0.7.4.0.1.0.0.2.ip6.arpa"
    
    if config and "cloudflare" in config:
        cf_token = config["cloudflare"].get("api_token")
        zone_id = config["cloudflare"].get("zone_id")
        reverse_domain = config["reverse_dns"].get("reverse_domain", reverse_domain) if "reverse_dns" in config else reverse_domain
        print("🎯 从配置文件读取Cloudflare配置")
    else:
        print("🎯 请提供Cloudflare配置信息:")
        cf_token = input("请输入Cloudflare API Token: ").strip()
        zone_id = input("请输入Cloudflare Zone ID: ").strip()
        user_input = input(f"请输入反向DNS域名 (默认: {reverse_domain}): ").strip()
        if user_input:
            reverse_domain = user_input
    
    if not cf_token or not zone_id:
        print("❌ 请提供完整的Cloudflare配置信息")
        return
    
    success = upload_ips_to_cf_reverse_dns(
        input_dir="valid_proxies",
        reverse_domain=reverse_domain,
        cf_token=cf_token,
        zone_id=zone_id
    )
    
    if success:
        print("\n🎉 反向DNS记录上传完成！")
    else:
        print("\n❌ 反向DNS记录上传失败，请检查配置信息。")

if __name__ == "__main__":
    main()
