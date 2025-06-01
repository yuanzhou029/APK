from telethon import TelegramClient
from telethon.sessions import StringSession
import re
import os
import asyncio

# 从环境变量读取敏感信息（GitHub Actions 中通过 Secrets 注入）
api_id = os.getenv('TELEGRAM_API_ID')
api_hash = os.getenv('TELEGRAM_API_HASH')
session_string = os.getenv('TELEGRAM_SESSION_STRING')

# 定义正则表达式，用于匹配订阅链接（调整后支持反引号包裹的链接）
# 定义正则表达式（优化后仅捕获链接）
SUBSCRIPTION_LINK_REGEX = r'(?:🔗订阅链接|v2ray订阅):\s*`(https?://[^\s`]+)`'  # 匹配格式：🔗订阅链接: `http://xxx` 或 v2ray订阅: `http://xxx`
MAX_LINKS = 50  # 最大链接数（提取为常量）
RETRY_TIMES = 3  # 重试次数

async def get_subscription_links(group_username):
    """独立客户端实例的抓取函数（修改核心）"""
    links = []
    for attempt in range(RETRY_TIMES):
        try:
            # 每个任务创建独立客户端实例（关键修改）
            client = TelegramClient(
                StringSession(session_string),
                api_id,
                api_hash
            )
            
            await client.start()  # 独立连接
            print(f"[Attempt {attempt+1}] 客户端已连接，开始抓取群组 {group_username}...")
            
            async for message in client.iter_messages(group_username, limit=200):
                if message.text:
                    matched_links = re.findall(SUBSCRIPTION_LINK_REGEX, message.text)
                    if matched_links:
                        # 去重逻辑（保持原逻辑）
                        new_links = [link for link in matched_links if link not in links]
                        links.extend(new_links)
                        for link in new_links:
                            print(f"[群组 {group_username}] 发现订阅链接: {link}")
                        # 提前终止检查（保持原逻辑）
                        if len(links) >= MAX_LINKS:
                            print(f"已收集到 {MAX_LINKS} 条订阅链接，提前终止抓取...")
                            break
            
            # 正常完成后退出循环
            break
            
        except Exception as e:
            print(f"[群组 {group_username}] 第 {attempt+1} 次抓取失败: {str(e)}")
            if attempt == RETRY_TIMES - 1:  # 最后一次重试失败
                print(f"[群组 {group_username}] 所有重试次数耗尽，抓取终止")
        finally:
            # 确保当前实例断开（不影响其他任务）
            if 'client' in locals():
                await client.disconnect()
    
    return links[:MAX_LINKS]

if __name__ == "__main__":
    groups = ['@fqDINYUE','@zzzjjjkkkoi','@anzhuoapk']  # 目标群组（保持原逻辑）

    async def main():
        semaphore = asyncio.Semaphore(3)  # 限制并发数（保持原逻辑）
        
        async def bounded_task(group):
            async with semaphore:
                return await get_subscription_links(group)
        
        tasks = [bounded_task(group) for group in groups]
        results = await asyncio.gather(*tasks)
        
        all_links = [link for sublist in results for link in sublist]
        print(f"\n抓取完成！共收集到 {len(all_links)} 个订阅链接。")

        # 写入文件（保持原逻辑）
        with open('links.txt', 'w', encoding='utf-8') as f:
            for link in all_links:
                f.write(link + '\n')
        print("已将订阅链接保存至 links.txt 文件。")

    asyncio.run(main())
