import re
import asyncio
from telegram import Update
from telegram.ext import ContextTypes

STRIPE_SECRET_KEY = "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"
TELEGRAM_BOT_TOKEN = "8203573400:AAH_5txmllDTVL_QTjbxlIqL2T3O9hgqZSs"

mass_results: list[str] = []


async def stripe_check_single(card_data: str) -> str | None:
    """Ek card ko Stripe se check kare: 4242...|MM|YYYY|CVC"""
    import stripe
    stripe.api_key = STRIPE_SECRET_KEY

    parts = re.split(r"[\|\s]+", card_data.strip())
    if len(parts) < 4:
        return None

    number = parts[0]
    mm = int(parts[1])
    yy = int(parts[2])
    cvc = parts[3]

    await asyncio.sleep(0.2)  # thoda delay

    try:
        intent = stripe.PaymentIntent.create(
            amount=100,          # ₹1
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
async def mass_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Up to 100 cards: /mass card1 card2 ... ya multi‑line paste."""
    global mass_results

    text = update.message.text or ""
    if text.startswith("/mass"):
        text = text[len("/mass"):].strip()

    if not text:
        await update.message.reply_text(
            "Mass example:\n"
            "/mass 4242...|12|25|123 4000...|01|26|999"
        )
        return

    # Split by space/newline, sirf woh parts lo jisme 13–19 digit hain
    raw_parts = re.split(r"[\s\r\n]+", text)
    cards = [p.strip() for p in raw_parts if re.search(r"\d{13,19}", p)]

    if not cards:
        await update.message.reply_text("No cards found.")
        return

    if len(cards) > 100:
        cards = cards[:100]

    mass_results = []
    await update.message.reply_text(f"Checking {len(cards)} cards...")
    sem = asyncio.Semaphore(10)  # 10 parallel

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
from telegram.ext import Application, CommandHandler

app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
app.add_handler(CommandHandler("mass", mass_command))
