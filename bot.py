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
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# Environment variables and constants
TELEGRAMBOTTOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "8497098081:AAFNQzwZxn-7vhTnR0d5fEUmvzDuQ4UEpGk")
ADMINUSERID = int(os.getenv("ADMIN_USER_ID", "729412805"))
BINCODESAPIKEY = os.getenv("BINCODES_API_KEY", "425be7cdecc63d7a92ebe8e9bc6773a0")
PLAYWRIGHT_BROWSERS_PATH = os.getenv("PLAYWRIGHT_BROWSERS_PATH", "0")

# In-memory storage (replace with persistent DB)
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

# Card scraping regex
def cc_scraper(text):
    regex = r"(\d{13,16})\|(\d{2})\|(\d{2,4})\|(\d{3,4})"
    found = re.findall(regex, text)
    cards = [{"card": c[0], "month": c[1], "year": c[2], "cvv": c[3]} for c in found]
    return cards

# BIN lookup async
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

# Luhn algorithm for card validation
def luhn_check(card_number):
    digits = list(map(int, str(card_number)))
    odd_sum = sum(digits[-1::-2])
    even_sum = sum(sum(divmod(2 * d, 10)) for d in digits[-2::-2])
    return (odd_sum + even_sum) % 10 == 0

# Stripe card check async
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

# Shopify checkout simulation with Playwright
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
            # TODO: customize add-to-cart and checkout flow here
            await asyncio.sleep(5)  # simulate delay
            await browser.close()
            return {"success": True, "message": f"Simulated checkout on {site_url}"}
    except Exception as e:
        return {"success": False, "message": str(e)}

# Telegram command handlers

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    log_activity(user.id, user.username or "none", "start", "User started bot")
    if user.id not in userproxies:
        userproxies[user.id] = []
    if user.id not in usersites:
        usersites[user.id] = []
    welcome_msg = (
        "Welcome to the Premium CC Checker Bot!\n"
        "Available commands:\n"
        "/setkey <gateway> <keys>\n"
        "/bin <bin>\n"
        "/scrape <cc data>\n"
        "/stripecheck <card|mm|yyyy|cvv>\n"
        "/checkout <card|mm|yyyy|cvv>\n"
        "/addproxy <ip:port>\n"
        "/myproxies\n"
        "/addsite <url>\n"
        "/mysites\n"
        "/adminstats (admin only)\n"
    )
    await update.message.reply_text(welcome_msg)

async def setkey(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    args = context.args
    if len(args) < 2:
        await update.message.reply_text(
            "Usage: /setkey <gateway> <key(s)>\n"
            "Example:\n"
            "/setkey stripe sk_test_xxx\n"
            "/setkey paypal client_id client_secret\n"
            "/setkey razorpay id secret"
        )
        return
    gateway = args[0].lower()
    if gateway == "stripe":
        set_user_key(user.id, "stripe", None, args[1])
        await update.message.reply_text("Stripe API key set.")
    elif gateway == "paypal":
        if len(args) < 3:
            await update.message.reply_text("Please provide PayPal client id and secret.")
            return
        set_user_key(user.id, "paypal", "id", args[1])
        set_user_key(user.id, "paypal", "secret", args[2])
        await update.message.reply_text("PayPal keys set.")
    elif gateway == "razorpay":
        if len(args) < 3:
            await update.message.reply_text("Please provide Razorpay id and secret.")
            return
        set_user_key(user.id, "razorpay", "id", args[1])
        set_user_key(user.id, "razorpay", "secret", args[2])
        await update.message.reply_text("Razorpay keys set.")
    else:
        await update.message.reply_text("Invalid gateway. Use stripe, paypal or razorpay.")

async def addproxy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not context.args:
        await update.message.reply_text("Usage: /addproxy <ip:port>")
        return
    proxy = context.args[0]
    if add_proxy(user.id, proxy):
        log_activity(user.id, user.username or "none", "addproxy", proxy)
        await update.message.reply_text(f"Proxy {proxy} added.")
    else:
        await update.message.reply_text("Proxy already exists.")

async def myproxies(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    proxies = userproxies.get(user.id, [])
    if proxies:
        await update.message.reply_text("Your proxies:\n" + "\n".join(proxies))
    else:
        await update.message.reply_text("No proxies added.")

async def addsite(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not context.args:
        await update.message.reply_text("Usage: /addsite <https://example.com>")
        return
    site = context.args[0]
    if not re.match(r"^https?://", site):
        await update.message.reply_text("Site URL must start with http:// or https://")
        return
    if add_site(user.id, site):
        log_activity(user.id, user.username or "none", "addsite", site)
        await update.message.reply_text(f"Site {site} added.")
    else:
        await update.message.reply_text("Site already exists.")

async def mysites(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    sites = usersites.get(user.id, [])
    if sites:
        await update.message.reply_text("Your sites:\n" + "\n".join(sites))
    else:
        await update.message.reply_text("No sites added.")

async def binlookup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not context.args:
        await update.message.reply_text("Usage: /bin <bin>")
        return
    bin_num = context.args[0]
    await update.message.reply_text("Looking up BIN info...")
    data = await lookup_bin(bin_num)
    if data.get("success"):
        resp = (
            f"BIN: {data['bin']}\nBank: {data['bank']}\nCountry: {data['country']}\n"
            f"Brand: {data['brand']}\nType: {data['type']}\nLevel: {data['level']}\n"
            f"VBV: {data['vbv']}\n3DS: {data['3ds']}"
        )
    else:
        resp = "BIN not found or invalid."
    log_activity(user.id, user.username or "none", "binlookup", bin_num)
    await update.message.reply_text(resp)

async def scrapecc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    text = update.message.text
    cards = cc_scraper(text)
    if not cards:
        await update.message.reply_text("No valid cards found in input.")
        return
    reply = f"Found {len(cards)} cards:\n"
    for c in cards[:10]:
        reply += f"{c['card']}|{c['month']}|{c['year']}|{c['cvv']}\n"
    log_activity(user.id, user.username or "none", "scrapecc", f"{len(cards)} cards found")
    await update.message.reply_text(reply)

async def stripecheck(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not context.args:
        await update.message.reply_text("Usage: /stripecheck <card|mm|yyyy|cvv>")
        return
    data = " ".join(context.args)
    parts = data.split("|")
    if len(parts) != 4:
        await update.message.reply_text("Invalid format. Use card|mm|yyyy|cvv")
        return
    card, mm, yyyy, cvv = parts
    if not luhn_check(card):
        await update.message.reply_text("Invalid card number (Luhn check failed).")
        return
    keys = get_user_keys(user.id)
    msg = await update.message.reply_text("Checking card with Stripe...")
    result = await stripe_check(card, mm, yyyy, cvv, keys.get("stripe"))
    if result["success"]:
        await update.message.reply_text(f"✅ Stripe check approved: {result['message']}")
    else:
        await update.message.reply_text(f"❌ Stripe decline: {result['error']}")
    log_activity(user.id, user.username or "none", "stripecheck", card[:6]+"..."+card[-4:])

async def checkout(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not context.args:
        await update.message.reply_text("Usage: /checkout <card|mm|yyyy|cvv>")
        return
    data = context.args[0]
    parts = data.split("|")
    if len(parts) != 4:
        await update.message.reply_text("Invalid format. Use card|mm|yyyy|cvv")
        return
    card, mm, yyyy, cvv = parts
    if not luhn_check(card):
        await update.message.reply_text("Invalid card number (Luhn check failed).")
        return
    sites = usersites.get(user.id, [])
    proxies = userproxies.get(user.id, [])
    if not sites:
        await update.message.reply_text("No Shopify sites configured. Use /addsite")
        return
    site = random.choice(sites)
    proxy = random.choice(proxies) if proxies else None
    msg = await update.message.reply_text(f"Running checkout simulation on {site} with proxy {proxy}...")
    result = await shopify_checkout_simulation(card, mm, yyyy, cvv, site, proxy)
    if result["success"]:
        await update.message.reply_text(f"✅ Checkout successful: {result['message']}")
    else:
        await update.message.reply_text(f"❌ Checkout failed: {result.get('message', 'unknown error')}")
    log_activity(user.id, user.username or "none", "checkout", f"{card[:6]}... via {site}")

async def adminstats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not is_admin(user.id):
        await update.message.reply_text("Admin only command.")
        return
    total_users = len(userapikeys)
    total_activities = len(useractivitylog)
    total_proxies = sum(len(v) for v in userproxies.values())
    total_sites = sum(len(v) for v in usersites.values())
    recent_logs = useractivitylog[-10:]
    msg = (
        f"Admin Stats:\nUsers: {total_users}\nTotal Activities: {total_activities}\n"
        f"Total Proxies: {total_proxies}\nTotal Sites: {total_sites}\n\nRecent Activity:\n"
    )
    for log in recent_logs:
        msg += f"{log['username']} [{log['userid']}]: {log['action']} - {log['details']} at {log['timestamp']}\n"
    await update.message.reply_text(msg)

# Main function to run bot
def main():
    application = Application.builder().token(TELEGRAMBOTTOKEN).build()

    # Register all handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("setkey", setkey))
    application.add_handler(CommandHandler("addproxy", addproxy))
    application.add_handler(CommandHandler("myproxies", myproxies))
    application.add_handler(CommandHandler("addsite", addsite))
    application.add_handler(CommandHandler("mysites", mysites))
    application.add_handler(CommandHandler("bin", binlookup))
    application.add_handler(CommandHandler("scrape", scrapecc))
    application.add_handler(CommandHandler("stripecheck", stripecheck))
    application.add_handler(CommandHandler("checkout", checkout))
    application.add_handler(CommandHandler("adminstats", adminstats))

    logger.info("Bot started polling...")
    application.run_polling()

if __name__ == "__main__":
    main()
