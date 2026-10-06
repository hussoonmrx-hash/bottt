import discord
from discord.ext import commands
from discord import app_commands
import json
import asyncio
import re
from datetime import datetime, timedelta, timezone
from typing import Optional, List
import aiosqlite

DB_FILE = "moderation.db"


async def init_db():
    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS cases (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                moderator_id INTEGER NOT NULL,
                action TEXT NOT NULL,
                reason TEXT,
                duration TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                moderator_id INTEGER NOT NULL,
                note TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS warnings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                moderator_id INTEGER NOT NULL,
                reason TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS config (
                guild_id INTEGER PRIMARY KEY,
                audit_log_channel INTEGER,
                mod_log_channel INTEGER,
                welcome_channel INTEGER,
                verification_channel INTEGER,
                verification_role INTEGER,
                min_account_age_days INTEGER DEFAULT 7,
                require_avatar BOOLEAN DEFAULT 1,
                anti_alt_enabled BOOLEAN DEFAULT 1,
                anti_vpn_enabled BOOLEAN DEFAULT 0,
                anti_webhook_enabled BOOLEAN DEFAULT 1,
                anti_invite_enabled BOOLEAN DEFAULT 1
            )
        """)
        await db.commit()


async def get_config(guild_id: int):
    async with aiosqlite.connect(DB_FILE) as db:
        async with db.execute("SELECT * FROM config WHERE guild_id = ?", (guild_id,)) as cur:
            row = await cur.fetchone()
            if row:
                cols = [d[0] for d in cur.description]
                return dict(zip(cols, row))
            return {
                "guild_id": guild_id,
                "audit_log_channel": None,
                "mod_log_channel": None,
                "welcome_channel": None,
                "verification_channel": None,
                "verification_role": None,
                "min_account_age_days": 7,
                "require_avatar": 1,
                "anti_alt_enabled": 1,
                "anti_vpn_enabled": 0,
                "anti_webhook_enabled": 1,
                "anti_invite_enabled": 1
            }


async def set_config(guild_id: int, **kwargs):
    async with aiosqlite.connect(DB_FILE) as db:
        existing = await get_config(guild_id)
        existing.update(kwargs)
        cols = ", ".join([f"{k} = ?" for k in existing.keys() if k != "guild_id"])
        vals = [v for k, v in existing.items() if k != "guild_id"] + [guild_id]
        await db.execute(f"INSERT OR REPLACE INTO config ({', '.join(existing.keys())}) VALUES ({', '.join(['?'] * len(existing))})", list(existing.values()))
        await db.commit()


async def add_case(guild_id: int, user_id: int, moderator_id: int, action: str, reason: str = None, duration: str = None):
    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute(
            "INSERT INTO cases (guild_id, user_id, moderator_id, action, reason, duration) VALUES (?, ?, ?, ?, ?, ?)",
            (guild_id, user_id, moderator_id, action, reason, duration)
        )
        await db.commit()


async def get_cases(guild_id: int, user_id: int) -> List[dict]:
    async with aiosqlite.connect(DB_FILE) as db:
        async with db.execute(
            "SELECT * FROM cases WHERE guild_id = ? AND user_id = ? ORDER BY created_at DESC",
            (guild_id, user_id)
        ) as cur:
            rows = await cur.fetchall()
            cols = [d[0] for d in cur.description]
            return [dict(zip(cols, r)) for r in rows]


async def add_note(guild_id: int, user_id: int, moderator_id: int, note: str):
    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute(
            "INSERT INTO notes (guild_id, user_id, moderator_id, note) VALUES (?, ?, ?, ?)",
            (guild_id, user_id, moderator_id, note)
        )
        await db.commit()


async def get_notes(guild_id: int, user_id: int) -> List[dict]:
    async with aiosqlite.connect(DB_FILE) as db:
        async with db.execute(
            "SELECT * FROM notes WHERE guild_id = ? AND user_id = ? ORDER BY created_at DESC",
            (guild_id, user_id)
        ) as cur:
            rows = await cur.fetchall()
            cols = [d[0] for d in cur.description]
            return [dict(zip(cols, r)) for r in rows]


async def add_warning(guild_id: int, user_id: int, moderator_id: int, reason: str):
    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute(
            "INSERT INTO warnings (guild_id, user_id, moderator_id, reason) VALUES (?, ?, ?, ?)",
            (guild_id, user_id, moderator_id, reason)
        )
        await db.commit()


async def get_warnings(guild_id: int, user_id: int) -> List[dict]:
    async with aiosqlite.connect(DB_FILE) as db:
        async with db.execute(
            "SELECT * FROM warnings WHERE guild_id = ? AND user_id = ? ORDER BY created_at DESC",
            (guild_id, user_id)
        ) as cur:
            rows = await cur.fetchall()
            cols = [d[0] for d in cur.description]
            return [dict(zip(cols, r)) for r in rows]


async def log_audit(guild: discord.Guild, title: str, description: str, color: int = 0x2B2D31, fields: dict = None):
    config = await get_config(guild.id)
    channel_id = config.get("audit_log_channel") or config.get("mod_log_channel")
    if not channel_id:
        return
    channel = guild.get_channel(channel_id)
    if not channel:
        return
    embed = discord.Embed(title=title, description=description, color=color, timestamp=datetime.now(timezone.utc))
    embed.set_footer(text="ARF Audit System", icon_url=guild.icon.url if guild.icon else None)
    if fields:
        for name, value, inline in fields:
            embed.add_field(name=name, value=value, inline=inline)
    try:
        await channel.send(embed=embed)
    except:
        pass


class Moderation(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.invite_regex = re.compile(r'(discord\.gg/|discord\.com/invite/|discordapp\.com/invite/)[a-zA-Z0-9]+')
        self.webhook_cache = {}

    async def cog_load(self):
        await init_db()

    @app_commands.command(name="setup_mod", description="إعداد نظام المودريشن والتدقيق")
    @app_commands.default_permissions(administrator=True)
    @app_commands.describe(
        audit_channel="قناة سجل التدقيق (Audit Log)",
        mod_channel="قناة سجل المودريشن (Mod Log)",
        welcome_channel="قناة الترحيب",
        verification_channel="قناة التحقق",
        verification_role="الرتبة الممنوحة بعد التحقق",
        min_account_age="الحد الأدنى لعمر الحساب بالأيام",
        require_avatar="اشتراط صورة البروفايل",
        anti_alt="تفعيل منع الحسابات البديلة",
        anti_vpn="تفعيل حماية VPN/Proxy",
        anti_webhook="تفعيل حماية الويب هوك",
        anti_invite="تفعيل منع روابط الدعوة"
    )
    async def setup_mod(self, interaction: discord.Interaction,
                        audit_channel: discord.TextChannel = None,
                        mod_channel: discord.TextChannel = None,
                        welcome_channel: discord.TextChannel = None,
                        verification_channel: discord.TextChannel = None,
                        verification_role: discord.Role = None,
                        min_account_age: app_commands.Range[int, 0, 365] = 7,
                        require_avatar: bool = True,
                        anti_alt: bool = True,
                        anti_vpn: bool = False,
                        anti_webhook: bool = True,
                        anti_invite: bool = True):
        await set_config(interaction.guild.id,
                         audit_log_channel=audit_channel.id if audit_channel else None,
                         mod_log_channel=mod_channel.id if mod_channel else None,
                         welcome_channel=welcome_channel.id if welcome_channel else None,
                         verification_channel=verification_channel.id if verification_channel else None,
                         verification_role=verification_role.id if verification_role else None,
                         min_account_age_days=min_account_age,
                         require_avatar=int(require_avatar),
                         anti_alt_enabled=int(anti_alt),
                         anti_vpn_enabled=int(anti_vpn),
                         anti_webhook_enabled=int(anti_webhook),
                         anti_invite_enabled=int(anti_invite))

        embed = discord.Embed(title="✅ تم إعداد نظام المودريشن", color=0x57F287)
        embed.add_field(name="Audit Log", value=audit_channel.mention if audit_channel else "غير محدد", inline=True)
        embed.add_field(name="Mod Log", value=mod_channel.mention if mod_channel else "غير محدد", inline=True)
        embed.add_field(name="Welcome", value=welcome_channel.mention if welcome_channel else "غير محدد", inline=True)
        embed.add_field(name="Verification", value=f"{verification_channel.mention if verification_channel else 'غير محدد'} | {verification_role.mention if verification_role else 'بدون رتبة'}", inline=True)
        embed.add_field(name="Min Account Age", value=f"{min_account_age} أيام", inline=True)
        embed.add_field(name="Require Avatar", value="نعم" if require_avatar else "لا", inline=True)
        embed.add_field(name="Anti-Alt", value="مفعل" if anti_alt else "معطل", inline=True)
        embed.add_field(name="Anti-VPN", value="مفعل" if anti_vpn else "معطل", inline=True)
        embed.add_field(name="Anti-Webhook", value="مفعل" if anti_webhook else "معطل", inline=True)
        embed.add_field(name="Anti-Invite", value="مفعل" if anti_invite else "معطل", inline=True)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ═══════════════════════════════════════════════
    # Mod Commands
    # ═══════════════════════════════════════════════
    @app_commands.command(name="warn", description="إعطاء تحذير لعضو")
    @app_commands.default_permissions(manage_messages=True)
    @app_commands.describe(user="العضو", reason="السبب")
    async def warn(self, interaction: discord.Interaction, user: discord.Member, reason: str = "لا يوجد سبب"):
        if user.id == interaction.user.id:
            await interaction.response.send_message("لا يمكنك تحذير نفسك.", ephemeral=True)
            return
        if user.top_role >= interaction.user.top_role and interaction.user.id != interaction.guild.owner_id:
            await interaction.response.send_message("لا يمكنك تحذير هذا العضو.", ephemeral=True)
            return

        await add_warning(interaction.guild.id, user.id, interaction.user.id, reason)
        warnings = await get_warnings(interaction.guild.id, user.id)

        embed = discord.Embed(title="⚠️ تحذير", color=0xFEE75C, timestamp=datetime.now(timezone.utc))
        embed.add_field(name="العضو", value=f"{user.mention} (`{user.id}`)", inline=True)
        embed.add_field(name="بواسطة", value=interaction.user.mention, inline=True)
        embed.add_field(name="السبب", value=reason, inline=False)
        embed.add_field(name="إجمالي التحذيرات", value=str(len(warnings)), inline=True)
        embed.set_footer(text=f"Case ID: {len(warnings)}", icon_url=interaction.guild.icon.url if interaction.guild.icon else None)

        await interaction.response.send_message(embed=embed)
        await log_audit(interaction.guild, "تحذير", f"{interaction.user.mention} حذر {user.mention}", 0xFEE75C,
                       [("السبب", reason, False), ("التحذير رقم", str(len(warnings)), True)])

        try:
            dm_embed = discord.Embed(title="⚠️ تلقيت تحذيراً", description=f"في سيرفر **{interaction.guild.name}**", color=0xFEE75C)
            dm_embed.add_field(name="السبب", value=reason)
            dm_embed.add_field(name="المشرف", value=interaction.user.display_name)
            await user.send(embed=dm_embed)
        except:
            pass

    @app_commands.command(name="mute", description="إعطاء تايم آوت لعضو")
    @app_commands.default_permissions(moderate_members=True)
    @app_commands.describe(user="العضو", duration="المدة (مثال: 10m, 1h, 1d)", reason="السبب")
    async def mute(self, interaction: discord.Interaction, user: discord.Member,
                   duration: str, reason: str = "لا يوجد سبب"):
        if user.id == interaction.user.id:
            await interaction.response.send_message("لا يمكنك ميوت نفسك.", ephemeral=True)
            return
        if user.top_role >= interaction.user.top_role and interaction.user.id != interaction.guild.owner_id:
            await interaction.response.send_message("لا يمكنك ميوت هذا العضو.", ephemeral=True)
            return
        if user.timed_out_until and user.timed_out_until > datetime.now(timezone.utc):
            await interaction.response.send_message("هذا العضو لديه تايم آوت بالفعل.", ephemeral=True)
            return

        td = self._parse_duration(duration)
        if not td:
            await interaction.response.send_message("تنسيق المدة غير صحيح. استخدم: 10m, 1h, 1d, 1w", ephemeral=True)
            return

        until = datetime.now(timezone.utc) + td
        try:
            await user.timeout(until, reason=reason)
        except discord.Forbidden:
            await interaction.response.send_message("لا أملك صلاحية ميوت هذا العضو.", ephemeral=True)
            return

        await add_case(interaction.guild.id, user.id, interaction.user.id, "MUTE", reason, duration)

        embed = discord.Embed(title="🔇 تايم آوت", color=0xED4245, timestamp=datetime.now(timezone.utc))
        embed.add_field(name="العضو", value=f"{user.mention} (`{user.id}`)", inline=True)
        embed.add_field(name="بواسطة", value=interaction.user.mention, inline=True)
        embed.add_field(name="المدة", value=duration, inline=True)
        embed.add_field(name="السبب", value=reason, inline=False)
        embed.set_footer(text="ARF Moderation", icon_url=interaction.guild.icon.url if interaction.guild.icon else None)
        await interaction.response.send_message(embed=embed)
        await log_audit(interaction.guild, "تايم آوت", f"{interaction.user.mention} أعطى تايم آوت لـ {user.mention}", 0xED4245,
                       [("المدة", duration, True), ("السبب", reason, False)])

    @app_commands.command(name="unmute", description="إزالة التايم آوت عن عضو")
    @app_commands.default_permissions(moderate_members=True)
    @app_commands.describe(user="العضو", reason="السبب")
    async def unmute(self, interaction: discord.Interaction, user: discord.Member, reason: str = "انتهى التايم آوت"):
        if not user.timed_out_until or user.timed_out_until <= datetime.now(timezone.utc):
            await interaction.response.send_message("هذا العضو ليس لديه تايم آوت.", ephemeral=True)
            return
        await user.timeout(None, reason=reason)
        await add_case(interaction.guild.id, user.id, interaction.user.id, "UNMUTE", reason)

        embed = discord.Embed(title="🔊 تم إزالة التايم آوت", color=0x57F287, timestamp=datetime.now(timezone.utc))
        embed.add_field(name="العضو", value=f"{user.mention} (`{user.id}`)", inline=True)
        embed.add_field(name="بواسطة", value=interaction.user.mention, inline=True)
        embed.add_field(name="السبب", value=reason, inline=False)
        await interaction.response.send_message(embed=embed)
        await log_audit(interaction.guild, "إزالة تايم آوت", f"{interaction.user.mention} أزال التايم آوت عن {user.mention}", 0x57F287,
                       [("السبب", reason, False)])

    @app_commands.command(name="ban", description="حظر عضو")
    @app_commands.default_permissions(ban_members=True)
    @app_commands.describe(user="العضو", reason="السبب", delete_history="حذف رسائل آخر 24 ساعة")
    async def ban(self, interaction: discord.Interaction, user: discord.User,
                  reason: str = "لا يوجد سبب", delete_history: bool = False):
        if isinstance(user, discord.Member):
            if user.id == interaction.user.id:
                await interaction.response.send_message("لا يمكنك حظر نفسك.", ephemeral=True)
                return
            if user.top_role >= interaction.user.top_role and interaction.user.id != interaction.guild.owner_id:
                await interaction.response.send_message("لا يمكنك حظر هذا العضو.", ephemeral=True)
                return

        try:
            await interaction.guild.ban(user, reason=reason, delete_message_seconds=86400 if delete_history else 0)
        except discord.Forbidden:
            await interaction.response.send_message("لا أملك صلاحية حظر هذا العضو.", ephemeral=True)
            return

        await add_case(interaction.guild.id, user.id, interaction.user.id, "BAN", reason)

        embed = discord.Embed(title="🔨 حظر", color=0xFF0000, timestamp=datetime.now(timezone.utc))
        embed.add_field(name="العضو", value=f"{user.mention} (`{user.id}`)", inline=True)
        embed.add_field(name="بواسطة", value=interaction.user.mention, inline=True)
        embed.add_field(name="السبب", value=reason, inline=False)
        await interaction.response.send_message(embed=embed)
        await log_audit(interaction.guild, "حظر", f"{interaction.user.mention} حظر {user.mention}", 0xFF0000,
                       [("السبب", reason, False)])

    @app_commands.command(name="unban", description="إلغاء حظر عضو")
    @app_commands.default_permissions(ban_members=True)
    @app_commands.describe(user_id="معرف العضو", reason="السبب")
    async def unban(self, interaction: discord.Interaction, user_id: str, reason: str = "تم إلغاء الحظر"):
        try:
            uid = int(user_id)
        except:
            await interaction.response.send_message("معرف غير صحيح.", ephemeral=True)
            return
        try:
            user = await self.bot.fetch_user(uid)
            await interaction.guild.unban(user, reason=reason)
        except discord.NotFound:
            await interaction.response.send_message("هذا العضو غير محظور.", ephemeral=True)
            return
        except discord.Forbidden:
            await interaction.response.send_message("لا أملك صلاحية إلغاء الحظر.", ephemeral=True)
            return

        await add_case(interaction.guild.id, uid, interaction.user.id, "UNBAN", reason)

        embed = discord.Embed(title="✅ تم إلغاء الحظر", color=0x57F287, timestamp=datetime.now(timezone.utc))
        embed.add_field(name="العضو", value=f"{user.mention} (`{uid}`)", inline=True)
        embed.add_field(name="بواسطة", value=interaction.user.mention, inline=True)
        embed.add_field(name="السبب", value=reason, inline=False)
        await interaction.response.send_message(embed=embed)
        await log_audit(interaction.guild, "إلغاء حظر", f"{interaction.user.mention} ألغى حظر {user.mention}", 0x57F287,
                       [("السبب", reason, False)])

    @app_commands.command(name="kick", description="طرد عضو")
    @app_commands.default_permissions(kick_members=True)
    @app_commands.describe(user="العضو", reason="السبب")
    async def kick(self, interaction: discord.Interaction, user: discord.Member, reason: str = "لا يوجد سبب"):
        if user.id == interaction.user.id:
            await interaction.response.send_message("لا يمكنك طرد نفسك.", ephemeral=True)
            return
        if user.top_role >= interaction.user.top_role and interaction.user.id != interaction.guild.owner_id:
            await interaction.response.send_message("لا يمكنك طرد هذا العضو.", ephemeral=True)
            return

        try:
            await user.kick(reason=reason)
        except discord.Forbidden:
            await interaction.response.send_message("لا أملك صلاحية طرد هذا العضو.", ephemeral=True)
            return

        await add_case(interaction.guild.id, user.id, interaction.user.id, "KICK", reason)

        embed = discord.Embed(title="👢 طرد", color=0xFAA61A, timestamp=datetime.now(timezone.utc))
        embed.add_field(name="العضو", value=f"{user.mention} (`{user.id}`)", inline=True)
        embed.add_field(name="بواسطة", value=interaction.user.mention, inline=True)
        embed.add_field(name="السبب", value=reason, inline=False)
        await interaction.response.send_message(embed=embed)
        await log_audit(interaction.guild, "طرد", f"{interaction.user.mention} طرد {user.mention}", 0xFAA61A,
                       [("السبب", reason, False)])

    @app_commands.command(name="note", description="إضافة ملاحظة داخلية لعضو (للستاف فقط)")
    @app_commands.default_permissions(manage_messages=True)
    @app_commands.describe(user="العضو", note="الملاحظة")
    async def note(self, interaction: discord.Interaction, user: discord.Member, note: str):
        await add_note(interaction.guild.id, user.id, interaction.user.id, note)
        embed = discord.Embed(title="📝 ملاحظة مضافة", color=0x5865F2, timestamp=datetime.now(timezone.utc))
        embed.add_field(name="العضو", value=f"{user.mention} (`{user.id}`)", inline=True)
        embed.add_field(name="بواسطة", value=interaction.user.mention, inline=True)
        embed.add_field(name="الملاحظة", value=note, inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)
        await log_audit(interaction.guild, "ملاحظة ستاف", f"{interaction.user.mention} أضاف ملاحظة لـ {user.mention}", 0x5865F2,
                       [("الملاحظة", note, False)])

    @app_commands.command(name="history", description="عرض سجل العضو (تحذيرات، قضايا، ملاحظات)")
    @app_commands.default_permissions(manage_messages=True)
    @app_commands.describe(user="العضو")
    async def history(self, interaction: discord.Interaction, user: discord.Member):
        cases = await get_cases(interaction.guild.id, user.id)
        warnings = await get_warnings(interaction.guild.id, user.id)
        notes = await get_notes(interaction.guild.id, user.id)

        embed = discord.Embed(title=f"📋 سجل {user.display_name}", color=0x2B2D31, timestamp=datetime.now(timezone.utc))
        embed.set_thumbnail(url=user.display_avatar.url)

        if cases:
            case_text = "\n".join([f"`{c['action']}` • {c['reason'] or 'بدون سبب'} • <t:{int(datetime.fromisoformat(c['created_at']).timestamp())}:R>" for c in cases[:10]])
            embed.add_field(name=f"القضايا ({len(cases)})", value=case_text[:1024] or "لا يوجد", inline=False)
        else:
            embed.add_field(name="القضايا", value="لا يوجد", inline=False)

        if warnings:
            warn_text = "\n".join([f"{w['reason'] or 'بدون سبب'} • <t:{int(datetime.fromisoformat(w['created_at']).timestamp())}:R>" for w in warnings[:10]])
            embed.add_field(name=f"التحذيرات ({len(warnings)})", value=warn_text[:1024] or "لا يوجد", inline=False)
        else:
            embed.add_field(name="التحذيرات", value="لا يوجد", inline=False)

        if notes:
            note_text = "\n".join([f"{n['note'][:100]} • <t:{int(datetime.fromisoformat(n['created_at']).timestamp())}:R>" for n in notes[:5]])
            embed.add_field(name=f"ملاحظات الستاف ({len(notes)})", value=note_text[:1024] or "لا يوجد", inline=False)
        else:
            embed.add_field(name="ملاحظات الستاف", value="لا يوجد", inline=False)

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="case", description="عرض تفاصيل قضية برقمها")
    @app_commands.default_permissions(manage_messages=True)
    @app_commands.describe(case_id="رقم القضية")
    async def case(self, interaction: discord.Interaction, case_id: int):
        async with aiosqlite.connect(DB_FILE) as db:
            async with db.execute("SELECT * FROM cases WHERE id = ? AND guild_id = ?", (case_id, interaction.guild.id)) as cur:
                row = await cur.fetchone()
        if not row:
            await interaction.response.send_message("القضية غير موجودة.", ephemeral=True)
            return
        cols = [d[0] for d in cur.description]
        c = dict(zip(cols, row))

        user = interaction.guild.get_member(c['user_id']) or await self.bot.fetch_user(c['user_id'])
        mod = interaction.guild.get_member(c['moderator_id']) or await self.bot.fetch_user(c['moderator_id'])

        embed = discord.Embed(title=f"📄 Case #{c['id']} • {c['action']}", color=0x2B2D31, timestamp=datetime.fromisoformat(c['created_at']))
        embed.add_field(name="العضو", value=f"{user.mention} (`{c['user_id']}`)", inline=True)
        embed.add_field(name="المشرف", value=f"{mod.mention} (`{c['moderator_id']}`)", inline=True)
        embed.add_field(name="المدة", value=c['duration'] or "دائم", inline=True)
        embed.add_field(name="السبب", value=c['reason'] or "لا يوجد", inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ═══════════════════════════════════════════════
    # Listeners for Audit Logging
    # ═══════════════════════════════════════════════
    @commands.Cog.listener()
    async def on_member_ban(self, guild, user):
        await log_audit(guild, "🔨 حظر", f"تم حظر {user.mention} (`{user.id}`)", 0xFF0000)

    @commands.Cog.listener()
    async def on_member_unban(self, guild, user):
        await log_audit(guild, "✅ إلغاء حظر", f"تم إلغاء حظر {user.mention} (`{user.id}`)", 0x57F287)

    @commands.Cog.listener()
    async def on_member_remove(self, member):
        await asyncio.sleep(1)
        try:
            async for entry in member.guild.audit_logs(limit=1, action=discord.AuditLogAction.kick):
                if entry.target.id == member.id:
                    await log_audit(member.guild, "👢 طرد", f"{entry.user.mention} طرد {member.mention} (`{member.id}`)\nالسبب: {entry.reason or 'لا يوجد'}", 0xFAA61A)
                    break
        except:
            pass

    @commands.Cog.listener()
    async def on_member_update(self, before, after):
        if before.roles != after.roles:
            added = set(after.roles) - set(before.roles)
            removed = set(before.roles) - set(after.roles)
            if added or removed:
                try:
                    async for entry in after.guild.audit_logs(limit=1, action=discord.AuditLogAction.member_role_update):
                        if entry.target.id == after.id:
                            changes = []
                            if added:
                                changes.append(f"➕ أضيفت: {', '.join(r.mention for r in added)}")
                            if removed:
                                changes.append(f"➖ أزيلت: {', '.join(r.mention for r in removed)}")
                            await log_audit(after.guild, "🎭 تحديث رتب", f"{entry.user.mention} غير رتب {after.mention}", 0x5865F2,
                                           [("التغييرات", "\n".join(changes), False)])
                            break
                except:
                    pass

    @commands.Cog.listener()
    async def on_guild_channel_create(self, channel):
        await asyncio.sleep(1)
        try:
            async for entry in channel.guild.audit_logs(limit=1, action=discord.AuditLogAction.channel_create):
                await log_audit(channel.guild, "📝 إنشاء قناة", f"{entry.user.mention} أنشأ {channel.mention} (`{channel.id}`)", 0x57F287)
                break
        except:
            pass

    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel):
        await asyncio.sleep(1)
        try:
            async for entry in channel.guild.audit_logs(limit=1, action=discord.AuditLogAction.channel_delete):
                await log_audit(channel.guild, "🗑️ حذف قناة", f"{entry.user.mention} حذف `{channel.name}` (`{channel.id}`)", 0xED4245)
                break
        except:
            pass

    @commands.Cog.listener()
    async def on_guild_channel_update(self, before, after):
        if not isinstance(before, discord.TextChannel):
            return
        changes = []
        if before.name != after.name:
            changes.append(f"الاسم: `{before.name}` → `{after.name}`")
        if before.topic != after.topic:
            changes.append("تم تغيير الوصف")
        if before.nsfw != after.nsfw:
            changes.append(f"NSFW: `{before.nsfw}` → `{after.nsfw}`")
        if changes:
            try:
                async for entry in after.guild.audit_logs(limit=1, action=discord.AuditLogAction.channel_update):
                    await log_audit(after.guild, "✏️ تعديل قناة", f"{entry.user.mention} عدل {after.mention}", 0xFEE75C,
                                   [("التغييرات", "\n".join(changes), False)])
                    break
            except:
                pass

    @commands.Cog.listener()
    async def on_guild_role_create(self, role):
        await asyncio.sleep(1)
        try:
            async for entry in role.guild.audit_logs(limit=1, action=discord.AuditLogAction.role_create):
                await log_audit(role.guild, "🎭 إنشاء رتبة", f"{entry.user.mention} أنشأ {role.mention} (`{role.id}`)", 0x57F287)
                break
        except:
            pass

    @commands.Cog.listener()
    async def on_guild_role_delete(self, role):
        await asyncio.sleep(1)
        try:
            async for entry in role.guild.audit_logs(limit=1, action=discord.AuditLogAction.role_delete):
                await log_audit(role.guild, "🗑️ حذف رتبة", f"{entry.user.mention} حذف `{role.name}` (`{role.id}`)", 0xED4245)
                break
        except:
            pass

    @commands.Cog.listener()
    async def on_guild_role_update(self, before, after):
        changes = []
        if before.name != after.name:
            changes.append(f"الاسم: `{before.name}` → `{after.name}`")
        if before.color != after.color:
            changes.append(f"اللون: `{before.color}` → `{after.color}`")
        if before.permissions != after.permissions:
            changes.append("تم تغيير الصلاحيات")
        if changes:
            try:
                async for entry in after.guild.audit_logs(limit=1, action=discord.AuditLogAction.role_update):
                    await log_audit(after.guild, "✏️ تعديل رتبة", f"{entry.user.mention} عدل {after.mention}", 0xFEE75C,
                                   [("التغييرات", "\n".join(changes), False)])
                    break
            except:
                pass

    @commands.Cog.listener()
    async def on_message_edit(self, before, after):
        if before.author.bot or before.content == after.content:
            return
        config = await get_config(before.guild.id)
        if config.get("mod_log_channel"):
            channel = before.guild.get_channel(config["mod_log_channel"])
            if channel:
                embed = discord.Embed(title="✏️ تعديل رسالة", color=0xFEE75C, timestamp=datetime.now(timezone.utc))
                embed.add_field(name="الكاتب", value=f"{before.author.mention} (`{before.author.id}`)", inline=True)
                embed.add_field(name="القناة", value=before.channel.mention, inline=True)
                embed.add_field(name="قبل", value=before.content[:1024] or "*فارغ*", inline=False)
                embed.add_field(name="بعد", value=after.content[:1024] or "*فارغ*", inline=False)
                embed.set_footer(text=f"Message ID: {before.id}")
                try:
                    await channel.send(embed=embed)
                except:
                    pass

    @commands.Cog.listener()
    async def on_message_delete(self, message):
        if message.author.bot or not message.guild:
            return
        config = await get_config(message.guild.id)
        if config.get("mod_log_channel"):
            channel = message.guild.get_channel(config["mod_log_channel"])
            if channel:
                embed = discord.Embed(title="🗑️ رسالة محذوفة", color=0xED4245, timestamp=datetime.now(timezone.utc))
                embed.add_field(name="الكاتب", value=f"{message.author.mention} (`{message.author.id}`)", inline=True)
                embed.add_field(name="القناة", value=message.channel.mention, inline=True)
                embed.add_field(name="المحتوى", value=message.content[:1024] or "*مرفقات فقط*", inline=False)
                if message.attachments:
                    embed.add_field(name="مرفقات", value=f"{len(message.attachments)} ملف(ات)", inline=True)
                embed.set_footer(text=f"Message ID: {message.id}")
                try:
                    await channel.send(embed=embed)
                except:
                    pass

    def _parse_duration(self, duration: str) -> Optional[timedelta]:
        duration = duration.lower().strip()
        if duration.endswith('s'):
            return timedelta(seconds=int(duration[:-1]))
        elif duration.endswith('m'):
            return timedelta(minutes=int(duration[:-1]))
        elif duration.endswith('h'):
            return timedelta(hours=int(duration[:-1]))
        elif duration.endswith('d'):
            return timedelta(days=int(duration[:-1]))
        elif duration.endswith('w'):
            return timedelta(weeks=int(duration[:-1]))
        return None


async def setup(bot):
    await bot.add_cog(Moderation(bot))