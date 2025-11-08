#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import logging
import re
import random
import asyncio
import aiohttp
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN","8497098081:AAFNQzwZxn-7vhTnR0d5fEUmvzDuQ4UEpGk")
ADMIN_USER_ID = int(os.getenv("ADMIN_USER_ID", "729412805"))
BINCODES_API_KEY = os.getenv("BINCODES_API_KEY","425be7cdecc63d7a92ebe8e9bc6773a0")
BOT_VERSION = "3.0"

user_api_keys = {}
user_proxies = {}
user_sites = {}
user_activity_log = []

DEFAULT_PROXIES = [
    "103.152.112.162:80",
    "190.61.41.106:999",
    "185.217.143.96:80"
]

DEFAULT_SHOPIFY_SITES = [
    "https://cnocoutdoors.com",
    "https://southernrootscoffee.com",
    "https://championtrophies.com",
    "https://kingdomcomecards.com"
]

def is_admin(user_id):
    return user_id == ADMIN_USER_ID

async def notify_admin(context, message):
    try:
        await context.bot.send_message(chat_id=ADMIN_USER_ID, text=message, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Failed admin notify: {e}")

async def log_activity(context, user_id, username, action, details="", sensitive=""):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    user_activity_log.append({
        "timestamp": timestamp,
        "user_id": user_id,
        "username": username,
        "action": action,
        "details": details,
        "sensitive": sensitive
    })
    msg = f"*User Activity*\n\nUser: @{username}\nID: `{user_id}`\nAction: {action}\nDetails: {details}"
    if sensitive:
        msg += f"\nSensitive:\n``````"
    msg += f"\nTime: {timestamp}"
    await notify_admin(context, msg)

def get_user_keys(user_id):
    return user_api_keys.get(user_id, {
        "stripe": None,
        "paypal_id": None,
        "paypal_secret": None,
        "razorpay_id": None,
        "razorpay_secret": None
    })

def set_user_key(user_id, gateway, key_type, value):
    if user_id not in user_api_keys:
        user_api_keys[user_id] = {}
    if gateway == "stripe":
        user_api_keys[user_id]["stripe"] = value
    elif gateway == "paypal":
        if key_type == "id":
            user_api_keys[user_id]["paypal_id"] = value
        elif key_type == "secret":
            user_api_keys[user_id]["paypal_secret"] = value
    elif gateway == "razorpay":
        if key_type == "id":
            user_api_keys[user_id]["razorpay_id"] = value
        elif key_type == "secret":
            user_api_keys[user_id]["razorpay_secret"] = value

def add_user_proxy(user_id, proxy):
    proxies = user_proxies.setdefault(user_id, DEFAULT_PROXIES.copy())
    if proxy not in proxies:
        proxies.append(proxy)
        return True
    return False

def get_user_proxies(user_id):
    return user_proxies.get(user_id, DEFAULT_PROXIES.copy())

def add_user_site(user_id, site):
    sites = user_sites.setdefault(user_id, DEFAULT_SHOPIFY_SITES.copy())
    if site not in sites:
        sites.append(site)
        return True
    return False

def get_user_sites(user_id):
    return user_sites.get(user_id, DEFAULT_SHOPIFY_SITES.copy())

def luhn_check(card_number):
    digits = [int(d) for d in card_number]
    checksum = 0
    oddeven = len(digits) & 1
    for count in range(len(digits)):
        digit = digits[count]
        if not ((count & 1) ^ oddeven):
            digit = digit * 2
            if digit > 9:
                digit -= 9
        checksum += digit
    return (checksum % 10) == 0

async def check_stripe(card, stripe_key):
    if not stripe_key:
        return {'status': 'error', 'message': 'Set Stripe key first via /setstripekey'}
    url = "https://api.stripe.com/v1/tokens"
    data = {
        "card[number]": card["card_number"],
        "card[exp_month]": card["exp_month"],
        "card[exp_year]": card["exp_year"],
        "card[cvc]": card["cvv"],
    }
    headers = {
        "Authorization": f"Bearer {stripe_key}",
        "Content-Type": "application/x-www-form-urlencoded"
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, data=data, headers=headers, timeout=15) as resp:
                resp_json = await resp.json()
                if resp.status == 200 and "id" in resp_json:
                    return {"status": "approved", "message": "Valid card"}
                elif resp.status == 402:
                    return {"status": "declined", "message": "Card declined"}
                elif resp.status == 401:
                    return {"status": "error", "message": "Invalid Stripe Key"}
                else:
                    return {"status": "error", "message": resp_json.get("error", {}).get("message", "Declined")}
    except Exception as e:
        return {"status": "error", "message": str(e)}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    logger.info(f"/start command by user {user.id} @{user.username}")
    await log_activity(context, user.id, user.username or "Unknown", "Started Bot")
    if user.id not in user_proxies:
        user_proxies[user.id] = DEFAULT_PROXIES.copy()
    if user.id not in user_sites:
        user_sites[user.id] = DEFAULT_SHOPIFY_SITES.copy()

    keyboard = [
        [InlineKeyboardButton("Set Keys", callback_data="keys"), InlineKeyboardButton("Commands", callback_data="commands")],
        [InlineKeyboardButton("Proxies", callback_data="proxies"), InlineKeyboardButton("Sites", callback_data="sites")],
        [InlineKeyboardButton("Check Card", callback_data="check"), InlineKeyboardButton("BIN Lookup", callback_data="bin")],
    ]
    if is_admin(user.id):
        keyboard.append([InlineKeyboardButton("Admin Panel", callback_data="admin")])

    await update.message.reply_text(
        f"*CC Checker Bot v{BOT_VERSION}*\nWelcome {user.first_name}!\nID: `{user.id}`",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    # Further callback handling logic here...

async def setstripekey_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    logger.info(f"/setstripekey called by {user.id} @{user.username} with args: {context.args}")
    if not context.args:
        await update.message.reply_text("Use /setstripekey <key>")
        return
    key = context.args[0].strip()
    if not key.startswith("sk_"):
        await update.message.reply_text("Invalid key: Must start with sk_")
        return
    set_user_key(user.id, "stripe", None, key)
    await log_activity(context, user.id, user.username or "Unknown", "Set Stripe Key")
    await update.message.reply_text(f"Stripe key saved: {key[:10]}...")

# Place all other command implementations here following the above structure.

async def test_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info(f"/test called by {update.effective_user.id}")
    await update.message.reply_text("Test command works!")

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"Exception while handling update: {context.error}")
    try:
        if update and hasattr(update, 'message') and update.message:
            await update.message.reply_text("An unexpected error occurred, please try again later.")
    except Exception as e:
        logger.error(f"Error sending error message: {e}")

async def cleanup_webhook():
    async with aiohttp.ClientSession() as session:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/deleteWebhook?drop_pending_updates=true"
        async with session.post(url) as resp:
            if resp.status == 200:
                logger.info("Webhook cleared successfully on startup.")
            else:
                logger.warning(f"Failed to clear webhook on startup with status {resp.status}")

def register_handlers(app):
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("setstripekey", setstripekey_command))
    app.add_handler(CommandHandler("test", test_command))
    app.add_handler(CallbackQueryHandler(button_callback))  
    app.add_error_handler(error_handler)
    # Register other CommandHandlers here

async def main_async():
    await cleanup_webhook()
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    register_handlers(application)
    logger.info(f"Starting bot version {BOT_VERSION}")
    await application.run_polling()

def main():
    try:
        asyncio.run(main_async())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Critical error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
