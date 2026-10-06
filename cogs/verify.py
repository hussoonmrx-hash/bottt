import discord
from discord.ext import commands
import json
import os
from datetime import datetime

VERIFY_FILE = "verify_message.json"
EMOJI = "✅"

def load_json(path, default):
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return default

def save_json(path, data):
    try:
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[Verify] save error: {e}")

class Verify(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def get_config(self):
        return load_json('config.json', {})

    async def do_activate(self, guild: discord.Guild, user_id: int):
        config = self.get_config()
        try:
            member = guild.get_member(user_id)
            if not member:
                try:
                    member = await guild.fetch_member(user_id)
                except discord.NotFound:
                    return False
                except Exception as e:
                    print(f"[Verify] fetch member error: {e}")
                    return False

            if member.bot:
                return False

            member_role_id = config.get("member_role_id")
            waiting_role_id = config.get("waiting_role_id")
            unverified_role_id = config.get("unverified_role_id")

            member_role = guild.get_role(member_role_id) if member_role_id else None
            if not member_role:
                print(f"[Verify] member_role not found: {member_role_id}")
                return False

            # لو عنده الرتبة خلاص لا تعيد
            if member_role in member.roles:
                return True

            await member.add_roles(member_role, reason="تفعيل بالايموجي ✅")

            waiting_role = guild.get_role(waiting_role_id) if waiting_role_id else None
            if waiting_role and waiting_role in member.roles:
                await member.remove_roles(waiting_role, reason="تفعيل بالايموجي ✅")

            unverified_role = guild.get_role(unverified_role_id) if unverified_role_id else None
            if unverified_role and unverified_role in member.roles:
                await member.remove_roles(unverified_role, reason="تفعيل بالايموجي ✅")

            # سجل في لوق التفعيل
            log_channel_id = config.get("mod_action_log_channel_id") or 1495348639327846470
            try:
                log_channel = guild.get_channel(log_channel_id)
                if not log_channel:
                    log_channel = await guild.fetch_channel(log_channel_id)
                if log_channel:
                    embed = discord.Embed(
                        title="✅ تم تفعيل حساب جديد",
                        description=f"قام **{member.mention}** بتفعيل حسابه بالايموجي",
                        color=0x2ECC71,
                        timestamp=datetime.now(),
                    )
                    embed.add_field(name="العضو", value=f"{member} (ID: {user_id})", inline=False)
                    if member.display_avatar:
                        embed.set_thumbnail(url=member.display_avatar.url)
                    embed.set_footer(text="ARF Verification System")
                    await log_channel.send(embed=embed)
            except Exception as e:
                print(f"[Verify] log error: {e}")

            print(f"[Verify] {member} activated via emoji")
            return True
        except Exception as e:
            print(f"[Verify] activate error: {e}")
            return False

    @commands.hybrid_command(name="verify", aliases=["setup_verify"], description="إرسال رسالة التفعيل بالايموجي")
    @commands.has_permissions(administrator=True)
    async def verify(self, ctx: commands.Context):
        embed = discord.Embed(
            title="يا هلا بيك في سيرفر ARF",
            description=(
                "عشان تفتح لك كل الرومات، **اضغط على ✅ اللي تحت**.\n\n"
                "أول ما تضغطها بتاخذ رتبة العضو تلقائياً.\n\n"
                "منور السيرفر! ❤️"
            ),
            color=0x2B2D31
        )
        embed.set_footer(text="ARF Server Verification • اضغط ✅ للتفعيل")

        banner_path = 'assets/verify_banner.png'
        file = None
        if os.path.exists(banner_path):
            file = discord.File(banner_path, filename="verify_banner.png")
            embed.set_image(url="attachment://verify_banner.png")

        if file:
            msg = await ctx.send(embed=embed, file=file)
        else:
            msg = await ctx.send(embed=embed)

        try:
            await msg.add_reaction(EMOJI)
        except Exception as e:
            print(f"[Verify] add reaction error: {e}")

        save_json(VERIFY_FILE, {"message_id": msg.id, "channel_id": msg.channel.id, "guild_id": msg.guild.id if msg.guild else None})

        if not ctx.interaction and ctx.message:
            try:
                await ctx.message.delete()
            except:
                pass

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        # تجاهل البوتات
        if payload.user_id == self.bot.user.id:
            return
        if str(payload.emoji.name) != EMOJI:
            return

        data = load_json(VERIFY_FILE, {})
        saved_id = data.get("message_id")
        # لو فيه رسالة مسجلة، التفعيل فقط عليها. لو ما فيه، اقبل أي ✅ (للباكورد)
        if saved_id and payload.message_id != saved_id:
            return

        guild = self.bot.get_guild(payload.guild_id) if payload.guild_id else None
        if not guild:
            return

        success = await self.do_activate(guild, payload.user_id)
        # شيل الرياكشن عشان يقدر يضغط مرة ثانية لو احتاج
        if success:
            try:
                channel = guild.get_channel(payload.channel_id)
                if not channel:
                    channel = await guild.fetch_channel(payload.channel_id)
                msg = await channel.fetch_message(payload.message_id)
                member = guild.get_member(payload.user_id)
                if member:
                    await msg.remove_reaction(payload.emoji, member)
            except:
                pass

async def setup(bot):
    await bot.add_cog(Verify(bot))
