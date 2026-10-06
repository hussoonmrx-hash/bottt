import discord
from discord.ext import commands
import json
import re
import asyncio
from datetime import timedelta, datetime, timezone
from urllib.parse import urlparse
import aiohttp


BANNED_USER_IDS = {1536524633858113596}

class Protection(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.link_regex = re.compile(r'https?://[^\s]+')
        self.spam_control = {}
        self.mention_warnings = {}
        self.everyone_warnings = {}
        self.bot_color = 0x2b2d31
        self.raid_joins = {}
        self.nuke_channel_deletes = {}
        self.nuke_role_deletes = {}
        self.mass_kick_tracker = {}
        self.voice_disconnect_tracker = {}

        # --- Advanced Protection ---
        self.invite_regex = re.compile(r'(discord\.(gg|com/invite|me)/[a-zA-Z0-9]+|discordapp\.com/invite/[a-zA-Z0-9]+)')
        # Shortened URL protection (discord.gg, bit.ly, tinyurl, etc.)
        self.shortened_url_regex = re.compile(
            r'(?:https?://)?(?:'
            r'discord\.(?:gg|com/invite|me)/[a-zA-Z0-9]+|'
            r'bit\.ly/[a-zA-Z0-9]+|'
            r'tinyurl\.com/[a-zA-Z0-9]+|'
            r't\.co/[a-zA-Z0-9]+|'
            r'short\.link/[a-zA-Z0-9]+|'
            r'cutt\.ly/[a-zA-Z0-9]+|'
            r'rb\.gy/[a-zA-Z0-9]+|'
            r'v\.gd/[a-zA-Z0-9]+|'
            r'is\.gd/[a-zA-Z0-9]+|'
            r'ow\.ly/[a-zA-Z0-9]+|'
            r'buff\.ly/[a-zA-Z0-9]+|'
            r'rebrand\.ly/[a-zA-Z0-9]+|'
            r'bl\.ink/[a-zA-Z0-9]+|'
            r'short\.io/[a-zA-Z0-9]+|'
            r'lnkd\.in/[a-zA-Z0-9]+|'
            r'goo\.gl/[a-zA-Z0-9]+|'
            r'adf\.ly/[a-zA-Z0-9]+|'
            r'bc\.vc/[a-zA-Z0-9]+|'
            r'clck\.ru/[a-zA-Z0-9]+|'
            r'sh\.st/[a-zA-Z0-9]+'
            r')',
            re.IGNORECASE
        )
        self.webhook_messages = {}  # {webhook_id: [timestamps]}
        self.join_verification = {}  # {guild_id: {user_id: verified}}
        self.vpn_cache = {}  # {ip: (is_vpn, timestamp)}

        # --- NEW: Advanced Protection Systems ---
        self.antiraid_join_tracker = {}  # {guild_id: {subnet: [timestamps]}}
        self.spam_patterns = {}  # {user_id: {pattern_hash: count}}
        self.honeypot_channels = set()  # channel_ids that are traps
        self.zalgo_regex = re.compile(r'[\u0300-\u036f\u1ab0-\u1aff\u1dc0-\u1dff\u20d0-\u20ff\ufe20-\ufe2f]')
        self.invisible_char_regex = re.compile(r'[\u200b-\u200f\u202a-\u202e\u2060-\u206f\ufeff]')
        self.homoglyph_map = {
            'а': 'a', 'е': 'e', 'о': 'o', 'р': 'p', 'с': 'c', 'у': 'y', 'х': 'x',
            'і': 'i', 'ѕ': 's', 'ј': 'j', 'ѡ': 'w', 'ѕ': 's', 'ԁ': 'd', 'ԛ': 'q',
            'Ａ': 'A', 'Ｂ': 'B', 'Ｃ': 'C', 'Ｄ': 'D', 'Ｅ': 'E', 'Ｆ': 'F',
            '０': '0', '１': '1', '２': '2', '３': '3', '４': '4', '５': '5',
            '６': '6', '７': '7', '８': '8', '９': '9'
        }
        self.repeated_char_regex = re.compile(r'(.)\1{5,}')  # Same char 6+ times
        self.message_fingerprints = {}  # {user_id: [content_hashes]}
        self.join_timestamps = {}  # {guild_id: [join_timestamps]}
        self.subnet_join_tracker = {}  # {guild_id: {subnet: [timestamps]}}
        self.spam_strike_tracker = {}  # {user_id: strike_count}
        self.user_join_tracker = {}  # {user_id: [timestamps]}
        self.global_spam_tracker = {}  # {user_id: [timestamps]} - strong spam even for admins
        self.bot_message_tracker = {}  # {bot_id: count}

        # --- Emoji Reaction Spam Protection (طلب: أكثر من 4 إيموجيات من نفس الشخص = تايم 5 ساعات) ---
        self.emoji_reaction_tracker = {}  # {user_id: [ {"ts": datetime, "emoji": str, "emoji_obj": PartialEmoji, "channel_id": int, "message_id": int} ] } - global
        self.emoji_msg_tracker = {}  # {(guild_id, message_id, user_id): [ {"ts": datetime, "emoji": str, "emoji_obj": PartialEmoji} ] } - per-message

        self.bad_words_light = [
            "غبي", "يا غبي", "اهبل", "هبيلة", "دلوخ", "دلخ",
            "لوتي", "سلتوح", "سرابيت", "سربوت", "شحات", "متسول",
            "stupid", "idiot", "dumb", "fool", "loser", "jerk",
            "donkey", "monkey"
        ]

        self.bad_words_medium = [
            "كس", "طيز", "زب", "عير", "نغل", "مغولي",
            "منيوك", "مينوك", "امك", "ابوك",
            "ابن الحرام", "ولد الحرام", "كسمك", "كسختك",
            "طيزك", "عرص", "ديوث", "قواد", "شاذ", "خول", "ورع",
            "kosomk", "kosomak", "kosokhtak", "6eezak", "3ars",
            "dayouth", "gawad", "sharmota", "sharmouta", "manyouk",
            "bitch", "asshole", "dick", "pussy", "cunt", "slut",
            "whore", "faggot", "hoe", "retard"
        ]

        self.bad_words_heavy = [
            "شرمو", "سكس", "اباحه", "نيكو", "منيكو",
            "عقه", "فقحه", "شرمر", "شلموط", "كس امك",
            "قحبه", "نجس", "شرموط", "قحاب", "قحوب",
            "شرموطه", "شرموطة", "قحبة", "مصاص", "امص", "يمص",
            "تناك", "ينكح", "نكاح", "سحاق", "لوطي",
            "ممحون", "ممحونه", "ممحونة", "شهواني", "بزاز",
            "fuck", "fucker", "motherfucker", "milf", "porn",
            "sex", "hentai", "xxx", "cock", "penis", "vagina",
            "blowjob", "deepthroat", "orgasm", "cum", "semen", "prostitute"
        ]

        self.compiled_light = self.compile_bad_words(self.bad_words_light)
        self.compiled_medium = self.compile_bad_words(self.bad_words_medium)
        self.compiled_heavy = self.compile_bad_words(self.bad_words_heavy)

        self.scam_keywords = [
            "activate code", "bonus code", "rakeback", "withdrawal successful",
            "crypto bonus", "free bonus", "promo code", "claim bonus",
            "deposit bonus", "vip club", "casino bonus", "bet bonus",
            "أدخل كود", "كود بونص", "بونص مجاني", "سحب ناجح",
            "كريبتو", "تداول", "استثمار", "ربح سريع",
            "محتوى إباحي", "content is nsfw", "verify your age",
            "sugar daddy", "sugar momma", "free nitro", "airdrop",
            "矿池", "binance bonus", "bybit bonus"
        ]

    def get_config(self):
        try:
            with open('config.json', 'r') as f:
                return json.load(f)
        except:
            return {}

    def clean_content(self, content):
        content = re.sub(r'[\u0617-\u061A\u064B-\u0652\u0640]', '', content)
        return content

    def compile_bad_words(self, bad_words_list):
        compiled_patterns = []
        arabic_prefixes = r"(?:ال|وال|فال|بال|كال|لل|و|ف|ب|ك|ل|يا\s*)?"
        arabic_suffixes = r"(?:ك|كم|كن|ها|هم|هن|ني|ي|ه|ة|ان|ين|ون|وا|ات)?"
        english_prefixes = r"(?:un|re|in)?"
        english_suffixes = r"(?:ing|er|s|ed|es|y)?"

        for word in bad_words_list:
            word = word.strip()
            if not word:
                continue
            is_arabic = any(ord(c) >= 0x0600 and ord(c) <= 0x06FF for c in word)
            clean_word = word.replace(" ", "")
            pattern = r""
            for char in clean_word:
                if char in '\u0623\u0625\u0622':
                    pattern += r"[\u0623\u0625\u0622]+\s*"
                elif char in '\u0647\u0629':
                    pattern += r"[\u0647\u0629]+\s*"
                elif char in '\u064a\u0649':
                    pattern += r"[\u064a\u0649]+\s*"
                else:
                    pattern += re.escape(char) + r"+\s*"
            pattern = pattern.rstrip(r"\s*")
            if is_arabic:
                full_pattern = rf"(?:\W|^){arabic_prefixes}{pattern}{arabic_suffixes}(?:\W|$)"
            else:
                full_pattern = rf"(?:\W|^){english_prefixes}{pattern}{english_suffixes}(?:\W|$)"
            compiled_patterns.append((word, re.compile(full_pattern, re.IGNORECASE)))
        return compiled_patterns

    def find_bad_word(self, content, compiled_list):
        cleaned_content = self.clean_content(content)
        for original_word, pattern in compiled_list:
            if pattern.search(cleaned_content):
                return original_word
        return None

    def is_link_whitelisted(self, url, whitelisted_domains):
        try:
            parsed = urlparse(url)
            host = (parsed.hostname or "").lower()
            for domain in whitelisted_domains:
                if host == domain or host.endswith("." + domain):
                    return True
        except:
            pass
        return False

    def is_mention_whitelisted(self, member):
        config = self.get_config()
        whitelist_role_ids = config.get("mention_whitelisted_roles", [])
        if not whitelist_role_ids:
            return False
        member_role_ids = {r.id for r in member.roles}
        return bool(member_role_ids & set(whitelist_role_ids))

    def has_media_content(self, message: discord.Message) -> bool:
        if len(message.attachments) > 0 or len(message.stickers) > 0:
            return True
        content = message.content.lower()
        media_extensions = ('.png', '.jpg', '.jpeg', '.gif', '.webp', '.mp4', '.mov', '.mkv', '.webm', '.avi')
        if any(ext in content for ext in media_extensions):
            return True
        media_hosts = ('tenor.com', 'giphy.com', 'imgur.com', 'gfycat.com', 'cdn.discordapp.com/attachments', 'media.discordapp.net/attachments')
        if any(host in content for host in media_hosts):
            return True
        return False

    def is_media_allowed_channel(self, channel, config: dict) -> bool:
        ch_name = (getattr(channel, 'name', '') or '').lower()
        if ch_name.startswith("ticket-") or "ticket" in ch_name:
            return True

        ticket_cat_keys = [
            "ticket_category_id",
            "ticket_inquiry_category_id",
            "ticket_purchase_category_id",
            "ticket_support_category_id"
        ]
        category_id = getattr(channel, 'category_id', None)
        if category_id:
            for key in ticket_cat_keys:
                configured_id = config.get(key)
                if configured_id:
                    try:
                        if int(configured_id) == category_id:
                            return True
                    except (ValueError, TypeError):
                        pass

        allowed_single_id = config.get("allowed_image_channel_id")
        if allowed_single_id:
            try:
                if channel.id == int(allowed_single_id):
                    return True
            except (ValueError, TypeError):
                pass

        allowed_media_ids = config.get("allowed_media_channel_ids", [])
        if channel.id in allowed_media_ids or str(channel.id) in allowed_media_ids:
            return True

        clip_keywords = ["clip", "clips", "كليب", "كليبسات", "media", "صور", "ميديا"]
        if any(kw in ch_name for kw in clip_keywords):
            return True

        return False

    # ============================
    # Merchant Protection Helpers
    # ============================
    def is_merchant(self, member: discord.Member) -> bool:
        """Check if member is a merchant (has merchant role or is in merchant user IDs list)"""
        config = self.get_config()
        merchant_role_id = config.get("merchant_role_id")
        merchant_user_ids = config.get("merchant_user_ids", [])
        
        # Check role
        if merchant_role_id:
            merchant_role = member.guild.get_role(merchant_role_id)
            if merchant_role and merchant_role in member.roles:
                return True
        
        # Check user IDs
        if member.id in merchant_user_ids:
            return True
        
        return False

    def is_purchase_ticket_channel(self, channel: discord.TextChannel) -> bool:
        """Check if channel is a purchase ticket channel (in purchase category)"""
        config = self.get_config()
        purchase_category_id = config.get("ticket_purchase_category_id")
        
        if not purchase_category_id:
            return False
        
        # Check if channel is in purchase category
        if channel.category_id == purchase_category_id:
            return True
        
        # Also check channel name pattern for purchase tickets
        ch_name = (getattr(channel, 'name', '') or '').lower()
        if ch_name.startswith("ticket-"):
            # Check if it's in purchase category by name or parent
            return True
        
        return False

    def is_merchant_in_purchase_ticket(self, message: discord.Message) -> bool:
        """Check if message author is merchant AND channel is purchase ticket"""
        if not isinstance(message.author, discord.Member):
            return False
        return self.is_merchant(message.author) and self.is_purchase_ticket_channel(message.channel)

    # ═══════════════════════════════════════════
    # Advanced Protection Helpers
    # ═══════════════════════════════════════════
    async def check_vpn_proxy(self, ip: str) -> bool:
        if ip in self.vpn_cache:
            cached, ts = self.vpn_cache[ip]
            if (datetime.now(timezone.utc) - ts).total_seconds() < 3600:
                return cached
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"http://ip-api.com/json/{ip}?fields=proxy,hosting", timeout=5) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        is_vpn = data.get("proxy", False) or data.get("hosting", False)
                        self.vpn_cache[ip] = (is_vpn, datetime.now(timezone.utc))
                        return is_vpn
        except:
            pass
        self.vpn_cache[ip] = (False, datetime.now(timezone.utc))
        return False

    def is_invite_link(self, content: str) -> bool:
        return bool(self.invite_regex.search(content))

    def check_webhook_spam(self, webhook_id: int) -> bool:
        now = datetime.now(timezone.utc)
        if webhook_id not in self.webhook_messages:
            self.webhook_messages[webhook_id] = []
        self.webhook_messages[webhook_id] = [
            t for t in self.webhook_messages[webhook_id]
            if (now - t).total_seconds() < 10
        ]
        self.webhook_messages[webhook_id].append(now)
        return len(self.webhook_messages[webhook_id]) > 10

    async def verify_account(self, member: discord.Member) -> dict:
        config = self.get_config()
        if not config.get("anti_alt_enabled", True):
            return {"passed": True, "reasons": []}

        results = {"passed": True, "reasons": []}
        min_age = config.get("min_account_age_days", 7)
        require_avatar = config.get("require_avatar", True)

        account_age = (datetime.now(timezone.utc) - member.created_at).days
        if account_age < min_age:
            results["passed"] = False
            results["reasons"].append(f"عمر الحساب {account_age} يوم (أقل من {min_age} أيام)")

        if require_avatar and member.display_avatar == member.default_avatar:
            results["passed"] = False
            results["reasons"].append("لا توجد صورة بروفايل مخصصة")

        mutual = len([g for g in self.bot.guilds if g.get_member(member.id)])
        if mutual == 0:
            results["reasons"].append("لا توجد سيرفرات مشتركة (حساب جديد/معزول)")

        return results

    async def handle_verification_failure(self, member: discord.Member, results: dict):
        config = self.get_config()
        verification_channel_id = config.get("verification_channel")
        guild = member.guild
        reason = " | ".join(results["reasons"])

        await self.log_action(
            guild, "حساب مشبوه",
            f"{member.mention} (`{member.id}`) لم يجتز التحقق:\n{reason}",
            0xED4245
        )

        if verification_channel_id:
            ch = guild.get_channel(verification_channel_id)
            if ch:
                embed = discord.Embed(title="حساب يحتاج تحقق", color=0xED4245)
                embed.add_field(name="العضو", value=f"{member.mention} (`{member.id}`)", inline=True)
                embed.add_field(name="العمر", value=f"{(datetime.now(timezone.utc) - member.created_at).days} يوم", inline=True)
                embed.add_field(name="الأسباب", value="\n".join(f"• {r}" for r in results["reasons"]), inline=False)
                embed.timestamp = datetime.now(timezone.utc)
                try:
                    await ch.send(content=member.mention, embed=embed)
                except:
                    pass

        account_age = (datetime.now(timezone.utc) - member.created_at).days
        if not results["passed"] and account_age < 1:
            try:
                await member.kick(reason=f"Anti-Alt: {reason}")
            except:
                pass

    async def log_action(self, guild, title, description, color=0xE74C3C):
        config = self.get_config()
        log_channel_id = config.get("admin_log_channel_id")
        if not log_channel_id:
            return
        log_channel = guild.get_channel(int(log_channel_id))
        if not log_channel:
            try:
                log_channel = await guild.fetch_channel(int(log_channel_id))
            except:
                return
        embed = discord.Embed(title=title, description=description, color=color)
        embed.set_footer(text="ARF Security System", icon_url=self.bot.user.display_avatar.url)
        embed.timestamp = datetime.now(timezone.utc)
        try:
            await log_channel.send(embed=embed)
        except:
            pass

    async def log_mod_action(self, guild, action_type, user, moderator, reason, duration=None):
        config = self.get_config()
        channel_id = config.get("mod_action_log_channel_id")
        if not channel_id:
            return
        channel = guild.get_channel(int(channel_id))
        if not channel:
            try:
                channel = await guild.fetch_channel(int(channel_id))
            except:
                return

        if action_type == "ban":
            emoji = "🔨"
            title = "تم حظر عضو"
            color = 0xFF0000
        elif action_type == "timeout":
            emoji = "🔇"
            title = "تم تايم آوت عضو"
            color = 0xED4245
        elif action_type == "kick":
            emoji = "👢"
            title = "تم طرد عضو"
            color = 0xFAA61A
        else:
            emoji = "⚠️"
            title = action_type
            color = 0xFEE75C

        embed = discord.Embed(title=f"{emoji} {title}", color=color)
        embed.add_field(name="العضو", value=f"{user.mention} (`{user.id}`)", inline=True)
        embed.add_field(name="بواسطة", value=f"{moderator.mention}", inline=True)
        embed.add_field(name="السبب", value=reason, inline=False)
        if duration:
            embed.add_field(name="المدة", value=duration, inline=True)
        embed.set_footer(text="ARF Moderation Log")
        embed.timestamp = datetime.now(timezone.utc)
        try:
            await channel.send(embed=embed)
        except:
            pass

    # ═══════════════════════════════════════════
    # Advanced Protection Helpers
    # ═══════════════════════════════════════════
    def _get_subnet(self, ip: str) -> str:
        try:
            parts = ip.split('.')
            return '.'.join(parts[:3]) + '.0/24' if len(parts) == 4 else ip
        except:
            return ip

    def _normalize_text(self, text: str) -> str:
        normalized = []
        for ch in text:
            normalized.append(self.homoglyph_map.get(ch, ch))
        return ''.join(normalized)

    def _content_fingerprint(self, content: str) -> str:
        import hashlib
        clean = re.sub(r'\s+', '', content.lower())
        clean = self._normalize_text(clean)
        return hashlib.md5(clean.encode()).hexdigest()[:16]

    def _detect_zalgo(self, text: str) -> int:
        return len(self.zalgo_regex.findall(text))

    def _detect_invisible_chars(self, text: str) -> int:
        return len(self.invisible_char_regex.findall(text))

    def get_explicit_mentions(self, message: discord.Message):
        """
        Returns (explicit_users, explicit_roles) by checking if mention tags are explicitly present in message.content.
        Filters out automatic Discord reply mentions.
        """
        if not message.content:
            return [], []
        explicit_user_ids = set(re.findall(r'<@!?(\d+)>', message.content))
        explicit_role_ids = set(re.findall(r'<@&(\d+)>', message.content))
        exp_users = [u for u in message.mentions if str(u.id) in explicit_user_ids]
        exp_roles = [r for r in message.role_mentions if str(r.id) in explicit_role_ids]
        return exp_users, exp_roles

    def _detect_repeated_chars(self, text: str) -> bool:
        matches = self.repeated_char_regex.finditer(text)
        laughter_chars = {'ه', 'ا', 'خ', 'ف', 'و', 'y', 'h', 'a', 'w', 'k', 'l', 'o', 'x', 'd', 'j', 's', 'z', '\u0640'}
        for match in matches:
            char = match.group(1).lower()
            if char not in laughter_chars:
                return True
        return False

    def _check_spam_patterns(self, user_id: int, content: str) -> dict:
        """Returns dict with spam detection results"""
        results = {"is_spam": False, "reasons": [], "score": 0, "delete_only": False}
        fp = self._content_fingerprint(content)
        now = datetime.now(timezone.utc)

        if user_id not in self.message_fingerprints:
            self.message_fingerprints[user_id] = []

        # Keep fingerprints only from the last 10 seconds (rapid repeat window)
        self.message_fingerprints[user_id] = [
            item for item in self.message_fingerprints[user_id]
            if isinstance(item, dict) and (now - item.get("ts", now)).total_seconds() < 10
        ]

        recent_fps = [item["fp"] for item in self.message_fingerprints[user_id] if isinstance(item, dict)]

        # Duplicate message check ONLY within the last 10 seconds
        if fp in recent_fps:
            results["is_spam"] = True
            results["reasons"].append("محتوى مكرر خلال وقت قصير")
            results["score"] += 3

        if self._detect_zalgo(content) > 10:
            results["is_spam"] = True
            results["reasons"].append("نص زالجو (Zalgo text)")
            results["score"] += 4

        if self._detect_invisible_chars(content) > 5:
            results["is_spam"] = True
            results["reasons"].append("أحرف غير مرئية مشبوهة")
            results["score"] += 3

        # Check for extreme character elongation or line flood (>=30 lines or >=300 repeated chars in a row)
        # Normal letter repetitions (like "حييييييي", "ههههههههه", "هلااااااا") are allowed and NOT penalized.
        lines_count = content.count('\n') + 1
        max_repeated = 0
        for match in re.finditer(r'(.)\1{10,}', content):
            max_repeated = max(max_repeated, len(match.group(0)))

        if lines_count >= 30 or max_repeated >= 300:
            results["is_spam"] = True
            results["delete_only"] = True
            results["reasons"].append("تكرار مفرط جداً للحروف/الأسطر")

        self.message_fingerprints[user_id].append({"fp": fp, "ts": now})

        return results

    async def _check_antiraid_advanced(self, member: discord.Member):
        """Advanced anti-raid: subnet tracking, join velocity, account age correlation"""
        config = self.get_config()
        if not config.get("anti_raid_enabled", True):
            return

        guild_id = member.guild.id
        now = datetime.now(timezone.utc)

        # Track join timestamps for velocity
        if guild_id not in self.join_timestamps:
            self.join_timestamps[guild_id] = []
        self.join_timestamps[guild_id] = [
            t for t in self.join_timestamps[guild_id]
            if (now - t).total_seconds() < 60
        ]
        self.join_timestamps[guild_id].append(now)

        # Subnet tracking (simulated - real impl needs IP from audit log or external)
        account_age = (now - member.created_at).days
        is_suspicious = account_age < 7

        velocity = len(self.join_timestamps[guild_id])
        threshold = config.get("anti_raid_threshold", 10)

        if velocity >= threshold or (velocity >= threshold // 2 and is_suspicious):
            await self.log_action(
                member.guild, "رَيْد محتمل (Advanced)",
                f"انضمامات في 60ث: {velocity}\n"
                f"العتبة: {threshold}\n"
                f"الحساب مشبوه: {'نعم' if is_suspicious else 'لا'}\n"
                f"آخر عضو: {member.mention} (`{member.id}`)\n"
                f"عمر الحساب: {account_age} يوم",
                0xED4245
            )

            if velocity >= threshold:
                action = config.get("anti_raid_action", "kick")
                try:
                    if action == "ban":
                        await member.ban(reason=f"Anti-Raid Advanced: {velocity} joins/min")
                    else:
                        await member.kick(reason=f"Anti-Raid Advanced: {velocity} joins/min")
                except:
                    pass

    async def _scan_message_advanced(self, message: discord.Message) -> dict:
        """Advanced message scanning"""
        results = {"action": None, "reason": "", "severity": "low"}

        content = message.content
        if not content:
            return results

        # 1. Spam pattern detection
        spam_check = self._check_spam_patterns(message.author.id, content)
        if spam_check["is_spam"]:
            if spam_check.get("delete_only"):
                results["action"] = "delete_only"
                results["reason"] = f"Spam patterns: {', '.join(spam_check['reasons'])}"
                results["severity"] = "low"
            else:
                results["action"] = "timeout"
                results["reason"] = f"Spam patterns: {', '.join(spam_check['reasons'])}"
                results["severity"] = "medium" if spam_check["score"] >= 5 else "low"
            return results

        # 2. Invite links (if enabled)
        config = self.get_config()
        if config.get("anti_invite_enabled", True):
            if self.is_invite_link(content):
                results["action"] = "delete_timeout"
                results["reason"] = "رابط دعوة Discord"
                results["severity"] = "medium"
                return results

        # 3. Mass mentions (explicit text mentions only)
        exp_users, exp_roles = self.get_explicit_mentions(message)
        total_mentions = len(exp_users) + len(exp_roles)
        if message.mention_everyone:
            total_mentions += 5
        if total_mentions > 5:
            results["action"] = "delete_timeout"
            results["reason"] = f"منشنات مفرطة ({total_mentions})"
            results["severity"] = "high"
            return results

        # 4. Link protection with whitelist
        if self.link_regex.search(content):
            whitelisted = config.get("whitelisted_links", [])
            urls = re.findall(r'https?://[^\s]+', content)
            all_whitelisted = all(self.is_link_whitelisted(u, whitelisted) for u in urls)
            if not all_whitelisted:
                results["action"] = "delete_timeout"
                results["reason"] = "رابط غير مسموح"
                results["severity"] = "high"
                return results

        return results

    async def _apply_scan_action(self, message: discord.Message, results: dict):
        """Apply the action determined by advanced scan"""
        action = results.get("action")
        reason = results.get("reason", "Advanced protection")
        severity = results.get("severity", "low")

        if not action:
            return

        config = self.get_config()

        if action == "delete_only":
            try:
                await message.delete()
            except:
                pass
            return

        if action == "delete_timeout":
            try:
                await message.delete()
            except:
                pass
            duration_map = {"low": timedelta(minutes=2), "medium": timedelta(minutes=10), "high": timedelta(hours=1)}
            duration = duration_map.get(severity, timedelta(minutes=10))
            try:
                await message.author.timeout(duration, reason=f"Advanced Protection: {reason}")
            except:
                pass
            try:
                await message.channel.send(
                    f"{message.author.mention}, {reason}. تايم آوت {duration.seconds // 60} دقيقة.",
                    delete_after=10
                )
            except:
                pass
            await self.log_action(
                message.guild, "Advanced Protection",
                f"Member: {message.author.mention} (`{message.author.id}`)\n"
                f"Channel: {message.channel.mention}\n"
                f"Action: Delete + Timeout ({duration.seconds // 60}min)\n"
                f"Reason: {reason}\n"
                f"Severity: {severity}\n\n"
                f"Content:\n```\n{message.content[:500]}\n```",
                color=0xED4245 if severity == "high" else (0xFEE75C if severity == "medium" else 0x3498DB)
            )

        elif action == "timeout":
            duration_map = {"low": timedelta(minutes=2), "medium": timedelta(minutes=10), "high": timedelta(minutes=30)}
            duration = duration_map.get(severity, timedelta(minutes=10))
            try:
                await message.author.timeout(duration, reason=f"Advanced Protection: {reason}")
            except:
                pass
            try:
                await message.channel.send(
                    f"{message.author.mention}, {reason}. تايم آوت {duration.seconds // 60} دقيقة.",
                    delete_after=10
                )
            except:
                pass
            await self.log_action(
                message.guild, "Advanced Protection",
                f"Member: {message.author.mention} (`{message.author.id}`)\n"
                f"Channel: {message.channel.mention}\n"
                f"Action: Timeout ({duration.seconds // 60}min)\n"
                f"Reason: {reason}\n"
                f"Severity: {severity}",
                color=0xED4245 if severity == "high" else (0xFEE75C if severity == "medium" else 0x3498DB)
            )

    # ═══════════════════════════════════════════
    # Anti-Raid + Account Verification (ADVANCED)
    # ═══════════════════════════════════════════
    @commands.Cog.listener()
    async def on_member_join(self, member):
        # --- Permanent ban for blacklisted ID ---
        if member.id in BANNED_USER_IDS:
            try:
                await member.ban(reason="Blacklisted user ID - auto ban on join", delete_message_days=1)
                await self.log_action(member.guild, "🚫 Auto-Ban (Blacklist)", f"تم حظر العضو تلقائياً عند الدخول: {member.mention} (`{member.id}`)", 0xFF0000)
            except Exception as e:
                print(f"[Blacklist Ban Error] {e}")
            return
        if member.bot:
            return
        config = self.get_config()

        # Account Verification (Anti-Alt)
        if config.get("anti_alt_enabled", True):
            results = await self.verify_account(member)
            if not results["passed"]:
                await self.handle_verification_failure(member, results)

        # Anti Single-User Rejoin Spam (تخريب خروج ودخول متكرر)
        if config.get("anti_rejoin_spam_enabled", True):
            user_id = member.id
            now = datetime.now(timezone.utc)
            rejoin_window = config.get("rejoin_window_seconds", 600)  # 10 minutes
            max_rejoins = config.get("max_joins_per_user", 3)
            rejoin_action = config.get("rejoin_action", "ban")

            if user_id not in self.user_join_tracker:
                self.user_join_tracker[user_id] = []
            self.user_join_tracker[user_id] = [
                t for t in self.user_join_tracker[user_id]
                if (now - t).total_seconds() < rejoin_window
            ]
            self.user_join_tracker[user_id].append(now)

            if len(self.user_join_tracker[user_id]) >= max_rejoins:
                join_count = len(self.user_join_tracker[user_id])
                self.user_join_tracker.pop(user_id, None)
                reason = f"Anti-Rejoin Spam: Joined {join_count} times within {rejoin_window // 60} minutes"
                await self.log_action(
                    member.guild, "🚨 Anti-Rejoin Spam (تخريب دخول/خروج متكرر)",
                    f"العضو: {member.mention} (`{member.id}`)\n"
                    f"السبب: تكرار خروج ودخول مكثف ({join_count} مرات خلال {rejoin_window // 60} دقائق)\n"
                    f"الإجراء المتخذ: `{rejoin_action.upper()}`",
                    0xFF0000
                )
                try:
                    if rejoin_action == "kick":
                        await member.kick(reason=reason)
                    else:
                        await member.ban(reason=reason, delete_message_days=1)
                except Exception as e:
                    print(f"[Anti-Rejoin Spam Error] {e}")
                return

        # Advanced Anti-Raid
        if not config.get("anti_raid_enabled", True):
            return

        guild_id = member.guild.id
        threshold = config.get("anti_raid_threshold", 10)
        window = config.get("anti_raid_window_seconds", 30)
        action = config.get("anti_raid_action", "kick")

        now = datetime.now(timezone.utc)

        # Track joins per guild
        if guild_id not in self.join_timestamps:
            self.join_timestamps[guild_id] = []
        self.join_timestamps[guild_id] = [t for t in self.join_timestamps[guild_id] if (now - t).total_seconds() < window]
        self.join_timestamps[guild_id].append(now)

        # Track joins per subnet (first 3 octets of IP - simulated via join pattern)
        # Since we can't get IP from Discord, we use join velocity patterns
        join_key = f"{guild_id}:{len(self.join_timestamps[guild_id]) // 5}"  # Group by velocity
        if join_key not in self.subnet_join_tracker:
            self.subnet_join_tracker[join_key] = []
        self.subnet_join_tracker[join_key] = [t for t in self.subnet_join_tracker[join_key] if (now - t).total_seconds() < window]
        self.subnet_join_tracker[join_key].append(now)

        # Check global threshold
        global_joins = len(self.join_timestamps[guild_id])
        subnet_joins = len(self.subnet_join_tracker[join_key])

        # Dynamic threshold based on server size
        member_count = member.guild.member_count
        dynamic_threshold = max(threshold, int(member_count * 0.02))  # 2% of server size

        raid_detected = False
        raid_type = ""

        if global_joins >= dynamic_threshold:
            raid_detected = True
            raid_type = f"Global join spike ({global_joins} joins in {window}s)"
        elif subnet_joins >= threshold:
            raid_detected = True
            raid_type = f"Coordinated join pattern ({subnet_joins} similar-timing joins)"

        if raid_detected:
            self.join_timestamps[guild_id] = []
            self.subnet_join_tracker[join_key] = []
            await self.log_action(
                member.guild, "🚨 Raid Detected",
                f"Type: `{raid_type}`\nThreshold: `{dynamic_threshold}` joins in `{window}`s\nAction: `{action}`\nMember: {member.mention} (`{member.id}`)"
            )
            try:
                if action == "ban":
                    await member.ban(reason=f"Anti-Raid: {raid_type}")
                else:
                    await member.kick(reason=f"Anti-Raid: {raid_type}")
            except:
                pass

        # Honeypot: If member joins and immediately speaks in honeypot channel
        # (handled in on_message)

    # ═══════════════════════════════════════════
    # Anti-Nuke (Channel Delete)
    # ═══════════════════════════════════════════
    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel):
        config = self.get_config()
        if not config.get("anti_nuke_enabled", True):
            return

        guild_id = channel.guild.id
        threshold = config.get("anti_nuke_channel_threshold", 5)
        window = config.get("anti_nuke_window_seconds", 60)

        now = datetime.now(timezone.utc)
        if guild_id not in self.nuke_channel_deletes:
            self.nuke_channel_deletes[guild_id] = []
        self.nuke_channel_deletes[guild_id] = [t for t in self.nuke_channel_deletes[guild_id] if (now - t).total_seconds() < window]
        self.nuke_channel_deletes[guild_id].append(now)

        if len(self.nuke_channel_deletes[guild_id]) >= threshold:
            self.nuke_channel_deletes[guild_id] = []
            await self.log_action(
                channel.guild, "Nuke Detected (Channels)",
                f"Threshold: `{threshold}` channel deletions in `{window}` seconds\nLast deleted: `{channel.name}`"
            )
            try:
                async for entry in channel.guild.audit_logs(limit=5, action=discord.AuditLogAction.channel_delete):
                    if entry.user and not entry.user.bot:
                        if not (entry.user.guild_permissions.administrator or entry.user.id == channel.guild.owner_id):
                            try:
                                await entry.user.timeout(timedelta(hours=1), reason="Anti-Nuke: rapid channel deletion")
                            except:
                                pass
                        break
            except:
                pass

    # ═══════════════════════════════════════════
    # Anti-Nuke (Role Delete)
    # ═══════════════════════════════════════════
    @commands.Cog.listener()
    async def on_guild_role_delete(self, role):
        config = self.get_config()
        if not config.get("anti_nuke_enabled", True):
            return

        guild_id = role.guild.id
        threshold = config.get("anti_nuke_role_threshold", 5)
        window = config.get("anti_nuke_window_seconds", 60)

        now = datetime.now(timezone.utc)
        if guild_id not in self.nuke_role_deletes:
            self.nuke_role_deletes[guild_id] = []
        self.nuke_role_deletes[guild_id] = [t for t in self.nuke_role_deletes[guild_id] if (now - t).total_seconds() < window]
        self.nuke_role_deletes[guild_id].append(now)

        if len(self.nuke_role_deletes[guild_id]) >= threshold:
            self.nuke_role_deletes[guild_id] = []
            await self.log_action(
                role.guild, "Nuke Detected (Roles)",
                f"Threshold: `{threshold}` role deletions in `{window}` seconds\nLast deleted: `{role.name}`"
            )
            try:
                async for entry in role.guild.audit_logs(limit=5, action=discord.AuditLogAction.role_delete):
                    if entry.user and not entry.user.bot:
                        if not (entry.user.guild_permissions.administrator or entry.user.id == role.guild.owner_id):
                            try:
                                await entry.user.timeout(timedelta(hours=1), reason="Anti-Nuke: rapid role deletion")
                            except:
                                pass
                        break
            except:
                pass

    # ═══════════════════════════════════════════
    # Anti Voice Disconnect
    # ═══════════════════════════════════════════
    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        if member.bot:
            return
        config = self.get_config()
        if not config.get("anti_vc_disconnect", True):
            return

        if before.channel and after.channel is None:
            try:
                async for entry in member.guild.audit_logs(limit=5, action=discord.AuditLogAction.member_disconnect):
                    if entry.user and not entry.user.bot:
                        if entry.target and entry.target.id == member.id:
                            if not (entry.user.guild_permissions.administrator or entry.user.id == member.guild.owner_id):
                                user_id = entry.user.id
                                now = datetime.now(timezone.utc)
                                if user_id not in self.voice_disconnect_tracker:
                                    self.voice_disconnect_tracker[user_id] = []
                                self.voice_disconnect_tracker[user_id] = [
                                    t for t in self.voice_disconnect_tracker[user_id]
                                    if (now - t).total_seconds() < 60
                                ]
                                self.voice_disconnect_tracker[user_id].append(now)

                                if len(self.voice_disconnect_tracker[user_id]) >= 3:
                                    self.voice_disconnect_tracker[user_id] = []
                                    try:
                                        await entry.user.timeout(timedelta(hours=1), reason="Anti-VC: repeated disconnects")
                                    except:
                                        pass
                                    await self.log_action(
                                        member.guild, "Voice Disconnect Abuse",
                                        f"User: {entry.user.mention} (`{entry.user.id}`)\nDisconnected multiple users\nAction: 1 hour timeout"
                                    )
                                else:
                                    try:
                                        await entry.user.timeout(timedelta(minutes=10), reason="Anti-VC: unauthorized disconnect")
                                    except:
                                        pass
                                    await self.log_action(
                                        member.guild, "Voice Disconnect Protection",
                                        f"User: {entry.user.mention} (`{entry.user.id}`)\nDisconnected: {member.mention}\nAction: 10 minute timeout"
                                    )
                            break
            except:
                pass

    # ═══════════════════════════════════════════
    # Anti Mass Kick
    # ═══════════════════════════════════════════
    @commands.Cog.listener()
    async def on_member_remove(self, member):
        if member.bot:
            return
        config = self.get_config()
        if not config.get("anti_mass_kick_enabled", True):
            return

        try:
            async for entry in member.guild.audit_logs(limit=3, action=discord.AuditLogAction.kick):
                if entry.user and not entry.user.bot:
                    if entry.target and entry.target.id == member.id:
                        kicker_id = entry.user.id
                        now = datetime.now(timezone.utc)
                        threshold = config.get("anti_mass_kick_threshold", 3)
                        window = config.get("anti_mass_kick_window_seconds", 30)

                        if kicker_id not in self.mass_kick_tracker:
                            self.mass_kick_tracker[kicker_id] = []
                        self.mass_kick_tracker[kicker_id] = [
                            t for t in self.mass_kick_tracker[kicker_id]
                            if (now - t).total_seconds() < window
                        ]
                        self.mass_kick_tracker[kicker_id].append(now)

                        if len(self.mass_kick_tracker[kicker_id]) >= threshold:
                            self.mass_kick_tracker[kicker_id] = []
                            kicker = member.guild.get_member(kicker_id)
                            if kicker and not (kicker.guild_permissions.administrator or kicker.id == member.guild.owner_id):
                                roles_to_remove = [r for r in kicker.roles if r != member.guild.default_role]
                                if roles_to_remove:
                                    try:
                                        await kicker.remove_roles(*roles_to_remove, reason="Anti-Mass-Kick: kicked multiple members")
                                    except:
                                        pass
                                await self.log_action(
                                    member.guild, "Mass Kick Detected",
                                    f"User: {kicker.mention} (`{kicker.id}`)\nKicked {threshold}+ members in {window}s\nAction: All roles removed"
                                )
                        break
        except:
            pass

    @commands.Cog.listener()
    async def on_ready(self):
        # Auto-ban blacklisted users if already in guild
        for guild in self.bot.guilds:
            for uid in BANNED_USER_IDS:
                member = guild.get_member(uid)
                if member:
                    try:
                        await guild.ban(member, reason="Blacklisted user ID - auto ban on startup", delete_message_days=1)
                        await self.log_action(guild, "🚫 Auto-Ban (Blacklist Startup)", f"تم حظر العضو المحظور الموجود في السيرفر: {member.mention} (`{uid}`)", 0xFF0000)
                    except Exception as e:
                        print(f"[Blacklist Startup Ban Error] {e}")

    # ═══════════════════════════════════════════
    # on_message: Auto-Mod (Enhanced)
    # ═══════════════════════════════════════════
    @commands.Cog.listener()
    async def on_message(self, message):
        if not message.guild:
            return

        # --- Ignore our own bot completely ---
        if self.bot.user and message.author.id == self.bot.user.id:
            return

        # --- Permanent ban + delete for blacklisted ID (works even if bot) ---
        if message.author.id in BANNED_USER_IDS:
            try:
                await message.delete()
            except:
                pass
            try:
                await message.guild.ban(message.author, reason="Blacklisted user ID - auto ban on message", delete_message_days=1)
                await self.log_action(message.guild, "🚫 Auto-Ban (Blacklist)", f"تم حظر وحذف رسالة العضو المحظور: {message.author.mention} (`{message.author.id}`)\nالقناة: {message.channel.mention}", 0xFF0000)
            except Exception as e:
                print(f"[Blacklist Ban Error] {e}")
            return

        # --- BLOCK WEBHOOKS / APPS (لا تسمح لأي تطبيق خارجي يرسل رسائل، باستثناء بوتنا) ---
        if message.webhook_id is not None:
            try:
                await message.delete()
            except:
                pass
            await self.log_action(message.guild, "🚫 Webhook Blocked", f"تم حذف رسالة Webhook في {message.channel.mention}\nID: `{message.webhook_id}`\nالمحتوى: ```{message.content[:300]}```", 0xFF0000)
            return
        if getattr(message, 'application_id', None) is not None:
            if self.bot.application_id and message.application_id == self.bot.application_id:
                return
            if self.bot.user and message.author.id == self.bot.user.id:
                return
            try:
                await message.delete()
            except:
                pass
            await self.log_action(message.guild, "🚫 App Blocked", f"تم حذف رسالة تطبيق في {message.channel.mention}\nApp ID: `{message.application_id}`\nالمرسل: {message.author} (`{message.author.id}`)", 0xFF0000)
            # حاول حظر المرسل إذا كان بوت خارجي
            if message.author.bot and message.author.id != self.bot.user.id:
                try:
                    await message.guild.ban(message.author, reason="App/Bot sending messages blocked", delete_message_days=1)
                except:
                    pass
            return

        # --- BAN ANY BOT THAT SENDS MESSAGE (حظر فوري لأي بوت يرسل رسالة) ---
        if message.author.bot:
            if self.bot.user and message.author.id != self.bot.user.id:
                try:
                    await message.delete()
                except:
                    pass
                try:
                    await message.guild.ban(message.author, reason="Auto-Ban: Bots not allowed to send messages", delete_message_days=1)
                    await self.log_action(message.guild, "🤖 Bot Auto-Ban", f"تم حظر بوت حاول الإرسال: {message.author.mention} (`{message.author.id}`)\nالقناة: {message.channel.mention}", 0xFF0000)
                except Exception as e:
                    print(f"[Bot Auto-Ban Error] {e}")
            return

        # --- GLOBAL ANTI-SPAM STRONG (يطبق على الجميع حتى الإدمن) ---
        # Skip for merchants in purchase tickets
        if not self.is_merchant_in_purchase_ticket(message):
            try:
                now = datetime.now(timezone.utc)
                uid = message.author.id
                if uid not in self.global_spam_tracker:
                    self.global_spam_tracker[uid] = []
                self.global_spam_tracker[uid] = [t for t in self.global_spam_tracker[uid] if (now - t).total_seconds() < 6]
                self.global_spam_tracker[uid].append(now)
                count = len(self.global_spam_tracker[uid])
                # 8 رسائل خلال 6 ثواني = باند فوري حتى لو إدمن
                if count >= 8:
                    try:
                        await message.delete()
                    except:
                        pass
                    try:
                        await message.guild.ban(message.author, reason=f"Mass spam: {count} messages in 6s (even admin)", delete_message_days=1)
                        await self.log_action(message.guild, "🚨 Mass Spam Ban (Admin included)", f"العضو: {message.author.mention} (`{uid}`)\nالعدد: {count} رسائل في 6 ثواني\nالإجراء: باند فوري", 0xFF0000)
                    except Exception as e:
                        print(f"[Global Spam Ban Error] {e}")
                    self.global_spam_tracker[uid] = []
                    return
                # 5 رسائل خلال 4 ثواني = تايم 3 أيام
                elif count >= 5:
                    # check window 4s
                    recent_4s = [t for t in self.global_spam_tracker[uid] if (now - t).total_seconds() < 4]
                    if len(recent_4s) >= 5:
                        try:
                            await message.delete()
                        except:
                            pass
                        try:
                            await message.author.timeout(timedelta(days=3), reason="Spam flood 5 msgs in 4s")
                            await message.channel.send(f"{message.author.mention} تم إعطاؤك تايم آوت 3 أيام بسبب السبام المتتالي.", delete_after=10)
                            await self.log_action(message.guild, "⚠️ Spam Flood Timeout", f"العضو: {message.author.mention} (`{uid}`)\nالعدد: 5 رسائل في 4 ثواني\nالإجراء: تايم 3 أيام", 0xED4245)
                        except:
                            pass
                        return
            except Exception as e:
                print(f"[Global Spam Check Error] {e}")

        config = self.get_config()
        content = message.content.strip()

        is_staff = (
            message.author.guild_permissions.manage_messages
            or message.author.guild_permissions.administrator
            or message.author.guild_permissions.manage_channels
        )

        is_mention_wl = self.is_mention_whitelisted(message.author)

        # --- MERCHANT EXEMPTION CHECK ---
        is_merchant_in_purchase = self.is_merchant_in_purchase_ticket(message)

        # --- ADVANCED SCANNING (runs for everyone except staff and merchant in purchase tickets) ---
        if not is_staff and not is_merchant_in_purchase:
            # -- Anti-Media Protection (Disabled to allow images everywhere) --
            if config.get("anti_media_enabled", False) and self.has_media_content(message):
                if not self.is_media_allowed_channel(message.channel, config):
                    try:
                        await message.delete()
                        await message.channel.send(
                            f"❌ {message.author.mention}، يُسمح إرسال الصور والوسائط فقط داخل تذاكر الدعم وقنوات الكليبسات المخصصة.",
                            delete_after=6
                        )
                        await self.log_action(
                            message.guild, "Anti-Media Protection",
                            f"Member: {message.author.mention} (`{message.author.id}`)\nChannel: {message.channel.mention}\nAction: Media message deleted"
                        )
                    except Exception as me:
                        print(f"[Anti-Media Error] {me}")
                    return

            scan_result = await self._scan_message_advanced(message)
            if scan_result["action"]:
                await self._apply_scan_action(message, scan_result)
                return

        if not is_staff and not is_mention_wl and not is_merchant_in_purchase:
            # -- @everyone / @here Protection --
            if message.mention_everyone or ("@everyone" in content) or ("@here" in content):
                user_id = message.author.id
                if user_id not in self.everyone_warnings:
                    self.everyone_warnings[user_id] = 0
                self.everyone_warnings[user_id] += 1

                try:
                    await message.delete()
                except:
                    pass

                if self.everyone_warnings[user_id] >= 3:
                    duration = timedelta(minutes=30)
                    await message.author.timeout(duration, reason="Repeated @everyone/@here")
                    await message.channel.send(
                        f"{message.author.mention}, تم إعطاؤك تايم آوت لمدة 30 دقيقة بسبب تكرار منشن الجميع.",
                        delete_after=10
                    )
                    self.everyone_warnings[user_id] = 0
                elif self.everyone_warnings[user_id] == 2:
                    duration = timedelta(minutes=2)
                    await message.author.timeout(duration, reason="@everyone/@here warning")
                    await message.channel.send(
                        f"{message.author.mention}, تحذير: ميوت دقيقتين بسبب منشن الجميع. التكرار = تايم آوت.",
                        delete_after=10
                    )
                else:
                    await message.channel.send(
                        f"{message.author.mention}, تحذير: يُمنع منشنeveryone/@here.",
                        delete_after=5
                    )
                return

            # -- General Mention Spam (Explicit admin/staff mentions only, ignoring replies) --
            exp_users, exp_roles = self.get_explicit_mentions(message)
            admin_role_id = config.get("admin_role_id")
            admin_mentions_count = 0

            for u in exp_users:
                is_admin_user = (
                    u.guild_permissions.administrator or
                    u.guild_permissions.manage_messages or
                    u.guild_permissions.manage_channels or
                    (admin_role_id and any(r.id == admin_role_id for r in u.roles))
                )
                if is_admin_user:
                    admin_mentions_count += 1

            for r in exp_roles:
                if (admin_role_id and r.id == admin_role_id) or r.permissions.administrator or r.permissions.manage_messages:
                    admin_mentions_count += 1

            if admin_mentions_count > 0:
                user_id = message.author.id
                if user_id not in self.mention_warnings:
                    self.mention_warnings[user_id] = 0
                self.mention_warnings[user_id] += admin_mentions_count

                if self.mention_warnings[user_id] >= 5:
                    try:
                        await message.delete()
                    except:
                        pass
                    duration = timedelta(minutes=15)
                    await message.author.timeout(duration, reason="Mention spam (Admin)")
                    await message.channel.send(
                        f"{message.author.mention}, تم إعطاؤك تايم آوت لمدة 15 دقيقة بسبب تكرار منشن الإدارة.",
                        delete_after=10
                    )
                    self.mention_warnings[user_id] = 0
                    return
                elif self.mention_warnings[user_id] >= 3:
                    try:
                        await message.channel.send(
                            f"{message.author.mention}, تحذير: لا تكرر منشن الإدارة.",
                            delete_after=5
                        )
                    except:
                        pass

            # -- Ticket Mention Spam (Explicit mentions only) --
            if message.channel.name and message.channel.name.startswith("ticket-") and not is_merchant_in_purchase:
                total_explicit = len(exp_users) + len(exp_roles)
                if message.mention_everyone:
                    total_explicit += 1
                if total_explicit > 1:
                    try:
                        await message.delete()
                        duration = timedelta(minutes=15)
                        await message.author.timeout(duration, reason="Ticket mention spam")
                        await message.channel.send(
                            f"{message.author.mention}, يمكنك منشن عضو أو رتبة واحدة فقط في التذكرة. تايم آوت 15 دقيقة.",
                            delete_after=10
                        )
                        await self.log_action(
                            message.guild, "Ticket Mention Spam",
                            f"User: {message.author.mention} (`{message.author.id}`)\nChannel: {message.channel.name}\nAction: 15 minute timeout"
                        )
                    except Exception as te:
                        print(f"Error handling mention spam: {te}")
                    return

            # -- 1. Anti-Spam --
            if not is_merchant_in_purchase:
                user_id = message.author.id
                now = datetime.now(timezone.utc)
                if user_id not in self.spam_control:
                    self.spam_control[user_id] = []
                self.spam_control[user_id] = [t for t in self.spam_control[user_id] if (now - t).total_seconds() < 5]
                self.spam_control[user_id].append(now)

                if len(self.spam_control[user_id]) > 5:
                    try:
                        await message.delete()
                        duration = timedelta(days=3)
                        await message.author.timeout(duration, reason="Anti-Spam")
                        strike = self.spam_strike_tracker.get(user_id, 0) + 1
                        self.spam_strike_tracker[user_id] = strike
                        await self.log_mod_action(
                            message.guild, "timeout", message.author,
                            self.bot.user, "سبام متكرر (تكرار الرسائل)", "3 أيام"
                        )
                        if strike >= 2:
                            try:
                                await message.author.ban(reason="تكرار السبام بعد التحذير")
                                await self.log_mod_action(
                                    message.guild, "ban", message.author,
                                    self.bot.user, "تكرار السبام بعد تايم آوت سابق"
                                )
                                self.spam_strike_tracker.pop(user_id, None)
                            except:
                                pass
                            return
                        await message.channel.send(
                            f"{message.author.mention}, تم إعطاؤك تايم آوت لمدة 3 أيام بسبب السبام المتتالي.",
                            delete_after=10
                        )
                        return
                    except:
                        pass

            # -- 2. Anti-Caps --
            if not is_merchant_in_purchase:
                if len(content) > 10:
                    caps_count = sum(1 for c in content if c.isupper())
                    if caps_count / len(content) > 0.7:
                        try:
                            await message.delete()
                            await message.channel.send(
                                f"{message.author.mention}, لا تستخدم الأحرف الكبيرة بكثرة.",
                                delete_after=5
                            )
                            return
                        except:
                            pass

            # -- 3. Swear Filter (Softened) --
            if not is_merchant_in_purchase:
                found_word = self.find_bad_word(content, self.compiled_heavy)
                severity = "heavy" if found_word else None

                if not found_word:
                    found_word = self.find_bad_word(content, self.compiled_medium)
                    if found_word:
                        severity = "medium"

                if not found_word:
                    found_word = self.find_bad_word(content, self.compiled_light)
                    if found_word:
                        severity = "light"

                if found_word:
                    try:
                        await message.delete()

                        if severity == "light":
                            duration = timedelta(minutes=2)
                            msg = f"{message.author.mention}, اللغة غير اللائقة ممنوعة. ميوت دقيقتين."
                        elif severity == "medium":
                            duration = timedelta(minutes=10)
                            msg = f"{message.author.mention}, اللغة غير اللائقة ممنوعة. تايم آوت 10 دقائق."
                        else:
                            duration = timedelta(minutes=30)
                            msg = f"{message.author.mention}, اللغة غير اللائقة ممنوعة. تايم آوت 30 دقيقة."

                        await message.author.timeout(duration, reason=f"Swearing ({severity})")
                        await message.channel.send(msg, delete_after=10)

                        censored_word = found_word[0] + "*" * (len(found_word) - 1) if len(found_word) > 1 else found_word
                        await self.log_action(
                            message.guild, "Auto-Mod (Swearing)",
                            f"Member: {message.author.mention} (`{message.author.id}`)\nChannel: {message.channel.mention}\nSeverity: `{severity.upper()}`\nDuration: `{duration}`\nMatched: `{censored_word}`\n\nContent:\n```\n{content}\n```",
                            color=0xE74C3C if severity == "heavy" else (0xF1C40F if severity == "medium" else 0x3498DB)
                        )
                    except Exception as e:
                        print(f"[AutoMod Error] Swear filter: {e}")
                    return

        # -- 4. Auto Replies --
        if content == "السلام عليكم":
            await message.reply("وعليكم السلام ورحمة الله وبركاته")
        elif content in ["ارحب", "ارحبو"]:
            await message.reply("تبقا ويون")

        if not is_staff and not is_merchant_in_purchase:
            # -- Anti-Webhook Spam --
            if message.webhook_id:
                if self.check_webhook_spam(message.webhook_id):
                    try:
                        await message.delete()
                        await self.log_action(
                            message.guild, "Anti-Webhook Spam",
                            f"Webhook `{message.webhook_id}` exceeded rate limit in {message.channel.mention}",
                            0xED4245
                        )
                    except:
                        pass
                    return

            # -- Anti-Invite Links --
            if config.get("anti_invite_enabled", True):
                if self.is_invite_link(message.content):
                    try:
                        await message.delete()

                        # Ban bots immediately
                        if message.author.bot:
                            try:
                                await message.author.ban(reason="Bot sending Discord invite link")
                                await self.log_action(
                                    message.guild, "Auto-Mod (Bot Invite Ban)",
                                    f"Bot banned: {message.author.mention} (`{message.author.id}`)\nChannel: {message.channel.mention}\nContent:\n```\n{content}\n```"
                                )
                            except Exception as e:
                                print(f"[AutoMod Error] Bot ban failed: {e}")
                            return

                        # 1 hour timeout for users
                        duration = timedelta(hours=1)
                        await message.author.timeout(duration, reason="Discord invite link")
                        await message.channel.send(
                            f"{message.author.mention}, روابط الدعوة ممنوعة! تايم آوت ساعة كاملة.",
                            delete_after=10
                        )
                        await self.log_action(
                            message.guild, "Anti-Invite",
                            f"Member: {message.author.mention} (`{message.author.id}`)\nChannel: {message.channel.mention}\nContent:\n```\n{content}\n```"
                        )
                    except Exception as e:
                        print(f"[AutoMod Error] Invite filter: {e}")
                    return

            # -- Shortened URL Protection (discord.gg, bit.ly, tinyurl, etc.) --
            if config.get("anti_shortened_url_enabled", True):
                shortened_match = self.shortened_url_regex.search(message.content)
                if shortened_match:
                    try:
                        await message.delete()

                        matched_url = shortened_match.group(0)

                        # Ban bots immediately
                        if message.author.bot:
                            try:
                                await message.author.ban(reason=f"Bot sending shortened URL: {matched_url}")
                                await self.log_action(
                                    message.guild, "🚫 Shortened URL (Bot Ban)",
                                    f"Bot banned: {message.author.mention} (`{message.author.id}`)\n"
                                    f"Channel: {message.channel.mention}\n"
                                    f"Matched URL: `{matched_url}`\n"
                                    f"Content:\n```\n{content}\n```",
                                    0xFF0000
                                )
                            except Exception as e:
                                print(f"[AutoMod Error] Bot ban failed: {e}")
                            return

                        # 1 week timeout for users
                        duration = timedelta(weeks=1)
                        try:
                            await message.author.timeout(duration, reason=f"Shortened URL detected: {matched_url}")
                        except discord.Forbidden:
                            await self.log_action(
                                message.guild, "⚠️ Shortened URL — Timeout Failed",
                                f"Member: {message.author.mention} (`{message.author.id}`)\n"
                                f"Channel: {message.channel.mention}\n"
                                f"Matched URL: `{matched_url}`\n"
                                f"Error: Missing Moderate Members permission",
                                0xED4245
                            )
                            return

                        # Send log to admin/mod log channel with full user details
                        await self.log_action(
                            message.guild, "🔗 Shortened URL Detected — 1 Week Timeout",
                            f"**Member:** {message.author.mention} (`{message.author.id}`)\n"
                            f"**Username:** `{message.author}`\n"
                            f"**Display Name:** `{message.author.display_name}`\n"
                            f"**Account Created:** <t:{int(message.author.created_at.timestamp())}:F> (<t:{int(message.author.created_at.timestamp())}:R>)\n"
                            f"**Joined Server:** <t:{int(message.author.joined_at.timestamp())}:F> (<t:{int(message.author.joined_at.timestamp())}:R>) if available\n"
                            f"**Roles:** {', '.join([r.mention for r in message.author.roles[1:]]) if len(message.author.roles) > 1 else 'None'}\n"
                            f"**Is Bot:** `{message.author.bot}`\n"
                            f"**Channel:** {message.channel.mention}\n"
                            f"**Matched URL:** `{matched_url}`\n"
                            f"**Timeout Duration:** `1 Week`\n\n"
                            f"**Message Content:**\n```\n{content}\n```",
                            0xED4245
                        )

                        # Also log to mod_action_log_channel_id
                        try:
                            await self.log_mod_action(
                                message.guild, "timeout", message.author,
                                self.bot.user, f"Shortened URL: {matched_url}", "1 Week"
                            )
                        except:
                            pass

                        # Try to DM the user
                        try:
                            await message.author.send(
                                f"🔇 تم إعطاؤك تايم آوت **أسبوع كامل** في **{message.guild.name}** "
                                f"بسبب إرسال رابط مختصر: `{matched_url}`\n"
                                f"روابط الاختصار (bit.ly, tinyurl, discord.gg, إلخ) ممنوعة."
                            )
                        except:
                            pass

                    except Exception as e:
                        print(f"[AutoMod Error] Shortened URL filter: {e}")
                    return

            # -- 5. Link Protection (with Whitelist) --
            if self.link_regex.search(message.content):
                whitelisted_domains = config.get("whitelisted_links", [])
                urls = re.findall(r'https?://[^\s]+', message.content)
                all_whitelisted = all(self.is_link_whitelisted(u, whitelisted_domains) for u in urls)

                if not all_whitelisted:
                    try:
                        await message.delete()

                        # Ban bots immediately
                        if message.author.bot:
                            try:
                                await message.author.ban(reason="Bot sending non-whitelisted link")
                                await self.log_action(
                                    message.guild, "Auto-Mod (Bot Link Ban)",
                                    f"Bot banned: {message.author.mention} (`{message.author.id}`)\nChannel: {message.channel.mention}\nContent:\n```\n{content}\n```"
                                )
                            except Exception as e:
                                print(f"[AutoMod Error] Bot ban failed: {e}")
                            return

                        # 1 hour timeout for users
                        duration = timedelta(hours=1)
                        await message.author.timeout(duration, reason="Non-whitelisted link")
                        await message.channel.send(
                            f"{message.author.mention}, الروابط غير مسموح بها! تايم آوت ساعة كاملة.",
                            delete_after=10
                        )
                        await self.log_action(
                            message.guild, "Auto-Mod (Links)",
                            f"Member: {message.author.mention} (`{message.author.id}`)\nChannel: {message.channel.mention}\nContent:\n```\n{content}\n```"
                        )
                    except Exception as e:
                        print(f"[AutoMod Error] Link filter: {e}")
                    return

            # -- 6. Image Protection (Disabled to allow images everywhere) --
            if message.attachments and config.get("anti_media_enabled", False):
                is_image = any(att.content_type and att.content_type.startswith('image') for att in message.attachments)
                if is_image:
                    allowed_channel_id = config.get("allowed_image_channel_id")
                    if allowed_channel_id and message.channel.id != allowed_channel_id:
                        try:
                            await message.delete()
                            await message.channel.send(
                                f"{message.author.mention}, الصور مسموح بها فقط في <#{allowed_channel_id}>!",
                                delete_after=5
                            )
                            await self.log_action(
                                message.guild, "Auto-Mod (Image)",
                                f"Member: {message.author.mention} (`{message.author.id}`)\nChannel: {message.channel.mention}\nAction: Image deleted"
                            )
                        except Exception as e:
                            print(f"[AutoMod Error] Image filter: {e}")

            # -- 7. Scam Detection (Crypto/Gambling/Phishing) --
            if not is_staff and not is_merchant_in_purchase and not message.webhook_id:
                is_scam = False
                content_lower = content.lower()
                if any(kw in content_lower for kw in self.scam_keywords):
                    is_scam = True
                elif message.attachments and any(att.content_type and 'image' in att.content_type for att in message.attachments):
                    if any(kw in content_lower for kw in ["crypto", "bonus", "bet", "casino", "promo", "airdrop", "كود", "بونص", "سحب"]):
                        is_scam = True
                elif len(message.mentions) >= 3 and any(kw in content_lower for kw in ["free", "نترو", "هجوم", "giveaway", "هدية", "مفاجأة"]):
                    is_scam = True

                if is_scam:
                    try:
                        await message.delete()
                        try:
                            await message.author.send(
                                f"رسالتك في {message.guild.name} تم حذفها لأنها تحتوي على محتوى احتيالي أو روابط مشبوهة.\n"
                                "إذا كان هذا خطأ، تواصل مع الإدارة."
                            )
                        except:
                            pass
                        await self.log_action(
                            message.guild, "كشف احتيال",
                            f"العضو: {message.author.mention} (`{message.author.id}`)\n"
                            f"القناة: {message.channel.mention}\n"
                            f"المحتوى:\n```\n{content}\n```"
                        )
                    except Exception as e:
                        print(f"[AutoMod Error] Scam filter: {e}")

    # ═══════════════════════════════════════════
    # Emoji Reaction Spam Protection — أكثر من 4 إيموجيات متتالية من نفس الشخص = تايم 5 ساعات
    # يفرق بين من يبدا الإيموجي (initiator) ومن يصوت على إيموجي موجود (voter)
    # ═══════════════════════════════════════════
    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        # تجاهل خارج السيرفر / البوت نفسه
        if payload.guild_id is None:
            return
        if payload.user_id == self.bot.user.id:
            return

        guild = self.bot.get_guild(payload.guild_id)
        if guild is None:
            try:
                guild = await self.bot.fetch_guild(payload.guild_id)
            except:
                return
            if guild is None:
                return

        member = guild.get_member(payload.user_id)
        if member is None:
            try:
                member = await guild.fetch_member(payload.user_id)
            except:
                return
            if member is None:
                return

        if member.bot:
            return

        config = self.get_config()
        if not config.get("emoji_spam_enabled", True):
            return

        # إعفاء الإدارة (مثل باقي الحمايات) — يمكن إلغاء هذا الشرط إذا تريد تطبيقه على الإدمن أيضاً
        is_staff = (
            member.guild_permissions.manage_messages
            or member.guild_permissions.administrator
            or member.guild_permissions.manage_channels
        )
        if is_staff and not config.get("emoji_spam_affect_staff", False):
            return

        # Skip for merchants in purchase ticket channels
        try:
            channel = guild.get_channel(payload.channel_id)
            if channel and self.is_purchase_ticket_channel(channel) and self.is_merchant(member):
                return
        except:
            pass

        threshold = config.get("emoji_spam_threshold", 2)  # أكثر من 2 = 3 إيموجيات = تايم
        window = config.get("emoji_spam_window_seconds", 60)
        timeout_hours = config.get("emoji_spam_timeout_hours", 5)

        # نحتاج نعرف هل هذا الإيموجي هو الأول على الرسالة (initiator) أم تصويت (voter)
        # إذا الإيموجي كان موجود مسبقاً count > 1 → تصويت عادي، لا نحسبه سبام
        try:
            channel = guild.get_channel(payload.channel_id)
            if channel is None:
                try:
                    channel = await guild.fetch_channel(payload.channel_id)
                except:
                    return
            try:
                message = await channel.fetch_message(payload.message_id)
            except:
                # رسالة غير موجودة أو لا يمكن جلبها — نتجاهل
                return

            emoji_str = str(payload.emoji)
            matched = None
            for r in message.reactions:
                if str(r.emoji) == emoji_str:
                    matched = r
                    break

            # إذا الإيموجي موجود وعدد المستخدمين >1 → هذا تصويت على إيموجي غيره، مسموح
            if matched is not None and matched.count > 1:
                return

            # إذا لم نجد الماتش و count ضمن payload هو 1 (حالة نادرة) نعتبره initiator
            # وصولنا هنا يعني self-initiated

        except Exception as e:
            # أي خطأ في الجلب لا نعتبره سبام حتى لا نعاقب خطأ
            print(f"[EmojiSpam] fetch error: {e}")
            return

        now = datetime.now(timezone.utc)
        emoji_entry_global = {"ts": now, "emoji": emoji_str, "emoji_obj": payload.emoji, "channel_id": payload.channel_id, "message_id": payload.message_id}
        emoji_entry_msg = {"ts": now, "emoji": emoji_str, "emoji_obj": payload.emoji}

        # 1) تتبع عام لكل المستخدم (عبر كل الرسائل) خلال window
        if member.id not in self.emoji_reaction_tracker:
            self.emoji_reaction_tracker[member.id] = []
        # تنظيف القديم
        self.emoji_reaction_tracker[member.id] = [
            e for e in self.emoji_reaction_tracker[member.id] if (now - e["ts"]).total_seconds() < window
        ]
        self.emoji_reaction_tracker[member.id].append(emoji_entry_global)

        # 2) تتبع per-message (نفس الرسالة)
        msg_key = (payload.guild_id, payload.message_id, payload.user_id)
        if msg_key not in self.emoji_msg_tracker:
            self.emoji_msg_tracker[msg_key] = []
        self.emoji_msg_tracker[msg_key] = [
            e for e in self.emoji_msg_tracker[msg_key] if (now - e["ts"]).total_seconds() < window
        ]
        self.emoji_msg_tracker[msg_key].append(emoji_entry_msg)

        # تنظيف الذاكرة دورياً
        if len(self.emoji_reaction_tracker) > 500:
            # احذف القديم
            for uid in list(self.emoji_reaction_tracker.keys())[:100]:
                if not self.emoji_reaction_tracker[uid]:
                    del self.emoji_reaction_tracker[uid]
        if len(self.emoji_msg_tracker) > 1000:
            for k in list(self.emoji_msg_tracker.keys())[:200]:
                if not self.emoji_msg_tracker[k]:
                    del self.emoji_msg_tracker[k]

        # تحقق: هل تجاوز الحد في أي من التتبعين؟
        global_count = len(self.emoji_reaction_tracker[member.id])
        msg_count = len(self.emoji_msg_tracker[msg_key])

        # نعتبر سبام إذا تجاوز threshold في العام أو في نفس الرسالة
        is_spam = global_count > threshold or msg_count > threshold

        if not is_spam:
            return

        # تجنب تكرار التايم إذا المستخدم لديه تايم فعال
        try:
            if member.timed_out_until and member.timed_out_until > now:
                return
        except:
            pass

        duration = timedelta(hours=timeout_hours)
        reason = f"Emoji spam: {global_count} self-initiated reactions in {window}s (msg: {msg_count} on same message) — threshold {threshold}"

        # جمع كل المدخلات قبل المسح لإزالتها بعد التايم
        entries_to_remove = list(self.emoji_reaction_tracker.get(member.id, []))
        seen = set()
        deduped = []
        for e in entries_to_remove:
            key = (e["channel_id"], e["message_id"], e["emoji"])
            if key not in seen:
                seen.add(key)
                deduped.append(e)

        # محاولة التايم أولاً
        timeout_ok = False
        try:
            await member.timeout(duration, reason=reason)
            timeout_ok = True
        except discord.Forbidden:
            await self.log_action(
                guild, "⚠️ Emoji Spam — فشل التايم",
                f"العضو: {member.mention} (`{member.id}`)\nالقناة: {channel.mention}\nالرسالة: `{payload.message_id}`\nالسبب: أضاف {global_count} إيموجيات (في نفس الرسالة {msg_count}) خلال {window} ثانية\nخطأ: البوت لا يملك صلاحية Timeout",
                color=0xED4245
            )
            # حتى لو فشل التايم، نزيل الإيموجيات ونمسح العداد
        except Exception as e:
            print(f"[EmojiSpam] timeout error: {e}")
            # استمر للإزالة

        # إزالة كامل الإيموجيات اللي هو حاطهم اللي عرضته للتايم
        removed_count = 0
        for e in deduped:
            try:
                ch = guild.get_channel(e["channel_id"])
                if ch is None:
                    try:
                        ch = await guild.fetch_channel(e["channel_id"])
                    except:
                        continue
                try:
                    msg_rm = await ch.fetch_message(e["message_id"])
                except:
                    continue
                try:
                    await msg_rm.remove_reaction(e["emoji_obj"], member)
                    removed_count += 1
                except discord.NotFound:
                    pass
                except discord.Forbidden:
                    pass
                except Exception:
                    try:
                        await msg_rm.remove_reaction(e["emoji"], member)
                        removed_count += 1
                    except:
                        pass
                await asyncio.sleep(0.25)
            except Exception as e_rm:
                print(f"[EmojiSpam] remove error {e_rm}")
                continue

        # مسح العداد بعد العقاب حتى لا يعاقب مباشرة مرة أخرى
        self.emoji_reaction_tracker[member.id] = []
        self.emoji_msg_tracker[msg_key] = []

        if not timeout_ok:
            return

        # إرسال تنبيه خاص للعضو (DM) بدلاً من رسالة في القناة
        try:
            await member.send(
                f"🔇 تم إعطاؤك تايم آوت **{timeout_hours} ساعات** في **{guild.name}** بسبب إضافة **{global_count} إيموجيات** متتالية خلال **{window} ثانية** (أنت من بدأ الإيموجي، ليس تصويت). تم إزالة **{removed_count}** إيموجي. يُمنع سبام الإيموجيات."
            )
        except discord.Forbidden:
            pass  # العضو مغلق DM
        except:
            pass

        await self.log_action(
            guild, "🔇 Emoji Spam Timeout",
            f"العضو: {member.mention} (`{member.id}`)\n"
            f"القناة: {channel.mention}\n"
            f"الرسالة: https://discord.com/channels/{payload.guild_id}/{payload.channel_id}/{payload.message_id}\n"
            f"الإيموجي الأخير: `{emoji_str}`\n"
            f"العدد العام: `{global_count}` في `{window}`ث\n"
            f"العدد بنفس الرسالة: `{msg_count}`\n"
            f"العتبة: `>{threshold}`\n"
            f"المدة: `{timeout_hours} ساعات`\n"
            f"تمت إزالة: `{removed_count}` إيموجي\n"
            f"ملاحظة: التصويت على إيموجيات الآخرين (`count>1`) لا يُحتسب.",
            color=0xED4245
        )

        try:
            await self.log_mod_action(
                guild, "timeout", member,
                self.bot.user, f"سبام إيموجيات ({global_count} إيموجيات متتالية)", f"{timeout_hours} ساعات"
            )
        except:
            pass

    # ═══════════════════════════════════════════
    # Helper Methods
    # ═══════════════════════════════════════════
    def is_invite_link(self, content: str) -> bool:
        return bool(self.invite_regex.search(content))

    def check_webhook_spam(self, webhook_id: int) -> bool:
        now = datetime.now(timezone.utc)
        if webhook_id not in self.webhook_messages:
            self.webhook_messages[webhook_id] = []
        self.webhook_messages[webhook_id] = [
            t for t in self.webhook_messages[webhook_id]
            if (now - t).total_seconds() < 10
        ]
        self.webhook_messages[webhook_id].append(now)
        return len(self.webhook_messages[webhook_id]) > 10


async def setup(bot):
    await bot.add_cog(Protection(bot))