import asyncio
import json
import os
import random
import time
from datetime import datetime, timedelta
from io import BytesIO
import hashlib
import tempfile
import re

from telethon import TelegramClient, events
from telethon.tl.types import User, MessageEntityPre, InputMediaUploadedPhoto
from telethon.tl.functions.messages import GetMessagesRequest
from telethon.tl.functions.channels import GetParticipantsRequest
from telethon.tl.types import ChannelParticipantsSearch


class UltimateCharacterCatcherBot:
    def __init__(self):
        # 🔧 BASIC CONFIGURATION
        self.api_id = '20230268'
        self.api_hash = '72c3bf193f58a0e4b83bfd2b78dadf8c'
        self.session_name = 'autocatch'

        # 👑 ADMIN SYSTEM
        self.admin_users = {5496411145, 7902256131}
        self.bot_owner_id = 5496411145

        # 🚨 CONTROL SYSTEM
        self.stop_auto_reply_flag = False
        self.skip_queue_flag = False
        self.paused = False

        # 🗑️ AUTO DELETE SYSTEM
        self.auto_delete_enabled = False
        self.auto_delete_targets = {}  # chat_id: {target_user_ids}
        self.deleted_messages_count = 0
        self.auto_delete_start_time = None
        self.auto_delete_mode = {}  # 'user' or 'group'
        self.message_monitor_tasks = {}

        # ⚡ RATE LIMITING
        self.rate_limits = {
            'last_message_time': 0,
            'messages_in_last_second': 0,
            'max_messages_per_second': 3,
            'cooldown_between_users': 0.5,
            'last_user_reply_time': {},
            'consecutive_reply_count': {},
            'max_consecutive_replies': 50,
            'group_cooldown': {},
            'min_group_cooldown': 0.3
        }

        # ⚡ TIMING
        self.auto_reply_delay = 4.0
        self.reply_index = 0
        self.last_reply_times = {}
        self.user_message_times = {}

        # ======== 🎮 CHARACTER CATCHER CONFIG ========
        self.character_bot_username = '@Character_Catcher_Bot'
        self.grab_bot_username = '@Waifu_Grabber_Bot'
        self.guess_bot_username = '@Husbando_Grabber_Bot'
        self.cheats_bot_username = '@BikaWaifuCheatBot'

        self.character_catcher_active = False
        self.character_catcher_stats = {
            'total_spawns': 0,
            'successful_catches': 0,
            'failed_catches': 0,
            'api_errors': 0,
            'last_catch': None,
            'cheats_bot_requests': 0,
            'cheats_bot_success': 0,
            'processing_time': [],
            'cached_names': 0,
            'missed_names': 0,
            'duplicates_skipped': 0,
            'pending_requests': 0,
            'auto_deleted_catch_messages': 0  # NEW: Track auto-deleted catch messages
        }

        self.character_process_queue = []
        self.is_processing_character = False
        self.cheats_bot_waiting_responses = {}
        self.forwarded_messages = {}
        # FIFO queue of pending requests sent to cheats bot.
        # Each item: {'photo_hash', 'request_id', 'timestamp', 'chat_title'}
        self.cheats_bot_pending_queue = []

        # Photo hash
        self.photo_hashes = {}
        self.photo_hash_ttl = 300

        # Speed settings
        self.forward_delay = 0.05
        self.catch_delay = 0.1
        self.cheats_bot_timeout = 8

        # Character name cache
        self.character_name_cache = {}
        self.cache_size_limit = 100
        self.cache_hits = 0
        self.cache_misses = 0

        # ======== 💬 AUTO-REPLY SYSTEM ========
        self.is_replying = False
        self.pending_replies = []
        self.auto_reply_groups = set()
        self.auto_reply_users = set()
        self.excluded_users = set()

        # Reply messages
        self.reply_messages = [
            "ဟုတ်ပါပြီဖာသည်မသား", "ဖြည်းဖြည်းလန့်တာ", "စတာပါမစဲပါနဲ့ဟပျင်းသာ",
            "စမ်းချင်သလိုစမ်းမောင်ဘဂျမ်းပဲငါက", "ဘာလည်းလီးလားနှမလိုး",
            "သိပါပီမင်းမေသူများလိုးတဲ့ကိစ္စ", "မင်းအမေကိုဇောက်ထိုးလိုးပြ",
            "ငါလိုးမရဲ့သားနဲ့တော့ပြဿနာပဲ", "ဟျောင့်မင်းမေမင်းပြေးလိုးလိုက်ဒါဆို",
            "ပြောမရလဲကိုက်ကွာမအေလိုး", "ဗျဗျဦးဦးမအေလိုး", "အပျင်းမပြေဘူးလိုင်းပိတ်ရိုက်",
            "မအေလိုးလေးအသေကိုက်လေ", "ဖာသည်မသားလီးလား", "ဘာလားပဲစောက်တောသား",
            "မအေလိုးကိုက်", "ဘာလည်းမလုပ်နဲ့အာဖြဲပြီးချီးပါထည့်ပေးလိုက်မယ်",
            "ဟဖာသည်မသားလေး", "ဘာလည်းငါလိုးမသား", "မင်းအမေငါလိုး",
            "ဟဖာသည်မသား", "သိဘူးယေဆက်ကိုက်", "မင်းနှမစောက်ပက်",
            "မင်းအမေဖာသည်မ", "ဂရု့မစိုက်ဘူးဆဲမှာပဲမင်းအမေငါလိုး",
            "ဟုတ်ကဲ့ပါဖာသည်မသား", "ငါလိုးမသားမင်းဗျာများနေတာလား",
            "မင်းမေလိုးနေလို့လား", "ဟျောင့်ငါလိုးမအမျိုးယုတ်",
            "မသိဘူးဆဲမှာပဲဟျောင့်", "အက်တာဆိုကိုမေကိုလိုးလိုက်လေ",
            "ဘာနေနေကိုက်", "ခွေးသူတောင်းစား", "လန့်တာ", "အီးယား",
            "မင်းမေလိုးဖြစ်တာလား", "ဒေါပွနေတာလား", "မသိဘူးမအေလိုးဘာပြောတာ?",
            "ဟျောင့်ကိုမေကိုလိုးမျိုး", "ဖာသည်မသားလေး", "စောက်ပတ်ယားပြတာလား",
            "ဆက်ကိုက်", "မသိချင်ဘူးကွာ", "ပြိတ္တာကောင်",
            "ဟျောင်ဖာသည်မသား စောက်သုံးမကျတဲ့ကောင်",
            "ကိုက်မှာဆိုကိုက်မအေလိုးခွေး မသား",
            "ငါကမင်းကို လူလိုသူလိုအသိဉာဏ်တိုးအောင် ပြောပြတာကို မင်းကခွေးလိုပြန်ဟောင်ပြနေတော့လည်း ငါကတော့ ဘာမှမတတ်နိုင်ဘူး",
            "မှန်ထောင်ပြီးပြောနေတာလားမင်းငါလိုးမစောက‌်ဘောမနဲ့တော့လက်ညိုးမထောင်နဲ့ဒီဇမ္ဘူတစ်ခွင်မှာဖာသည်မသားဆိုလို့မင်းပဲရှိတယ်",
            "တင်းလာပြီငါလိုးမသားမင်းထိုးမှာလား",
            "စောက်ကုလားမစောက်စကားကိုများတယ် တင်ကြောကို ‌လီးကြောနဲ့ထိုးထည့်လိုက်လို့ စအိုမှာသွေးကွက်ကွက်လန်သွားမယ်ဖာသည်မသမီး",
            "ကြာပွတ်နဲ့တင်ကြောနဲ့မိတ်ဆက်ပေးလိုက်လို့ အမေရိကန်နစ်ဂါဘ၀ကို မျက်စိမှိတ်ဒူးမှိတ်ခံစားသွားမယ်",
            "မင်းအမေကို အောက်ထပ်ကငရဲမင်းက မီးပူသံလျပ်နဲ့ တက်ထိုးတာ မင်းအမေသေနေပြီ",
            "ဖာသည်မသားကလဲဆက်တိုက်ကိုက်ဟဘာလို့နားနားသွား တာတုန်းတပည့်ကတော့",
            "စောက်ကုလားမကလဲဝက်သားမစားရလို့စိတ်ညစ်ပြတာလားဟုတ်လား",
            "ထိရောက်မှုလဲမရှိဖြစ်ထွန်းမှုလဲမရှိ ညဏ်ရည်လဲမမှီ",
            "မင်းပြေးတိုင်းငါကလိုက်စရာလားဖာသည်မ",
            "အရှုံးပေးတာလားဖာသည်မသားလေး",
            "စောက်ဖာသည်မသားဘာနား တာလည်း",
            "မင်းအမေဝက်ကုလားတက်လိုးခံရပြီ စောက်သုံးမကျတဲ့ခွေး",
            "မင်းကိုနိုင်ဖို့ ငါ့ရဲ့ အင်အား 1% တောင်သုံးစရာမလိုဘူး",
            "မင်းလိုကောင်ဆဲရတာ ရပ်ကွက်ထဲကလေးတစ်ယောက်စီကပါးရိုက်ပြီးမုန့်လုရတာ‌ထက်တောင်လွယ်နေသေးတယ်",
            "မအူအလည်ဖြစ်နေတာလား ကိုမေကိုလိုးစောက်ခြောက်",
            "ငါလိုးမ‌သားစောက်ခွက်က တစ်ရေးနိုးလို့ထကြည့်ရင်တောင် ၅ပြား မတန်ဘူး",
            "မအေလိုးစောက်ပေါ အရင်လို စောက်နုပဲလား",
            "မအေလိုးလေးအသည်းအသန်ခဲမှန်ကိုက်လေ ဘာလဲအားလျော့တာလား",
            "နံရိုးချိုးခံရမယ်ဘောမ ကိုက်ဆိုကိုက်လိုက်", "စိတ်ဓာတ်ကျတာလားဘောမ",
            "ခွေးမသားမင်းကိုက်လေလီးလုပ်နေတာလား ",
            "မအေလိုးမင်းမေစောက်ပက်မင်းယက်ပြစမ်းကွာဖာသည်မသား",
            " မအေလိုးဖာသည်မသားကိုက်လေလီးလုပ်တာလား ",
            "ကိုမေ‌ကိုလိုးရေမင်းမေစောက်ဖုတ်မင်းပြန်ယက်နေတာလားဟျောင့်"
        ]

        # ======== 🔵 AUTO MENTION SYSTEM ========
        self.auto_mention_active = {}
        self.auto_mention_targets = {}
        self.auto_mention_nicknames = {}
        self.auto_mention_intervals = {}
        self.auto_mention_counters = {}
        self.auto_mention_loops = {}
        self.mention_user_data = {}
        self.mention_messages = {}
        self.auto_mention_reply_index = {}

        # Default settings
        self.default_mention_interval = 30

        # Client
        self.client = None

        # Load saved data
        self.load_data()

        print(f"👑 Admin Users: {self.admin_users}")
        print(f"⚡ Default Auto-Reply Delay: {self.auto_reply_delay} seconds")
        print(f"🗑️ Auto Delete: READY")
        print(f"🔵 Auto Mention System: READY")

    # ======== 🗑️ AUTO DELETE METHODS ========

    async def start_auto_delete(self, event):
        """Start auto-delete system - INSTANT ACTION"""
        if not await self.require_admin(event):
            return

        sender = await event.get_sender()
        chat_id = event.chat_id

        # Delete admin's command message IMMEDIATELY
        try:
            await event.delete()
            print(f"🗑️ Deleted admin's /ကန် command message")
        except Exception as e:
            print(f"❌ Error deleting command: {e}")

        # Check if already active for this chat
        if chat_id in self.auto_delete_mode:
            await self.send_dm(sender.id, f"⚠️ Auto delete ဖွင့်ပြီးသားဖြစ်နေပါတယ်။\nChat: {chat_id}\nရပ်ရန်: `/မကန်နဲ့`")
            return

        # Check if reply mode
        if event.is_reply:
            # Specific user target mode
            reply_msg = await event.get_reply_message()
            target_user = await reply_msg.get_sender()

            if isinstance(target_user, User):
                # Initialize targets for this chat
                if chat_id not in self.auto_delete_targets:
                    self.auto_delete_targets[chat_id] = set()

                # Add specific user
                self.auto_delete_targets[chat_id].add(target_user.id)
                self.auto_delete_mode[chat_id] = 'user'

                await self.send_dm(sender.id, f"""✅ Auto delete စတင်ပါပြီ!

🎯 Target Mode: SPECIFIC USER
• Target User: @{target_user.username if target_user.username else target_user.id}
• User ID: {target_user.id}
• Chat: {chat_id}
• Action: INSTANT DELETE (no delay)

⚠️ @{target_user.username if target_user.username else target_user.id} ရဲ့ message အားလုံးကို ချက်ချင်း delete လုပ်ပါမယ်။

ရပ်ရန်: `/မကန်နဲ့`
""")
                print(f"🗑️ Auto delete started for user {target_user.id} in chat {chat_id}")
            else:
                await self.send_dm(sender.id, "❌ User ကိုမရှာတွေ့ပါ။")
                return
        else:
            # Reply မထောက်ရင် error
            await self.send_dm(sender.id, "❌ **အသုံးပြုနည်း:**\n`/ကန်` command ကို user တစ်ယောက်ရဲ့ message ကို **reply ထောက်** ပြီးမှသုံးပါ။\n\nExample:\n1. User ရဲ့ message ကို reply ထောက်\n2. `/ကန်` လို့ရိုက်\n3. Bot က အဲ့ဒီ user ရဲ့ message တွေကို auto delete လုပ်မယ်။")
            return

        self.auto_delete_enabled = True
        self.auto_delete_start_time = datetime.now()

        # Start message monitor for this chat
        asyncio.create_task(self.monitor_chat_messages(chat_id))

    async def monitor_chat_messages(self, chat_id):
        """Monitor and delete messages in specific chat - INSTANT ACTION"""
        print(f"👁️ Started monitoring chat {chat_id} for auto delete")

        while chat_id in self.auto_delete_mode:
            try:
                # Get recent messages (last 50 messages)
                messages = await self.client.get_messages(
                    chat_id, 
                    limit=50
                )

                for message in messages:
                    if chat_id not in self.auto_delete_mode:
                        break

                    try:
                        # Skip if no sender
                        if not message.sender_id:
                            continue

                        sender_id = message.sender_id

                        # Skip admins
                        if sender_id in self.admin_users:
                            continue

                        # Skip bot itself
                        me = await self.client.get_me()
                        if sender_id == me.id:
                            continue

                        # Check mode
                        mode = self.auto_delete_mode.get(chat_id, 'user')

                        if mode == 'user':
                            # Check if user is in target list
                            if chat_id in self.auto_delete_targets:
                                if sender_id in self.auto_delete_targets[chat_id]:
                                    # DELETE USER MESSAGE IMMEDIATELY
                                    await message.delete()
                                    self.deleted_messages_count += 1
                                    print(f"🗑️ Deleted user {sender_id}'s message in chat {chat_id}")
                                    await asyncio.sleep(0.1)  # Small delay to avoid rate limit
                        else:  # group mode (not used in this version)
                            pass

                    except Exception as e:
                        # Ignore delete errors
                        if "MESSAGE_DELETE_FORBIDDEN" not in str(e) and "not found" not in str(e) and "message_id" not in str(e):
                            print(f"⚠️ Error deleting message: {e}")
                        continue

                # Short wait to avoid rate limiting
                await asyncio.sleep(1)

            except Exception as e:
                print(f"❌ Error monitoring chat {chat_id}: {e}")
                await asyncio.sleep(3)

    async def stop_auto_delete(self, event):
        """Stop auto-delete system"""
        if not await self.require_admin(event):
            return

        sender = await event.get_sender()
        chat_id = event.chat_id

        # Delete admin's command message
        try:
            await event.delete()
            print(f"🗑️ Deleted admin's /မကန်နဲ့ command")
        except Exception as e:
            print(f"❌ Error deleting command: {e}")

        if chat_id not in self.auto_delete_mode:
            await self.send_dm(sender.id, f"ℹ️ Chat {chat_id} မှာ auto delete ပိတ်ထားပါတယ်။\nစတင်ရန်: user message ကို reply ထောက်ပြီး `/ကန်`")
            return

        # Get target user info before clearing
        target_info = ""
        if chat_id in self.auto_delete_targets:
            for user_id in self.auto_delete_targets[chat_id]:
                try:
                    user = await self.client.get_entity(user_id)
                    target_info += f"• @{user.username if user.username else user_id} (ID: {user_id})\n"
                except:
                    target_info += f"• User ID: {user_id}\n"

        # Clear targets for this chat
        if chat_id in self.auto_delete_targets:
            del self.auto_delete_targets[chat_id]
        if chat_id in self.auto_delete_mode:
            del self.auto_delete_mode[chat_id]

        # Check if any chats left
        if not self.auto_delete_mode:
            self.auto_delete_enabled = False

        run_duration = datetime.now() - self.auto_delete_start_time if self.auto_delete_start_time else timedelta(0)

        await self.send_dm(sender.id, f"""⛔️ Auto delete ရပ်ဆိုင်းလိုက်ပါပြီ!

📊 Statistics:
• Total Deleted: {self.deleted_messages_count}
• Run Duration: {str(run_duration).split('.')[0]}
• Start Time: {self.auto_delete_start_time.strftime('%H:%M:%S') if self.auto_delete_start_time else 'N/A'}
• End Time: {datetime.now().strftime('%H:%M:%S')}
• Chat ID: {chat_id}

🎯 Target Users:
{target_info if target_info else '• No target users'}

✅ Auto delete ပိတ်ပြီးပါပြီ။
""")

        print(f"🗑️ Auto delete stopped for chat {chat_id}. Deleted {self.deleted_messages_count} messages total")

    # ======== 🗑️ AUTO DELETE FOR CATCH MESSAGES ========
    async def auto_delete_catch_message(self, message, delay=0.8):
        """Auto delete a catch message after specified delay"""
        try:
            await asyncio.sleep(delay)
            await message.delete()
            self.character_catcher_stats['auto_deleted_catch_messages'] += 1
            print(f"🗑️ Auto-deleted /catch message after {delay}s (Total: {self.character_catcher_stats['auto_deleted_catch_messages']})")
        except Exception as e:
            print(f"⚠️ Failed to auto-delete catch message: {e}")

    # ========== 🔵 AUTO MENTION METHODS ==========

    async def start_auto_mention(self, event):
        """Start auto mention in a group"""
        if not await self.require_admin(event):
            return

        sender = await event.get_sender()
        chat_id = event.chat_id

        # Extract target user from message
        target_user = await self.extract_target_from_message(event)

        if not target_user:
            await event.reply("⚠️ **အသုံးပြုနည်း:**\n"
                             "`/ဆဲမယ် @username`\n"
                             "ဒါမှမဟုတ်\n"
                             "`/ဆဲမယ် user_id`\n"
                             "ဒါမှမဟုတ် user message ကို reply လုပ်ပြီး `/ဆဲမယ်` ရိုက်ပါ။")
            await event.delete()
            return

        # Check if already active
        if chat_id in self.auto_mention_active and self.auto_mention_active.get(chat_id):
            await event.reply("⚠️ Auto Mention ဖွင့်ပြီးသားဖြစ်နေပါသည်။\nရပ်ရန်: `/ရပ်လိုက်`")
            await event.delete()
            return

        # Store target
        self.auto_mention_active[chat_id] = True
        self.auto_mention_targets[chat_id] = target_user.id
        self.auto_mention_intervals[chat_id] = self.default_mention_interval
        self.auto_mention_counters[chat_id] = 0
        self.auto_mention_reply_index[chat_id] = 0

        # Store user data
        self.mention_user_data[str(target_user.id)] = {
            'id': target_user.id,
            'username': target_user.username,
            'first_name': target_user.first_name,
            'last_name': target_user.last_name
        }

        # Get nickname if exists
        nickname = self.auto_mention_nicknames.get(str(target_user.id), "မသတ်မှတ်ရသေး")

        # Send start message in group
        reply_text = f"✅ Auto Mention စတင်ပါပြီ!\n\n"
        reply_text += f"Target: @{target_user.username if target_user.username else target_user.id}\n"
        reply_text += f"Nickname: {nickname}\n"
        reply_text += f"Interval: {self.default_mention_interval} စက္ကန့်\n\n"
        reply_text += f"ရပ်ရန်: `/ရပ်လိုက်`"

        await event.reply(reply_text)

        # Send DM to admin
        await self.send_dm(sender.id, f"✅ Auto Mention စတင်ပါပြီ!\n\nTarget: @{target_user.username if target_user.username else target_user.id}\nChat ID: {chat_id}\nInterval: {self.default_mention_interval}s")

        # Start auto mention loop
        asyncio.create_task(self.auto_mention_loop(chat_id, target_user))

        print(f"🔵 Auto Mention started in chat {chat_id} for user {target_user.id}")
        await event.delete()

    async def extract_target_from_message(self, event):
        """Extract target user from message"""
        try:
            message_text = event.message.text

            # Check if replying to a message
            if event.is_reply:
                reply_msg = await event.get_reply_message()
                if reply_msg and reply_msg.sender:
                    return reply_msg.sender

            # Extract from text
            if '@' in message_text:
                match = re.search(r'@(\w+)', message_text)
                if match:
                    username = match.group(1)
                    try:
                        users = await self.client.get_participants(event.chat_id, search=username)
                        if users:
                            return users[0]
                    except:
                        pass

            # Extract user ID
            match = re.search(r'\b(\d+)\b', message_text)
            if match:
                user_id = int(match.group(1))
                try:
                    user = await self.client.get_entity(user_id)
                    return user
                except:
                    pass

            return None
        except Exception as e:
            print(f"❌ Error extracting target: {e}")
            return None

    async def auto_mention_loop(self, chat_id, target_user):
        """Main auto mention loop - SIMPLE VERSION"""
        while chat_id in self.auto_mention_active and self.auto_mention_active.get(chat_id):
            try:
                # Get interval
                interval = self.auto_mention_intervals.get(chat_id, self.default_mention_interval)

                # Get reply message from self.reply_messages
                if chat_id not in self.auto_mention_reply_index:
                    self.auto_mention_reply_index[chat_id] = 0

                reply_index = self.auto_mention_reply_index[chat_id]

                if self.reply_messages:
                    reply_message = self.reply_messages[reply_index]
                    self.auto_mention_reply_index[chat_id] = (reply_index + 1) % len(self.reply_messages)
                else:
                    reply_message = "စာများ"

                # SIMPLE MENTION FORMAT
                mention_text = f"@{target_user.username if target_user.username else target_user.id}\n"
                mention_text += f"{reply_message}"

                # Send mention
                await self.client.send_message(
                    chat_id,
                    mention_text,
                    link_preview=False
                )

                # Update counter
                self.auto_mention_counters[chat_id] = self.auto_mention_counters.get(chat_id, 0) + 1

                # Wait for next interval
                await asyncio.sleep(interval)

            except Exception as e:
                print(f"❌ Error in auto mention loop: {e}")
                await asyncio.sleep(5)

    async def stop_auto_mention(self, event):
        """Stop auto mention"""
        if not await self.require_admin(event):
            return

        sender = await event.get_sender()
        chat_id = event.chat_id

        if chat_id in self.auto_mention_active and self.auto_mention_active[chat_id]:
            # Get target user info
            target_id = self.auto_mention_targets.get(chat_id)

            # Stop loop
            self.auto_mention_active[chat_id] = False

            # Remove from active mentions
            if chat_id in self.auto_mention_loops:
                del self.auto_mention_loops[chat_id]

            # Send stop message in group
            reply_text = f"⛔️ Auto Mention ရပ်ဆိုင်းလိုက်ပါပြီ!\n\n"
            reply_text += f"📊 Mention အကြိမ်ရေ: {self.auto_mention_counters.get(chat_id, 0)}"

            await event.reply(reply_text)

            # Send DM to admin
            await self.send_dm(sender.id, f"⛔️ Auto Mention ရပ်ဆိုင်းလိုက်ပါပြီ!\n\nChat ID: {chat_id}\nMention အကြိမ်ရေ: {self.auto_mention_counters.get(chat_id, 0)}")

            print(f"🔵 Auto Mention stopped in chat {chat_id}")
        else:
            await event.reply("ℹ️ လောလောဆယ် Auto Mention ဖွင့်မထားပါ။")

        await event.delete()

    async def set_nickname(self, event):
        """Set nickname for user"""
        if not await self.require_admin(event):
            return

        sender = await event.get_sender()

        try:
            # Extract target user and nickname
            message_text = event.message.text
            parts = message_text.split(maxsplit=2)

            if len(parts) < 3:
                await event.reply("⚠️ **အသုံးပြုနည်း:**\n"
                                 "`/setnick @username nickname`\n"
                                 "ဒါမှမဟုတ်\n"
                                 "`/setnick user_id nickname`")
                await event.delete()
                return

            # Extract target user
            target_user = await self.extract_target_from_message(event)
            if not target_user:
                await event.reply("❌ User ကိုမသိနိုင်ပါ။")
                await event.delete()
                return

            # Extract nickname
            nickname = parts[2]

            # Store nickname
            user_id_str = str(target_user.id)
            if user_id_str not in self.auto_mention_nicknames:
                self.auto_mention_nicknames[user_id_str] = {}

            self.auto_mention_nicknames[user_id_str]['nickname'] = nickname
            self.auto_mention_nicknames[user_id_str]['set_by'] = sender.id
            self.auto_mention_nicknames[user_id_str]['set_at'] = datetime.now().isoformat()

            # Send DM to admin
            await self.send_dm(sender.id, f"✅ Nickname သတ်မှတ်ပြီးပါပြီ!\n\nUser: @{target_user.username if target_user.username else target_user.id}\nNickname: {nickname}")

            # Reply in group
            reply_text = f"✅ Nickname သတ်မှတ်ပြီးပါပြီ!\n\n"
            reply_text += f"User: @{target_user.username if target_user.username else target_user.id}\n"
            reply_text += f"Nickname: {nickname}"

            await event.reply(reply_text)
            print(f"🔵 Nickname set for user {target_user.id}: {nickname}")

        except Exception as e:
            await event.reply(f"❌ Error: {str(e)}")

        await event.delete()

    async def set_mention_interval(self, event):
        """Set mention interval in seconds"""
        if not await self.require_admin(event):
            return

        try:
            message_text = event.message.text
            parts = message_text.split()

            if len(parts) < 2:
                await event.reply("⚠️ **အသုံးပြုနည်း:**\n`/setsec 30`")
                await event.delete()
                return

            try:
                seconds = int(parts[1])
            except ValueError:
                await event.reply("❌ စက္ကန့်ကို နံပါတ်ဖြင့် ရိုက်ထည့်ပါ။")
                await event.delete()
                return

            if seconds < 10:
                await event.reply("⚠️ စက္ကန့် ၁၀ အောက် မထားသင့်ပါ။")
                await event.delete()
                return

            sender = await event.get_sender()
            chat_id = event.chat_id
            self.auto_mention_intervals[chat_id] = seconds

            # Send DM to admin
            await self.send_dm(sender.id, f"✅ Mention Interval သတ်မှတ်ပြီးပါပြီ!\n\nChat ID: {chat_id}\nNew Interval: {seconds} စက္ကန့်")

            # Reply in group
            reply_text = f"✅ Mention Interval သတ်မှတ်ပြီးပါပြီ!\n\n"
            reply_text += f"{seconds} စက္ကန့် တစ်ခါ mention လုပ်ပေးပါမယ်။"

            await event.reply(reply_text)
            print(f"🔵 Interval set to {seconds}s for chat {chat_id}")

        except Exception as e:
            await event.reply(f"❌ Error: {str(e)}")

        await event.delete()

    async def show_mention_status(self, event):
        """Show current auto mention status"""
        if not await self.require_admin(event):
            return

        sender = await event.get_sender()
        chat_id = event.chat_id

        if chat_id in self.auto_mention_active and self.auto_mention_active[chat_id]:
            target_id = self.auto_mention_targets.get(chat_id)

            # Get user info
            user_info = None
            if target_id:
                user_info = self.mention_user_data.get(str(target_id))

            # Get nickname
            nickname = "မသတ်မှတ်ရသေး"
            if target_id:
                nickname_data = self.auto_mention_nicknames.get(str(target_id), {})
                nickname = nickname_data.get('nickname', 'မသတ်မှတ်ရသေး')

            # Get interval
            interval = self.auto_mention_intervals.get(chat_id, self.default_mention_interval)

            # Get next reply message
            next_reply_index = self.auto_mention_reply_index.get(chat_id, 0)
            next_reply = self.reply_messages[next_reply_index] if self.reply_messages else "မရှိပါ"

            reply_text = f"📊 Auto Mention Status\n\n"

            if user_info:
                reply_text += f"Target User: @{user_info.get('username', user_info.get('id', 'Unknown'))}\n"

            reply_text += f"Nickname: {nickname}\n"
            reply_text += f"Interval: {interval} seconds\n"
            reply_text += f"Mention အကြိမ်ရေ: {self.auto_mention_counters.get(chat_id, 0)}\n"
            reply_text += f"နောက်တစ်ခါပြောမည့်စာ: {next_reply[:50]}...\n\n"
            reply_text += f"Status: 🟢 အလုပ်လုပ်နေဆဲ"

        else:
            reply_text = "ℹ️ Auto Mention ပိတ်ထားပါတယ်။"

        await event.reply(reply_text)
        await event.delete()

    # ========== 📢 LOG METHODS (DM ONLY) ==========
    async def send_dm(self, user_id, message):
        """Send message via DM"""
        try:
            await self.client.send_message(user_id, message)
            print(f"📤 Sent DM to {user_id}")
        except Exception as e:
            print(f"❌ Error sending DM: {e}")

    # ========== 🎮 CHARACTER CATCHER METHODS ========
    def get_photo_hash(self, photo_bytes):
        """Generate simple hash for photo"""
        return hashlib.md5(photo_bytes).hexdigest()[:16]

    async def is_duplicate_photo(self, photo_bytes):
        """Check if photo was recently processed"""
        photo_hash = self.get_photo_hash(photo_bytes)
        current_time = time.time()

        # Clean old hashes
        expired_hashes = [h for h, t in self.photo_hashes.items() 
                         if current_time - t > self.photo_hash_ttl]
        for h in expired_hashes:
            del self.photo_hashes[h]

        if photo_hash in self.photo_hashes:
            return True

        self.photo_hashes[photo_hash] = current_time
        return False

    async def toggle_character_catcher(self, event):
        """Toggle character catcher on/off"""
        if not await self.require_admin(event):
            return

        sender = await event.get_sender()

        self.character_catcher_active = not self.character_catcher_active

        status = "✅ ACTIVATED" if self.character_catcher_active else "⏸️ DEACTIVATED"
        stats_msg = f"""🎮 Character Catcher {status}!

🎯 Target Bots:
• {self.character_bot_username} → /catch
• {self.grab_bot_username} → /grab
• {self.guess_bot_username} → /grab

🤖 Cheats Bot: {self.cheats_bot_username}
⚡ Speed: {self.forward_delay}s forward, {self.catch_delay}s catch
🗑️ Auto Delete: /catch messages will be deleted after 0.8s

📊 Stats:
• Total Spawns: {self.character_catcher_stats['total_spawns']}
• Successful: {self.character_catcher_stats['successful_catches']}
• Failed: {self.character_catcher_stats['failed_catches']}
• Cache Hits: {self.cache_hits}
• Queue: {len(self.character_process_queue)} items
• Pending: {self.character_catcher_stats['pending_requests']}
• Auto-Deleted Messages: {self.character_catcher_stats['auto_deleted_catch_messages']}
"""

        await self.send_dm(sender.id, stats_msg)

        if self.character_catcher_active:
            print(f"🎮 Character Catcher activated!")
            asyncio.create_task(self.process_character_queue_fast())
        else:
            print(f"🎮 Character Catcher deactivated")

        await event.delete()

    async def handle_character_spawn(self, event):
        """Handle character spawn messages from all bots"""
        if not self.character_catcher_active or self.paused:
            return

        try:
            message = event.message
            message_text = message.text or message.caption or ""
            sender = await event.get_sender()
            sender_username = f"@{sender.username}" if sender.username else ""

            # Check if from target bot
            target_bots = [self.character_bot_username, self.grab_bot_username, self.guess_bot_username]
            if sender_username not in target_bots:
                return

            # Check spawn patterns
            spawn_patterns = [
                "ᴀ ᴄʜᴀʀᴀᴄᴛᴇʀ ʜᴀs sᴘᴀᴡɴᴇᴅ",
                "character has spawned",
                "has spawned",
                "New Waifu Is Here",
                "Hurry-Up,Grab Using",
                "Grab Using /grab",
                "ɴᴇᴡ ᴡᴀɪғᴜ ʜᴀs ᴊᴜsᴛ ᴀᴘᴘᴇᴀʀᴇᴅ",
                "Gʀᴇᴀᴛ! ᴀ ɴᴇᴡ ᴡᴀɪғᴜ",
                "ᴜsᴇ /guess ɴᴀᴍᴇ"
            ]

            if not any(pattern.lower() in message_text.lower() for pattern in spawn_patterns):
                return

            self.character_catcher_stats['total_spawns'] += 1

            chat_id = event.chat_id
            message_id = message.id
            chat = await event.get_chat()
            chat_title = getattr(chat, 'title', 'Private Chat')

            print(f"🎯 Character #{self.character_catcher_stats['total_spawns']} detected in {chat_title} from {sender_username}")

            if message.photo:
                # Download photo
                file = BytesIO()
                await self.client.download_media(message.photo, file)
                photo_bytes = file.getvalue()

                print(f"📥 Downloaded photo: {len(photo_bytes)} bytes")

                # Check for duplicates
                if await self.is_duplicate_photo(photo_bytes):
                    print(f"⚠️ Duplicate photo detected, skipping")
                    self.character_catcher_stats['duplicates_skipped'] += 1
                    return

                # Check cache first
                photo_hash = self.get_photo_hash(photo_bytes)
                if photo_hash in self.character_name_cache:
                    character_name = self.character_name_cache[photo_hash]
                    self.cache_hits += 1
                    print(f"✅ Cache hit: {character_name}")

                    # Send appropriate command
                    command = "/catch"
                    if "grab" in sender_username.lower():
                        command = "/grab"
                    elif "guess" in sender_username.lower():
                        command = "/guess"

                    catch_message = await self.send_catch_command_fast(
                        chat_id, 
                        character_name,
                        command,
                        time.time(),
                        photo_bytes
                    )

                    # Auto delete the catch message after 0.8 seconds
                    if catch_message:
                        asyncio.create_task(self.auto_delete_catch_message(catch_message, 0.8))

                    self.character_catcher_stats['successful_catches'] += 1
                    return

                self.cache_misses += 1

                # Add to processing queue
                queue_item = {
                    'chat_id': chat_id,
                    'message_id': message_id,
                    'chat_title': chat_title,
                    'photo_bytes': photo_bytes,
                    'photo_hash': photo_hash,
                    'timestamp': datetime.now(),
                    'start_time': time.time(),
                    'sender_bot': sender_username
                }

                # Limit queue size
                if len(self.character_process_queue) < 50:
                    self.character_process_queue.append(queue_item)

                    # Start processing if not already processing
                    if not self.is_processing_character:
                        asyncio.create_task(self.process_character_queue_fast())
                    else:
                        print(f"📦 Added to queue. Queue size: {len(self.character_process_queue)}")
                else:
                    print(f"⚠️ Queue full, dropping character")
                    self.character_catcher_stats['failed_catches'] += 1
            else:
                print("⚠️ No photo found in character spawn message")
                self.character_catcher_stats['failed_catches'] += 1

        except Exception as e:
            print(f"❌ Error in handle_character_spawn: {e}")
            self.character_catcher_stats['failed_catches'] += 1

    async def process_character_queue_fast(self):
        """Process character queue with ULTRA FAST speed"""
        if self.is_processing_character:
            return

        self.is_processing_character = True

        try:
            while self.character_process_queue and self.character_catcher_active and not self.paused:
                char_data = self.character_process_queue.pop(0)

                try:
                    print(f"⚡ Processing character from {char_data['chat_title']}...")

                    # Forward to cheats bot and get name
                    character_name = await self.get_character_name_from_cheats_bot_fixed(char_data)

                    if character_name:
                        # Cache the name
                        if len(self.character_name_cache) < self.cache_size_limit:
                            self.character_name_cache[char_data['photo_hash']] = character_name

                        # Send appropriate command
                        command = "/catch"
                        if "grab" in char_data['sender_bot'].lower():
                            command = "/grab"
                        elif "guess" in char_data['sender_bot'].lower():
                            command = "/guess"

                        catch_message = await self.send_catch_command_fast(
                            char_data['chat_id'], 
                            character_name,
                            command,
                            char_data['start_time'],
                            char_data['photo_bytes']
                        )

                        # Auto delete the catch message after 0.8 seconds
                        if catch_message:
                            asyncio.create_task(self.auto_delete_catch_message(catch_message, 0.8))

                        self.character_catcher_stats['successful_catches'] += 1
                    else:
                        print(f"❌ Could not get character name for {char_data['chat_title']}")
                        self.character_catcher_stats['failed_catches'] += 1

                    # Ultra fast delay
                    if self.forward_delay > 0:
                        await asyncio.sleep(self.forward_delay)

                except Exception as e:
                    print(f"❌ Error processing character: {e}")
                    self.character_catcher_stats['failed_catches'] += 1
                    await asyncio.sleep(0.1)
        finally:
            self.is_processing_character = False

        if not self.character_process_queue:
            print("📭 Character queue empty")

    async def get_character_name_from_cheats_bot_fixed(self, char_data):
        """Send spawn to cheats bot (forward first, fallback to re-upload) and wait for name"""
        try:
            print(f"📷 Photo hash: {char_data['photo_hash'][:8]}")
            print(f"➡️ Sending spawn from {char_data['chat_title']} to cheats bot")

            message = None

            # ── Method 1: Forward original spawn message (fast, no upload) ──
            try:
                forwarded = await self.client.forward_messages(
                    entity=self.cheats_bot_username,
                    messages=char_data['message_id'],
                    from_peer=char_data['chat_id'],
                    silent=True
                )

                if isinstance(forwarded, list):
                    message = forwarded[0] if forwarded else None
                else:
                    message = forwarded

                if message:
                    print(f"✅ Forwarded successfully (ID: {message.id})")

            except Exception as e:
                # Likely ChatForwardsRestrictedError — group has "Restrict Saving" enabled
                print(f"⚠️ Forward blocked ({type(e).__name__}: {e}); falling back to re-upload")
                message = None

            # ── Method 2: Fallback — re-upload the photo bytes ──
            if message is None:
                if not char_data.get('photo_bytes') or len(char_data['photo_bytes']) < 100:
                    print(f"❌ No usable photo bytes for fallback upload")
                    return None

                tmp_path = None
                try:
                    with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as tmp:
                        tmp.write(char_data['photo_bytes'])
                        tmp_path = tmp.name

                    message = await self.client.send_file(
                        entity=self.cheats_bot_username,
                        file=tmp_path,
                        caption="",
                        silent=True,
                        force_document=False,
                        allow_cache=False,
                        supports_streaming=True,
                        parse_mode=None
                    )
                    print(f"✅ Re-uploaded photo successfully (ID: {message.id})")
                except Exception as e:
                    print(f"❌ Fallback upload also failed: {e}")
                    return None
                finally:
                    if tmp_path and os.path.exists(tmp_path):
                        try:
                            os.unlink(tmp_path)
                        except Exception:
                            pass

            self.character_catcher_stats['cheats_bot_requests'] += 1
            self.character_catcher_stats['pending_requests'] += 1
            request_id = message.id

            # Store in forwarded messages dict (legacy reply-based matching)
            self.forwarded_messages[request_id] = {
                'timestamp': time.time(),
                'chat_title': char_data['chat_title'],
                'photo_hash': char_data['photo_hash']
            }

            # Append to FIFO pending queue (for new bot that doesn't reply)
            self.cheats_bot_pending_queue.append({
                'photo_hash': char_data['photo_hash'],
                'request_id': request_id,
                'timestamp': time.time(),
                'chat_title': char_data['chat_title']
            })

            print(f"📤 Sent to cheats bot (ID: {request_id}, queue depth: {len(self.cheats_bot_pending_queue)})")

            # Wait for response
            start_time = time.time()
            character_name = None

            failed = False
            while time.time() - start_time < self.cheats_bot_timeout:
                # Check if cheats bot has responded with this photo hash
                for msg_id, response_data in list(self.cheats_bot_waiting_responses.items()):
                    if response_data.get('photo_hash') == char_data['photo_hash']:
                        if response_data.get('failed'):
                            failed = True
                            del self.cheats_bot_waiting_responses[msg_id]
                            break
                        if response_data.get('character_name'):
                            character_name = response_data['character_name']
                            print(f"✅ Got name from cheats bot: {character_name}")
                            del self.cheats_bot_waiting_responses[msg_id]
                            break

                if character_name or failed:
                    if character_name:
                        self.character_catcher_stats['cheats_bot_success'] += 1
                    break

                await asyncio.sleep(0.1)

            # Clean up pending request count
            self.character_catcher_stats['pending_requests'] = max(0, self.character_catcher_stats['pending_requests'] - 1)

            if not character_name:
                print(f"⏱️ Timeout waiting for response from cheats bot")

            return character_name

        except Exception as e:
            print(f"❌ Error getting name from cheats bot: {e}")
            self.character_catcher_stats['pending_requests'] = max(0, self.character_catcher_stats['pending_requests'] - 1)
            return None

    async def handle_cheats_bot_response(self, event):
        """Handle responses from cheats bot (HusbandosWaifusCheatsBot format)"""
        if not self.character_catcher_active:
            return

        try:
            message = event.message
            message_text = message.text or ""

            print(f"🤖 Cheats bot response: {message_text[:120]}...")

            # ── Match this response to a pending request ──
            forwarded_data = None

            # Method A: Reply-based (legacy bots that reply)
            if message.is_reply:
                try:
                    reply_to = await message.get_reply_message()
                    if reply_to and reply_to.id in self.forwarded_messages:
                        forwarded_data = self.forwarded_messages[reply_to.id]
                        # Also remove the matching item from FIFO queue (if present)
                        for i, item in enumerate(self.cheats_bot_pending_queue):
                            if item['request_id'] == reply_to.id:
                                self.cheats_bot_pending_queue.pop(i)
                                break
                except Exception:
                    pass

            # Method B: FIFO queue (new bot doesn't use reply)
            if forwarded_data is None:
                # Drop expired entries from the front of the queue
                now = time.time()
                while self.cheats_bot_pending_queue and \
                        (now - self.cheats_bot_pending_queue[0]['timestamp']) > self.cheats_bot_timeout + 5:
                    expired = self.cheats_bot_pending_queue.pop(0)
                    print(f"🗑️ Dropped expired pending request for {expired['chat_title']}")

                if self.cheats_bot_pending_queue:
                    pending = self.cheats_bot_pending_queue.pop(0)
                    forwarded_data = {
                        'timestamp': pending['timestamp'],
                        'chat_title': pending['chat_title'],
                        'photo_hash': pending['photo_hash']
                    }
                else:
                    print(f"⚠️ Got cheats bot response but no pending request to match")
                    return

            # If response is an error, mark as failed and don't bother parsing
            error_markers = ['Unknown', 'Admin Only', 'not found', 'Not Found']
            if any(marker in message_text for marker in error_markers):
                print(f"⚠️ Cheats bot returned error for hash {forwarded_data['photo_hash'][:8]}: {message_text[:60]}")
                # Mark as failed so the waiter can move on
                self.cheats_bot_waiting_responses[message.id] = {
                    'character_name': None,
                    'photo_hash': forwarded_data['photo_hash'],
                    'timestamp': time.time(),
                    'failed': True
                }
                return

            # Extract character name from response
            character_name = None

            def clean_name(raw):
                """Strip markdown chars and surrounding whitespace from a captured name."""
                if not raw:
                    return raw
                # Remove backticks, asterisks, underscores, tildes used by Markdown
                cleaned = re.sub(r'[`*_~]+', '', raw).strip()
                # Trim trailing punctuation that may have leaked in
                cleaned = cleaned.rstrip(',.;:').strip()
                return cleaned

            # Primary format (HusbandosWaifusCheatsBot):
            #   **NAME :** `Rukia Kuchiki [🧹]`
            #   ━━━━━━━━━━━━━━━━━━
            #   🔹 **Hint :** `/catch rukia`
            #   🔸 **Full :** `/catch Rukia Kuchiki [🧹]`
            #
            # Use the Hint line (lowercase short name) for the catch command.
            for line in message_text.split('\n'):
                if 'Hint' in line:
                    hint_match = re.search(r'/(?:catch|grab|guess|loot|seize)\s+(.+?)\s*$', line.strip())
                    if hint_match:
                        character_name = clean_name(hint_match.group(1))
                        break

            # Fallback: legacy formats
            if not character_name:
                if message_text.startswith('Name:'):
                    parts = message_text.split(':', 1)
                    if len(parts) > 1:
                        character_name = clean_name(parts[1])

                elif 'Humanizer:' in message_text:
                    for line in message_text.split('\n'):
                        if 'Humanizer:' in line:
                            parts = line.split(':', 1)
                            if len(parts) > 1:
                                character_name = clean_name(parts[1].replace('/catch ', ''))
                                break

                elif 'Command:' in message_text:
                    for line in message_text.split('\n'):
                        if 'Command:' in line:
                            parts = line.split(':', 1)
                            if len(parts) > 1:
                                character_name = clean_name(parts[1].replace('/catch ', ''))
                                break

            # Last-resort fallback: any /catch /grab /guess in the body
            if not character_name:
                for cmd in ['/catch', '/grab', '/guess', '/loot', '/seize']:
                    match = re.search(fr'{cmd}\s+([^\n`*]+)', message_text)
                    if match:
                        character_name = clean_name(match.group(1))
                        break

            if character_name:
                # Store in waiting responses
                self.cheats_bot_waiting_responses[message.id] = {
                    'character_name': character_name,
                    'photo_hash': forwarded_data['photo_hash'],
                    'timestamp': time.time()
                }

                print(f"✅ Cheats bot response for hash {forwarded_data['photo_hash'][:8]}: {character_name}")
            else:
                print(f"⚠️ Could not extract character name from response: {message_text[:200]}")

        except Exception as e:
            print(f"❌ Error handling cheats bot response: {e}")

    async def send_catch_command_fast(self, chat_id, character_name, command, start_time, photo_bytes):
        """Send catch command to chat and return the message object for auto-deletion"""
        try:
            # Calculate processing time
            processing_time = time.time() - start_time
            self.character_catcher_stats['processing_time'].append(processing_time)

            # Clean old processing times
            if len(self.character_catcher_stats['processing_time']) > 100:
                self.character_catcher_stats['processing_time'] = self.character_catcher_stats['processing_time'][-50:]

            # Clean character name
            character_name = character_name.strip()

            # Small delay before sending
            if self.catch_delay > 0:
                await asyncio.sleep(self.catch_delay)

            # Send catch command
            full_command = f"{command} {character_name}"
            message = await self.client.send_message(
                chat_id,
                full_command,
                silent=True
            )

            # Update stats
            self.character_catcher_stats['last_catch'] = datetime.now()

            print(f"🎯 Sent: {full_command} (in {processing_time:.2f}s)")

            # Return the message object for auto-deletion
            return message

        except Exception as e:
            print(f"❌ Error sending catch command: {e}")
            self.character_catcher_stats['failed_catches'] += 1
            return None

    # ========== 🚨 IMMEDIATE CONTROL SYSTEM ==========
    async def stop_auto_reply_immediately(self, event):
        """Stop all auto-reply immediately and remove group from JSON"""
        if not await self.require_admin(event):
            return

        sender = await event.get_sender()
        chat_id = event.chat_id

        print("🛑 Stopping auto-reply immediately...")

        # Stop auto-reply
        self.stop_auto_reply_flag = True
        self.skip_queue_flag = True

        pending_count = len(self.pending_replies)
        self.pending_replies.clear()
        self.is_replying = False

        # Remove this group from auto-reply list
        if chat_id in self.auto_reply_groups:
            self.auto_reply_groups.discard(chat_id)

            # Save to JSON file immediately
            self.save_data()

            print(f"🗑️ Removed group {chat_id} from auto-reply list")

            # Notify admin via DM
            await self.send_dm(sender.id, f"🛑 AUTO-REPLY STOPPED & GROUP REMOVED!\n\nGroup ID {chat_id} ကို auto-reply list ကနေဖယ်လိုက်ပါပြီ။\nကျန်ရှိနေသေးတဲ့ groups: {len(self.auto_reply_groups)}")
        else:
            await self.send_dm(sender.id, f"🛑 AUTO-REPLY STOPPED!\n\nAuto-reply အားလုံးရပ်လိုက်ပါပြီ။\nလက်ရှိ active groups: {len(self.auto_reply_groups)}")

        print(f"✅ Auto-reply STOPPED!")
        print(f"   Cleared {pending_count} pending replies")
        print(f"   Current auto-reply groups: {len(self.auto_reply_groups)}")

        # Auto-reset stop flag after 3 seconds
        asyncio.create_task(self.auto_reset_stop_flag())

    async def auto_reset_stop_flag(self, delay_seconds=3):
        """Auto-reset stop flag after delay"""
        await asyncio.sleep(delay_seconds)
        self.stop_auto_reply_flag = False
        self.skip_queue_flag = False
        print(f"🔄 Auto-reply auto-resumed after {delay_seconds} seconds")

    async def pause_all(self):
        """Pause all activities"""
        self.paused = True
        print("⏸️ All activities paused")

    async def resume_all(self):
        """Resume all activities"""
        self.paused = False
        print("▶️ All activities resumed")

    # ========== ⚡ AUTO-REPLY SYSTEM ==========
    async def process_auto_reply(self, event, sender, current_time):
        """Process auto-reply"""
        if self.stop_auto_reply_flag or self.paused:
            return

        if sender.id in self.excluded_users:
            return

        chat_id = event.chat_id
        is_target_group = chat_id in self.auto_reply_groups
        is_target_user = sender.id in self.auto_reply_users

        if not (is_target_group or is_target_user):
            return

        if sender.id in self.last_reply_times:
            time_diff = (current_time - self.last_reply_times[sender.id]).total_seconds()
            if time_diff < self.auto_reply_delay:
                return

        twenty_seconds_ago = current_time - timedelta(seconds=20)

        if sender.id not in self.user_message_times:
            return

        last_user_message = self.user_message_times[sender.id]
        if last_user_message < twenty_seconds_ago:
            return

        if not self.reply_messages:
            return

        reply_text = self.reply_messages[self.reply_index]

        self.pending_replies.append({
            'chat_id': chat_id,
            'user_id': sender.id,
            'reply_text': reply_text,
            'event': event,
            'timestamp': current_time
        })

        self.reply_index = (self.reply_index + 1) % len(self.reply_messages)

        if not self.is_replying:
            asyncio.create_task(self.process_pending_replies())

    async def process_pending_replies(self):
        """Process pending replies"""
        self.is_replying = True

        while self.pending_replies and not self.stop_auto_reply_flag:
            try:
                if self.skip_queue_flag:
                    self.pending_replies.clear()
                    print("🔄 Skipping all pending replies")
                    break

                reply_data = self.pending_replies.pop(0)

                # Apply rate limits
                await self.apply_rate_limits(reply_data['user_id'], reply_data['chat_id'])

                try:
                    async with self.client.action(reply_data['chat_id'], 'typing'):
                        await asyncio.sleep(0.02)
                except:
                    pass

                await reply_data['event'].reply(reply_data['reply_text'])
                self.last_reply_times[reply_data['user_id']] = reply_data['timestamp']

                await asyncio.sleep(0.1)

            except Exception as e:
                if "Auto-reply stopped" in str(e):
                    print("🛑 Auto-reply stopped by user command")
                    break
                print(f"❌ Error processing pending reply: {e}")
                await asyncio.sleep(0.1)

        self.is_replying = False
        if not self.pending_replies:
            print("📭 Pending queue empty")

    # ========== ⚡ RATE LIMITING FUNCTIONS ==========
    async def apply_rate_limits(self, user_id, chat_id):
        """Apply all rate limits before sending message"""
        if self.stop_auto_reply_flag:
            raise Exception("Auto-reply stopped by user command")

        # Check global rate limit
        current_time = time.time()
        if current_time - self.rate_limits['last_message_time'] > 1:
            self.rate_limits['messages_in_last_second'] = 0
            self.rate_limits['last_message_time'] = current_time

        if self.rate_limits['messages_in_last_second'] >= self.rate_limits['max_messages_per_second']:
            wait_time = 1 - (current_time - self.rate_limits['last_message_time'])
            if wait_time > 0:
                await asyncio.sleep(wait_time)
            self.rate_limits['messages_in_last_second'] = 0
            self.rate_limits['last_message_time'] = time.time()

        # Check group cooldown
        if chat_id in self.rate_limits['group_cooldown']:
            time_since_last = current_time - self.rate_limits['group_cooldown'][chat_id]
            if time_since_last < self.rate_limits['min_group_cooldown']:
                wait_time = self.rate_limits['min_group_cooldown'] - time_since_last
                await asyncio.sleep(wait_time)
        self.rate_limits['group_cooldown'][chat_id] = current_time

        # Check user cooldown
        if user_id in self.rate_limits['last_user_reply_time']:
            time_since_last = current_time - self.rate_limits['last_user_reply_time'][user_id]
            if time_since_last < self.rate_limits['cooldown_between_users']:
                wait_time = self.rate_limits['cooldown_between_users'] - time_since_last
                await asyncio.sleep(wait_time)
        self.rate_limits['last_user_reply_time'][user_id] = current_time

        # Check consecutive replies
        if user_id not in self.rate_limits['consecutive_reply_count']:
            self.rate_limits['consecutive_reply_count'][user_id] = 0
        self.rate_limits['consecutive_reply_count'][user_id] += 1
        if self.rate_limits['consecutive_reply_count'][user_id] > self.rate_limits['max_consecutive_replies']:
            self.rate_limits['consecutive_reply_count'][user_id] = 0

        random_delay = random.uniform(0.05, 0.2)
        await asyncio.sleep(random_delay)

        self.rate_limits['messages_in_last_second'] += 1
        return True

    # ========== 👑 ADMIN CHECK SYSTEM ==========
    async def is_admin(self, user_id):
        """Check if user is admin"""
        return user_id in self.admin_users

    async def require_admin(self, event):
        """Decorator function to check admin status"""
        sender = await event.get_sender()
        if not await self.is_admin(sender.id):
            await event.delete()
            return False
        return True

    # ========== 💾 DATA MANAGEMENT ==========
    def load_data(self):
        """Load saved bot data"""
        try:
            if os.path.exists('ultimate_bot_data.json'):
                with open('ultimate_bot_data.json', 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.auto_reply_groups = set(data.get('auto_reply_groups', []))
                    self.auto_reply_users = set(data.get('auto_reply_users', []))
                    self.excluded_users = set(data.get('excluded_users', []))
                    self.reply_messages = data.get('reply_messages', self.reply_messages)
                    self.auto_reply_delay = data.get('auto_reply_delay', 4.0)

                    # Load auto delete settings
                    self.auto_delete_enabled = data.get('auto_delete_enabled', False)
                    self.deleted_messages_count = data.get('deleted_messages_count', 0)

                    # Load character catcher data
                    self.character_catcher_active = data.get('character_catcher_active', False)
                    self.catch_delay = data.get('character_catch_delay', 0.1)
                    self.forward_delay = data.get('character_process_delay', 0.05)
                    self.cheats_bot_timeout = data.get('cheats_bot_timeout', 5)

                    # Load character cache
                    self.character_name_cache = data.get('character_name_cache', {})

                    # Load admin users if saved
                    if 'admin_users' in data:
                        self.admin_users = set(data['admin_users'])

                    # Load stats
                    if 'character_stats' in data:
                        self.character_catcher_stats = data['character_stats']
                        # Ensure new stat exists
                        if 'auto_deleted_catch_messages' not in self.character_catcher_stats:
                            self.character_catcher_stats['auto_deleted_catch_messages'] = 0

                    # Load auto mention data
                    self.auto_mention_active = data.get('auto_mention_active', {})
                    self.auto_mention_targets = data.get('auto_mention_targets', {})
                    self.auto_mention_nicknames = data.get('auto_mention_nicknames', {})
                    self.auto_mention_intervals = data.get('auto_mention_intervals', {})
                    self.auto_mention_counters = data.get('auto_mention_counters', {})
                    self.mention_user_data = data.get('mention_user_data', {})
                    self.auto_mention_reply_index = data.get('auto_mention_reply_index', {})

                    print(f"✅ Loaded {len(self.reply_messages)} reply messages")
                    print(f"✅ Loaded {len(self.auto_reply_groups)} auto-reply groups")
                    print(f"✅ Loaded {len(self.auto_reply_users)} auto-reply users")
                    print(f"✅ Loaded {len(self.admin_users)} admin users")
                    print(f"⚡ Loaded auto-reply delay: {self.auto_reply_delay} seconds")
                    print(f"🗑️ Auto Delete: {'✅ Enabled' if self.auto_delete_enabled else '❌ Disabled'}")
                    print(f"🎮 Character Catcher: {'✅ Active' if self.character_catcher_active else '❌ Inactive'}")
                    print(f"🎮 Loaded {len(self.character_name_cache)} cached character names")
                    print(f"🔵 Loaded {len(self.auto_mention_active)} active auto mentions")
        except Exception as e:
            print(f"❌ Error loading data: {e}")

    def save_data(self):
        """Save bot data to JSON file"""
        try:
            data = {
                'auto_reply_groups': list(self.auto_reply_groups),
                'auto_reply_users': list(self.auto_reply_users),
                'excluded_users': list(self.excluded_users),
                'reply_messages': self.reply_messages,
                'auto_reply_delay': self.auto_reply_delay,
                'admin_users': list(self.admin_users),
                'auto_delete_enabled': self.auto_delete_enabled,
                'deleted_messages_count': self.deleted_messages_count,
                'character_catcher_active': self.character_catcher_active,
                'character_catch_delay': self.catch_delay,
                'character_process_delay': self.forward_delay,
                'cheats_bot_timeout': self.cheats_bot_timeout,
                'character_name_cache': self.character_name_cache,
                'character_stats': self.character_catcher_stats,
                'auto_mention_active': self.auto_mention_active,
                'auto_mention_targets': self.auto_mention_targets,
                'auto_mention_nicknames': self.auto_mention_nicknames,
                'auto_mention_intervals': self.auto_mention_intervals,
                'auto_mention_counters': self.auto_mention_counters,
                'mention_user_data': self.mention_user_data,
                'auto_mention_reply_index': self.auto_mention_reply_index
            }

            with open('ultimate_bot_data.json', 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

            print("✅ Data saved successfully to ultimate_bot_data.json")
            print(f"   • Auto-reply groups: {len(self.auto_reply_groups)}")
            print(f"   • Auto-reply users: {len(self.auto_reply_users)}")
            print(f"   • Auto delete: {'Enabled' if self.auto_delete_enabled else 'Disabled'}")
            print(f"   • Deleted messages: {self.deleted_messages_count}")

        except Exception as e:
            print(f"❌ Error saving data: {e}")

    # ========== ⚡ EVENT HANDLERS ==========
    async def setup_handlers(self):
        """Setup all event handlers"""

        # ======== 🗑️ AUTO DELETE COMMANDS ========
        @self.client.on(events.NewMessage(pattern='/ကန်'))
        async def auto_delete_start(event):
            await self.start_auto_delete(event)

        @self.client.on(events.NewMessage(pattern='/မကန်နဲ့'))
        async def auto_delete_stop(event):
            await self.stop_auto_delete(event)

        # ======== 🔵 AUTO MENTION COMMANDS ========
        @self.client.on(events.NewMessage(pattern='/ဆဲမယ်'))
        async def auto_mention_start(event):
            await self.start_auto_mention(event)

        @self.client.on(events.NewMessage(pattern='/ရပ်လိုက်'))
        async def auto_mention_stop(event):
            await self.stop_auto_mention(event)

        @self.client.on(events.NewMessage(pattern='/setnick'))
        async def auto_mention_setnick(event):
            await self.set_nickname(event)

        @self.client.on(events.NewMessage(pattern='/setsec'))
        async def auto_mention_setsec(event):
            await self.set_mention_interval(event)

        @self.client.on(events.NewMessage(pattern='/mention_status'))
        async def auto_mention_status(event):
            await self.show_mention_status(event)

        # ======== 🎮 CHARACTER CATCHER COMMANDS ========
        @self.client.on(events.NewMessage(pattern='/character'))
        async def character_catcher_toggle(event):
            await self.toggle_character_catcher(event)

        @self.client.on(events.NewMessage(pattern='/character_stats'))
        async def character_stats_handler(event):
            await self.show_character_stats(event)

        @self.client.on(events.NewMessage(pattern='/character_speed'))
        async def character_speed_handler(event):
            await self.set_character_speed(event)

        @self.client.on(events.NewMessage(pattern='/clear_character_cache'))
        async def clear_character_cache_handler(event):
            await self.clear_character_cache(event)

        @self.client.on(events.NewMessage(pattern='/clear_character_queue'))
        async def clear_character_queue_handler(event):
            await self.clear_character_queue(event)

        # ======== 🎮 CHARACTER CATCHER MESSAGE HANDLERS ========
        target_bots = [self.character_bot_username, self.grab_bot_username, self.guess_bot_username]
        for bot in target_bots:
            @self.client.on(events.NewMessage(from_users=bot))
            async def handler(event):
                await self.handle_character_spawn(event)

        @self.client.on(events.NewMessage(from_users=self.cheats_bot_username))
        async def handler(event):
            await self.handle_cheats_bot_response(event)

        # ======== 🚨 IMMEDIATE CONTROL COMMANDS ========
        @self.client.on(events.NewMessage(pattern='ဟဟဟ'))
        async def immediate_stop_command(event):
            await self.stop_auto_reply_immediately(event)
            await event.delete()

        @self.client.on(events.NewMessage(pattern='ရပ်'))
        async def pause_auto_reply(event):
            if not await self.require_admin(event):
                return

            sender = await event.get_sender()

            self.stop_auto_reply_flag = True
            await event.delete()
            await self.send_dm(sender.id, "⏸️ Auto-reply PAUSED!\n'စပါ' လို့ရိုက်ရင် ပြန်စမယ်။")
            print(f"⏸️ Auto-reply paused by user {sender.id}")

        @self.client.on(events.NewMessage(pattern='စပါ'))
        async def resume_auto_reply(event):
            if not await self.require_admin(event):
                return

            sender = await event.get_sender()

            self.stop_auto_reply_flag = False
            self.skip_queue_flag = False

            await event.delete()
            await self.send_dm(sender.id, "▶️ Auto-reply RESUMED!")
            print(f"▶️ Auto-reply resumed by user {sender.id}")

        # ======== ⚡ SPEED CONTROL COMMANDS ========
        @self.client.on(events.NewMessage(pattern='/delay'))
        async def set_custom_delay(event):
            if not await self.require_admin(event):
                return

            sender = await event.get_sender()

            try:
                args = event.message.text.split()
                if len(args) > 1:
                    try:
                        new_delay = float(args[1])
                    except ValueError:
                        await self.send_dm(sender.id, "❌ Please enter a valid number")
                        await event.delete()
                        return

                    if new_delay >= 0.1:
                        old_delay = self.auto_reply_delay
                        self.auto_reply_delay = new_delay
                        await self.send_dm(sender.id, f"⚡ Auto-reply delay changed!\nOld: {old_delay}s → New: {new_delay}s\nကြိုက်သလောက်ထားလို့ရ!")
                        self.save_data()
                        print(f"⚡ Auto-reply delay changed: {old_delay}s → {new_delay}s")
                    elif new_delay == 0:
                        old_delay = self.auto_reply_delay
                        self.auto_reply_delay = 0
                        await self.send_dm(sender.id, f"⚡ INSTANT REPLY MODE!\nDelay set to 0 seconds\nစာတွေ ချက်ချင်းပြန်ပို့မယ်!")
                        self.save_data()
                        print(f"⚡ Instant reply mode activated (0 seconds)")
                    else:
                        await self.send_dm(sender.id, "❌ Delay must be at least 0.1 seconds (or 0 for instant)")
                else:
                    await self.send_dm(sender.id, f"⚡ Usage: /delay <seconds>\nCurrent delay: {self.auto_reply_delay}s\nExample: /delay 0.1 (super fast), /delay 0 (instant)")
            except Exception as e:
                await self.send_dm(sender.id, f"❌ Error: {str(e)}")
            await event.delete()

        @self.client.on(events.NewMessage(pattern='/currentdelay'))
        async def show_current_delay(event):
            if not await self.require_admin(event):
                return

            sender = await event.get_sender()

            delay_text = f"⏱️ Current auto-reply delay: {self.auto_reply_delay} seconds"
            if self.auto_reply_delay == 0:
                delay_text += " ⚡ (INSTANT REPLY MODE)"
            elif self.auto_reply_delay <= 0.5:
                delay_text += " ⚡ (SUPER FAST)"
            elif self.auto_reply_delay <= 2:
                delay_text += " 🚀 (FAST)"

            await self.send_dm(sender.id, f"{delay_text}\n⚡ Change with: /delay <seconds>")
            await event.delete()

        # ======== 🎯 AUTO-REPLY TARGET COMMANDS ========
        @self.client.on(events.NewMessage(pattern='ဘာလဲလီးလား'))
        async def add_group_target(event):
            if not await self.require_admin(event):
                return

            if not event.is_private:
                sender = await event.get_sender()
                chat_id = event.chat_id

                self.auto_reply_groups.add(chat_id)
                await event.delete()

                await self.send_dm(sender.id, f"✅ Group added to auto-reply!\nChat ID: {chat_id}\nCurrent delay: {self.auto_reply_delay}s\nTotal groups: {len(self.auto_reply_groups)}")
                self.save_data()
                print(f"✅ Added group {chat_id} to auto-reply")

        @self.client.on(events.NewMessage(pattern='ဟဟဟဟ'))
        async def remove_group_target(event):
            if not await self.require_admin(event):
                return

            if not event.is_private:
                sender = await event.get_sender()
                chat_id = event.chat_id

                if chat_id in self.auto_reply_groups:
                    self.auto_reply_groups.discard(chat_id)
                    await event.delete()
                    await self.send_dm(sender.id, f"❌ Group removed from auto-reply!\nChat ID: {chat_id}")
                    self.save_data()
                    print(f"❌ Removed group {chat_id} from auto-reply")
                else:
                    await event.delete()
                    await self.send_dm(sender.id, f"⚠️ Group not in auto-reply list\nChat ID: {chat_id}")

        @self.client.on(events.NewMessage(pattern='/ပြန်ပြော'))
        async def add_user_target(event):
            if not await self.require_admin(event):
                return

            if event.is_reply:
                sender = await event.get_sender()
                reply_msg = await event.get_reply_message()
                reply_sender = await reply_msg.get_sender()

                if isinstance(reply_sender, User):
                    self.auto_reply_users.add(reply_sender.id)
                    await event.delete()
                    await self.send_dm(sender.id, f"✅ User added to auto-reply!\nUser ID: {reply_sender.id}\nTotal users: {len(self.auto_reply_users)}")
                    self.save_data()
                    print(f"✅ Added user {reply_sender.id} to auto-reply")

        @self.client.on(events.NewMessage(pattern='ဟဟ'))
        async def remove_user_target(event):
            if not await self.require_admin(event):
                return

            if event.is_reply:
                sender = await event.get_sender()
                reply_msg = await event.get_reply_message()
                reply_sender = await reply_msg.get_sender()

                if isinstance(reply_sender, User):
                    self.auto_reply_users.discard(reply_sender.id)
                    await event.delete()
                    await self.send_dm(sender.id, f"❌ User removed from auto-reply!\nUser ID: {reply_sender.id}")
                    self.save_data()
                    print(f"❌ Removed user {reply_sender.id} from auto-reply")

        @self.client.on(events.NewMessage(pattern='okeokebro'))
        async def exclude_user(event):
            if not await self.require_admin(event):
                return

            if event.is_reply:
                sender = await event.get_sender()
                reply_msg = await event.get_reply_message()
                reply_sender = await reply_msg.get_sender()

                if isinstance(reply_sender, User):
                    self.excluded_users.add(reply_sender.id)
                    await event.delete()
                    await self.send_dm(sender.id, f"⛔ User excluded from auto-reply!\nUser ID: {reply_sender.id}")
                    self.save_data()
                    print(f"⛔ Excluded user {reply_sender.id} from auto-reply")

        @self.client.on(events.NewMessage(pattern='မအေလိုးကိုက်'))
        async def include_user(event):
            if not await self.require_admin(event):
                return

            if event.is_reply:
                sender = await event.get_sender()
                reply_msg = await event.get_reply_message()
                reply_sender = await reply_msg.get_sender()

                if isinstance(reply_sender, User):
                    self.excluded_users.discard(reply_sender.id)
                    await event.delete()
                    await self.send_dm(sender.id, f"✅ User included back in auto-reply!\nUser ID: {reply_sender.id}")
                    self.save_data()
                    print(f"✅ Included user {reply_sender.id} back in auto-reply")

        # ======== 📝 REPLY MANAGEMENT COMMANDS ========
        @self.client.on(events.NewMessage(pattern='/replies'))
        async def show_replies(event):
            if not await self.require_admin(event):
                return

            sender = await event.get_sender()

            if not self.reply_messages:
                await self.send_dm(sender.id, "📭 No reply messages found. Use /add_reply to add some.")
            else:
                replies = "\n".join([f"{i+1}. {msg[:100]}..." if len(msg) > 100 else f"{i+1}. {msg}" 
                                   for i, msg in enumerate(self.reply_messages[:20])])

                if len(self.reply_messages) > 20:
                    replies += f"\n\n... and {len(self.reply_messages) - 20} more replies"

                await self.send_dm(sender.id, f"💬 Reply Messages ({len(self.reply_messages)} total):\n\n{replies}")
            await event.delete()

        @self.client.on(events.NewMessage(pattern='/add_reply'))
        async def add_reply(event):
            if not await self.require_admin(event):
                return

            sender = await event.get_sender()

            try:
                args = event.message.text.split(maxsplit=1)
                if len(args) > 1:
                    new_reply = args[1]
                    self.reply_messages.append(new_reply)
                    await self.send_dm(sender.id, f"✅ Reply added!\nTotal replies: {len(self.reply_messages)}\n\n{new_reply[:200]}...")
                    self.save_data()
                    print(f"✅ Added reply: {new_reply[:50]}...")
                else:
                    await self.send_dm(sender.id, "❌ Usage: /add_reply <message>")
            except:
                await self.send_dm(sender.id, "❌ Error adding reply")
            await event.delete()

        @self.client.on(events.NewMessage(pattern='/remove_reply'))
        async def remove_reply(event):
            if not await self.require_admin(event):
                return

            sender = await event.get_sender()

            try:
                args = event.message.text.split()
                if len(args) > 1:
                    index = int(args[1]) - 1
                    if 0 <= index < len(self.reply_messages):
                        removed = self.reply_messages.pop(index)
                        await self.send_dm(sender.id, f"🗑️ Removed reply #{index+1}:\n{removed[:200]}...\nTotal replies: {len(self.reply_messages)}")
                        self.save_data()
                        print(f"🗑️ Removed reply #{index+1}")
                    else:
                        await self.send_dm(sender.id, f"❌ Invalid index. Please use 1-{len(self.reply_messages)}")
                else:
                    await self.send_dm(sender.id, "❌ Usage: /remove_reply <number>")
            except:
                await self.send_dm(sender.id, "❌ Error removing reply")
            await event.delete()

        @self.client.on(events.NewMessage(pattern='/clear_replies'))
        async def clear_replies(event):
            if not await self.require_admin(event):
                return

            sender = await event.get_sender()

            count = len(self.reply_messages)
            self.reply_messages.clear()
            await self.send_dm(sender.id, f"🧹 Cleared ALL {count} reply messages!")
            self.save_data()
            print(f"🧹 Cleared {count} reply messages")
            await event.delete()

        # ======== 📊 STATUS & HELP COMMANDS ========
        @self.client.on(events.NewMessage(pattern='/help'))
        async def show_help(event):
            sender = await event.get_sender()

            if not await self.is_admin(sender.id):
                await event.delete()
                return

            help_text = f"""🤖 ULTIMATE CHARACTER CATCHER BOT - ADMIN COMMANDS

🗑️ AUTO DELETE SYSTEM:
• /ကန် - User ရဲ့ message ကို reply ထောက်ပြီး auto delete စတင်ရန်
• /မကန်နဲ့ - Auto delete ရပ်ရန်

🔵 AUTO MENTION SYSTEM:
• /ဆဲမယ် @username or user_id - Auto Mention စတင်ရန်
• /ရပ်လိုက် - Auto Mention ရပ်ရန်
• /setnick @username nickname - Nickname သတ်မှတ်ရန်
• /setsec seconds - Mention အကြိမ်အချိန်သတ်မှတ်ရန်
• /mention_status - လက်ရှိအခြေအနေကြည့်ရန်

🎮 CHARACTER CATCHER:
• /character - Character Catcher ဖွင့်/ပိတ်
• /character_stats - Character Catcher stats ကြည့်
• /character_speed <setting> <value> - Speed ပြင်ရန်
• /clear_character_cache - Cache ရှင်းရန်
• /clear_character_queue - Queue ရှင်းရန်
• 🗑️ Auto Delete: /catch messages will be deleted after 0.8 seconds

🚨 IMMEDIATE CONTROL:
• ဟဟဟ - AUTO-REPLY အားလုံးရပ် & GROUP ဖြုတ်
• ရပ် - Auto-reply ခေတ္တရပ်
• စပါ - Auto-reply ပြန်စ

⚡ SPEED CONTROL:
• /delay <seconds> - Auto-reply delay ပြောင်းရန်
• /currentdelay - လက်ရှိ delay ကြည့်ရန်

🎯 AUTO-REPLY TARGETS:
• ဘာလဲလီးလား - Group target အဖြစ်သတ်မှတ်
• ဟဟဟဟ - Group target ကနေဖယ်
• /ပြန်ပြော - User target အဖြစ်သတ်မှတ် (Reply)
• ဟဟ - User target ကနေဖယ် (Reply)
• okeokebro - User exclude လုပ်ရန် (Reply)
• မအေလိုးကိုက် - User include ပြန်လုပ်ရန် (Reply)

📝 REPLY MANAGEMENT:
• /replies - Reply messages ကြည့်ရန်
• /add_reply <message> - Reply အသစ်ထည့်
• /remove_reply <number> - Reply ဖျက်
• /clear_replies - Reply အားလုံးဖျက်

📊 STATUS:
• /status - Bot status ကြည့်ရန်
• /save - Data သိမ်းရန်
• /whois - User info ကြည့်ရန် (Reply)

👑 ADMIN MANAGEMENT:
• /admins - Admin စာရင်းကြည့်
• /addadmin - Admin အသစ်ထည့် (Owner Only)
• /removeadmin - Admin ဖျက် (Owner Only)

📢 LOG: All logs sent to admin DM only
"""
            await self.send_dm(sender.id, help_text)
            await event.delete()

        @self.client.on(events.NewMessage(pattern='/status'))
        async def show_status(event):
            sender = await event.get_sender()

            if not await self.is_admin(sender.id):
                await event.delete()
                return

            delay_mode = ""
            if self.auto_reply_delay == 0:
                delay_mode = "⚡ INSTANT MODE"
            elif self.auto_reply_delay <= 0.5:
                delay_mode = "⚡ SUPER FAST"
            elif self.auto_reply_delay <= 2:
                delay_mode = "🚀 FAST"
            else:
                delay_mode = "🐢 NORMAL"

            # Calculate character catcher stats
            total_spawns = self.character_catcher_stats['total_spawns']
            successful = self.character_catcher_stats['successful_catches']
            success_rate = (successful / total_spawns * 100) if total_spawns > 0 else 0

            processing_times = self.character_catcher_stats['processing_time']
            avg_time = sum(processing_times) / len(processing_times) if processing_times else 0

            # Calculate auto mention stats
            active_mentions = sum(1 for v in self.auto_mention_active.values() if v)

            # Calculate auto delete stats
            active_auto_delete = len(self.auto_delete_mode)

            status_text = f"""🤖 ULTIMATE CHARACTER CATCHER BOT - STATUS

🗑️ AUTO DELETE SYSTEM:
• Active Chats: {active_auto_delete}
• Deleted Messages: {self.deleted_messages_count}
• Mode: REPLY-ONLY (user message ကို reply ထောက်မှသာ)

🔵 AUTO MENTION SYSTEM:
• Active Mentions: {active_mentions}
• Default Interval: {self.default_mention_interval}s
• Reply Messages: {len(self.reply_messages)} ခု

🎮 CHARACTER CATCHER:
• Active: {'✅ YES' if self.character_catcher_active else '❌ NO'}
• Total Spawns: {total_spawns}
• Successful: {successful}
• Success Rate: {success_rate:.1f}%
• Avg Time: {avg_time:.2f}s
• In Queue: {len(self.character_process_queue)}
• Cache: {len(self.character_name_cache)} names
• Pending: {self.character_catcher_stats['pending_requests']}
• 🗑️ Auto-Deleted /catch: {self.character_catcher_stats['auto_deleted_catch_messages']}

🚨 CONTROL STATUS:
• Auto-reply: {'❌ STOPPED' if self.stop_auto_reply_flag else '✅ RUNNING'}
• Paused: {'✅ YES' if self.paused else '❌ NO'}
• Queue Skipping: {'✅ YES' if self.skip_queue_flag else '❌ NO'}
• Processing: {'✅ Yes' if self.is_replying else '❌ No'}
• Pending Replies: {len(self.pending_replies)}

⚡ SPEED SETTINGS:
• Auto-reply Delay: {self.auto_reply_delay}s {delay_mode}
• Character Forward: {self.forward_delay}s
• Character Catch: {self.catch_delay}s
• Cheats Timeout: {self.cheats_bot_timeout}s
• Auto-Delete Delay: 0.8s

📊 AUTO-REPLY STATS:
• Active Groups: {len(self.auto_reply_groups)}
• Targeted Users: {len(self.auto_reply_users)}
• Excluded Users: {len(self.excluded_users)}
• Available Replies: {len(self.reply_messages)}
• Next Reply Index: {self.reply_index + 1}/{len(self.reply_messages)}

👑 ADMIN INFO:
• Total Admins: {len(self.admin_users)}
• Your ID: {sender.id}
• Your Status: ✅ ADMIN

📈 ACTIVITY:
• Users tracked: {len(self.user_message_times)}
• Users with replies: {len(self.last_reply_times)}
• Active conversations: {len(self.rate_limits['last_user_reply_time'])}

💾 DATA: {'✅ Saved' if os.path.exists('ultimate_bot_data.json') else '❌ Not saved'}
"""
            await self.send_dm(sender.id, status_text)
            await event.delete()

        @self.client.on(events.NewMessage(pattern='/save'))
        async def save_command(event):
            if not await self.require_admin(event):
                return

            sender = await event.get_sender()

            self.save_data()
            await self.send_dm(sender.id, "💾 Bot data saved successfully!")
            await event.delete()

        @self.client.on(events.NewMessage(pattern='/whois'))
        async def whois_command(event):
            if not await self.require_admin(event):
                return

            if event.is_reply:
                sender = await event.get_sender()
                reply_msg = await event.get_reply_message()
                reply_sender = await reply_msg.get_sender()

                if isinstance(reply_sender, User):
                    # Check if has nickname
                    nickname_data = self.auto_mention_nicknames.get(str(reply_sender.id), {})
                    nickname = nickname_data.get('nickname', 'မရှိပါ')

                    info = f"""
👤 User Information:
• ID: {reply_sender.id}
• First Name: {reply_sender.first_name or 'N/A'}
• Last Name: {reply_sender.last_name or 'N/A'}
• Username: @{reply_sender.username or 'N/A'}
• Bot: {'✅ Yes' if reply_sender.bot else '❌ No'}
• Is Admin: {'✅ Yes' if reply_sender.id in self.admin_users else '❌ No'}
• Auto-reply Target: {'✅ Yes' if reply_sender.id in self.auto_reply_users else '❌ No'}
• Excluded: {'✅ Yes' if reply_sender.id in self.excluded_users else '❌ No'}
• Auto Mention Nickname: {nickname}
"""
                    await self.send_dm(sender.id, info)
            await event.delete()

        # ========== 👑 ADMIN MANAGEMENT COMMANDS ==========
        @self.client.on(events.NewMessage(pattern='/addadmin'))
        async def add_admin_handler(event):
            if not await self.require_admin(event):
                return

            sender = await event.get_sender()

            if sender.id != self.bot_owner_id:
                await self.send_dm(sender.id, "❌ Only bot owner can add admins")
                await event.delete()
                return

            if event.is_reply:
                reply_msg = await event.get_reply_message()
                reply_sender = await reply_msg.get_sender()

                if isinstance(reply_sender, User):
                    self.admin_users.add(reply_sender.id)
                    await event.delete()
                    await self.send_dm(sender.id, f"✅ Admin အသစ်ထည့်ပြီးပါပြီ!\nUser ID: {reply_sender.id}\nTotal Admins: {len(self.admin_users)}")
                    self.save_data()
                    print(f"✅ Added admin {reply_sender.id}")

        @self.client.on(events.NewMessage(pattern='/removeadmin'))
        async def remove_admin_handler(event):
            if not await self.require_admin(event):
                return

            sender = await event.get_sender()

            if sender.id != self.bot_owner_id:
                await self.send_dm(sender.id, "❌ Only bot owner can remove admins")
                await event.delete()
                return

            if event.is_reply:
                reply_msg = await event.get_reply_message()
                reply_sender = await reply_msg.get_sender()

                if isinstance(reply_sender, User) and reply_sender.id != self.bot_owner_id:
                    self.admin_users.discard(reply_sender.id)
                    await event.delete()
                    await self.send_dm(sender.id, f"🗑️ Admin ဖျက်လိုက်ပြီ!\nUser ID: {reply_sender.id}\nTotal Admins: {len(self.admin_users)}")
                    self.save_data()
                    print(f"🗑️ Removed admin {reply_sender.id}")

        @self.client.on(events.NewMessage(pattern='/admins'))
        async def list_admins_handler(event):
            if not await self.require_admin(event):
                return

            sender = await event.get_sender()

            admin_list = "\n".join([f"• {admin_id}" for admin_id in self.admin_users])
            await self.send_dm(sender.id, f"👑 Admin List ({len(self.admin_users)} users):\n\n{admin_list}")
            await event.delete()

        # ======== 🎯 MAIN MESSAGE HANDLER ========
        @self.client.on(events.NewMessage)
        async def handle_all_messages(event):
            """Handle all messages for auto-reply system"""
            try:
                if self.stop_auto_reply_flag or self.paused:
                    return

                sender = await event.get_sender()
                me = await self.client.get_me()

                if sender.id == me.id:
                    return

                if isinstance(sender, User) and sender.bot:
                    return

                current_time = datetime.now()
                self.user_message_times[sender.id] = current_time

                await self.process_auto_reply(event, sender, current_time)

            except Exception as e:
                if "Auto-reply stopped" not in str(e):
                    print(f"❌ Error in handle_all_messages: {e}")

    # ========== 📊 CHARACTER STATS METHODS ==========
    async def show_character_stats(self, event):
        """Show character catcher statistics"""
        if not await self.require_admin(event):
            return

        sender = await event.get_sender()

        if self.character_catcher_stats['last_catch']:
            last_catch_str = self.character_catcher_stats['last_catch'].strftime('%H:%M:%S')
        else:
            last_catch_str = "Never"

        # Calculate stats
        processing_times = self.character_catcher_stats['processing_time']
        if processing_times:
            avg_time = sum(processing_times) / len(processing_times)
        else:
            avg_time = 0

        total_spawns = self.character_catcher_stats['total_spawns']
        successful = self.character_catcher_stats['successful_catches']
        success_rate = (successful / total_spawns * 100) if total_spawns > 0 else 0

        cache_total = self.cache_hits + self.cache_misses
        cache_rate = (self.cache_hits / cache_total * 100) if cache_total > 0 else 0

        stats_text = f"""
🎮 CHARACTER CATCHER STATS

📊 Performance:
• Total Spawns: {total_spawns}
• Successful: {successful}
• Failed: {self.character_catcher_stats['failed_catches']}
• Success Rate: {success_rate:.1f}%
• Last Catch: {last_catch_str}

⚡ Speed:
• Avg Time: {avg_time:.2f}s
• Cheats Requests: {self.character_catcher_stats['cheats_bot_requests']}
• Cheats Success: {self.character_catcher_stats['cheats_bot_success']}
• Pending: {self.character_catcher_stats['pending_requests']}

💾 Cache:
• Hits: {self.cache_hits}
• Misses: {self.cache_misses}
• Hit Rate: {cache_rate:.1f}%
• Cached: {len(self.character_name_cache)} names

📈 Status:
• Active: {'✅ Yes' if self.character_catcher_active else '❌ No'}
• Queue: {len(self.character_process_queue)} items
• Processing: {'✅ Yes' if self.is_processing_character else '❌ No'}

⚙️ Settings:
• Forward Delay: {self.forward_delay}s
• Catch Delay: {self.catch_delay}s
• Timeout: {self.cheats_bot_timeout}s
• 🗑️ Auto-Delete Delay: 0.8s
• 🗑️ Messages Auto-Deleted: {self.character_catcher_stats['auto_deleted_catch_messages']}
"""

        await self.send_dm(sender.id, stats_text)
        await event.delete()

    async def set_character_speed(self, event):
        """Set character catcher speed"""
        if not await self.require_admin(event):
            return

        sender = await event.get_sender()

        try:
            args = event.message.text.split()
            if len(args) == 3:
                setting = args[1]
                value = float(args[2])

                if setting == 'forward':
                    if 0.01 <= value <= 5:
                        self.forward_delay = value
                        await self.send_dm(sender.id, f"⚡ Forward delay set to {value} seconds")
                        print(f"⚡ Forward delay: {value}s")
                    else:
                        await self.send_dm(sender.id, "❌ Value must be between 0.01-5")

                elif setting == 'catch':
                    if 0.01 <= value <= 5:
                        self.catch_delay = value
                        await self.send_dm(sender.id, f"🎯 Catch delay set to {value} seconds")
                        print(f"🎯 Catch delay: {value}s")
                    else:
                        await self.send_dm(sender.id, "❌ Value must be between 0.01-5")

                elif setting == 'timeout':
                    if 1 <= value <= 10:
                        self.cheats_bot_timeout = value
                        await self.send_dm(sender.id, f"⏱️ Timeout set to {value} seconds")
                        print(f"⏱️ Timeout: {value}s")
                    else:
                        await self.send_dm(sender.id, "❌ Value must be between 1-10")

                else:
                    await self.send_dm(sender.id, "❌ Invalid setting. Use: forward, catch, or timeout")
            else:
                await self.send_dm(sender.id, f"""⚡ Usage: /character_speed <setting> <value>

Current Settings:
• Forward Delay: {self.forward_delay}s
• Catch Delay: {self.catch_delay}s
• Timeout: {self.cheats_bot_timeout}s

Examples:
• /character_speed forward 0.05
• /character_speed catch 0.1
• /character_speed timeout 3
""")
        except Exception as e:
            await self.send_dm(sender.id, f"❌ Error: {e}")

        await event.delete()

    async def clear_character_cache(self, event):
        """Clear character name cache"""
        if not await self.require_admin(event):
            return

        sender = await event.get_sender()

        cache_size = len(self.character_name_cache)
        forwarded_size = len(self.forwarded_messages)

        self.character_name_cache.clear()
        self.forwarded_messages.clear()
        self.cheats_bot_waiting_responses.clear()
        self.photo_hashes.clear()
        self.cache_hits = 0
        self.cache_misses = 0

        await self.send_dm(sender.id, f"""🧹 Cleared character cache:
• Character Cache: {cache_size} items
• Forwarded Messages: {forwarded_size} items
• Photo Hashes: Cleared
""")
        print(f"🧹 Cleared character cache")

        await event.delete()

    async def clear_character_queue(self, event):
        """Clear character processing queue"""
        if not await self.require_admin(event):
            return

        sender = await event.get_sender()

        queue_size = len(self.character_process_queue)
        self.character_process_queue.clear()

        await self.send_dm(sender.id, f"🧹 Cleared {queue_size} characters from queue")
        print(f"🧹 Cleared character queue ({queue_size} items)")

        await event.delete()

    # ========== 🚀 START BOT ==========
    async def start(self):
        """Start the bot"""
        self.client = TelegramClient(self.session_name, self.api_id, self.api_hash)

        await self.client.start()

        me = await self.client.get_me()

        print("=" * 60)
        print(f"🤖 ULTIMATE CHARACTER CATCHER BOT STARTED!")
        print(f"👤 Name: {me.first_name}")
        print(f"🆔 User ID: {me.id}")
        print("=" * 60)
        print(f"🗑️ AUTO DELETE SYSTEM")
        print(f"   • Mode: REPLY-ONLY")
        print(f"   • Deleted: {self.deleted_messages_count} messages")
        print("=" * 60)
        print(f"🔵 AUTO MENTION SYSTEM")
        print(f"   • Default Interval: {self.default_mention_interval}s")
        print(f"   • Active Mentions: {sum(1 for v in self.auto_mention_active.values() if v)}")
        print("=" * 60)
        print(f"🎯 AUTO-REPLY SYSTEM")
        print(f"   • Auto-reply Delay: {self.auto_reply_delay}s")
        print(f"   • Reply Messages: {len(self.reply_messages)}")
        print(f"   • Active Groups: {len(self.auto_reply_groups)}")
        print("=" * 60)
        print(f"🎮 CHARACTER CATCHER SYSTEM")
        print(f"   • Status: {'✅ ACTIVE' if self.character_catcher_active else '❌ INACTIVE'}")
        print(f"   • Cached Names: {len(self.character_name_cache)}")
        print(f"   • 🗑️ Auto-Delete: /catch messages will be deleted after 0.8s")
        print("=" * 60)
        print(f"👑 ADMIN SYSTEM")
        print(f"   • Admin Users: {len(self.admin_users)}")
        print(f"   • Bot Owner: {self.bot_owner_id}")
        print("=" * 60)
        print("✅ Bot is ready! Use /help for commands")
        print("=" * 60)

        # Send startup message to admin DMs
        for admin_id in self.admin_users:
            await self.send_dm(admin_id, f"""🤖 ULTIMATE CHARACTER CATCHER BOT - ONLINE

✅ Bot has started successfully!

👤 User: {me.first_name} (ID: {me.id})
🗑️ Auto Delete: READY (Reply-Only Mode)
🔵 Auto Mention: {sum(1 for v in self.auto_mention_active.values() if v)} active
💬 Auto-reply: {len(self.auto_reply_groups)} groups
🎮 Character Catcher: {'ACTIVE' if self.character_catcher_active else 'INACTIVE'}
🗑️ Auto Delete /catch: 0.8 seconds delay

⏰ Start Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
📢 Log: All logs will be sent to this DM

Commands:
• /ကန် - User message ကို reply ထောက်ပြီး auto delete စတင်ရန်
• /မကန်နဲ့ - Auto delete ရပ်ရန်
• /help - အခြား commands များကြည့်ရန်
""")

        await self.setup_handlers()
        await self.client.run_until_disconnected()


def main():
    bot = UltimateCharacterCatcherBot()
    asyncio.run(bot.start())


if __name__ == '__main__':
    main()
