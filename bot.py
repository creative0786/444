
#!/usr/bin/env python3
import logging
import os
import re
import asyncio

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)
import stripe

# ========= CONFIG =========
TOKEN = os.getenv(
    "TELEGRAM_BOT_TOKEN",
    "8203573400:AAH_5txmllDTVL_QTjbxlIqL2T3O9hgqZSs",
)

STRIPE_SECRET_KEY = os.getenv(
    "STRIPE_SECRET_KEY",
    "sk_test_51RI8ZORVVVKRL9SxCtqjnMrJJiFQQhU7uS7jplFoIt4sQ2ciFVZ0Vow0DImqeVaeBBkKDx94NOSE62M30YommO9w00HU8zWbnu",
)

stripe.api_key = STRIPE_SECRET_KEY

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(name)

mass_results: list[str] = []


# ========= COMMANDS =========

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "MASS CC CHECKER v4.0"

"
        "/start  - Help
"
        "/setkey sk_live_...  - Stripe key set
"
        "/stripe card|MM|YY|CVC  - Single check
"
        "/mass <cards>  - Mass check (max 50)
"
        "/stats  - Summary
"
        "/clear  - Clear results
"
    )
    await update.message.reply_text(text)


async def stripe_check_single(card_data: str) -> str | None:
    """Ek card ko Stripe se check kare."""
    parts = re.split(r"[|s]+", card_data.strip())
    if len(parts) < 4:
        return None

    number = parts[0]
    mm = int(parts[1])
    yy = int(parts[2])
    cvc = parts[3]

    await asyncio.sleep(0.2)  # thoda delay – rate limit

    try:
        intent = stripe.PaymentIntent.create(
            amount=100,           # 100 paise = ₹1
            currency="inr",
            payment_method_data={
                "type": "card",
                "card": {
                    "number": number,
                    "exp_month": mm,
                    "exp_year": yy,
                    "cvc": cvc,
                },
            },
            confirm=True,
            automatic_payment_methods={"enabled": True},
        )
        status = "🟢 LIVE" if intent.status == "succeeded" else "🔴 DEAD"
        masked = f"{number[:6]}**{number[-4:]}"
        return f"{masked} | {status} | {intent.status}"
    except Exception as e:
        return f"{card_data[:15]}... | ❌ DECLINED ({type(e).name})"


async def cmd_stripe(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text(
            "Usage: /stripe 4242424242424242|12|25|123"
        )
        return

    data = " ".join(context.args)
    await update.message.reply_chat_action("typing")
    res = await stripe_check_single(data)
    await update.message.reply_text(res or "Invalid format", parse_mode="Markdown")


async def cmd_setkey(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /setkey sk_live_... ya sk_test_...")
        return

    new_key = context.args[0]
    try:
        stripe.api_key = new_key
        acc = stripe.Account.retrieve()
        mode = "LIVE" if new_key.startswith("sk_live_") else "TEST"
        await update.message.reply_text(
            f"Key updated ({mode}): {new_key[:10]}... (acct {acc.id})",
            parse_mode="Markdown",
        )
    except Exception as e:
        await update.message.reply_text(
            f"Invalid key: {str(e)[:80]}", parse_mode="Markdown"
        )


async def cmd_mass(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Multiple cards ek saath."""
    global mass_results

    if not context.args:
        await update.message.reply_text(
            "Mass example:
"
            "4242424242424242|12|25|123
"
            "4000000000000002|12|25|123"
        )
        return

    cards_text = " ".join(context.args)
    lines = [
        line.strip()
        for line in cards_text.split("
")
        if re.search(r"d{13,19}", line)
    ]
    if not lines:
        await update.message.reply_text("No cards found.")
        return

    if len(lines) > 50:
        lines = lines[:50]


mass_results = []
    await update.message.reply_text(f"Checking {len(lines)} cards...")
    sem = asyncio.Semaphore(5)

    async def worker(card: str):
        async with sem:
            r = await stripe_check_single(card)
            if r:
                mass_results.append(r)

    await asyncio.gather(*(worker(c) for c in lines))

    live = sum(1 for r in mass_results if "🟢 LIVE" in r)
    dead = len(mass_results) - live
    rate = (live / len(mass_results) * 100) if mass_results else 0.0

    msg = (
        f"Done!
LIVE: {live}
DEAD: {dead}
Rate: {rate:.1f}%

"
        "Last results:
````"
    )
    await update.message.reply_text(msg, parse_mode="Markdown")


async def cmd_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not mass_results:
        await update.message.reply_text("No mass results yet.")
        return
    live = sum(1 for r in mass_results if "🟢 LIVE" in r)
    rate = live / len(mass_results) * 100
    await update.message.reply_text(
        f"Stats: {live}/{len(mass_results)} LIVE ({rate:.1f}%)"
    )


async def cmd_clear(update: Update, context: ContextTypes.DEFAULT_TYPE):
    mass_results.clear()
    await update.message.reply_text("Results cleared.")


async def echo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text or ""

    # multi‑line → mass
    if "
" in text and re.search(r"d{16}", text):
        class Dummy:
            args = [text]
        await cmd_mass(update, Dummy)
    # single card
    elif re.search(r"d{13,19}[|s]d{1,2}[|s]d{2,4}[|s]d{3,4}", text):
        res = await stripe_check_single(text)
        await update.message.reply_text(res or "Invalid", parse_mode="Markdown")
    else:
        await update.message.reply_text("Use /start for help.")


# ========= MAIN =========

def main():
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("setkey", cmd_setkey))
    app.add_handler(CommandHandler("stripe", cmd_stripe))
    app.add_handler(CommandHandler("mass", cmd_mass))
    app.add_handler(CommandHandler("stats", cmd_stats))
    app.add_handler(CommandHandler("clear", cmd_clear))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo))

    logger.info("Bot running...")
    app.run_polling()


if name == "main":
    main()
