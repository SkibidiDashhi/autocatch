import sqlite3
import random
import string
import asyncio
from datetime import datetime, timedelta
from telethon import TelegramClient, events

# 🔧 CONFIGURATION
API_ID = '27577659'
API_HASH = '597f9920ee4168c320472f0d8005029a'
BOT_TOKEN = '8314114351:AAFRGFwaB2klPTdXp6CigU5NJpE3vECcEzU'  # Put your bot token here
ADMIN_IDS = [6593519190, 5496411145]  # List of authorized Admin IDs
APPROVED_GROUP_ID = -1002839273673    # The only group where the bot works

# 🗄️ DATABASE SETUP
conn = sqlite3.connect('license_database.db', check_same_thread=False)
c = conn.cursor()

c.execute('''CREATE TABLE IF NOT EXISTS keys
             (key TEXT PRIMARY KEY, duration_days REAL, used_by INTEGER, used_at TIMESTAMP)''')
c.execute('''CREATE TABLE IF NOT EXISTS active_users
             (user_id INTEGER PRIMARY KEY, expires_at TIMESTAMP)''')
conn.commit()

# Initialize the Client
bot = TelegramClient('key_manager_bot', API_ID, API_HASH)

def generate_key_string():
    """Generates a random key format: VIP-XXXX-XXXX-XXXX"""
    parts = [''.join(random.choices(string.ascii_uppercase + string.digits, k=4)) for _ in range(3)]
    return f"VIP-{parts[0]}-{parts[1]}-{parts[2]}"

def generate_trial_key_string():
    """Generates a random key format: TRIAL-XXXX-XXXX-XXXX"""
    parts = [''.join(random.choices(string.ascii_uppercase + string.digits, k=4)) for _ in range(3)]
    return f"TRIAL-{parts[0]}-{parts[1]}-{parts[2]}"

def is_approved_context(event):
    """Checks if the command is sent in the approved group OR by an admin"""
    return event.chat_id == APPROVED_GROUP_ID or event.sender_id in ADMIN_IDS

@bot.on(events.NewMessage(pattern=r'(?i)^/start(?:@\w+)?'))
async def start_handler(event):
    if not is_approved_context(event):
        return
    
    await event.reply(
        "👋 Welcome to the Auto-Catcher License Bot!\n\n"
        "Commands:\n"
        "• `/redeem <KEY>` - Activate your subscription\n"
        "• `/status` - Check your active subscription\n\n"
        "*(Admin) • `/gen <amount> <days>` - Generate keys*\n"
        "*(Admin) • `/trial <amount>` - Generate 2-hour trial keys*\n"
        "*(Admin) • `/auth <user_id> <days>` - Directly authorize user*"
    )

@bot.on(events.NewMessage(pattern=r'(?i)^/gen(?:@\w+)?\s+(\d+)\s+(-?\d+)'))
async def gen_keys_handler(event):
    """Admin command to generate keys. Usage: /gen 5 30"""
    if event.sender_id not in ADMIN_IDS:
        return await event.reply("❌ Access Denied.")

    try:
        amount = int(event.pattern_match.group(1))
        days = int(event.pattern_match.group(2))

        # Security & Overflow checks
        if amount <= 0 or days <= 0:
            return await event.reply("⚠️ Amount and days must be greater than 0.")
        if amount > 50:
            return await event.reply("⚠️ Maximum 50 keys at once to prevent spam.")
        if days > 3650:
            return await event.reply("⚠️ Maximum duration is 3650 days (10 years) to prevent database overflow.")

        new_keys = []
        for _ in range(amount):
            key = generate_key_string()
            c.execute("INSERT INTO keys (key, duration_days, used_by) VALUES (?, ?, NULL)", (key, days))
            new_keys.append(key)
        
        conn.commit()

        key_list = "\n".join([f"`{k}`" for k in new_keys])
        await event.reply(
            f"✅ **Generated {amount} Keys ({days} Days)**\n\n{key_list}\n\n"
            f"Share these with your users. They can use `/redeem KEY` here."
        )
    except Exception as e:
        await event.reply(f"❌ Error: {e}")

@bot.on(events.NewMessage(pattern=r'(?i)^/trial(?:@\w+)?\s+(\d+)'))
async def trial_keys_handler(event):
    """Admin command to generate 2-hour trial keys. Usage: /trial 5"""
    if event.sender_id not in ADMIN_IDS:
        return await event.reply("❌ Access Denied.")

    try:
        amount = int(event.pattern_match.group(1))

        if amount <= 0:
            return await event.reply("⚠️ Amount must be greater than 0.")
        if amount > 50:
            return await event.reply("⚠️ Maximum 50 keys at once to prevent spam.")

        new_keys = []
        trial_duration_days = 2.0 / 24.0

        for _ in range(amount):
            key = generate_trial_key_string()
            c.execute("INSERT INTO keys (key, duration_days, used_by) VALUES (?, ?, NULL)", (key, trial_duration_days))
            new_keys.append(key)
        
        conn.commit()

        key_list = "\n".join([f"`{k}`" for k in new_keys])
        await event.reply(
            f"🎁 **Generated {amount} Trial Keys (2 Hours)**\n\n{key_list}\n\n"
            f"Share these with your users. They can use `/redeem KEY` here."
        )
    except Exception as e:
        await event.reply(f"❌ Error: {e}")

@bot.on(events.NewMessage(pattern=r'(?i)^/auth(?:@\w+)?\s+(\d+)\s+(\d+)'))
async def auth_user_handler(event):
    """Admin command to directly authorize a user. Usage: /auth <user_id> <days>"""
    if event.sender_id not in ADMIN_IDS:
        return await event.reply("❌ Access Denied.")

    try:
        target_user_id = int(event.pattern_match.group(1))
        duration_days = int(event.pattern_match.group(2))

        # Security & Overflow checks
        if duration_days <= 0:
            return await event.reply("⚠️ Duration must be greater than 0.")
        if duration_days > 3650:
            return await event.reply("⚠️ Maximum duration is 3650 days (10 years) to prevent database overflow.")

        now = datetime.now()

        # Check if the user already has an active subscription
        c.execute("SELECT expires_at FROM active_users WHERE user_id = ?", (target_user_id,))
        user_data = c.fetchone()

        # Calculate new expiry time (adding to current time if active)
        try:
            if user_data and datetime.fromisoformat(user_data[0]) > now:
                current_expiry = datetime.fromisoformat(user_data[0])
                new_expiry = current_expiry + timedelta(days=duration_days)
            else:
                new_expiry = now + timedelta(days=duration_days)
        except OverflowError:
            # If the calculation exceeds Python's limits, cap it
            new_expiry = datetime.max

        # Directly update the active_users table
        c.execute("INSERT OR REPLACE INTO active_users (user_id, expires_at) VALUES (?, ?)", (target_user_id, new_expiry.isoformat()))
        conn.commit()

        await event.reply(
            f"✅ **DIRECT AUTHORIZATION SUCCESSFUL!** ✅\n\n"
            f"👤 **Target User ID:** `{target_user_id}`\n"
            f"⏳ **Added Time:** {duration_days} Days\n"
            f"📅 **New Expiry:** {new_expiry.strftime('%Y-%m-%d %H:%M:%S')}\n\n"
            f"The user's Auto-Catcher is now active."
        )
    except ValueError:
        await event.reply("❌ **Error:** Please make sure you are typing numbers for the ID and days. Example: `/auth 123456789 30`")
    except Exception as e:
        await event.reply(f"❌ Error: {e}")

@bot.on(events.NewMessage(pattern=r'(?i)^/redeem(?:@\w+)?\s+(.+)'))
async def redeem_handler(event):
    """User command to redeem a key"""
    if not is_approved_context(event):
        return await event.reply("❌ **Error:** You can only redeem keys in the approved group.")

    user_id = event.sender_id
    key_input = event.pattern_match.group(1).strip()

    c.execute("SELECT duration_days FROM keys WHERE key = ? AND used_by IS NULL", (key_input,))
    result = c.fetchone()

    if not result:
        return await event.reply("❌ **Invalid or Already Used Key.**\nPlease check for typos or contact support.")

    duration_days = result[0]
    now = datetime.now()

    c.execute("SELECT expires_at FROM active_users WHERE user_id = ?", (user_id,))
    user_data = c.fetchone()

    # Overflow-safe addition
    try:
        if user_data and datetime.fromisoformat(user_data[0]) > now:
            current_expiry = datetime.fromisoformat(user_data[0])
            new_expiry = current_expiry + timedelta(days=duration_days)
        else:
            new_expiry = now + timedelta(days=duration_days)
    except OverflowError:
        # If the generated key is completely corrupted, cap it at max allowed Python date
        new_expiry = datetime.max

    c.execute("UPDATE keys SET used_by = ?, used_at = ? WHERE key = ?", (user_id, now.isoformat(), key_input))
    c.execute("INSERT OR REPLACE INTO active_users (user_id, expires_at) VALUES (?, ?)", (user_id, new_expiry.isoformat()))
    conn.commit()

    if duration_days < 1:
        added_time_str = f"{int(round(duration_days * 24))} Hours"
    elif duration_days >= 3650:
        added_time_str = "Lifetime / Max Limit"
    else:
        added_time_str = f"{int(duration_days)} Days"

    await event.reply(
        f"🎉 **ACTIVATION SUCCESSFUL!** 🎉\n\n"
        f"Your Auto-Catcher access has been unlocked.\n"
        f"⏳ **Added Time:** {added_time_str}\n"
        f"📅 **New Expiry:** {new_expiry.strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        f"Your Userbot will now automatically recognize your active status!"
    )

@bot.on(events.NewMessage(pattern=r'(?i)^/status(?:@\w+)?'))
async def status_handler(event):
    """Check subscription status"""
    if not is_approved_context(event):
        return

    user_id = event.sender_id
    c.execute("SELECT expires_at FROM active_users WHERE user_id = ?", (user_id,))
    result = c.fetchone()

    if not result:
        return await event.reply("🔴 **No Active Subscription.**\nYou do not have an active Auto-Catcher license.")

    expires_at = datetime.fromisoformat(result[0])
    now = datetime.now()
    
    if expires_at > now:
        time_left = expires_at - now
        days_left = time_left.days
        hours_left = time_left.seconds // 3600
        mins_left = (time_left.seconds // 60) % 60
        
        if days_left > 0:
            time_left_str = f"{days_left} Days, {hours_left} Hours"
        else:
            time_left_str = f"{hours_left} Hours, {mins_left} Mins"

        await event.reply(
            f"🟢 **Subscription Active**\n\n"
            f"📅 **Expires:** {expires_at.strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"⏳ **Time Left:** {time_left_str}"
        )
    else:
        await event.reply("🔴 **Subscription Expired.**\nYour license has expired. Please purchase a new key.")

# 🚀 Asynchronous Startup Method
async def main():
    await bot.start(bot_token=BOT_TOKEN)
    print("🤖 Key Manager Bot is running...")
    await bot.run_until_disconnected()

if __name__ == '__main__':
    asyncio.run(main())
