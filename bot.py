#!/usr/bin/env python3
# coding: utf-8

import os
import sys
import re
import random
import logging
import asyncio
import aiohttp
from datetime import datetime
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
)
from playwright.async_api import async_playwright

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Environment variables and constants
TELEGRAMBOTTOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "8497098081:AAFNQzwZxn-7vhTnR0d5fEUmvzDuQ4UEpGk")
ADMINUSERID = int(os.getenv("ADMIN_USER_ID", "729412805"))
BINCODESAPIKEY = os.getenv("BINCODES_API_KEY", "425be7cdecc63d7a92ebe8e9bc6773a0")
PLAYWRIGHT_BROWSERS_PATH = os.getenv("PLAYWRIGHT_BROWSERS_PATH", "0")

# In-memory data stores (Replace with persistent DB for production)
userapikeys = {}
userproxies = {}
usersites = {}
useractivitylog = []

def is_admin(user_id):
    return user_id == ADMINUSERID

def log_activity(userid, username, action, details):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    useractivitylog.append({
        "timestamp": timestamp,
        "userid": userid,
        "username": username,
        "action": action,
        "details": details
    })
    logger.info(f"Activity logged: {userid} {username} {action} {details}")

async def notify_admin(context, message):
    try:
        await context.bot.send_message(chat_id=ADMINUSERID, text=message, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Error notifying admin: {e}")

def add_proxy(userid, proxy):
    proxies = userproxies.setdefault(userid, [])
    if proxy not in proxies:
        proxies.append(proxy)
        return True
    return False

def add_site(userid, site):
    sites = usersites.setdefault(userid, [])
    if site not in sites:
        sites.append(site)
        return True
    return False

def set_user_key(userid, gateway, keytype, value):
    keys = userapikeys.setdefault(userid, {
        "stripe": None,
        "paypalid": None,
        "paypalsecret": None,
        "razorpayid": None,
        "razorpaysecret": None,
    })
    if gateway == "stripe":
        keys["stripe"] = value
    elif gateway == "paypal":
        if keytype == "id":
            keys["paypalid"] = value
        elif keytype == "secret":
            keys["paypalsecret"] = value
    elif gateway == "razorpay":
        if keytype == "id":
            keys["razorpayid"] = value
        elif keytype == "secret":
            keys["razorpaysecret"] = value

def get_user_keys(userid):
    return userapikeys.get(userid, {
        "stripe": None,
        "paypalid": None,
        "paypalsecret": None,
        "razorpayid": None,
        "razorpaysecret": None,
    })

# Card scraper helper
def cc_scraper(text):
    regex = r"(\d{13,16})\|(\d{2})\|(\d{2,4})\|(\d{3,4})"
    found = re.findall(regex, text)
    cards = [{"card": c[0], "month": c[1], "year": c[2], "cvv": c[3]} for c in found]
    return cards

# BIN lookup function
async def lookup_bin(bin_num):
    url = f"https://api.bincodes.com/bin?format=json&apikey={BINCODESAPIKEY}&bin={bin_num}"
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url, timeout=10) as resp:
                if resp.status != 200:
                    return {"success": False, "error": f"HTTP {resp.status}"}
                data = await resp.json()
                if data.get("valid"):
                    return {
                        "success": True,
                        "bin": bin_num,
                        "bank": data.get("bank", "N/A"),
                        "country": data.get("country", "N/A"),
                        "brand": data.get("brand", "N/A"),
                        "type": data.get("type", "N/A"),
                        "level": data.get("level", "N/A"),
                        "vbv": "VBV" if "STANDARD" not in str(data.get("level", "")).upper() else "Non-VBV",
                        "3ds": "Yes" if "VBV" in data.get("level", "").upper() else "No",
                    }
                else:
                    return {"success": False, "bin": bin_num}
        except Exception as e:
            return {"success": False, "error": str(e)}

# Luhn check utility
def luhn_check(card_number):
    digits = list(map(int, str(card_number)))
    odd_sum = sum(digits[-1::-2])
    even_sum = sum(sum(divmod(2 * d, 10)) for d in digits[-2::-2])
    return (odd_sum + even_sum) % 10 == 0

# Stripe check
async def stripe_check(card, month, year, cvv, key):
    if not key:
        return {"success": False, "error": "Stripe key not set"}
    url = "https://api.stripe.com/v1/tokens"
    payload = {
        "card[number]": card,
        "card[exp_month]": month,
        "card[exp_year]": year,
        "card[cvc]": cvv
    }
    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/x-www-form-urlencoded"
    }
    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(url, data=payload, headers=headers, timeout=15) as resp:
                res = await resp.json()
                if resp.status == 200 and "id" in res:
                    return {"success": True, "message": "Card valid"}
                else:
                    msg = res.get("error", {}).get("message", "Declined")
                    return {"success": False, "error": msg}
        except Exception as e:
            return {"success": False, "error": str(e)}

# Playwright checkout simulation with proxy support
async def shopify_checkout_simulation(card, month, year, cvv, site_url, proxy=None):
    if PLAYWRIGHT_BROWSERS_PATH and int(PLAYWRIGHT_BROWSERS_PATH) == 0:
        os.environ["PLAYWRIGHT_BROWSERS_PATH"] = "0"
    proxy_arg = None
    if proxy:
        proxy_arg = {"server": proxy}
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(proxy=proxy_arg, headless=True)
            context = await browser.new_context()
            page = await context.new_page()
            await page.goto(site_url, timeout=60000)
            # Actual Shopify add to cart and checkout process to be implemented here
            await asyncio.sleep(5)  # demo wait
            await browser.close()
            return {"success": True, "message": f"Simulated checkout on {site_url}"}
    except Exception as e:
        return {"success": False, "message": str(e)}

# Telegram commands:

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    log_activity(user.id, user.username or "none", "start", "User started")
    if user.id not in userproxies:
        userproxies[user.id] = []
    if user.id not in usersites:
        usersites[user.id] = []
    await update.message.reply_text(
        "Welcome to CC Checker Bot! Available commands:\n"
        "/setkey <gateway> <key(s)>\n"
        "/bin <binnumber>\n"
        "/scrape <card data>\n"
        "/stripecheck <card|mm|yyyy|cvv>\n"
        "/checkout <card|mm|yyyy|cvv>\n"
        "/addproxy <ip:port>\n"
        "/myproxies\n"
        "/addsite <url>\n"
        "/mysites\n"
        "/adminstats (admin only)\n"
    )

# Add all other handlers here like setkey, addproxy, myproxies, etc...

# Main entrypoint
def main():
    app = Application.builder().token(TELEGRAMBOTTOKEN).build()

    app.add_handler(CommandHandler("start", start))
    # Add other handlers

    logger.info("Bot started polling...")
    app.run_polling()

if __name__ == "__main__":
    main()
