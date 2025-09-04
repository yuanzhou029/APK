import os
import requests

# 定义文件路径
links_file = 'links.txt'
output_file = 'usb.txt'

# 设置请求超时时间（秒）
TIMEOUT = 30

# 设置请求头，模拟浏览器行为
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}

def get_subscription_content():
    try:
        # 检查links.txt文件是否存在
        if not os.path.exists(links_file):
            print(f"错误: {links_file} 文件不存在")
            return
        
        # 读取links.txt中的订阅链接
        with open(links_file, 'r', encoding='utf-8') as f:
            links = [line.strip() for line in f if line.strip()]
        
        if not links:
            print(f"警告: {links_file} 文件中没有找到有效的订阅链接")
            return
        
        # 创建或清空usb.txt文件
        with open(output_file, 'w', encoding='utf-8') as f_out:
            
            # 处理每个链接
            for index, link in enumerate(links, 1):
                print(f"处理链接 {index}/{len(links)}: {link}")
                
                # 移除链接标题和分隔线
                # f_out.write(f"# 链接 {index}: {link}\n")
                # f_out.write(f"# " + "-"*50 + "\n")
                
                try:
                    # 发送请求获取链接内容
                    response = requests.get(link, headers=HEADERS, timeout=TIMEOUT)
                    response.raise_for_status()  # 检查请求是否成功
                    
                    # 仅写入纯链接内容，不添加额外格式
                    f_out.write(response.text + '\n')  # 保留一个换行分隔不同链接内容
                    print(f"  成功: 已获取并保存链接内容")
                    
                except requests.exceptions.RequestException as e:
                    error_msg = f"获取链接内容失败: {e}"
                    print(error_msg)
                    # 不在文件中记录错误信息
                    # f_out.write(f"# {error_msg}\n\n")
                
                # 移除分隔线
                # f_out.write("# " + "="*50 + "\n\n")
        
        print(f"\n成功: 已处理所有 {len(links)} 个订阅链接，并将内容保存到 {output_file} 文件中")
        
    except Exception as e:
        print(f"发生错误: {e}")

if __name__ == "__main__":
    get_subscription_content()
