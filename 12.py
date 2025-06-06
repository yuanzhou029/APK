from telethon import TelegramClient
from telethon.sessions import StringSession
import re
import os
import asyncio
import requests  # 新增：用于获取订阅内容

# 从环境变量读取敏感信息（GitHub Actions 中通过 Secrets 注入）
api_id = os.getenv('TELEGRAM_API_ID')
api_hash = os.getenv('TELEGRAM_API_HASH')
session_string = os.getenv('TELEGRAM_SESSION_STRING')

# 定义正则表达式，用于匹配订阅链接（调整后支持反引号包裹的链接）
# 定义正则表达式（优化后仅捕获链接）
SUBSCRIPTION_LINK_REGEX = r'(?:v2ray订阅):\s*`(https?://[^\s`]+)`' # 匹配格式：🔗订阅链接: `http://xxx` 或 v2ray订阅: `http://xxx`
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

# 新增：节点提取正则（复用之前TG.PY的扩展版本，覆盖更多特殊字符）
NODE_REGEX = r'vmess://[\w\-+\/=?&@#.:%]+|vless://[\w\-+\/=?&@#.:%]+|trojan://[\w\-+\/=?&@#.:%]+|ss://[\w\-+\/=?&@#.:%]+|hysteria2://[\w\-+\/=?&@#.:%]+'

async def fetch_subscription_content(url):
    """获取订阅链接的原始内容（带异常处理）"""
    try:
        response = requests.get(url, timeout=15)
        response.raise_for_status()
        return response.text
    except Exception as e:
        print(f"获取订阅链接 {url} 失败: {str(e)}")
        return None

async def process_links_and_count_nodes():
    """处理links.txt中的链接，累计节点并去重统计"""
    # 读取links.txt中的所有订阅链接
    if not os.path.exists('links.txt'):
        print("错误：未找到 links.txt 文件")
        return

    with open('links.txt', 'r', encoding='utf-8') as f:
        subscription_links = [line.strip() for line in f.readlines() if line.strip()]

    if not subscription_links:
        print("错误：links.txt 中无有效订阅链接")
        return

    # 累计节点到临时文件（temp_nodes.txt）
    temp_nodes_path = 'temp_nodes.txt'
    if os.path.exists(temp_nodes_path):
        os.remove(temp_nodes_path)  # 每次运行前清空临时文件

    total_nodes = 0
    for url in subscription_links:
        content = await fetch_subscription_content(url)
        if content:
            # 提取节点并追加到临时文件
            nodes = re.findall(NODE_REGEX, content)
            with open(temp_nodes_path, 'a', encoding='utf-8') as f:
                f.write('\n'.join(nodes) + '\n')  # 换行分隔节点
            total_nodes += len(nodes)
            print(f"处理链接 {url} 成功，提取节点数: {len(nodes)}，累计节点数: {total_nodes}")

    # 去重并统计最终节点数
    if not os.path.exists(temp_nodes_path):
        print("错误：临时文件 temp_nodes.txt 未生成")
        return

    with open(temp_nodes_path, 'r', encoding='utf-8') as f:
        all_nodes = [line.strip() for line in f.readlines() if line.strip()]

    unique_nodes = list(set(all_nodes))  # 去重
    unique_count = len(unique_nodes)
    print(f"\n最终统计：累计原始节点数 {total_nodes}，去重后节点数 {unique_count}")

    # 保存去重后的节点（可选）
    with open('unique_nodes.txt', 'w', encoding='utf-8') as f:
        f.write('\n'.join(unique_nodes))
    print(f"已将去重后的 {unique_count} 个节点保存至 unique_nodes.txt")

if __name__ == "__main__":
    groups = ['@pgkj0402']  # 目标群组（保持原逻辑）

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

        # 新增：抓取完成后处理节点统计
        await process_links_and_count_nodes()

    asyncio.run(main())
