import discord
from discord.ext import commands
from discord import app_commands
import json
import asyncio
import functools
from datetime import datetime, timezone

def safe_listener(func):
    """Wrap a listener so one bad event never breaks the rest of logging."""
    @functools.wraps(func)
    async def wrapper(self, *args, **kwargs):
        try:
            await func(self, *args, **kwargs)
        except Exception as e:
            print(f"[Logging] Error in listener '{func.__name__}': {e}")
    return wrapper

class Logging(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.log_channel_id = 1476665802060075152

        # Premium Color Palette
        self.color_msg_delete = 0xE03C3E     # Red
        self.color_msg_edit = 0xF1C40F       # Amber/Gold
        self.color_bulk_delete = 0x962D2D     # Dark Crimson
        self.color_reaction = 0x2B2D31        # Muted Dark Grey
        
        self.color_role_create = 0x2ECC71     # Green
        self.color_role_delete = 0xE74C3C     # Red
        self.color_role_update = 0x9B59B6     # Purple
        
        self.color_channel_create = 0x1ABC9C   # Teal/Cyan
        self.color_channel_delete = 0xC0392B   # Deep Red
        self.color_channel_update = 0x3498DB   # Blue
        
        self.color_member_join = 0x2ECC71     # Green
        self.color_member_leave = 0xE67E22    # Orange
        self.color_member_ban = 0x7F1D1D      # Dark Red
        self.color_member_unban = 0x2ECC71    # Green
        self.color_member_update = 0x34495E   # Slate Grey
        
        self.color_voice_join = 0x3498DB      # Blue
        self.color_voice_leave = 0xE74C3C     # Red
        self.color_voice_switch = 0xF39C12    # Orange/Yellow
        self.color_voice_update = 0x95A5A6    # Grey
        
        self.color_automod = 0xD35400         # Rust Orange
        self.color_invite = 0x1ABC9C          # Teal
        self.color_event = 0x9B59B6           # Purple
        self.color_stage = 0x9B59B6           # Purple

    def get_config(self):
        try:
            with open('config.json', 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return {}

    async def send_log(self, guild, embed, files=None):
        try:
            config = self.get_config()
            main_log_id = config.get("log_channel_id", self.log_channel_id)

            if not embed.thumbnail or not embed.thumbnail.url:
                if guild.icon:
                    embed.set_thumbnail(url=guild.icon.url)

            embed.set_footer(text=f"ARF Logging System • {guild.name}", icon_url=self.bot.user.display_avatar.url)

            channel = guild.get_channel(main_log_id)
            if not channel:
                try:
                    channel = await guild.fetch_channel(main_log_id)
                except:
                    channel = None

            if channel:
                await channel.send(embed=embed, files=files or [])
        except Exception as e:
            print(f"[Logging] Failed to send log: {e}")

    @app_commands.command(name="test_log", description="Send a test message to the log channel")
    @app_commands.default_permissions(administrator=True)
    async def test_log(self, interaction: discord.Interaction):
        e = discord.Embed(
            title="✅ Logging Connected", 
            description="Logging system connected successfully in the channel.", 
            color=self.color_role_create
        )
        e.timestamp = datetime.now(timezone.utc)
        await self.send_log(interaction.guild, e)
        await interaction.response.send_message("Test log sent. Check your log channel.", ephemeral=True)

    # ============================================================
    # Message Events
    # ============================================================
    @commands.Cog.listener()
    @safe_listener
    async def on_message_delete(self, message):
        if not message.guild or message.author.bot:
            return

        e = discord.Embed(
            title="🗑️ Message Deleted",
            color=self.color_msg_delete,
            timestamp=datetime.now(timezone.utc)
        )
        e.set_author(name=f"{message.author}", icon_url=message.author.display_avatar.url)
        e.description = (
            f"**Author:** {message.author.mention} (`{message.author.id}`)\n"
            f"**Channel:** {message.channel.mention}\n\n"
            f"**Content:**\n"
            f"```\n{message.content or '*No Text*'}\n```"
        )

        files = []
        if message.attachments:
            attachment_list = []
            for attachment in message.attachments:
                try:
                    file = await attachment.to_file()
                    files.append(file)
                except:
                    pass
                attachment_list.append(f"└ [`{attachment.filename}`]({attachment.url})")
            e.description += "\n\n**Attachments:**\n" + "\n".join(attachment_list)

        await self.send_log(message.guild, e, files=files)

    @commands.Cog.listener()
    @safe_listener
    async def on_message_edit(self, before, after):
        if not before.guild or before.author.bot:
            return
        if before.content == after.content and before.pinned == after.pinned:
            return

        if before.pinned != after.pinned:
            action = "Message Pinned" if after.pinned else "Message Unpinned"
            e = discord.Embed(
                title=f"📌 {action}",
                color=self.color_msg_edit,
                timestamp=datetime.now(timezone.utc)
            )
            e.set_author(name=f"{after.author}", icon_url=after.author.display_avatar.url)
            e.description = (
                f"**Author:** {after.author.mention}\n"
                f"**Channel:** {after.channel.mention}\n"
                f"**Jump Link:** [Click Here]({after.jump_url})"
            )
            await self.send_log(after.guild, e)
            return

        e = discord.Embed(
            title="✏️ Message Edited",
            color=self.color_msg_edit,
            timestamp=datetime.now(timezone.utc)
        )
        e.set_author(name=f"{before.author}", icon_url=before.author.display_avatar.url)
        e.description = (
            f"**Author:** {before.author.mention} (`{before.author.id}`)\n"
            f"**Channel:** {before.channel.mention}\n"
            f"**Jump Link:** [Go to Message]({after.jump_url})\n\n"
            f"**Before:**\n"
            f"```\n{before.content or '*Empty*'}\n```\n"
            f"**After:**\n"
            f"```\n{after.content or '*Empty*'}\n```"
        )
        await self.send_log(before.guild, e)

    @commands.Cog.listener()
    @safe_listener
    async def on_message_bulk_delete(self, messages):
        if not messages:
            return
        guild = messages[0].guild
        if not guild:
            return

        e = discord.Embed(
            title="📂 Bulk Message Deleted",
            description=(
                f"**Channel:** {messages[0].channel.mention}\n"
                f"**Count:** `{len(messages)}` messages deleted bulk."
            ),
            color=self.color_bulk_delete,
            timestamp=datetime.now(timezone.utc)
        )
        await self.send_log(guild, e)

    @commands.Cog.listener()
    @safe_listener
    async def on_raw_reaction_add(self, payload):
        if not payload.guild_id:
            return
        guild = self.bot.get_guild(payload.guild_id)
        if not guild:
            return
        user = payload.member or guild.get_member(payload.user_id)
        if user and user.bot:
            return

        channel = guild.get_channel(payload.channel_id)
        e = discord.Embed(
            title="➕ Reaction Added",
            color=self.color_reaction,
            timestamp=datetime.now(timezone.utc)
        )
        e.description = (
            f"**User:** <@{payload.user_id}>\n"
            f"**Channel:** {channel.mention if channel else 'Unknown'}\n"
            f"**Emoji:** {payload.emoji}\n"
            f"**Message ID:** `{payload.message_id}`"
        )
        await self.send_log(guild, e)

    @commands.Cog.listener()
    @safe_listener
    async def on_raw_reaction_remove(self, payload):
        if not payload.guild_id:
            return
        guild = self.bot.get_guild(payload.guild_id)
        if not guild:
            return

        channel = guild.get_channel(payload.channel_id)
        e = discord.Embed(
            title="➖ Reaction Removed",
            color=self.color_reaction,
            timestamp=datetime.now(timezone.utc)
        )
        e.description = (
            f"**User:** <@{payload.user_id}>\n"
            f"**Channel:** {channel.mention if channel else 'Unknown'}\n"
            f"**Emoji:** {payload.emoji}\n"
            f"**Message ID:** `{payload.message_id}`"
        )
        await self.send_log(guild, e)

    # ============================================================
    # Role Events
    # ============================================================
    @commands.Cog.listener()
    @safe_listener
    async def on_guild_role_create(self, role):
        e = discord.Embed(
            title="➕ Role Created",
            color=self.color_role_create,
            timestamp=datetime.now(timezone.utc)
        )
        e.description = (
            f"**Name:** {role.mention} (`{role.name}`)\n"
            f"**Color:** `{role.color}`\n"
            f"**ID:** `{role.id}`"
        )
        await self.send_log(role.guild, e)

    @commands.Cog.listener()
    @safe_listener
    async def on_guild_role_delete(self, role):
        e = discord.Embed(
            title="➖ Role Deleted",
            color=self.color_role_delete,
            timestamp=datetime.now(timezone.utc)
        )
        e.description = (
            f"**Name:** `{role.name}`\n"
            f"**ID:** `{role.id}`"
        )
        await self.send_log(role.guild, e)

    @commands.Cog.listener()
    @safe_listener
    async def on_guild_role_update(self, before, after):
        changes = []
        if before.name != after.name:
            changes.append(f"**Name:** `{before.name}` → `{after.name}`")
        if before.color != after.color:
            changes.append(f"**Color:** `{before.color}` → `{after.color}`")
        if before.permissions != after.permissions:
            changes.append("**Permissions Updated**")
        if before.hoist != after.hoist:
            changes.append(f"**Hoisted:** `{before.hoist}` → `{after.hoist}`")
        if before.mentionable != after.mentionable:
            changes.append(f"**Mentionable:** `{before.mentionable}` → `{after.mentionable}`")
        if before.position != after.position:
            changes.append(f"**Position:** `{before.position}` → `{after.position}`")

        if not changes:
            return

        e = discord.Embed(
            title="⚙️ Role Updated",
            color=self.color_role_update,
            timestamp=datetime.now(timezone.utc)
        )
        e.description = (
            f"**Role:** {after.mention}\n"
            f"**ID:** `{after.id}`\n\n"
            f"**Changes:**\n" + "\n".join(changes)
        )
        await self.send_log(after.guild, e)

    # ============================================================
    # Channel Events
    # ============================================================
    @commands.Cog.listener()
    @safe_listener
    async def on_guild_channel_create(self, channel):
        e = discord.Embed(
            title="🆕 Channel Created",
            color=self.color_channel_create,
            timestamp=datetime.now(timezone.utc)
        )
        e.description = (
            f"**Channel:** {channel.mention} (`#{channel.name}`)\n"
            f"**Type:** `{channel.type}`\n"
            f"**ID:** `{channel.id}`"
        )
        await self.send_log(channel.guild, e)

    @commands.Cog.listener()
    @safe_listener
    async def on_guild_channel_delete(self, channel):
        e = discord.Embed(
            title="❌ Channel Deleted",
            color=self.color_channel_delete,
            timestamp=datetime.now(timezone.utc)
        )
        e.description = (
            f"**Name:** `#{channel.name}`\n"
            f"**Type:** `{channel.type}`\n"
            f"**ID:** `{channel.id}`"
        )
        await self.send_log(channel.guild, e)

    @commands.Cog.listener()
    @safe_listener
    async def on_guild_channel_update(self, before, after):
        changes = []
        if before.name != after.name:
            changes.append(f"**Name:** `#{before.name}` → `#{after.name}`")
        if before.topic != after.topic:
            changes.append(f"**Topic:** `{before.topic or 'None'}` → `{after.topic or 'None'}`")
        if before.slowmode_delay != after.slowmode_delay:
            changes.append(f"**Slowmode:** `{before.slowmode_delay}s` → `{after.slowmode_delay}s`")
        if before.nsfw != after.nsfw:
            changes.append(f"**NSFW:** `{before.nsfw}` → `{after.nsfw}`")
        if getattr(before, 'bitrate', None) != getattr(after, 'bitrate', None):
            changes.append(f"**Bitrate:** `{before.bitrate // 1000}kbps` → `{after.bitrate // 1000}kbps`")
        if getattr(before, 'user_limit', None) != getattr(after, 'user_limit', None):
            changes.append(f"**User Limit:** `{before.user_limit}` → `{after.user_limit}`")
        if before.category != after.category:
            changes.append(f"**Category:** `{before.category}` → `{after.category}`")
        if before.overwrites != after.overwrites:
            changes.append("**Permissions Updated**")

        if not changes:
            return

        e = discord.Embed(
            title="🔧 Channel Updated",
            color=self.color_channel_update,
            timestamp=datetime.now(timezone.utc)
        )
        e.description = (
            f"**Channel:** {after.mention}\n"
            f"**ID:** `{after.id}`\n\n"
            f"**Changes:**\n" + "\n".join(changes)
        )
        await self.send_log(after.guild, e)

    @commands.Cog.listener()
    @safe_listener
    async def on_guild_channel_pins_update(self, channel, last_pin):
        e = discord.Embed(
            title="📌 Channel Pins Updated",
            color=self.color_channel_update,
            timestamp=datetime.now(timezone.utc)
        )
        e.description = f"**Channel:** {channel.mention}\n**Last Pin Date:** `{last_pin}`"
        await self.send_log(channel.guild, e)

    @commands.Cog.listener()
    @safe_listener
    async def on_webhooks_update(self, channel):
        e = discord.Embed(
            title="🕸️ Webhooks Updated",
            color=self.color_channel_update,
            timestamp=datetime.now(timezone.utc)
        )
        e.description = f"**Channel:** {channel.mention}"
        await self.send_log(channel.guild, e)

    # ============================================================
    # Thread Events
    # ============================================================
    @commands.Cog.listener()
    @safe_listener
    async def on_thread_create(self, thread):
        e = discord.Embed(
            title="🧵 Thread Created",
            color=self.color_channel_create,
            timestamp=datetime.now(timezone.utc)
        )
        e.description = (
            f"**Thread:** {thread.mention} (`#{thread.name}`)\n"
            f"**Parent:** {thread.parent.mention if thread.parent else 'Unknown'}\n"
            f"**ID:** `{thread.id}`"
        )
        await self.send_log(thread.guild, e)

    @commands.Cog.listener()
    @safe_listener
    async def on_thread_delete(self, thread):
        e = discord.Embed(
            title="🧵 Thread Deleted",
            color=self.color_channel_delete,
            timestamp=datetime.now(timezone.utc)
        )
        e.description = (
            f"**Name:** `#{thread.name}`\n"
            f"**Parent:** {thread.parent.mention if thread.parent else 'Unknown'}\n"
            f"**ID:** `{thread.id}`"
        )
        await self.send_log(thread.guild, e)

    @commands.Cog.listener()
    @safe_listener
    async def on_thread_update(self, before, after):
        changes = []
        if before.name != after.name:
            changes.append(f"**Name:** `{before.name}` → `{after.name}`")
        if before.archived != after.archived:
            changes.append(f"**Archived:** `{before.archived}` → `{after.archived}`")
        if before.locked != after.locked:
            changes.append(f"**Locked:** `{before.locked}` → `{after.locked}`")

        if not changes:
            return

        e = discord.Embed(
            title="🧵 Thread Updated",
            color=self.color_channel_update,
            timestamp=datetime.now(timezone.utc)
        )
        e.description = (
            f"**Thread:** {after.mention}\n"
            f"**Changes:**\n" + "\n".join(changes)
        )
        await self.send_log(after.guild, e)

    # ============================================================
    # Member Events
    # ============================================================
    @commands.Cog.listener()
    @safe_listener
    async def on_member_join(self, member):
        e = discord.Embed(
            title="📥 Member Joined",
            color=self.color_member_join,
            timestamp=datetime.now(timezone.utc)
        )
        e.set_thumbnail(url=member.display_avatar.url)
        created_timestamp = int(member.created_at.timestamp())
        e.description = (
            f"**User:** {member.mention} (`{member.name}`)\n"
            f"**ID:** `{member.id}`\n"
            f"**Account Created:** <t:{created_timestamp}:D> (<t:{created_timestamp}:R>)"
        )
        await self.send_log(member.guild, e)

    @commands.Cog.listener()
    @safe_listener
    async def on_member_remove(self, member):
        e = discord.Embed(
            title="📤 Member Left",
            color=self.color_member_leave,
            timestamp=datetime.now(timezone.utc)
        )
        e.set_thumbnail(url=member.display_avatar.url)
        roles = [role.mention for role in member.roles if not role.is_default()]
        e.description = (
            f"**User:** `{member.name}` ({member.mention})\n"
            f"**ID:** `{member.id}`\n"
            f"**Roles:** " + (", ".join(roles) if roles else "None")
        )
        await self.send_log(member.guild, e)

    @commands.Cog.listener()
    @safe_listener
    async def on_member_update(self, before, after):
        changes = []
        if before.nick != after.nick:
            changes.append(f"**Nickname:** `{before.nick or 'None'}` → `{after.nick or 'None'}`")

        if before.roles != after.roles:
            added = [r.mention for r in after.roles if r not in before.roles]
            removed = [r.mention for r in before.roles if r not in after.roles]
            if added:
                changes.append(f"**Added Roles:** {', '.join(added)}")
            if removed:
                changes.append(f"**Removed Roles:** {', '.join(removed)}")

        if getattr(before, 'timed_out_until', None) != getattr(after, 'timed_out_until', None):
            if getattr(after, 'timed_out_until', None) is not None:
                changes.append(f"**Timeout:** Timed out until <t:{int(after.timed_out_until.timestamp())}:F>")
            else:
                changes.append("**Timeout:** Timeout removed.")

        if before.pending != after.pending:
            status = "Passed Screening" if not after.pending else "Pending Screening"
            changes.append(f"**Membership Screening:** `{status}`")

        if not changes:
            return

        e = discord.Embed(
            title="👤 Member Updated",
            color=self.color_member_update,
            timestamp=datetime.now(timezone.utc)
        )
        e.set_author(name=f"{after}", icon_url=after.display_avatar.url)
        e.description = (
            f"**Member:** {after.mention} (`{after.id}`)\n\n"
            f"**Changes:**\n" + "\n".join(changes)
        )
        await self.send_log(after.guild, e)

    @commands.Cog.listener()
    @safe_listener
    async def on_member_ban(self, guild, user):
        e = discord.Embed(
            title="🚫 Member Banned",
            color=self.color_member_ban,
            timestamp=datetime.now(timezone.utc)
        )
        avatar_url = user.display_avatar.url if hasattr(user, 'display_avatar') else self.bot.user.display_avatar.url
        e.set_thumbnail(url=avatar_url)
        e.description = (
            f"**Banned User:** `{user.name}` ({user.mention if hasattr(user, 'mention') else '<@' + str(user.id) + '>'})\n"
            f"**ID:** `{user.id}`"
        )
        await self.send_log(guild, e)

    @commands.Cog.listener()
    @safe_listener
    async def on_member_unban(self, guild, user):
        e = discord.Embed(
            title="🔓 Member Unbanned",
            color=self.color_member_unban,
            timestamp=datetime.now(timezone.utc)
        )
        avatar_url = user.display_avatar.url if hasattr(user, 'display_avatar') else self.bot.user.display_avatar.url
        e.set_thumbnail(url=avatar_url)
        e.description = (
            f"**Unbanned User:** `{user.name}` ({user.mention if hasattr(user, 'mention') else '<@' + str(user.id) + '>'})\n"
            f"**ID:** `{user.id}`"
        )
        await self.send_log(guild, e)

    # ============================================================
    # Voice Events
    # ============================================================
    @commands.Cog.listener()
    @safe_listener
    async def on_voice_state_update(self, member, before, after):
        # Channel join
        if not before.channel and after.channel:
            e = discord.Embed(
                title="🎙️ Joined Voice",
                color=self.color_voice_join,
                timestamp=datetime.now(timezone.utc)
            )
            e.set_author(name=f"{member}", icon_url=member.display_avatar.url)
            e.description = f"{member.mention} joined voice channel: **{after.channel.name}**"
            await self.send_log(member.guild, e)

        # Channel leave
        elif before.channel and not after.channel:
            e = discord.Embed(
                title="🚪 Left Voice",
                color=self.color_voice_leave,
                timestamp=datetime.now(timezone.utc)
            )
            e.set_author(name=f"{member}", icon_url=member.display_avatar.url)
            e.description = f"{member.mention} left voice channel: **{before.channel.name}**"
            await self.send_log(member.guild, e)

        # Channel switch
        elif before.channel and after.channel and before.channel != after.channel:
            e = discord.Embed(
                title="🔀 Switched Voice",
                color=self.color_voice_switch,
                timestamp=datetime.now(timezone.utc)
            )
            e.set_author(name=f"{member}", icon_url=member.display_avatar.url)
            e.description = f"{member.mention} switched from **{before.channel.name}** to **{after.channel.name}**"
            await self.send_log(member.guild, e)

        # Server mute / deafen
        voice_changes = []
        if before.mute != after.mute:
            status = "Muted" if after.mute else "Unmuted"
            voice_changes.append(f"**Server Mute:** `{status}`")
        if before.deaf != after.deaf:
            status = "Deafened" if after.deaf else "Undeafened"
            voice_changes.append(f"**Server Deafen:** `{status}`")

        if voice_changes:
            e = discord.Embed(
                title="🔇 Voice Status Updated",
                color=self.color_voice_update,
                timestamp=datetime.now(timezone.utc)
            )
            e.set_author(name=f"{member}", icon_url=member.display_avatar.url)
            e.description = f"**Member:** {member.mention}\n\n" + "\n".join(voice_changes)
            await self.send_log(member.guild, e)

    # ============================================================
    # Guild Events
    # ============================================================
    @commands.Cog.listener()
    @safe_listener
    async def on_guild_update(self, before, after):
        e = discord.Embed(
            title="🌐 Server Updated",
            color=self.color_voice_update,
            timestamp=datetime.now(timezone.utc)
        )

        changes = []
        if before.name != after.name:
            changes.append(f"**Server Name:** `{before.name}` → `{after.name}`")
        if before.icon != after.icon:
            changes.append("**Server Icon Updated**")
        if before.owner != after.owner:
            changes.append(f"**Owner:** {before.owner.mention} → {after.owner.mention}")
        if before.verification_level != after.verification_level:
            changes.append(f"**Verification:** `{before.verification_level}` → `{after.verification_level}`")

        if not changes:
            return
        e.description = "\n".join(changes)
        await self.send_log(after, e)

    @commands.Cog.listener()
    @safe_listener
    async def on_guild_emojis_update(self, guild, before, after):
        added = [emoji for emoji in after if emoji not in before]
        removed = [emoji for emoji in before if emoji not in after]

        changes = []
        if added:
            changes.append(f"**Added:** " + ", ".join([str(em) for em in added]))
        if removed:
            changes.append(f"**Removed:** " + ", ".join([f"`{em.name}`" for em in removed]))

        if not changes:
            return

        e = discord.Embed(
            title="✨ Emojis Updated",
            color=self.color_voice_update,
            timestamp=datetime.now(timezone.utc)
        )
        e.description = "\n".join(changes)
        await self.send_log(guild, e)

    @commands.Cog.listener()
    @safe_listener
    async def on_guild_stickers_update(self, guild, before, after):
        added = [s for s in after if s not in before]
        removed = [s for s in before if s not in after]
        if not added and not removed:
            return

        changes = []
        if added:
            changes.append(f"**Added Sticker:** " + ", ".join([f"`{s.name}`" for s in added]))
        if removed:
            changes.append(f"**Removed Sticker:** " + ", ".join([f"`{s.name}`" for s in removed]))

        e = discord.Embed(
            title="🎨 Stickers Updated",
            color=self.color_voice_update,
            timestamp=datetime.now(timezone.utc)
        )
        e.description = "\n".join(changes)
        await self.send_log(guild, e)

    # ============================================================
    # Invite Events
    # ============================================================
    @commands.Cog.listener()
    @safe_listener
    async def on_invite_create(self, invite):
        e = discord.Embed(
            title="🔗 Invite Created",
            color=self.color_invite,
            timestamp=datetime.now(timezone.utc)
        )
        e.description = (
            f"**Code:** `{invite.code}`\n"
            f"**Channel:** {invite.channel.mention}\n"
            f"**Creator:** {invite.inviter.mention if invite.inviter else 'Unknown'}\n"
            f"**Expires:** " + (discord.utils.format_dt(invite.expires_at, "R") if invite.expires_at else "Never")
        )
        await self.send_log(invite.guild, e)

    @commands.Cog.listener()
    @safe_listener
    async def on_invite_delete(self, invite):
        e = discord.Embed(
            title="💔 Invite Deleted",
            color=self.color_role_delete,
            timestamp=datetime.now(timezone.utc)
        )
        e.description = f"**Code:** `{invite.code}`"
        await self.send_log(invite.guild, e)

    # ============================================================
    # AutoMod Events
    # ============================================================
    @commands.Cog.listener()
    @safe_listener
    async def on_automod_rule_create(self, rule):
        e = discord.Embed(
            title="🛡️ AutoMod Rule Created",
            color=self.color_automod,
            timestamp=datetime.now(timezone.utc)
        )
        e.description = f"**Rule Name:** `{rule.name}`\n**ID:** `{rule.id}`"
        await self.send_log(rule.guild, e)

    @commands.Cog.listener()
    @safe_listener
    async def on_automod_rule_update(self, rule):
        e = discord.Embed(
            title="🛡️ AutoMod Rule Updated",
            color=self.color_automod,
            timestamp=datetime.now(timezone.utc)
        )
        e.description = f"**Rule Name:** `{rule.name}`\n**ID:** `{rule.id}`"
        await self.send_log(rule.guild, e)

    @commands.Cog.listener()
    @safe_listener
    async def on_automod_rule_delete(self, rule):
        e = discord.Embed(
            title="🛡️ AutoMod Rule Deleted",
            color=self.color_automod,
            timestamp=datetime.now(timezone.utc)
        )
        e.description = f"**Rule Name:** `{rule.name}`\n**ID:** `{rule.id}`"
        await self.send_log(rule.guild, e)

    @commands.Cog.listener()
    @safe_listener
    async def on_automod_action(self, execution):
        e = discord.Embed(
            title="⚡ AutoMod Action Triggered",
            color=self.color_automod,
            timestamp=datetime.now(timezone.utc)
        )
        e.description = (
            f"**User:** <@{execution.user_id}>\n"
            f"**Channel:** <#{execution.channel_id}>\n"
            f"**Action:** `{execution.action.type}`\n"
            f"**Matched Content:**\n"
            f"```\n{execution.matched_content or 'N/A'}\n```"
        )
        await self.send_log(execution.guild, e)

    # ============================================================
    # Scheduled Events & Stage Instances
    # ============================================================
    @commands.Cog.listener()
    @safe_listener
    async def on_scheduled_event_create(self, event):
        e = discord.Embed(
            title="📅 Event Scheduled",
            color=self.color_event,
            timestamp=datetime.now(timezone.utc)
        )
        e.description = (
            f"**Event:** `{event.name}`\n"
            f"**Starts:** " + (discord.utils.format_dt(event.start_time, "R") if event.start_time else "N/A")
        )
        await self.send_log(event.guild, e)

    @commands.Cog.listener()
    @safe_listener
    async def on_scheduled_event_delete(self, event):
        e = discord.Embed(
            title="📅 Event Cancelled",
            color=self.color_role_delete,
            timestamp=datetime.now(timezone.utc)
        )
        e.description = f"**Event:** `{event.name}`"
        await self.send_log(event.guild, e)

    @commands.Cog.listener()
    @safe_listener
    async def on_scheduled_event_update(self, before, after):
        changes = []
        if before.name != after.name:
            changes.append(f"**Name:** `{before.name}` → `{after.name}`")
        if before.status != after.status:
            changes.append(f"**Status:** `{before.status}` → `{after.status}`")

        if not changes:
            return

        e = discord.Embed(
            title="📅 Event Updated",
            color=self.color_event,
            timestamp=datetime.now(timezone.utc)
        )
        e.description = f"**Event:** `{after.name}`\n\n**Changes:**\n" + "\n".join(changes)
        await self.send_log(after.guild, e)

    @commands.Cog.listener()
    @safe_listener
    async def on_stage_instance_create(self, stage_instance):
        e = discord.Embed(
            title="🎭 Stage Started",
            color=self.color_stage,
            timestamp=datetime.now(timezone.utc)
        )
        e.description = (
            f"**Topic:** `{stage_instance.topic}`\n"
            f"**Channel:** {stage_instance.channel.mention if stage_instance.channel else 'Unknown'}"
        )
        await self.send_log(stage_instance.guild, e)

    @commands.Cog.listener()
    @safe_listener
    async def on_stage_instance_delete(self, stage_instance):
        e = discord.Embed(
            title="🎭 Stage Ended",
            color=self.color_role_delete,
            timestamp=datetime.now(timezone.utc)
        )
        e.description = f"**Topic:** `{stage_instance.topic}`"
        await self.send_log(stage_instance.guild, e)

    # ============================================================
    # User Profile Events
    # ============================================================
    @commands.Cog.listener()
    @safe_listener
    async def on_user_update(self, before, after):
        changes = []
        if before.name != after.name:
            changes.append(f"**Username:** `{before.name}` → `{after.name}`")
        if getattr(before, 'global_name', None) != getattr(after, 'global_name', None):
            changes.append(f"**Global Name:** `{getattr(before, 'global_name', None)}` → `{getattr(after, 'global_name', None)}`")
        if before.display_avatar != after.display_avatar:
            changes.append(f"**Avatar Updated:** [View New Avatar]({after.display_avatar.url})")

        if not changes:
            return

        for guild in after.mutual_guilds:
            e = discord.Embed(
                title="👤 User Profile Updated",
                color=self.color_member_update,
                timestamp=datetime.now(timezone.utc)
            )
            e.set_author(name=f"{after}", icon_url=after.display_avatar.url)
            e.description = (
                f"**User:** {after.mention} (`{after.id}`)\n\n"
                f"**Changes:**\n" + "\n".join(changes)
            )
            await self.send_log(guild, e)


async def setup(bot):
    await bot.add_cog(Logging(bot))
