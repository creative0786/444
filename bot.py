#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import logging
import re
import requests
from datetime import datetime
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CommandHandler, CallbackQueryHandler

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Environment variables
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ADMIN_USER_ID = int(os.getenv("ADMIN_USER_ID", "729412805"))
BINCODES_API_KEY = os.getenv("BINCODES_API_KEY")
BOT_VERSION = "3.0"

# Exit if env vars missing
if not TELEGRAM_BOT_TOKEN:
    logger.error("TELEGRAM_BOT_TOKEN environment variable missing")
    sys.exit(1)
if not BINCODES_API_KEY:
    logger.error("BINCODES_API_KEY environment variable missing")
    sys.exit(1)

# Data storage
user_api_keys = {}
user_proxies = {}
user_sites = {}
user_activity_log = []

# Defaults
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

# Helper functions
def is_admin(user_id):
    return user_id == ADMIN_USER_ID

def notify_admin(bot, message):
    try:
        bot.send_message(chat_id=ADMIN_USER_ID, text=message, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Failed to notify admin: {e}")

def log_activity(bot, user_id, username, action, details="", sensitive=""):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    user_activity_log.append({
        "timestamp": timestamp,
        "user_id": user_id,
        "username": username,
        "action": action,
        "details": details,
        "sensitive": sensitive
    })
    msg = f"*User Activity*\n\nUser: @{username}\nID: `{user_id}`\nAction: {action}\nDetails: {details}\nTime: {timestamp}"
    notify_admin(bot, msg)

def get_user_keys(user_id):
    return user_api_keys.get(user_id, {
        "stripe": None, "paypal_id": None, "paypal_secret": None,
        "razorpay_id": None, "razorpay_secret": None
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

def check_stripe(card, stripe_key):
    if not stripe_key:
        return {'status': 'error', 'message': 'Set Stripe key first via /setstripekey'}
    url = "https://api.stripe.com/v1/tokens"
    data = {
        "card[number]": card["card_number"],
        "card[exp_month]": card["exp_month"],
        "card[exp_year]": card["exp_year"],
        "card[cvc]": card["cvv"]
    }
    headers = {
        "Authorization": f"Bearer {stripe_key}",
        "Content-Type": "application/x-www-form-urlencoded"
    }
    resp = requests.post(url, data=data, headers=headers, timeout=15)
    resp_json = resp.json()
    if resp.status_code == 200 and "id" in resp_json:
        return {"status": "approved", "message": "Valid card"}
    elif resp.status_code == 402:
        return {"status": "declined", "message": "Card declined"}
    elif resp.status_code == 401:
        return {"status": "error", "message": "Invalid Stripe Key"}
    else:
        return {"status": "error", "message": resp_json.get("error", {}).get("message", "Declined")}

# Command handlers using sync functions
def start(update, context):
    user = update.effective_user
    log_activity(context.bot, user.id, user.username or "Unknown", "Started Bot")
    if user.id not in user_proxies:
        user_proxies[user.id] = DEFAULT_PROXIES[:]
    if user.id not in user_sites:
        user_sites[user.id] = DEFAULT_SHOPIFY_SITES[:]
    keyboard = [
        [InlineKeyboardButton("Set Keys", callback_data="keys"),
         InlineKeyboardButton("Commands", callback_data="commands")],
        [InlineKeyboardButton("Proxies", callback_data="proxies"),
         InlineKeyboardButton("Sites", callback_data="sites")],
        [InlineKeyboardButton("Check Card", callback_data="check"),
         InlineKeyboardButton("BIN Lookup", callback_data="bin")]
    ]
    if is_admin(user.id):
        keyboard.append([InlineKeyboardButton("Admin Panel", callback_data="admin")])
    update.message.reply_text(
        f"*CC Checker Bot v{BOT_VERSION}*\nWelcome {user.first_name}!\nID: `{user.id}`",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

def button_callback(update, context):
    query = update.callback_query
    query.answer()
    data = query.data
    if data == "keys":
        query.message.reply_text("You clicked: Set Keys")
    elif data == "commands":
        query.message.reply_text("You clicked: Commands")
    elif data == "proxies":
        query.message.reply_text("You clicked: Proxies")
    elif data == "sites":
        query.message.reply_text("You clicked: Sites")
    elif data == "check":
        query.message.reply_text("You clicked: Check Card")
    elif data == "bin":
        query.message.reply_text("You clicked: BIN Lookup")
    elif data == "admin" and is_admin(query.from_user.id):
        query.message.reply_text("Admin Panel")
    else:
        query.message.reply_text("Unknown button clicked.")

def setstripekey_command(update, context):
    user = update.effective_user
    if not context.args:
        update.message.reply_text("Use /setstripekey <key>")
        return
    key = context.args[0].strip()
    if not key.startswith("sk_"):
        update.message.reply_text("Invalid key: Must start with sk_")
        return
    set_user_key(user.id, "stripe", None, key)
    log_activity(context.bot, user.id, user.username or "Unknown", "Set Stripe Key")
    update.message.reply_text(f"Stripe key saved: {key[:10]}...")

# Define other command functions like scrape_command, addproxy_command, etc. with similar sync patterns

def main():
    updater = Updater(TELEGRAM_BOT_TOKEN)
    dispatcher = updater.dispatcher

    dispatcher.add_handler(CommandHandler("start", start))
    dispatcher.add_handler(CommandHandler("setstripekey", setstripekey_command))
    # Add other command handlers here: scrape, addproxy, myproxies, addsite, mysites, kill, bin, mass, etc.
    dispatcher.add_handler(CallbackQueryHandler(button_callback))

    print("Bot starting...")
    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()

