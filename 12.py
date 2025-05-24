from telethon import TelegramClient
from telethon.sessions import StringSession
import re
import os
import asyncio

# 从环境变量读取敏感信息（GitHub Actions 中通过 Secrets 注入）
api_id = os.getenv('TELEGRAM_API_ID')
api_hash = os.getenv('TELEGRAM_API_HASH')
session_string = os.getenv('TELEGRAM_SESSION_STRING')

# 创建客户端（使用会话字符串认证，无文件依赖）
client = TelegramClient(
    StringSession(session_string),
    api_id,
    api_hash
)

# 定义正则表达式，用于匹配订阅链接（调整后支持反引号包裹的链接）
SUBSCRIPTION_LINK_REGEX = r'🔗订阅链接:\s*`(https?://[^\s`]+)`'  # 匹配格式：🔗订阅链接: `http://xxx`

async def get_subscription_links(group_username):
    """
    从指定群组抓取订阅链接（改进版：返回结果而非仅打印）
    :return: 抓取到的链接列表
    """
    links = []  # 存储结果
    MAX_LINKS = 50  # 最多获取50条链接
    try:
        await client.start()  # 无交互登录（通过会话字符串自动认证）
        print(f"客户端已连接，开始抓取群组 {group_username}...")
        
        # 新增：检查客户端是否已连接
        if not client.is_connected():
            print(f"错误：客户端未连接，跳过群组 {group_username}")
            return links

        # 新增：为消息迭代添加60秒超时
        try:
            async for message in asyncio.wait_for(
                client.iter_messages(group_username, limit=200),
                timeout=60.0  # 调整超时时间（根据实际情况）
            ):
                if message.text:
                    matched_links = re.findall(SUBSCRIPTION_LINK_REGEX, message.text)
                    if matched_links:
                        new_links = [link for link in matched_links if link not in links]
                        links.extend(new_links)
                        for link in new_links:
                            print(f"[群组 {group_username}] 发现订阅链接: {link}")
                        if len(links) >= MAX_LINKS:
                            print(f"已收集到 {MAX_LINKS} 条订阅链接，提前终止抓取...")
                            break
        except asyncio.TimeoutError:
            print(f"[群组 {group_username}] 抓取超时（60秒未完成），终止任务...")
        except asyncio.CancelledError:
            print(f"[群组 {group_username}] 任务被取消，可能是网络问题或API限制...")

    except Exception as e:
        print(f"[群组 {group_username}] 抓取失败: {str(e)}")
    finally:
        await client.disconnect()
    return links[:MAX_LINKS]  # 确保返回不超过50条

if __name__ == "__main__":
    groups = ['@zzzjjjkkkoi']  # 按需修改群组名

    async def main():
        semaphore = asyncio.Semaphore(3)  # 限制并发数
        
        async def bounded_task(group):
            async with semaphore:
                return await get_subscription_links(group)
        
        tasks = [bounded_task(group) for group in groups]
        results = await asyncio.gather(*tasks)
        
        all_links = [link for sublist in results for link in sublist]
        print(f"\n抓取完成！共收集到 {len(all_links)} 个订阅链接。")

        # 将链接写入文件
        with open('links.txt', 'w', encoding='utf-8') as f:
            for link in all_links:
                f.write(link + '\n')
        print("已将订阅链接保存至 links.txt 文件。")

    asyncio.run(main())
