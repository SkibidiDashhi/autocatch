import asyncio
import json
import os
import time
import sqlite3
from datetime import datetime
from io import BytesIO
import hashlib
import tempfile
import re

from telethon import TelegramClient, events
from telethon.tl.types import User

def get_subscription_status(user_id):
    """Checks the shared SQLite database for the user's subscription status."""
    try:
        # Connects to the DB created by the Key Manager Bot
        conn = sqlite3.connect('license_database.db', timeout=10) # Added timeout for concurrent reads
        c = conn.cursor()
        c.execute("SELECT expires_at FROM active_users WHERE user_id = ?", (user_id,))
        result = c.fetchone()
        conn.close()
        
        if result:
            return datetime.fromisoformat(result[0])
        return None
    except Exception as e:
        print(f"Database error: {e}")
        return None

class UltimateCharacterCatcherBot:
    def __init__(self, session_name):
        # 🔧 BASIC CONFIGURATION
        self.api_id = '27577659'
        self.api_hash = '597f9920ee4168c320472f0d8005029a'
        self.session_name = session_name
        self.data_file = f"{self.session_name}_data.json" 

        # 👑 ADMIN SYSTEM
        self.master_admin_id = 5496411145  # Your main account
        self.admin_users = {self.master_admin_id}
        self.bot_owner_id = 5496411145

        # 🚨 CONTROL SYSTEM
        self.paused = False
        
        # ✅ APPROVED COMMAND GROUP
        self.approved_group_id = -1003857059362

        # 🛑 BLACKLISTED GROUPS (for spawns)
        self.blacklisted_groups = {-1001947407820, -1003067509608, -1003315850707}

        # 🌟 RARITY SYSTEM
        self.rarity_map = {
            '🔵': 'Common',
            '🟣': 'Uncommon',
            '🟠': 'Rare',
            '🟡': 'Legendary',
            '💮': 'Mystical',
            '⚜️': 'Divine',
            '⚡️': 'CrossVerse',
            '✨': 'Cataphract',
            '🪞': 'Supreme'
        }
        self.skipped_rarities = {'Common', 'Uncommon', 'Rare'}

        # ======== 🎮 CHARACTER CATCHER CONFIG ========
        self.character_bot_username = '@Character_Catcher_Bot'
        self.cheats_bot_username = '@HusbandosWaifusCheatsBot'

        self.character_catcher_active = True
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
            'auto_deleted_catch_messages': 0 
        }

        self.character_process_queue = []
        self.is_processing_character = False
        self.cheats_bot_waiting_responses = {}
        self.forwarded_messages = {}
        
        self.cheats_bot_pending_queue = []
        self.photo_hashes = {}
        self.photo_hash_ttl = 300

        self.forward_delay = 0.05
        self.catch_delay = 0.1
        self.cheats_bot_timeout = 8

        self.character_name_cache = {}
        self.cache_size_limit = 100
        self.cache_hits = 0
        self.cache_misses = 0

        self.client = None
        self.load_data()

    # ======== 🗑️ AUTO DELETE FOR CATCH MESSAGES ========
    async def auto_delete_catch_message(self, message, delay=0.8):
        try:
            await asyncio.sleep(delay)
            await message.delete()
            self.character_catcher_stats['auto_deleted_catch_messages'] += 1
        except Exception as e:
            pass

    # ========== 📢 LOG METHODS (DM ONLY) ==========
    async def send_dm(self, user_id, message):
        try:
            await self.client.send_message(user_id, message)
        except Exception as e:
            pass

    # ========== 🎮 CHARACTER CATCHER METHODS ========
    def get_photo_hash(self, photo_bytes):
        return hashlib.md5(photo_bytes).hexdigest()[:16]

    async def is_duplicate_photo(self, photo_bytes):
        photo_hash = self.get_photo_hash(photo_bytes)
        current_time = time.time()
        expired_hashes = [h for h, t in self.photo_hashes.items() if current_time - t > self.photo_hash_ttl]
        for h in expired_hashes:
            del self.photo_hashes[h]

        if photo_hash in self.photo_hashes:
            return True

        self.photo_hashes[photo_hash] = current_time
        return False

    async def toggle_character_catcher(self, event):
        if not await self.require_admin(event): return

        sender = await event.get_sender()

        exp = get_subscription_status(self.bot_owner_id)
        if not exp or exp < datetime.now():
            await event.reply("🔴 **ACCESS DENIED:** You do not have an active subscription.\nPlease use the Manager Bot to redeem a key.")
            return

        self.character_catcher_active = not self.character_catcher_active

        status = "✅ ACTIVATED" if self.character_catcher_active else "⏸️ DEACTIVATED"
        # Removed session name from here
        stats_msg = f"""🎮 Character Catcher {status}!

🎯 Target Bot:
• {self.character_bot_username} → /catch

🤖 Cheats Bot: {self.cheats_bot_username}
⚡ Speed: {self.forward_delay}s forward, {self.catch_delay}s catch
🗑️ Auto Delete: /catch messages will be deleted after 0.8s
"""
        await self.send_dm(sender.id, stats_msg)

        if self.character_catcher_active:
            print(f"[{self.session_name}] 🎮 Character Catcher activated!")
            asyncio.create_task(self.process_character_queue_fast())
        else:
            print(f"[{self.session_name}] 🎮 Character Catcher deactivated")

        await event.delete()

    async def handle_character_spawn(self, event):
        if not self.character_catcher_active or self.paused: return
        if event.chat_id in self.blacklisted_groups: return

        exp = get_subscription_status(self.bot_owner_id)
        if not exp or exp < datetime.now():
            print(f"[{self.session_name}] 🔴 License expired or not found. Disabling catcher.")
            self.character_catcher_active = False
            await self.send_dm(self.bot_owner_id, "🔴 **Your Auto-Catcher subscription has expired!** The catcher has been deactivated.")
            return

        try:
            message = event.message
            message_text = message.text or message.caption or ""
            sender = await event.get_sender()
            sender_username = f"@{sender.username}" if sender.username else ""

            # Only check Character Catcher Bot now
            if sender_username != self.character_bot_username: return

            spawn_patterns = [
                "ᴀ ᴄʜᴀʀᴀᴄᴛᴇʀ ʜᴀs sᴘᴀᴡɴᴇᴅ", "character has spawned", "has spawned",
                "New Waifu Is Here", "Hurry-Up,Grab Using", "Grab Using /grab",
                "ɴᴇᴡ ᴡᴀɪғᴜ ʜᴀs ᴊᴜsᴛ ᴀᴘᴘᴇᴀʀᴇᴅ", "Gʀᴇᴀᴛ! ᴀ ɴᴇᴡ ᴡᴀɪғᴜ", "ᴜsᴇ /catch ɴᴀᴍᴇ"
            ]

            if not any(pattern.lower() in message_text.lower() for pattern in spawn_patterns): return

            self.character_catcher_stats['total_spawns'] += 1

            chat = await event.get_chat()
            chat_title = getattr(chat, 'title', 'Private Chat')
            chat_id = event.chat_id
            message_id = message.id

            spawn_rarity = 'Unknown'
            for emoji, rarity_name in self.rarity_map.items():
                if emoji in message_text:
                    spawn_rarity = rarity_name
                    break

            if spawn_rarity in self.skipped_rarities:
                print(f"[{self.session_name}] ⏭️ Skipped spawn in {chat_title} (Rarity: {spawn_rarity})")
                return

            print(f"[{self.session_name}] 🎯 Character #{self.character_catcher_stats['total_spawns']} ({spawn_rarity}) detected in {chat_title}")

            if message.photo:
                file = BytesIO()
                await self.client.download_media(message.photo, file)
                photo_bytes = file.getvalue()

                if await self.is_duplicate_photo(photo_bytes):
                    self.character_catcher_stats['duplicates_skipped'] += 1
                    return

                photo_hash = self.get_photo_hash(photo_bytes)
                if photo_hash in self.character_name_cache:
                    character_name = self.character_name_cache[photo_hash]
                    self.cache_hits += 1

                    # Only use /catch now
                    command = "/catch"

                    catch_message = await self.send_catch_command_fast(
                        chat_id, character_name, command, time.time(), photo_bytes
                    )

                    if catch_message:
                        asyncio.create_task(self.auto_delete_catch_message(catch_message, 0.8))

                    self.character_catcher_stats['successful_catches'] += 1
                    return

                self.cache_misses += 1

                queue_item = {
                    'chat_id': chat_id, 'message_id': message_id, 'chat_title': chat_title,
                    'photo_bytes': photo_bytes, 'photo_hash': photo_hash,
                    'timestamp': datetime.now(), 'start_time': time.time(),
                    'sender_bot': sender_username
                }

                if len(self.character_process_queue) < 50:
                    self.character_process_queue.append(queue_item)
                    if not self.is_processing_character:
                        asyncio.create_task(self.process_character_queue_fast())
                else:
                    self.character_catcher_stats['failed_catches'] += 1
            else:
                self.character_catcher_stats['failed_catches'] += 1

        except Exception as e:
            print(f"[{self.session_name}] ❌ Error in handle_character_spawn: {e}")
            self.character_catcher_stats['failed_catches'] += 1

    async def process_character_queue_fast(self):
        if self.is_processing_character: return
        self.is_processing_character = True

        try:
            while self.character_process_queue and self.character_catcher_active and not self.paused:
                char_data = self.character_process_queue.pop(0)

                try:
                    character_name = await self.get_character_name_from_cheats_bot_fixed(char_data)

                    if character_name:
                        if len(self.character_name_cache) < self.cache_size_limit:
                            self.character_name_cache[char_data['photo_hash']] = character_name

                        command = "/catch"

                        catch_message = await self.send_catch_command_fast(
                            char_data['chat_id'], character_name, command,
                            char_data['start_time'], char_data['photo_bytes']
                        )

                        if catch_message:
                            asyncio.create_task(self.auto_delete_catch_message(catch_message, 0.8))

                        self.character_catcher_stats['successful_catches'] += 1
                    else:
                        self.character_catcher_stats['failed_catches'] += 1

                    if self.forward_delay > 0:
                        await asyncio.sleep(self.forward_delay)
                except Exception:
                    self.character_catcher_stats['failed_catches'] += 1
                    await asyncio.sleep(0.1)
        finally:
            self.is_processing_character = False

    async def get_character_name_from_cheats_bot_fixed(self, char_data):
        try:
            message = None
            try:
                forwarded = await self.client.forward_messages(
                    entity=self.cheats_bot_username, messages=char_data['message_id'],
                    from_peer=char_data['chat_id'], silent=True
                )
                message = forwarded[0] if isinstance(forwarded, list) and forwarded else forwarded
            except Exception: pass

            if message is None:
                if not char_data.get('photo_bytes') or len(char_data['photo_bytes']) < 100: return None
                tmp_path = None
                try:
                    with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as tmp:
                        tmp.write(char_data['photo_bytes'])
                        tmp_path = tmp.name
                    message = await self.client.send_file(
                        entity=self.cheats_bot_username, file=tmp_path, caption="", silent=True
                    )
                except Exception: return None
                finally:
                    if tmp_path and os.path.exists(tmp_path):
                        try: os.unlink(tmp_path)
                        except Exception: pass

            self.character_catcher_stats['cheats_bot_requests'] += 1
            self.character_catcher_stats['pending_requests'] += 1
            request_id = message.id

            self.forwarded_messages[request_id] = {
                'timestamp': time.time(), 'chat_title': char_data['chat_title'],
                'photo_hash': char_data['photo_hash']
            }

            self.cheats_bot_pending_queue.append({
                'photo_hash': char_data['photo_hash'], 'request_id': request_id,
                'timestamp': time.time(), 'chat_title': char_data['chat_title']
            })

            start_time = time.time()
            character_name = None
            failed = False

            while time.time() - start_time < self.cheats_bot_timeout:
                for msg_id, response_data in list(self.cheats_bot_waiting_responses.items()):
                    if response_data.get('photo_hash') == char_data['photo_hash']:
                        if response_data.get('failed'):
                            failed = True
                            del self.cheats_bot_waiting_responses[msg_id]
                            break
                        if response_data.get('character_name'):
                            character_name = response_data['character_name']
                            del self.cheats_bot_waiting_responses[msg_id]
                            break
                if character_name or failed:
                    if character_name: self.character_catcher_stats['cheats_bot_success'] += 1
                    break
                await asyncio.sleep(0.1)

            self.character_catcher_stats['pending_requests'] = max(0, self.character_catcher_stats['pending_requests'] - 1)
            return character_name
        except Exception:
            self.character_catcher_stats['pending_requests'] = max(0, self.character_catcher_stats['pending_requests'] - 1)
            return None

    async def handle_cheats_bot_response(self, event):
        if not self.character_catcher_active: return
        try:
            message = event.message
            message_text = message.text or ""
            forwarded_data = None

            if message.is_reply:
                try:
                    reply_to = await message.get_reply_message()
                    if reply_to and reply_to.id in self.forwarded_messages:
                        forwarded_data = self.forwarded_messages[reply_to.id]
                        for i, item in enumerate(self.cheats_bot_pending_queue):
                            if item['request_id'] == reply_to.id:
                                self.cheats_bot_pending_queue.pop(i)
                                break
                except Exception: pass

            if forwarded_data is None:
                now = time.time()
                while self.cheats_bot_pending_queue and (now - self.cheats_bot_pending_queue[0]['timestamp']) > self.cheats_bot_timeout + 5:
                    self.cheats_bot_pending_queue.pop(0)

                if self.cheats_bot_pending_queue:
                    pending = self.cheats_bot_pending_queue.pop(0)
                    forwarded_data = {
                        'timestamp': pending['timestamp'], 'chat_title': pending['chat_title'],
                        'photo_hash': pending['photo_hash']
                    }
                else: return

            error_markers = ['Unknown', 'Admin Only', 'not found', 'Not Found']
            if any(marker in message_text for marker in error_markers):
                self.cheats_bot_waiting_responses[message.id] = {
                    'character_name': None, 'photo_hash': forwarded_data['photo_hash'],
                    'timestamp': time.time(), 'failed': True
                }
                return

            character_name = None
            def clean_name(raw):
                if not raw: return raw
                return re.sub(r'[`*_~]+', '', raw).strip().rstrip(',.;:').strip()

            for line in message_text.split('\n'):
                if 'Hint' in line:
                    hint_match = re.search(r'/(?:catch|grab|guess|loot|seize)\s+(.+?)\s*$', line.strip())
                    if hint_match:
                        character_name = clean_name(hint_match.group(1))
                        break

            if not character_name:
                for cmd in ['/catch', '/grab', '/guess', '/loot', '/seize']:
                    match = re.search(fr'{cmd}\s+([^\n`*]+)', message_text)
                    if match:
                        character_name = clean_name(match.group(1))
                        break

            if character_name:
                self.cheats_bot_waiting_responses[message.id] = {
                    'character_name': character_name, 'photo_hash': forwarded_data['photo_hash'],
                    'timestamp': time.time()
                }
        except Exception: pass

    async def send_catch_command_fast(self, chat_id, character_name, command, start_time, photo_bytes):
        try:
            processing_time = time.time() - start_time
            self.character_catcher_stats['processing_time'].append(processing_time)
            if len(self.character_catcher_stats['processing_time']) > 100:
                self.character_catcher_stats['processing_time'] = self.character_catcher_stats['processing_time'][-50:]

            character_name = character_name.strip()
            if self.catch_delay > 0: await asyncio.sleep(self.catch_delay)

            full_command = f"{command} {character_name}"
            message = await self.client.send_message(chat_id, full_command, silent=True)

            self.character_catcher_stats['last_catch'] = datetime.now()
            return message
        except Exception:
            self.character_catcher_stats['failed_catches'] += 1
            return None

    # ========== 👑 ADMIN CHECK SYSTEM ==========
    async def require_admin(self, event):
        sender = await event.get_sender()
        is_admin_user = sender.id in self.admin_users
        
        # Determine if the command was sent in a valid location (PM or Approved Group)
        is_private = event.is_private
        is_approved_group = event.chat_id == self.approved_group_id
        
        if not is_admin_user or not (is_private or is_approved_group):
            await event.delete()
            return False
            
        return True

    # ========== 💾 DATA MANAGEMENT ==========
    def load_data(self):
        try:
            if os.path.exists(self.data_file):
                with open(self.data_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.character_catcher_active = data.get('character_catcher_active', False)
                    self.catch_delay = data.get('character_catch_delay', 0.1)
                    self.forward_delay = data.get('character_process_delay', 0.05)
                    self.cheats_bot_timeout = data.get('cheats_bot_timeout', 5)
                    self.character_name_cache = data.get('character_name_cache', {})

                    if 'admin_users' in data:
                        self.admin_users = set(data['admin_users'])
                        self.admin_users.add(self.master_admin_id)
                    
                    if 'skipped_rarities' in data:
                        self.skipped_rarities = set(data['skipped_rarities'])

                    if 'character_stats' in data:
                        self.character_catcher_stats = data['character_stats']
                        if 'auto_deleted_catch_messages' not in self.character_catcher_stats:
                            self.character_catcher_stats['auto_deleted_catch_messages'] = 0
        except Exception as e:
            pass 

    def save_data(self):
        try:
            data = {
                'admin_users': list(self.admin_users),
                'character_catcher_active': self.character_catcher_active,
                'character_catch_delay': self.catch_delay,
                'character_process_delay': self.forward_delay,
                'cheats_bot_timeout': self.cheats_bot_timeout,
                'character_name_cache': self.character_name_cache,
                'character_stats': self.character_catcher_stats,
                'skipped_rarities': list(self.skipped_rarities)
            }
            with open(self.data_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[{self.session_name}] ❌ Error saving data: {e}")

    # ========== ⚡ EVENT HANDLERS ==========
    async def setup_handlers(self):
        
        @self.client.on(events.NewMessage(pattern='/mysub'))
        async def check_sub_handler(event):
            if not await self.require_admin(event): return
            exp = get_subscription_status(self.bot_owner_id)
            if exp:
                if exp > datetime.now():
                    days_left = (exp - datetime.now()).days
                    await event.reply(
                        f"🟢 **Subscription Active**\n"
                        f"📅 **Expires:** {exp.strftime('%Y-%m-%d %H:%M:%S')}\n"
                        f"⏳ **Time Left:** {days_left} Days"
                    )
                else:
                    await event.reply("🔴 **Subscription Expired.**\nYour license has expired. Please redeem a new key.")
            else:
                await event.reply("🔴 **No Active Subscription.**\nYou do not have a license in the database.")

        @self.client.on(events.NewMessage(pattern=r'(?i)^/skip(?: (.+))?'))
        async def skip_rarity_handler(event):
            if not await self.require_admin(event): return
            args = event.pattern_match.group(1)
            if not args:
                skipped = ", ".join(self.skipped_rarities) if self.skipped_rarities else "None"
                await self.send_dm(event.sender_id, f"🚫 **Currently Skipped Rarities:**\n{skipped}\n\nUse `/skip <RarityName>` to toggle.")
                await event.delete()
                return

            rarity_name = args.strip().title()
            valid_names = list(self.rarity_map.values())
            if rarity_name not in valid_names:
                valid_str = ", ".join(valid_names)
                await self.send_dm(event.sender_id, f"❌ **Invalid Rarity:** {rarity_name}\nValid options: {valid_str}")
                await event.delete()
                return
            
            if rarity_name in self.skipped_rarities:
                self.skipped_rarities.remove(rarity_name)
                action = "✅ Now CATCHING"
            else:
                self.skipped_rarities.add(rarity_name)
                action = "🚫 Now SKIPPING"
                
            self.save_data()
            await self.send_dm(event.sender_id, f"{action} **{rarity_name}** characters.")
            await event.delete()

        @self.client.on(events.NewMessage(pattern='/character'))
        async def character_catcher_toggle(event):
            await self.toggle_character_catcher(event)

        @self.client.on(events.NewMessage(pattern='/character_stats'))
        async def character_stats_handler(event):
            await self.show_character_stats(event)

        @self.client.on(events.NewMessage(pattern='/pause_catch'))
        async def pause_catcher(event):
            if not await self.require_admin(event): return
            self.paused = True
            await event.reply("⏸️ Character Catcher Paused")

        @self.client.on(events.NewMessage(pattern='/resume_catch'))
        async def resume_catcher(event):
            if not await self.require_admin(event): return
            self.paused = False
            await event.reply("▶️ Character Catcher Resumed")
            
        # ========================================================
        # NEW FIX: Added missing /status, /save, /admins, /addadmin, /removeadmin
        # ========================================================
        
        @self.client.on(events.NewMessage(pattern='/save'))
        async def save_handler(event):
            if not await self.require_admin(event): return
            self.save_data()
            await event.reply("💾 **Data saved successfully!**")

        @self.client.on(events.NewMessage(pattern='/status'))
        async def status_handler(event):
            if not await self.require_admin(event): return
            status_text = f"""🤖 **BOT STATUS** ({self.session_name})
🎮 Catcher Active: {'✅ Yes' if self.character_catcher_active else '❌ No'}
⏸️ Paused: {'✅ Yes' if self.paused else '❌ No'}
⚡ Forward Delay: {self.forward_delay}s
⏱️ Catch Delay: {self.catch_delay}s
⏳ Cheats Bot Timeout: {self.cheats_bot_timeout}s
📦 Cached Names: {len(self.character_name_cache)}
 صف Queue Size: {len(self.character_process_queue)}
👥 Admins: {len(self.admin_users)}
🚫 Skipped Rarities: {', '.join(self.skipped_rarities) if self.skipped_rarities else 'None'}
"""
            await event.reply(status_text)

        @self.client.on(events.NewMessage(pattern='/admins'))
        async def admins_handler(event):
            if not await self.require_admin(event): return
            admin_list = "\n".join([f"• `{uid}`" for uid in self.admin_users])
            await event.reply(f"👥 **Current Admins:**\n{admin_list}")

        @self.client.on(events.NewMessage(pattern=r'/addadmin(?: (\d+))?'))
        async def addadmin_handler(event):
            if event.sender_id != self.bot_owner_id:
                await event.reply("❌ **Owner Only Command**")
                return
            
            new_admin_id = event.pattern_match.group(1)
            if not new_admin_id:
                await event.reply("❌ Usage: `/addadmin <user_id>`")
                return
                
            try:
                new_admin_id = int(new_admin_id)
                self.admin_users.add(new_admin_id)
                self.save_data()
                await event.reply(f"✅ Added `{new_admin_id}` to admins.")
            except ValueError:
                await event.reply("❌ Invalid User ID.")

        @self.client.on(events.NewMessage(pattern=r'/removeadmin(?: (\d+))?'))
        async def removeadmin_handler(event):
            if event.sender_id != self.bot_owner_id:
                await event.reply("❌ **Owner Only Command**")
                return
                
            del_admin_id = event.pattern_match.group(1)
            if not del_admin_id:
                await event.reply("❌ Usage: `/removeadmin <user_id>`")
                return
                
            try:
                del_admin_id = int(del_admin_id)
                if del_admin_id == self.bot_owner_id or del_admin_id == self.master_admin_id:
                    await event.reply("❌ Cannot remove the owner/master admin.")
                    return
                    
                if del_admin_id in self.admin_users:
                    self.admin_users.remove(del_admin_id)
                    self.save_data()
                    await event.reply(f"✅ Removed `{del_admin_id}` from admins.")
                else:
                    await event.reply("❌ User is not an admin.")
            except ValueError:
                await event.reply("❌ Invalid User ID.")

        # ========================================================

        # Now only listens to Character Catcher Bot
        @self.client.on(events.NewMessage(from_users=self.character_bot_username))
        async def handler(event):
            await self.handle_character_spawn(event)

        @self.client.on(events.NewMessage(from_users=self.cheats_bot_username))
        async def handler(event):
            await self.handle_cheats_bot_response(event)
            
        @self.client.on(events.NewMessage(pattern='/help'))
        async def show_help(event):
            if not await self.require_admin(event): return
            help_text = """🎮 ULTIMATE CHARACTER CATCHER BOT - ADMIN COMMANDS

🔑 Subscription Info:
• /mysub - Check your remaining license time

🕹️ Catcher Commands:
• /character - Character Catcher ဖွင့်/ပိတ်
• /skip <rarity> - Ignore specific rarity (e.g., /skip Rare)
• /character_stats - Character Catcher stats ကြည့်
• /character_speed <setting> <value> - Speed ပြင်ရန်
• /clear_character_cache - Cache ရှင်းရန်
• /clear_character_queue - Queue ရှင်းရန်
• /pause_catch - ခေတ္တရပ်ရန်
• /resume_catch - ပြန်စရန်
• /status - Bot status ကြည့်ရန်
• /save - Data သိမ်းရန်
• /admins - Admin စာရင်းကြည့်
• /addadmin - Admin အသစ်ထည့် (Owner Only)
• /removeadmin - Admin ဖျက် (Owner Only)"""
            await self.send_dm(event.sender_id, help_text)
            await event.delete()

    # ========== 📊 CHARACTER STATS METHODS ==========
    async def show_character_stats(self, event):
        if not await self.require_admin(event): return
        last_catch_str = self.character_catcher_stats['last_catch'].strftime('%H:%M:%S') if self.character_catcher_stats['last_catch'] else "Never"
        total_spawns = self.character_catcher_stats['total_spawns']
        successful = self.character_catcher_stats['successful_catches']
        success_rate = (successful / total_spawns * 100) if total_spawns > 0 else 0

        stats_text = f"""🎮 {self.session_name.upper()} STATS

📊 Performance:
• Total Spawns: {total_spawns}
• Successful: {successful}
• Failed: {self.character_catcher_stats['failed_catches']}
• Success Rate: {success_rate:.1f}%
• Last Catch: {last_catch_str}
"""
        await self.send_dm(event.sender_id, stats_text)
        await event.delete()

    # ========== 🚀 START BOT ==========
    async def start(self):
        self.client = TelegramClient(self.session_name, self.api_id, self.api_hash)
        await self.client.start()
        me = await self.client.get_me()

        self.bot_owner_id = me.id
        self.admin_users.add(me.id)

        print("=" * 60)
        print(f"🤖 BOT STARTED: {self.session_name}")
        print(f"👤 Name: {me.first_name}")
        
        # 🔒 Check DB on boot
        exp = get_subscription_status(self.bot_owner_id)
        if exp and exp > datetime.now():
            print(f"🟢 [{self.session_name}] License Active! Expires: {exp.strftime('%Y-%m-%d')}")
        else:
            print(f"🔴 [{self.session_name}] NO ACTIVE LICENSE. Features are locked.")
            self.character_catcher_active = False

        print("=" * 60)
        await self.setup_handlers()
        await self.client.run_until_disconnected()

async def main():
    # 1. Find all .session files in the current directory and IGNORE the admin bot
    session_files = [
        f for f in os.listdir('.') 
        if f.endswith('.session') and 'key_manager_bot' not in f
    ]
    
    if not session_files:
        print("❌ No userbot .session files found in the current directory.")
        return

    print(f"🔄 Found {len(session_files)} userbot session files. Starting them all concurrently...")

    # 2. Create tasks for all found sessions
    tasks = []
    for file in session_files:
        session_name = file.replace('.session', '')
        bot_instance = UltimateCharacterCatcherBot(session_name)
        tasks.append(asyncio.create_task(bot_instance.start()))

    # 3. Run all tasks simultaneously
    await asyncio.gather(*tasks)

if __name__ == '__main__':
    # Silence non-critical telethon background warnings
    import logging
    logging.getLogger('telethon').setLevel(logging.ERROR)
    
    asyncio.run(main())
