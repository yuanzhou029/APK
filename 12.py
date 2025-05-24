from telethon import TelegramClient
import re

# 你的 API ID 和 API Hash
api_id = os.getenv('API_ID')
api_hash = os.getenv('API_HASH')

# 你的电话号码（用于登录 Telegram）
phone_number = os.getenv('PHONE_NUMBER')  # 替换为你的电话号码

# 创建客户端
client = TelegramClient('session_name', api_id, api_hash)

# 定义正则表达式，用于匹配订阅链接
SUBSCRIPTION_LINK_REGEX = r'订阅链接:\s*(https?://[^\s]+)'

async def get_subscription_links(group_username):
    """
    从指定的公开群组中获取免费订阅链接。
    :param group_username: 群组的用户名（例如：@public_group）
    """
    try:
        # 连接到 Telegram
        await client.start(phone=phone_number)
        print("客户端已成功连接...")

        # 获取群组消息
        print(f"正在从群组 {group_username} 中抓取消息...")
        async for message in client.iter_messages(group_username):
            if message.text:
                # 使用正则表达式匹配订阅链接
                links = re.findall(SUBSCRIPTION_LINK_REGEX, message.text)
                for link in links:
                    print(f"发现订阅链接: {link}")

    except Exception as e:
        print(f"发生错误: {e}")
    finally:
        # 断开客户端连接
        await client.disconnect()

# 运行脚本
if __name__ == "__main__":
    import asyncio
    # 替换为你要抓取的公开群组的用户名（例如：@public_group）
    group_username = '@zzzjjjkkkoi'
    asyncio.run(get_subscription_links(group_username))
