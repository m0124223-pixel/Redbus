import asyncio
from datetime import datetime
from playwright.async_api import async_playwright
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

BOT_TOKEN = "YOUR_BOT_TOKEN_HERE"

SOURCE = "Chennai"
DEST = "Coimbatore"
OPERATOR_NAME = "DELTA TRANSPORTS"

async def fetch_bus_data(date):
    url = f"https://www.redbus.in/bus-tickets/chennai-to-coimbatore?date={date}"

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto(url, timeout=60000)

        # Wait for buses to load
        await page.wait_for_selector("div.bus-item", timeout=15000)

        buses = await page.query_selector_all("div.bus-item")

        results = []

        for bus in buses:
            text = await bus.inner_text()

            if OPERATOR_NAME.lower() in text.lower():
                try:
                    price = await bus.query_selector(".fare span")
                    seats = await bus.query_selector(".seat-left")

                    price_text = await price.inner_text() if price else "N/A"
                    seats_text = await seats.inner_text() if seats else "N/A"

                    results.append(f"🚌 {OPERATOR_NAME}\n💰 {price_text}\n💺 {seats_text}")

                except:
                    continue

        await browser.close()
        return results


# Store running tasks
user_tasks = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Send me a date in format YYYY-MM-DD\nExample: 2026-05-10"
    )

async def handle_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.chat_id
    date = update.message.text.strip()

    try:
        datetime.strptime(date, "%Y-%m-%d")
    except:
        await update.message.reply_text("Invalid date format. Use YYYY-MM-DD")
        return

    await update.message.reply_text(f"Tracking started for {date} 🚀")

    async def track():
        last_sent = None
        while True:
            try:
                data = await fetch_bus_data(date)

                if data:
                    message = "\n\n".join(data)

                    if message != last_sent:
                        await context.bot.send_message(chat_id=user_id, text=message)
                        last_sent = message
                else:
                    await context.bot.send_message(chat_id=user_id, text="No buses found")

            except Exception as e:
                await context.bot.send_message(chat_id=user_id, text=f"Error: {e}")

            await asyncio.sleep(600)  # 10 minutes

    # Cancel previous task if exists
    if user_id in user_tasks:
        user_tasks[user_id].cancel()

    task = asyncio.create_task(track())
    user_tasks[user_id] = task


if __name__ == "__main__":
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_date))

    print("Bot running...")
    app.run_polling()
