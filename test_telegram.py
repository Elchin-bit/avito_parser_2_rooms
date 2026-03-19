import asyncio
from telegram import Bot


from config import TELEGRAM_BOT_TOKEN, CHAT_ID

async def send_test():
    bot = Bot(token=TELEGRAM_BOT_TOKEN)
    await bot.send_message(
        chat_id=CHAT_ID,
        text="🚀 ТЕСТ! Если видишь — всё работает!"
    )
    print("✅ Сообщение отправлено!")

if __name__ == "__main__":
    asyncio.run(send_test())