#!/usr/bin/env python3
import logging
import os
import re
import asyncio
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import stripe

# Bot Configuration - NEW TOKEN ADDED!
TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', '8203573400:AAH_5txmllDTVL_QTjbxlIqL2T3O9hgqZSs')
STRIPE_SECRET_KEY = os.getenv('STRIPE_SECRET_KEY', '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')

stripe.api_key = STRIPE_SECRET_KEY

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Mass check results storage
mass_results = []

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = """
🚀 **MASS CC CHECKER BOT v4.0 - LIVE!**

**✅ Features:**
• Single CC Check ✅
• **MASS Checker (50 cards)** ✅
• Stripe API Live/Test ✅
• Live/Dead Stats ✅
• **NEW BOT TOKEN** ✅

**Commands:**
"""
    await update.message.reply_text(help_text, parse_mode='Markdown')

async def stripe_check_single(card_data: str):
    """Single CC check with Stripe"""
    try:
        parts = re.split(r'[\|\s]+', card_data.strip())
        if len(parts) < 4:
            return None
        
        card_number, month, year, cvc = parts[0], int(parts[1]), int(parts[2]), parts[3]
        
        # Rate limit protection
        await asyncio.sleep(0.2)
        
        intent = stripe.PaymentIntent.create(
            amount=100,  # ₹1 test
            currency='inr',
            payment_method_data={
                'type': 'card',
                'card': {
                    'number': card_number,
                    'exp_month': month,
                    'exp_year': year,
                    'cvc': cvc,
                },
            },
            confirm=True,
            automatic_payment_methods={'enabled': True},
        )
        
        status = "🟢 LIVE" if intent.status == 'succeeded' else "🔴 DEAD"
        return f"`{card_number[-4:]}...` | {status} | {intent.status}"
        
    except Exception as e:
        return f"`{card_data[:15]}...` | ❌ DECLINED"

async def mass_check(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Mass card checker - up to 50 cards"""
    global mass_results
    
    if not context.args:
        await update.message.reply_text(
            "📋 **Mass Check:**\n\n"
            "Paste cards line by line:\n"
            "4242424242424242|12|25|123\n"
            "4000000000000002|12|25|123\n"
            "5555555555554444|12|25|123\n"
            "```\n\n"
            "Max 50 cards | Auto processing!", parse_mode='Markdown'
        )
        return
    
    # Extract cards from message
    cards_text = ' '.join(context.args)
    card_lines = [line.strip() for line in cards_text.split('\n') if re.search(r'\d{13,19}', line)]
    
    if len(card_lines) > 50:
        await update.message.reply_text("⚠️ Max 50 cards allowed!")
        card_lines = card_lines[:50]
    
    await update.message.reply_chat_action("typing")
    await update.message.reply_text(f"🔄 Checking **{len(card_lines)}** cards...", parse_mode='Markdown')
    
    mass_results.clear()
    
    # Concurrent checking with semaphore (max 5 at once)
    semaphore = asyncio.Semaphore(5)
    
    async def check_with_limit(card):
        async with semaphore:
            result = await stripe_check_single(card)
            if result:
                mass_results.append(result)
            return result
    
    tasks = [check_with_limit(card) for card in card_lines]
    await asyncio.gather(*tasks)
    
    # Results summary
    live_count = sum(1 for r in mass_results if '🟢 LIVE' in r)
    dead_count = len(mass_results) - live_count
    success_rate = (live_count / len(mass_results) * 100) if mass_results else 0
    
    summary = f"""
📊 **MASS CHECK COMPLETE!**
✅ **LIVE:** {live_count}
❌ **DEAD:** {dead_count} 
📈 **Success:** {success_rate:.1f}%
🔢 **Total:** {len(mass_results)}

**🎯 Top 10 Results:**
"""
    await update.message.reply_text(summary, parse_mode='Markdown')

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global mass_results
    if not mass_results:
        await update.message.reply_text("📭 No results. Use `/mass` first!")
        return
    
    live = sum(1 for r in mass_results if '🟢 LIVE' in r)
    rate = live / len(mass_results) * 100
    await update.message.reply_text(
        f"📈 **STATS:** `{live}/{len(mass_results)}` LIVE\n"
        f"📊 **{rate:.1f}%** Success Rate", parse_mode='Markdown')

async def setkey_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global stripe
    if not context.args:
        await update.message.reply_text("❌ `/setkey sk_live_...` or `/setkey sk_test_...`", parse_mode='Markdown')
        return
    
    new_key = context.args[0]
    try:
        stripe.api_key = new_key
        stripe.Account.retrieve()
        key_type = "🔴 LIVE" if new_key.startswith('sk_live_') else "🟢 TEST"
        await update.message.reply_text(
            f"✅ **Key Updated!**\n"
            f"{key_type} Mode\n"
            f"`{new_key[:10]}...`", parse_mode='Markdown')
    except Exception as e:
        await update.message.reply_text(f"❌ Invalid key: `{str(e)[:50]}`", parse_mode='Markdown')

async def stripe_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("❌ `/stripe 4242424242424242|12|25|123`", parse_mode='Markdown')
        return
    
    card_data = ' '.join(context.args)
    await update.message.reply_chat_action("typing")
    result = await stripe_check_single(card_data)
    await update.message.reply_text(result or "❌ Invalid format", parse_mode='Markdown')

async def clear_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global mass_results
    mass_results.clear()
    await update.message.reply_text("🗑️ Results cleared!")

async def echo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    
    # Auto mass check (multiple lines with cards)
    if '\n' in text and re.search(r'\d{16}', text):
        await mass_check(update, context)
    # Single card auto check
    elif re.search(r'\d{13,19}[|\s]\d{1,2}[|\s]\d{2,4}[|\s]\d{3,4}', text):
        result = await stripe_check_single(text)
        await update.message.reply_text(result or "❌ Invalid CC", parse_mode='Markdown')
    else:
        await update.message.reply_text(
            "💬 Send cards or use:\n"
            "• `/stripe card|MM|YY|CVC`\n"
            "• `/mass` + paste cards", parse_mode='Markdown')

def main():
    if not TOKEN:
        logger.error("🚫 TELEGRAM_BOT_TOKEN missing!")
        return
    
    app = Application.builder().token(TOKEN).build()
    
    # All command handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", start))
    app.add_handler(CommandHandler("setkey", setkey_command))
    app.add_handler(CommandHandler("stripe", stripe_command))
    app.add_handler(CommandHandler("mass", mass_check))
    app.add_handler(CommandHandler("stats", stats_command))
    app.add_handler(CommandHandler("clear", clear_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo))
    
    logger.info(f"🚀 MASS CC CHECKER started! Token: {TOKEN[:10]}...")
    logger.info(f"💳 Stripe: {STRIPE_SECRET_KEY[:10]}...")
    app.run_polling()

if __name__ == '__main__':
    main()
