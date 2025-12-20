#!/usr/bin/env python3
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

# ====== CONFIG ======
TELEGRAM_BOT_TOKEN = "8203573400:AAH_5txmllDTVL_QTjbxlIqL2T3O9hgqZSs"
STRIPE_SECRET_KEY = "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"

stripe.api_key = STRIPE_SECRET_KEY

mass_results: list[str] = []


# ====== HELP / START ======

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "🚀 MASS CC CHECKER (Stripe LIVE)\n\n"
        "/start - Help\n"
        "/mass card1 card2 ...  - Max 100 cards\n\n"
        "Format: card|MM|YYYY|CVC\n"
        "Example:\n"
        "/mass 4242424242424242|12|2025|123 4000000000000002|01|2026|999"
    )
    await update.message.reply_text(text)


# ====== SINGLE CARD CHECK ======

async def stripe_check_single(card_data: str) -> str | None:
    """Ek card ko Stripe se check kare: 4242...|MM|YYYY|CVC"""
    parts = re.split(r"[\|\s]+", card_data.strip())
    if len(parts) < 4:
        return None

    number = parts[0]
    mm = int(parts[1])
    yy = int(parts[2])
    cvc = parts[3]

    await asyncio.sleep(0.2)  # Rate limit

    try:
        intent = stripe.PaymentIntent.create(
            amount=100,          # 100 paise = ₹1
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
        masked = f"{number[:6]}******{number[-4:]}"
        return f"`{masked}` | {status} | {intent.status}"
    except Exception:
        return f"`{card_data[:15]}...` | ❌ DECLINED"


# ====== MASS CHECK (MAX 100) ======

async def mass_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Up to 100 cards: /mass card1 card2 ... ya multi‑line paste."""
    global mass_results

    text = update.message.text or ""
    if text.startswith("/mass"):
        text = text[len("/mass"):].strip()

    if not text:
        await update.message.reply_text(
            "Mass example:\n"
            "/mass 4242...|12|2025|123 4000...|01|2026|999"
        )
        return

    # Split by space/newline, sirf woh parts jisme 13–19 digits hain
    raw_parts = re.split(r"[\s\r\n]+", text)
    cards = [p.strip() for p in raw_parts if re.search(r"\d{13,19}", p)]

    if not cards:
        await update.message.reply_text("No cards found.")
        return

    if len(cards) > 100:
        cards = cards[:100]

    mass_results = []
    await update.message.reply_text(f"Checking {len(cards)} cards...")
    sem = asyncio.Semaphore(10)  # 10 parallel checks

    async def worker(card: str):
        async with sem:
            res = await stripe_check_single(card)
            if res:
                mass_results.append(res)

    await asyncio.gather(*(worker(c) for c in cards))

    live = sum(1 for r in mass_results if "🟢 LIVE" in r)
    dead = len(mass_results) - live
    rate = (live / len(mass_results) * 100) if mass_results else 0.0

    msg = (
        f"Done!\nLIVE: {live}\nDEAD: {dead}\nRate: {rate:.1f}%\n\n"
        "Last results:\n``````"
    )
    await update.message.reply_text(msg, parse_mode="Markdown")


# ====== ECHO (AUTO MASS / SINGLE) ======

async def echo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text or ""

    # Agar multiple cards lag rahe ho to mass treat karo
    if re.search(r"\d{16}.*\d{16}", text, re.S):
        class Dummy:
            args = []
        await mass_command(update, Dummy)
        return

    # Single card pattern
    if re.search(r"\d{13,19}[|\s]\d{1,2}[|\s]\d{2,4}[|\s]\d{3,4}", text):
        res = await stripe_check_single(text)
        await update.message.reply_text(res or "Invalid", parse_mode="Markdown")
    else:
        await update.message.reply_text("Use /mass or /start for help.")


# ====== MAIN ======

def main():
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("mass", mass_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo))

    app.run_polling()


if __name__ == "__main__":
    main()
