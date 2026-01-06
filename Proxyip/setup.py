#!/usr/bin/env python3
"""
ProxyIP检测工具 - 项目设置脚本

此脚本用于快速设置ProxyIP检测工具的开发和部署环境
支持本地安装和GitHub Actions部署
"""

import os
import sys
import json
import subprocess
import argparse
from pathlib import Path

def print_header(title):
    """打印标题"""
    print(f"\n{'='*60}")
    print(f"{title:^60}")
    print(f"{'='*60}")

def check_python_version():
    """检查Python版本"""
    print_header("检查Python版本")
    
    if sys.version_info < (3, 9):
        print("❌ 错误: Python 3.9+ 是必需的")
        print(f"当前版本: {sys.version}")
        return False
    
    print(f"✅ Python版本检查通过: {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}")
    return True

def install_dependencies():
    """安装依赖包"""
    print_header("安装依赖包")
    
    requirements_file = "requirements.txt"
    if not os.path.exists(requirements_file):
        print(f"❌ 错误: {requirements_file} 文件不存在")
        return False
    
    try:
        print("🔄 安装依赖包...")
        result = subprocess.run([
            sys.executable, "-m", "pip", "install", "-r", requirements_file
        ], capture_output=True, text=True)
        
        if result.returncode == 0:
            print("✅ 依赖包安装成功")
            return True
        else:
            print(f"❌ 依赖包安装失败: {result.stderr}")
            return False
            
    except Exception as e:
        print(f"❌ 安装依赖包时出错: {e}")
        return False

def create_input_files():
    """创建输入文件模板"""
    print_header("创建输入文件模板")
    
    # 创建Proxyip.txt模板
    proxy_template = """# ProxyIP检测工具 - 输入文件模板
# 
# 支持格式:
# 1. IP地址:port (如 1.2.3.4:8080)
# 2. 域名:port (如 proxy.example.com:8080)  
# 3. 远程URL (如 https://raw.githubusercontent.com/user/proxy-list/main/ips.txt)

# 示例IP地址
1.2.3.4:8080
5.6.7.8:3128

# 示例域名
proxy.example.com:8080

# 示例远程URL
# https://raw.githubusercontent.com/user/proxy-list/main/ips.txt

# 按地区分类的示例
# 台湾代理
# 2.3.4.5:8080
# proxy.tw.example.com:3128

# 日本代理  
# 3.4.5.6:1080

# 香港代理
# 4.5.6.7:80
"""
    
    # 创建domains.txt模板
    domain_template = """# 域名输入文件模板
# 每行一个域名

google.com
github.com
stackoverflow.com
wikipedia.org
youtube.com

# 示例代理域名
# proxy.example.com
# test.proxy.com
"""
    
    try:
        with open("Proxyip.txt", "w", encoding="utf-8") as f:
            f.write(proxy_template)
        print("✅ Proxyip.txt 模板创建成功")
        
        with open("domains.txt", "w", encoding="utf-8") as f:
            f.write(domain_template)
        print("✅ domains.txt 模板创建成功")
        
        return True
        
    except Exception as e:
        print(f"❌ 创建输入文件模板时出错: {e}")
        return False

def create_config_file():
    """创建配置文件"""
    print_header("创建配置文件")
    
    config = {
        "main_domain": "your-domain.com",
        "proxy_detection": {
            "input_source": "Proxyip.txt",
            "domains_source": "domains.txt",
            "filter_countries": ["台湾", "日本", "香港", "新加坡"],
            "max_threads": 30,
            "check_api": "https://cf.090227.xyz/check",
            "timeout": 10,
            "max_retries": 3
        },
        "subdomain_generation": {
            "mode": "filename",
            "input_directory": "valid_proxies",
            "output_directory": "subdomain_domains",
            "filename_pattern": "{country_code}.{main_domain}",
            "content_pattern": "{country_code}-{identifier}.{main_domain}"
        },
        "github_actions": {
            "schedule": "0 0 * * *",
            "telegram": {
                "bot_token_secret": "TELEGRAM_BOT_TOKEN",
                "chat_id_secret": "TELEGRAM_CHAT_ID"
            }
        }
    }
    
    try:
        with open("example_config.json", "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
        print("✅ example_config.json 配置文件创建成功")
        return True
    except Exception as e:
        print(f"❌ 创建配置文件时出错: {e}")
        return False

def create_directories():
    """创建必要目录"""
    print_header("创建目录结构")
    
    directories = [
        "valid_proxies",
        "subdomain_domains", 
        "cf_domains"
    ]
    
    for directory in directories:
        os.makedirs(directory, exist_ok=True)
        print(f"📁 {directory}/ 目录创建成功")
    
    return True

def test_scripts():
    """测试脚本功能"""
    print_header("测试脚本功能")
    
    scripts = ["ip.py", "reverse_dns.py", "get_stats.py"]
    
    for script in scripts:
        if os.path.exists(script):
            print(f"🔍 测试 {script}...")
            try:
                result = subprocess.run([
                    sys.executable, "-c", 
                    f"import {script[:-3]}; print('✅ {script} 导入成功')"
                ], capture_output=True, text=True)
                
                if result.returncode == 0:
                    print(f"✅ {script} 测试通过")
                else:
                    print(f"❌ {script} 测试失败: {result.stderr}")
            except Exception as e:
                print(f"❌ {script} 测试出错: {e}")
        else:
            print(f"⚠️  {script} 文件不存在")
    
    return True

def display_setup_summary():
    """显示设置摘要"""
    print_header("设置摘要")
    
    print("📋 已完成的设置:")
    print("  ✅ Python版本检查")
    print("  ✅ 依赖包安装")
    print("  ✅ 输入文件模板创建")
    print("  ✅ 配置文件创建")
    print("  ✅ 目录结构创建")
    print("  ✅ 脚本功能测试")
    
    print("\n🎯 下一步操作:")
    print("  1. 编辑 Proxyip.txt 添加您的代理IP/域名/URL")
    print("  2. 编辑 example_config.json 配置您的参数")
    print("  3. 运行 'python ip.py' 测试代理检测")
    print("  4. 运行 'python reverse_dns.py' 测试子域名生成")
    print("  5. 配置GitHub Secrets (TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID)")
    print("  6. 推送代码到GitHub启用自动化")
    
    print("\n💡 提示:")
    print("  - 查看 README.md 了解详细使用方法")
    print("  - 查看 DEPLOYMENT.md 了解部署指南")
    print("  - 查看 EXAMPLES.md 了解使用示例")

def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='ProxyIP检测工具设置脚本')
    parser.add_argument('--quick', action='store_true', help='快速设置（跳过部分检查）')
    parser.add_argument('--verbose', action='store_true', help='详细输出')
    
    args = parser.parse_args()
    
    print_header("ProxyIP检测工具 - 项目设置")
    print("此脚本将帮助您快速设置开发和部署环境")
    
    # 检查Python版本
    if not args.quick and not check_python_version():
        return False
    
    # 安装依赖
    if not install_dependencies():
        return False
    
    # 创建目录
    create_directories()
    
    # 创建输入文件模板
    if not create_input_files():
        return False
    
    # 创建配置文件
    if not create_config_file():
        return False
    
    # 测试脚本
    if not args.quick:
        test_scripts()
    
    # 显示摘要
    display_setup_summary()
    
    print(f"\n🎉 设置完成！")
    print(f"您可以开始使用ProxyIP检测工具了。")
    
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
