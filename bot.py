import asyncio
import os
from datetime import datetime
from playwright.async_api import async_playwright
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

BOT_TOKEN = os.getenv("BOT_TOKEN")

SOURCE = "chennai"
DEST = "coimbatore"
OPERATOR_NAME = "delta"   # flexible matching

CHECK_INTERVAL = 600  # 10 minutes

user_tasks = {}


# 🔎 Fetch data from redBus
async def fetch_bus_data(date):
    url = f"https://www.redbus.in/bus-tickets/{SOURCE}-to-{DEST}?date={date}"

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        try:
            await page.goto(url, timeout=60000)
            await page.wait_for_selector("div.bus-item", timeout=20000)
        except:
            await browser.close()
            return ["⚠️ Failed to load bus data"]

        buses = await page.query_selector_all("div.bus-item")
        results = []

        for bus in buses:
            try:
                text = await bus.inner_text()

                if OPERATOR_NAME in text.lower():
                    price_el = await bus.query_selector(".fare span")
                    seats_el = await bus.query_selector(".seat-left")

                    price = await price_el.inner_text() if price_el else "N/A"
                    seats = await seats_el.inner_text() if seats_el else "N/A"

                    results.append(
                        f"🚌 DELTA TRANSPORTS\n💰 {price}\n💺 {seats}"
                    )
            except:
                continue

        await browser.close()

        if not results:
            return ["❌ No matching buses found"]

        return results


# ▶️ /start command
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🚌 redBus Tracker Bot\n\n"
        "Send date in format YYYY-MM-DD\n"
        "Example: 2026-05-10"
    )


# 📅 Handle user date input
async def handle_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.chat_id
    date = update.message.text.strip()

    # Validate date
    try:
        datetime.strptime(date, "%Y-%m-%d")
    except:
        await update.message.reply_text("❌ Invalid date format. Use YYYY-MM-DD")
        return

    await update.message.reply_text(f"🚀 Tracking started for {date}")

    # Stop previous tracking if exists
    if user_id in user_tasks:
        user_tasks[user_id].cancel()

    async def track():
        last_message = None

        while True:
            try:
                data = await fetch_bus_data(date)
                message = "\n\n".join(data)

                # Send only if changed
                if message != last_message:
                    await context.bot.send_message(chat_id=user_id, text=message)
                    last_message = message

            except Exception as e:
                await context.bot.send_message(
                    chat_id=user_id,
                    text=f"⚠️ Error: {str(e)}"
                )

            await asyncio.sleep(CHECK_INTERVAL)

    task = asyncio.create_task(track())
    user_tasks[user_id] = task


# 🛑 Stop command (optional)
async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.chat_id

    if user_id in user_tasks:
        user_tasks[user_id].cancel()
        del user_tasks[user_id]
        await update.message.reply_text("🛑 Tracking stopped")
    else:
        await update.message.reply_text("No active tracking found")


# 🚀 Main
if __name__ == "__main__":
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("stop", stop))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_date))

    print("Bot running...")
    app.run_polling()
