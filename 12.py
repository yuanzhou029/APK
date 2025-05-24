from telethon import TelegramClient
import asyncio

# 你的 API ID 和 API Hash
api_id = '22012162'  # 替换为你的 API ID
api_hash = '844e41eece3ff519edb47f28e9240371'  # 替换为你的 API Hash

# 创建客户端
client = TelegramClient('session_name', api_id, api_hash)

async def get_group_or_channel_info():
    # 启动客户端
    await client.start()
    
    # 确认是否已登录
    if await client.is_user_authorized():
        print("登录成功！")
    else:
        print("登录失败！")
        return

    # 列出所有对话（包括群组、频道、私聊等）
    dialogs = await client.get_dialogs()
    
    print("你加入的群组和频道：")
    for dialog in dialogs:
        if dialog.is_group or dialog.is_channel:  # 过滤群组和频道
            print(f"名称: {dialog.name}, 用户名: {dialog.entity.username}, ID: {dialog.id}")

# 运行主函数
asyncio.run(get_group_or_channel_info())
