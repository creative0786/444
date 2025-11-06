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
    Application, CommandHandler, ContextTypes,
)
from playwright.async_api import async_playwright

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# Environment variables and constants
TELEGRAMBOTTOKEN = "8497098081:AAFNQzwZxn-7vhTnR0d5fEUmvzDuQ4UEpGk"
ADMINUSERID = 729412805
BINCODESAPIKEY = "425be7cdecc63d7a92ebe8e9bc6773a0"
PLAYWRIGHT_BROWSERS_PATH = "0"  # Can be set as environment or configured for playwright browsers
STRIPE_SECRET_KEY = None  # Set via /setkey command

# In-memory structures (replace with DB in production)
userapikeys = {}
userproxies = {}
usersites = {}
useractivitylog = []

# --- Helper functions ---

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
    logger.info(f"Activity log: {userid} {username} {action} {details}")

async def notify_admin(context, message):
    try:
        await context.bot.send_message(chat_id=ADMINUSERID, text=message, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Notify admin error: {e}")

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

# Card scraper via regex
def cc_scraper(text):
    regex = r"(\d{13,16})\|(\d{2})\|(\d{2,4})\|(\d{3,4})"
    found = re.findall(regex, text)
    cards = []
    for card in found:
        cards.append({
            "card": card[0],
            "month": card[1],
            "year": card[2],
            "cvv": card[3]
        })
    return cards

# BIN lookup
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

# Luhn check for card number validation
def luhn_check(card_number):
    digits = list(map(int, str(card_number)))
    odd_sum = sum(digits[-1::-2])
    even_sum = sum(sum(divmod(2 * d, 10)) for d in digits[-2::-2])
    return (odd_sum + even_sum) % 10 == 0

# Stripe card check via token creation API
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
            async with session.post(url, data=payload, headers=headers, timeout=20) as resp:
                res = await resp.json()
                if resp.status == 200 and "id" in res:
                    return {"success": True, "message": "Card valid"}
                else:
                    msg = res.get("error", {}).get("message", "Declined")
                    return {"success": False, "error": msg}
        except Exception as e:
            return {"success": False, "error": str(e)}

# Playwright Shopify checkout simulation with proxy support
async def shopify_checkout_simulation(card, month, year, cvv, site_url, proxy=None):
    if PLAYWRIGHT_BROWSERS_PATH and int(PLAYWRIGHT_BROWSERS_PATH) == 0:
        os.environ["PLAYWRIGHT_BROWSERS_PATH"] = "0"
    # Proxy format: http://user:pass@host:port or host:port
    proxy_arg = None
    if proxy:
        proxy_arg = {"server": proxy}
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(proxy=proxy_arg, headless=True)
            context = await browser.new_context()
            page = await context.new_page()
            await page.goto(site_url, timeout=60000)
            # You need to customize below code to your Shopify site cart add & checkout process:
            # For demo, will just wait and close after short delay
            await asyncio.sleep(5)
            await browser.close()
            return {"success": True, "message": f"Simulated checkout on {site_url}"}
    except Exception as e:
        return {"success": False, "message": str(e)}

# --- Telegram Bot commands ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    log_activity(user.id, user.username or "none", "start", "User started")
    if user.id not in userproxies:
        userproxies[user.id] = []
    if user.id not in usersites:
        usersites[user.id] = []
    await update.message.reply_text(
        f"Welcome {user.first_name}!\nCommands:\n/setkey <gateway> <keys>\n/bin <bin>\n/scrape <text>\n"
        "/stripecheck <card|mm|yyyy|cvv>\n/checkout <card|mm|yyyy|cvv>\n/addproxy <ip:port>\n/myproxies\n"
        "/addsite <url>\n/mysites\n/adminstats\n"
    )

async def setkey(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    args = context.args
    if len(args) < 2:
        await update.message.reply_text("Usage: /setkey <gateway> <key(s)>\nStripe: /setkey stripe <apikey>\nPayPal: /setkey paypal <id> <secret>\nRazorpay: /setkey razorpay <id> <secret>")
        return
    gateway = args[0].lower()
    if gateway == "stripe":
        set_user_key(user.id, "stripe", None, args[1])
        await update.message.reply_text("Stripe key saved.")
    elif gateway == "paypal" and len(args) == 3:
        set_user_key(user.id, "paypal", "id", args[1])
        set_user_key(user.id, "paypal", "secret", args[2])
        await update.message.reply_text("PayPal keys saved.")
    elif gateway == "razorpay" and len(args) == 3:
        set_user_key(user.id, "razorpay", "id", args[1])
        set_user_key(user.id, "razorpay", "secret", args[2])
        await update.message.reply_text("Razorpay keys saved.")
    else:
        await update.message.reply_text("Invalid or insufficient keys.")

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
        await update.message.reply_text(f"Proxy {proxy} already exists.")

async def myproxies(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    proxies = userproxies.get(user.id, [])
    if not proxies:
        await update.message.reply_text("No proxies added.")
    else:
        await update.message.reply_text("Your proxies:\n" + "\n".join(proxies))

async def addsite(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not context.args:
        await update.message.reply_text("Usage: /addsite <https://yoursite.com>")
        return
    site = context.args[0]
    if not re.match(r"^https?://", site):
        await update.message.reply_text("Site should start with http:// or https://")
        return
    if add_site(user.id, site):
        log_activity(user.id, user.username or "none", "addsite", site)
        await update.message.reply_text(f"Site {site} added.")
    else:
        await update.message.reply_text(f"Site {site} already exists.")

async def mysites(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    sites = usersites.get(user.id, [])
    if not sites:
        await update.message.reply_text("No sites added.")
    else:
        await update.message.reply_text("Your sites:\n" + "\n".join(sites))

async def binlookup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not context.args:
        await update.message.reply_text("Usage: /bin <bin>")
        return
    bin_num = context.args[0]
    await update.message.reply_text("Checking BIN info...")
    data = await lookup_bin(bin_num)
    if data.get("success"):
        resp = (
            f"BIN: {data['bin']}\nBank: {data['bank']}\nCountry: {data['country']}\n"
            f"Brand: {data['brand']}\nType: {data['type']}\nLevel: {data['level']}\n"
            f"VBV: {data['vbv']}\n3DS: {data['3ds']}\n"
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
        await update.message.reply_text("No valid cards found in the message text.")
        return
    reply = f"Found {len(cards)} cards:\n"
    for c in cards[:10]:
        reply += f"{c['card']}|{c['month']}|{c['year']}|{c['cvv']}\n"
    log_activity(user.id, user.username or "none", "scrapecc", f"{len(cards)} cards scraped")
    await update.message.reply_text(reply)

async def stripecheck(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not context.args:
        await update.message.reply_text("Usage: /stripecheck <card|mm|yyyy|cvv>")
        return
    carddata = " ".join(context.args)
    parts = carddata.split("|")
    if len(parts) != 4:
        await update.message.reply_text("Invalid format! Use card|mm|yyyy|cvv")
        return
    card, mm, yyyy, cvv = parts
    if not luhn_check(card):
        await update.message.reply_text("Invalid card number (Luhn check failed).")
        return
    keys = get_user_keys(user.id)
    msg = await update.message.reply_text("Checking card with Stripe...")
    result = await stripe_check(card, mm, yyyy, cvv, keys.get("stripe"))
    if result["success"]:
        await update.message.reply_text(f"✅ Card approved by Stripe: {result['message']}")
    else:
        await update.message.reply_text(f"❌ Stripe decline: {result['error']}")
    log_activity(user.id, user.username or "none", "stripecheck", card[:6]+"..."+card[-4:])

async def checkout(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not context.args:
        await update.message.reply_text("Usage: /checkout <card|mm|yyyy|cvv>")
        return
    carddata = context.args[0]
    parts = carddata.split("|")
    if len(parts) != 4:
        await update.message.reply_text("Invalid format! Use card|mm|yyyy|cvv")
        return
    card, mm, yyyy, cvv = parts
    if not luhn_check(card):
        await update.message.reply_text("Invalid card number (Luhn check failed)")
        return
    sites = usersites.get(user.id, [])
    proxies = userproxies.get(user.id, [])
    if not sites:
        await update.message.reply_text("No Shopify sites configured. Add with /addsite")
        return
    site = random.choice(sites)
    proxy = random.choice(proxies) if proxies else None
    msg = await update.message.reply_text(f"Attempting checkout on {site} using proxy {proxy}...")
    result = await shopify_checkout_simulation(card, mm, yyyy, cvv, site, proxy)
    if result["success"]:
        await update.message.reply_text(f"✅ Checkout succeeded: {result['message']}")
    else:
        await update.message.reply_text(f"❌ Checkout failed: {result.get('message', 'error')}")
    log_activity(user.id, user.username or "none", "checkout", f"{card[:6]}... with site {site}")

async def adminstats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not is_admin(user.id):
        await update.message.reply_text("Only admins can use this command.")
        return
    total_users = len(userapikeys)
    total_activities = len(useractivitylog)
    total_proxies = sum(len(v) for v in userproxies.values())
    total_sites = sum(len(v) for v in usersites.values())
    recent_logs = useractivitylog[-10:]
    message = (
        f"Admin Stats:\nUsers: {total_users}\nActivities: {total_activities}\n"
        f"Total Proxies: {total_proxies}\nTotal Sites: {total_sites}\n\nRecent Activity:\n"
    )
    for log in recent_logs:
        message += f"{log['username']} [{log['userid']}]: {log['action']} - {log['details']} at {log['timestamp']}\n"
    await update.message.reply_text(message)

# Main entry point
def main():
    app = Application.builder().token(TELEGRAMBOTTOKEN).build()

    handlers = [
        CommandHandler("start", start),
        CommandHandler("setkey", setkey),
        CommandHandler("addproxy", addproxy),
        CommandHandler("myproxies", myproxies),
        CommandHandler("addsite", addsite),
        CommandHandler("mysites", mysites),
        CommandHandler("bin", binlookup),
        CommandHandler("scrape", scrapecc),
        CommandHandler("stripecheck", stripecheck),
        CommandHandler("checkout", checkout),
        CommandHandler("adminstats", adminstats),
    ]

    for handler in handlers:
        app.add_handler(handler)

    logger.info("Bot started polling...")
    app.run_polling()

if __name__ == "__main__":
    main()
