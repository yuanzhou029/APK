from telethon import TelegramClient
import asyncio
import os

# 从环境变量中获取 API ID 和 API Hash
api_id = os.getenv('API_ID')
api_hash = os.getenv('API_HASH')
phone_number = os.getenv('PHONE_NUMBER')
group_id = int(os.getenv('GROUP_ID'))

# 创建客户端
client = TelegramClient('session_name', api_id, api_hash)

async def get_subscription_messages(group_id):
    # 启动客户端并自动处理验证码
    await client.start(phone=phone_number, code_callback=lambda: os.getenv('TELEGRAM_CODE'))
    
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
    asyncio.run(get_subscription_messages(group_id))
