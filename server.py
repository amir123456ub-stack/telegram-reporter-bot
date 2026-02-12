import asyncio
import sys
from bot import TelegramReporterBot

async def start_worker():
    try:
        bot = TelegramReporterBot()
        await bot.start_bot()
    except Exception as e:
        print(f"❌ Bot crashed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    print("🚀 Starting Telegram Reporter Bot on Render...")
    try:
        asyncio.run(start_worker())
    except KeyboardInterrupt:
        print("\n👋 Bot stopped by user")
    except Exception as e:
        print(f"❌ Fatal error: {e}")
        sys.exit(1)
