import asyncio
import re
import datetime
import os  # 新增：导入os模块用于文件操作
from crawl4ai import *

async def main():
    async with AsyncWebCrawler() as crawler:
        # 1. 爬取初始页面获取链接
        result = await crawler.arun(
            url="https://www.85la.com/internet-access/free-network-nodes",
        )
        
        # 添加结果有效性检查
        if not result or not hasattr(result, 'markdown') or result.markdown is None:
            print("错误：无法获取有效的页面内容")
            return
        
        pattern = r'\[(.*?)(\b\d{4}年\d{1,2}月\d{1,2}日\b)(.*?)\]\(([^)]+)\)'
        date_title_link_pairs = re.findall(pattern, result.markdown, re.DOTALL)
        
        latest_date = None
        latest_title = None
        latest_url = None
        
        for prefix, date_str, suffix, url in date_title_link_pairs:
            try:
                full_title = f"{prefix}{date_str}{suffix}"
                date_obj = datetime.datetime.strptime(date_str, '%Y年%m月%d日')
                
                if not latest_date or date_obj > latest_date:
                    latest_date = date_obj
                    latest_title = full_title
                    latest_url = url
            except ValueError:
                continue
        
        # 2. 输出初始提取结果
        if latest_date and latest_title and latest_url:
            print(latest_date.strftime('%Y年%m月%d日'))
            #print(latest_title)
            print(latest_url)
            
            # 3. 使用crawl4ai继续爬取提取到的链接
            try:
                # 爬取链接内容
                link_result = await crawler.arun(url=latest_url)
                # 仅输出爬取到的原始内容，不进行任何提取
                #print(link_result.markdown)
                
                # 提取v2ray
                # 确保使用正确的变量名（假设实际内容存储在link_result中）
                v2ray_pattern = re.compile(r'###\s*2\.\s*V2ray\s*订阅地址\s*<\s*(https?://[^>]+?)\s*>')
                # 使用实际返回的结果对象替代未定义的'content'变量
                v2ray_match = v2ray_pattern.search(link_result.markdown)
                # 先检查link_result和markdown属性是否存在
                if link_result and hasattr(link_result, 'markdown') and v2ray_match:
                    v2ray_content = v2ray_match.group(1).strip()
                    print("\n===== 提取到的v2ray订阅地址 =====")
                    print(v2ray_content)
                else:
                    print("\n===== 未找到有效的v2ray订阅地址 =====")
                    print("\n未找到V2ray订阅地址")
            except Exception as e:  # 添加缺失的except块
                print(f"二次爬取过程出错: {str(e)}")

if __name__ == "__main__":
    asyncio.run(main())
