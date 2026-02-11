from bot import TelegramReporterBot
import asyncio
import os

async def start_worker():
    bot = TelegramReporterBot()
    await bot.start_bot()

if __name__ == "__main__":
    print("🚀 Starting Telegram Reporter Bot on Render...")
    asyncio.run(start_worker())
