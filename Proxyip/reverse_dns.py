import os
import json
from pathlib import Path

def load_config():
    """从配置文件加载配置"""
    config_file = "example_config.json"
    if os.path.exists(config_file):
        with open(config_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    return None

def create_subdomains_from_files(main_domain, input_dir="valid_proxies", output_dir="subdomain_domains"):
    """
    将valid_proxies目录下的txt文件名作为子域名，与主域名组合
    
    Args:
        main_domain: 您指定的主域名
        input_dir: 输入目录，包含以国家代码命名的txt文件
        output_dir: 输出目录，保存生成的子域名
    """
    if not os.path.exists(input_dir):
        print(f"❌ 输入目录 {input_dir} 不存在")
        return
    
    # 创建输出目录
    os.makedirs(output_dir, exist_ok=True)
    
    total_subdomains = 0
    processed_files = 0
    
    print(f"🔄 开始处理 {input_dir} 目录下的文件...")
    print(f"🎯 主域名: {main_domain}")
    
    for filename in os.listdir(input_dir):
        if filename.endswith('.txt'):
            # 获取文件名（不含扩展名）作为子域名
            subdomain_name = filename.replace('.txt', '')
            
            input_file_path = os.path.join(input_dir, filename)
            
            # 读取文件中的内容（IP或域名）
            with open(input_file_path, 'r', encoding='utf-8') as f:
                lines = [line.strip() for line in f if line.strip()]
            
            # 生成子域名
            subdomains = []
            for line in lines:
                # 如果行中包含IP或域名，我们可以选择保留原内容或只生成子域名
                # 这里我们为每个文件生成一个基于文件名的子域名
                subdomain = f"{subdomain_name}.{main_domain}"
                if subdomain not in subdomains:
                    subdomains.append(subdomain)
            
            # 保存子域名到输出文件
            output_file = os.path.join(output_dir, filename)
            with open(output_file, 'w', encoding='utf-8') as f:
                for subdomain in sorted(subdomains):
                    f.write(subdomain + '\n')
            
            print(f"✅ {filename}: 生成 {len(subdomains)} 个子域名，保存到 {output_file}")
            total_subdomains += len(subdomains)
            processed_files += 1
    
    # 生成汇总信息
    summary_file = os.path.join(output_dir, "summary.json")
    summary = {
        "main_domain": main_domain,
        "total_subdomains": total_subdomains,
        "processed_files": processed_files,
        "output_directory": output_dir,
        "subdomain_files": [f for f in os.listdir(output_dir) if f.endswith('.txt')]
    }
    
    with open(summary_file, 'w', encoding='utf-8') as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    
    print(f"\n✅ 子域名生成完成！")
    print(f"🌍 总共处理文件: {processed_files}")
    print(f"🔗 总共生成子域名: {total_subdomains}")
    print(f"📁 输出目录: {output_dir}")
    print(f"📋 汇总信息: {summary_file}")

def create_subdomains_from_ip_content(main_domain, input_dir="valid_proxies", output_dir="subdomain_domains"):
    """
    从文件内容中提取信息作为子域名的一部分
    
    Args:
        main_domain: 您指定的主域名
        input_dir: 输入目录，包含以国家代码命名的txt文件
        output_dir: 输出目录，保存生成的子域名
    """
    if not os.path.exists(input_dir):
        print(f"❌ 输入目录 {input_dir} 不存在")
        return
    
    # 创建输出目录
    os.makedirs(output_dir, exist_ok=True)
    
    total_subdomains = 0
    processed_files = 0
    
    print(f"🔄 开始处理 {input_dir} 目录下的文件...")
    print(f"🎯 主域名: {main_domain}")
    
    for filename in os.listdir(input_dir):
        if filename.endswith('.txt'):
            # 获取文件名（不含扩展名）作为子域名标识
            country_code = filename.replace('.txt', '')
            
            input_file_path = os.path.join(input_dir, filename)
            
            # 读取文件中的IP/域名列表
            with open(input_file_path, 'r', encoding='utf-8') as f:
                lines = [line.strip() for line in f if line.strip()]
            
            # 为每个IP/域名生成对应的子域名
            subdomains = set()
            for line in lines:
                if line:  # 确保行不为空
                    # 使用国家代码作为子域名，加上IP/域名的某种标识
                    # 例如: jp-111-222-333-444.example.com (IP为111.222.333.444)
                    if '.' in line and not any(part.isdigit() for part in line.split('.')):
                        # 如果是域名，使用域名的第一部分
                        domain_prefix = line.split('.')[0][:10]  # 限制长度
                        subdomain = f"{country_code}-{domain_prefix}.{main_domain}"
                    else:
                        # 如果是IP，将IP中的点替换为连字符
                        ip_prefix = line.replace('.', '-')[:20]  # 限制长度
                        subdomain = f"{country_code}-{ip_prefix}.{main_domain}"
                    
                    subdomains.add(subdomain)
            
            # 保存子域名到输出文件
            output_file = os.path.join(output_dir, filename)
            with open(output_file, 'w', encoding='utf-8') as f:
                for subdomain in sorted(subdomains):
                    f.write(subdomain + '\n')
            
            print(f"✅ {filename}: 生成 {len(subdomains)} 个子域名，保存到 {output_file}")
            total_subdomains += len(subdomains)
            processed_files += 1
    
    # 生成汇总信息
    summary_file = os.path.join(output_dir, "summary.json")
    summary = {
        "main_domain": main_domain,
        "total_subdomains": total_subdomains,
        "processed_files": processed_files,
        "output_directory": output_dir,
        "subdomain_files": [f for f in os.listdir(output_dir) if f.endswith('.txt')]
    }
    
    with open(summary_file, 'w', encoding='utf-8') as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    
    print(f"\n✅ 子域名生成完成！")
    print(f"🌍 总共处理文件: {processed_files}")
    print(f"🔗 总共生成子域名: {total_subdomains}")
    print(f"📁 输出目录: {output_dir}")
    print(f"📋 汇总信息: {summary_file}")

def main():
    """主函数"""
    # 从配置文件读取主域名
    config = load_config()
    if config and "main_domain" in config:
        main_domain = config["main_domain"]
        print(f"🎯 从配置文件读取主域名: {main_domain}")
    else:
        main_domain = input("请输入您的主域名: ").strip()
        if not main_domain:
            print("❌ 请提供有效的主域名")
            return
    
    # 从配置文件读取模式，如果没有则提示用户选择
    mode = "filename"
    if config and "subdomain_generation" in config:
        mode = config["subdomain_generation"].get("mode", "filename")
        print(f"🎯 使用配置文件中的模式: {mode}")
    else:
        print("选择处理模式:")
        print("1. 使用文件名作为子域名 (如: jp.example.com)")
        print("2. 使用文件内容生成子域名 (如: jp-111-222-333-444.example.com)")
        choice = input("请选择 (1 或 2): ").strip()
        mode = "filename" if choice == "1" else "content"
    
    if mode == "filename":
        create_subdomains_from_files(main_domain)
    elif mode == "content":
        create_subdomains_from_ip_content(main_domain)
    else:
        print("❌ 无效选择，使用默认模式filename")
        create_subdomains_from_files(main_domain)

if __name__ == "__main__":
    main()
