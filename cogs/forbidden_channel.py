import discord
from discord.ext import commands
from discord import ui
import json
from datetime import datetime, timedelta, timezone


FORBIDDEN_CHANNEL_ID = 1542526402916651148
LOG_CHANNEL_ID = 1495348639327846470


class AppealButton(ui.View):
    def __init__(self, bot):
        super().__init__(timeout=None)
        self.bot = bot
        self.used = set()

    @ui.button(label="إرسال طلب لفك التايم آوت", style=discord.ButtonStyle.danger, custom_id="arf_appeal_btn")
    async def appeal_button(self, interaction: discord.Interaction, button: ui.Button):
        user_id = interaction.user.id
        if user_id in self.used:
            await interaction.response.send_message("لقد استخدمت الزر بالفعل.", ephemeral=True)
            return

        self.used.add(user_id)
        button.disabled = True
        button.label = "تم الإرسال"
        await interaction.message.edit(view=self)

        guild = self.bot.get_guild(interaction.guild_id) if interaction.guild_id else None
        log_channel = None
        if guild:
            log_channel = guild.get_channel(LOG_CHANNEL_ID)
        else:
            for g in self.bot.guilds:
                ch = g.get_channel(LOG_CHANNEL_ID)
                if ch:
                    log_channel = ch
                    break

        if log_channel:
            embed = discord.Embed(
                title="📩 طلب فك تايم آوت",
                description=(
                    f"العضو: {interaction.user.mention} (`{interaction.user.id}`)\n"
                    f"اليوزر: `@{interaction.user.name}`\n"
                    f"السبب: كتابة في روم ممنوع الكتابة به\n"
                    f"التايم آوت الحالي: ساعة"
                ),
                color=0xFEE75C
            )
            embed.set_footer(text="ARF Forbidden Channel System")
            embed.timestamp = datetime.now(timezone.utc)
            await log_channel.send(embed=embed)

        await interaction.response.send_message(
            "تم إرسال طلبك للإدارة. بانتظار الرد.", ephemeral=True
        )


class FirstButton(ui.View):
    def __init__(self, bot):
        super().__init__(timeout=None)
        self.bot = bot
        self.used = set()

    @ui.button(label="فهمت، اضغط هنا", style=discord.ButtonStyle.primary, custom_id="arf_first_btn")
    async def first_button(self, interaction: discord.Interaction, button: ui.Button):
        user_id = interaction.user.id
        if user_id in self.used:
            await interaction.response.send_message("لقد استخدمت الزر بالفعل.", ephemeral=True)
            return

        self.used.add(user_id)
        button.disabled = True
        button.label = "تم الضغط"
        await interaction.message.edit(view=self)

        guild = interaction.guild
        member = guild.get_member(user_id) if guild else None
        if member:
            try:
                await member.timeout(
                    timedelta(hours=1),
                    reason="تفعيل العقوبة الثانية: الضغط على زر التأكيد"
                )
            except Exception as e:
                print(f"[ForbiddenChannel] Error increasing timeout: {e}")

        try:
            embed2 = discord.Embed(
                title="⏰ تم زيادة التايم آوت",
                description=(
                    "لقد تم زيادة تايم آوتك إلى **ساعة** بسبب تفعيل العقوبة.\n"
                    "اذا كنت تبي تفك التايم، اضغط الزر أدناه وستصلك رسالة في روم الإدارين."
                ),
                color=0xED4245
            )
            embed2.set_footer(text="ARF Forbidden Channel System")
            embed2.timestamp = datetime.now(timezone.utc)
            appeal_view = AppealButton(self.bot)
            await interaction.user.send(embed2, view=appeal_view)
        except Exception as e:
            print(f"[ForbiddenChannel] Error sending DM2: {e}")

        log_channel = guild.get_channel(LOG_CHANNEL_ID) if guild else None
        if log_channel:
            embed = discord.Embed(
                title="⚠️ تفعيل عقوبة ثانية",
                description=(
                    f"العضو: {interaction.user.mention} (`{interaction.user.id}`)\n"
                    f"اليوزر: `@{interaction.user.name}`\n"
                    f"السبب: ضغط على زر التأكيد بعد الكتابة في الروم الممنوع\n"
                    f"العقوبة: تايم آوت ساعة"
                ),
                color=0xED4245
            )
            embed.set_footer(text="ARF Forbidden Channel System")
            embed.timestamp = datetime.now(timezone.utc)
            await log_channel.send(embed=embed)

        await interaction.response.send_message(
            "تم تفعيل العقوبة.", ephemeral=True
        )


class ForbiddenChannel(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def get_config(self):
        try:
            with open('config.json', 'r') as f:
                return json.load(f)
        except:
            return {}

    async def cog_load(self):
        self.bot.add_view(AppealButton(self.bot))
        self.bot.add_view(FirstButton(self.bot))
        print(f"[ForbiddenChannel] System loaded. Watching channel ID: {FORBIDDEN_CHANNEL_ID}")

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot or not message.guild:
            return

        if message.channel.id != FORBIDDEN_CHANNEL_ID:
            return

        # Allow pure channel mentions (#channel) with no penalty
        if message.channel_mentions and not message.mentions and not message.role_mentions:
            return

        # Allow staff
        is_staff = (
            message.author.guild_permissions.manage_messages
            or message.author.guild_permissions.administrator
            or message.author.guild_permissions.manage_channels
        )
        if is_staff:
            return

        try:
            await message.delete()
            print(f"[ForbiddenChannel] Deleted message from {message.author} in forbidden channel")
        except Exception as e:
            print(f"[ForbiddenChannel] Could not delete message: {e}")

        member = message.author
        try:
            await member.timeout(
                timedelta(minutes=30),
                reason="الكتابة في روم ممنوع الكتابة به"
            )
            print(f"[ForbiddenChannel] Timeout 30min applied to {member}")
        except Exception as e:
            print(f"[ForbiddenChannel] Could not timeout member: {e}")
            return

        try:
            embed = discord.Embed(
                title="🚫 ممنوع الكتابة في هذا الروم",
                description=(
                    "لقد كتبت رسالة في روم ممنوع الكتابة به.\n"
                    "تم تايم آوتك لمدة **نص ساعة**.\n\n"
                    "اذا تبي تأكد وتفهم العقوبة، اضغط الزر أدناه."
                ),
                color=0xED4245
            )
            embed.set_footer(text="ARF Forbidden Channel System")
            embed.timestamp = datetime.now(timezone.utc)
            view = FirstButton(self.bot)
            await member.send(embed=embed, view=view)
            print(f"[ForbiddenChannel] DM sent to {member}")
        except Exception as e:
            print(f"[ForbiddenChannel] Could not send DM: {e}")

        log_channel = message.guild.get_channel(LOG_CHANNEL_ID)
        if log_channel:
            embed = discord.Embed(
                title="🚫 كتابة في روم ممنوع",
                description=(
                    f"العضو: {member.mention} (`{member.id}`)\n"
                    f"اليوزر: `@{member.name}`\n"
                    f"القناة: {message.channel.mention}\n"
                    f"الإجراء: تايم آوت 30 دقيقة"
                ),
                color=0xED4245
            )
            embed.set_footer(text="ARF Forbidden Channel System")
            embed.timestamp = datetime.now(timezone.utc)
            await log_channel.send(embed=embed)


async def setup(bot):
    await bot.add_cog(ForbiddenChannel(bot))
