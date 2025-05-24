from telethon import TelegramClient
import asyncio

# 你的 API ID 和 API Hash
api_id = '22012162'  # 替换为你的 API ID
api_hash = '844e41eece3ff519edb47f28e9240371'  # 替换为你的 API Hash

# 创建客户端
client = TelegramClient('session_name', api_id, api_hash)

async def get_subscription_messages(group_id):
    # 启动客户端
    await client.start()
    
    # 确认是否已登录
    if await client.is_user_authorized():
        print("登录成功！")
    else:
        print("登录失败！")
        return

    # 获取群组实体
    group = await client.get_entity(group_id)
    
    # 获取群组中的最新消息
    messages = await client.get_messages(group, limit=10)  # 获取最新的10条消息
    
    print("订阅群组中的消息：")
    for message in messages:
        print(f"消息内容: {message.text}")

# 运行主函数
if __name__ == "__main__":
    group_id = -1002172828140  # 替换为你的群组ID
    asyncio.run(get_subscription_messages(group_id))
