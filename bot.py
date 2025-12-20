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

# ==== CONFIG ====
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "8203573400:AAH_5txmllDTVL_QTjbxlIqL2T3O9hgqZSs")
STRIPE_SECRET_KEY = os.getenv(
    "STRIPE_SECRET_KEY",
    "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",
)

stripe.api_key = STRIPE_SECRET_KEY

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

mass_results: list[str] = []


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "🚀 MASS CC CHECKER v4.0\n\n"
        "/start - Help\n"
        "/setkey sk_live_... - Stripe key set\n"
        "/stripe card|MM|YY|CVC - single check\n"
        "/mass <cards> - mass check (max 50)\n"
        "/stats - summary\n"
        "/clear - clear results\n"
    )
    await update.message.reply_text(text)


async def stripe_check_single(card_data: str) -> str | None:
    # split on | or whitespace
    parts = re.split(r"[\|\s]+", card_data.strip())
    if len(parts) < 4:
        return None

    number, mm, yy, cvc = parts[0], int(parts[1]), int(parts[2]), parts[3]

    await asyncio.sleep(0.2)

    try:
        intent = stripe.PaymentIntent.create(
            amount=100,  # ₹1
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
        return f"`{number[-4:]}...` | {status} | {intent.status}"
    except Exception:
        return f"`{card_data[:15]}...` | ❌ DECLINED"


async def stripe_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text(
            "Usage: /stripe 4242424242424242|12|25|123"
        )
        return

    data = " ".join(context.args)
    await update.message.reply_chat_action("typing")
    res = await stripe_check_single(data)
    await update.message.reply_text(res or "Invalid format", parse_mode="Markdown")


async def setkey_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /setkey sk_live_... ya sk_test_...")
        return

    new_key = context.args[0]
    try:
        stripe.api_key = new_key
        stripe.Account.retrieve()
        await update.message.reply_text(
            f"Key updated: `{new_key[:10]}...`", parse_mode="Markdown"
        )
    except Exception as e:
        await update.message.reply_text(
            f"Invalid key: `{str(e)[:80]}`", parse_mode="Markdown"
        )


async def mass_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global mass_results

    if not context.args:
        await update.message.reply_text(
            "Mass example:\n"
            "4242424242424242|12|25|123\n"
            "4000000000000002|12|25|123"
        )
        return

    cards_text = " ".join(context.args)
    # split by newline; match card numbers
    lines = [
        l.strip()
        for l in cards_text.split("\n")
        if re.search(r"\d{13,19}", l)
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
        f"Done!\nLIVE: {live}\nDEAD: {dead}\nRate: {rate:.1f}%\n\n"
        "Last results:\n``````"
    )
    await update.message.reply_text(msg, parse_mode="Markdown")


async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not mass_results:
        await update.message.reply_text("No mass results yet.")
        return
    live = sum(1 for r in mass_results if "🟢 LIVE" in r)
    rate = live / len(mass_results) * 100
    await update.message.reply_text(
        f"Stats: {live}/{len(mass_results)} LIVE ({rate:.1f}%)"
    )


async def clear_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    mass_results.clear()
    await update.message.reply_text("Results cleared.")


async def echo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text or ""
    # many lines → mass
    if "\n" in text and re.search(r"\d{16}", text):
        class Dummy:
            args = [text]
        await mass_command(update, Dummy)
    # single card pattern
    elif re.search(r"\d{13,19}[|\s]\d{1,2}[|\s]\d{2,4}[|\s]\d{3,4}", text):
        res = await stripe_check_single(text)
        await update.message.reply_text(res or "Invalid", parse_mode="Markdown")
    else:
        await update.message.reply_text("Use /start for help.")


def main():
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("setkey", setkey_command))
    app.add_handler(CommandHandler("stripe", stripe_command))
    app.add_handler(CommandHandler("mass", mass_command))
    app.add_handler(CommandHandler("stats", stats_command))
    app.add_handler(CommandHandler("clear", clear_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo))

    logger.info("Bot running...")
    app.run_polling()


if __name__ == "__main__":
    main()
