import discord
from discord.ext import commands
from discord import app_commands
import json

class Welcome(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.invites = {}
        self.welcomed_users = {}  # {user_id: timestamp}

    def get_config(self):
        try:
            with open('config.json', 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return {}

    @commands.Cog.listener()
    async def on_ready(self):
        # Cache invites for all guilds
        for guild in self.bot.guilds:
            try:
                self.invites[guild.id] = await guild.invites()
            except:
                pass

    @commands.Cog.listener()
    async def on_invite_create(self, invite):
        try:
            self.invites[invite.guild.id] = await invite.guild.invites()
        except:
            pass

    @commands.Cog.listener()
    async def on_invite_delete(self, invite):
        try:
            self.invites[invite.guild.id] = await invite.guild.invites()
        except:
            pass

    async def welcome_member(self, member: discord.Member):
        if member.bot:
            try:
                bot_role_id = 1485680187856126114
                role = member.guild.get_role(bot_role_id)
                if role:
                    await member.add_roles(role)
                    print(f"[Welcome] Assigned bot role to {member.name}")
            except Exception as e:
                print(f"[Welcome] Error assigning bot role: {e}")
            return True, "Bot joined, role assigned, welcome skipped."

        config = self.get_config()
        
        # 1. Invite Tracking (with error safety)
        if member.guild.id in self.invites:
            try:
                old_invites = self.invites[member.guild.id]
                new_invites = await member.guild.invites()
                self.invites[member.guild.id] = new_invites
            except Exception as e:
                print(f"[Welcome] Error tracking invite: {e}")

        # 2. Auto Role (give ONLY the waiting role, so users must activate)
        try:
            target_role_id = int(config.get("waiting_role_id") or 1534819630332383302)
            role = member.guild.get_role(target_role_id)
            if role:
                await member.add_roles(role)
                print(f"[Welcome] Successfully assigned waiting role: {role.name} to member: {member.name}")
            else:
                print(f"[Welcome] Could not find role with ID {target_role_id} in guild cache.")
        except Exception as e:
            print(f"[Welcome] Error assigning welcome role: {e}")

        # 3. Welcome Message (with cooldown to prevent rejoin spam)
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        cooldown_seconds = config.get("welcome_cooldown_seconds", 900)

        if member.id in self.welcomed_users:
            last_welcomed = self.welcomed_users[member.id]
            if (now - last_welcomed).total_seconds() < cooldown_seconds:
                print(f"[Welcome] Skipping welcome message for {member.name} (ID: {member.id}) due to cooldown ({int((now - last_welcomed).total_seconds())}s < {cooldown_seconds}s)")
                return True, "Welcome message skipped due to cooldown."

        self.welcomed_users[member.id] = now

        channel_id = config.get("welcome_channel_id")
        if not channel_id:
            msg = "welcome_channel_id is not set in config.json"
            print(f"[Welcome] {msg}")
            return False, msg
            
        try:
            channel_id = int(channel_id)
        except ValueError:
            msg = f"welcome_channel_id '{channel_id}' is not a valid integer."
            print(f"[Welcome] {msg}")
            return False, msg
            
        channel = member.guild.get_channel(channel_id)
        if not channel:
            try:
                print(f"[Welcome] Channel not found in cache. Attempting to fetch channel ID: {channel_id}")
                channel = await member.guild.fetch_channel(channel_id)
            except Exception as e:
                msg = f"Error fetching welcome channel {channel_id}: {e}"
                print(f"[Welcome] {msg}")
                return False, msg

        # تعديل الرسالة للنمط المطلوب
        welcome_msg = f"Welcome {member.mention}\nMember : {member.guild.member_count}\nWelcome to Erfan"

        try:
            await channel.send(content=welcome_msg)
            print(f"[Welcome] Successfully sent welcome message for {member.name} in channel #{channel.name}")
            return True, "Success"
        except Exception as e:
            msg = f"Error sending welcome message: {e}"
            print(f"[Welcome] {msg}")
            return False, msg

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        print(f"[Welcome] Event triggered! Member joined: {member.name} (ID: {member.id}) in guild: {member.guild.name} (ID: {member.guild.id})")
        await self.welcome_member(member)

    @app_commands.command(name="test_welcome", description="إرسال تجربة لرسالة الترحيب | Send a test welcome message")
    @app_commands.default_permissions(administrator=True)
    async def test_welcome(self, interaction: discord.Interaction, member: discord.Member = None):
        if not member:
            member = interaction.user
            
        await interaction.response.defer(ephemeral=True)
        
        success, message = await self.welcome_member(member)
        if success:
            await interaction.followup.send(f"✅ تم إرسال رسالة الترحيب التجريبية للعضو {member.mention} بنجاح!", ephemeral=True)
        else:
            await interaction.followup.send(f"❌ فشل إرسال رسالة الترحيب. السبب:\n`{message}`", ephemeral=True)

    @app_commands.command(name="simulate_join", description="محاكاة دخول عضو لتجربة الترحيب والرتب بالكامل | Simulate a member join to test welcome and roles")
    @app_commands.default_permissions(administrator=True)
    async def simulate_join(self, interaction: discord.Interaction, member: discord.Member = None):
        if not member:
            member = interaction.user
            
        await interaction.response.defer(ephemeral=True)
        
        print(f"[Simulation] Simulating member join for {member.name}")
        await self.welcome_member(member)
        await interaction.followup.send(f"✅ تم عمل محاكاة دخول للعضو {member.mention}! تفقد الرتب وقناة الترحيب وشاشة الكونسول لرؤية النتائج.", ephemeral=True)

    @app_commands.command(name="welcome_config", description="عرض إعدادات الترحيب الحالية وتفاصيل الصلاحيات | View current welcome settings and permissions")
    @app_commands.default_permissions(administrator=True)
    async def welcome_config(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        config = self.get_config()
        channel_id = config.get("welcome_channel_id")
        
        embed = discord.Embed(
            title="⚙️ تشخيص نظام الترحيب | Welcome System Diagnostics",
            color=0x3498DB
        )
        
        # 1. Check welcome_channel_id in config
        if not channel_id:
            embed.add_field(name="رقم الروم (Channel ID)", value="❌ غير محدد في config.json", inline=False)
            await interaction.followup.send(embed=embed, ephemeral=True)
            return
            
        embed.add_field(name="رقم الروم في config.json", value=f"`{channel_id}`", inline=False)
        
        # 2. Try parsing ID
        try:
            parsed_id = int(channel_id)
            embed.add_field(name="تحليل الآيدي", value="✅ آيدي صالح (رقمي)", inline=False)
        except ValueError:
            embed.add_field(name="تحليل الآيدي", value=f"❌ آيدي غير صالح (يجب أن يكون رقم فقط، القيمة الحالية: `{channel_id}`)", inline=False)
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        # 3. Check if channel is found in guild
        guild = interaction.guild
        channel = guild.get_channel(parsed_id)
        if channel:
            embed.add_field(name="الحصول على الروم من الكاش", value=f"✅ تم العثور عليه: {channel.mention} (`#{channel.name}`)", inline=False)
        else:
            embed.add_field(name="الحصول على الروم من الكاش", value="⚠️ لم يتم العثور عليه في الكاش، سيتم محاولة جلبه (fetch)...", inline=False)
            try:
                channel = await guild.fetch_channel(parsed_id)
                embed.add_field(name="جلب الروم (Fetch Channel)", value=f"✅ تم الجلب بنجاح: {channel.mention} (`#{channel.name}`)", inline=False)
            except Exception as e:
                embed.add_field(name="جلب الروم (Fetch Channel)", value=f"❌ فشل الجلب. الخطأ: `{e}`", inline=False)
                await interaction.followup.send(embed=embed, ephemeral=True)
                return

        # 4. Check Bot permissions in the channel
        bot_member = guild.me
        perms = channel.permissions_for(bot_member)
        
        perms_list = []
        if perms.view_channel:
            perms_list.append("✅ رؤية القناة (View Channel)")
        else:
            perms_list.append("❌ رؤية القناة (View Channel) - البوت لا يرى القناة!")
            
        if perms.send_messages:
            perms_list.append("✅ إرسال الرسائل (Send Messages)")
        else:
            perms_list.append("❌ إرسال الرسائل (Send Messages) - البوت لا يمكنه الإرسال!")
            
        if perms.embed_links:
            perms_list.append("✅ إدراج الروابط (Embed Links)")
        else:
            perms_list.append("⚠️ إدراج الروابط (Embed Links) - قد يمنع إرسال المرفقات بشكل صحيح.")
            
        embed.add_field(name="صلاحيات البوت في روم الترحيب", value="\n".join(perms_list), inline=False)
        
        # 5. Check if Intents are enabled in bot
        intents = self.bot.intents
        if intents.members:
            embed.add_field(name="صلاحية الأعضاء في الكود (Members Intent)", value="✅ مفعلة", inline=False)
        else:
            embed.add_field(name="صلاحية الأعضاء في الكود (Members Intent)", value="❌ معطلة! لن يعمل الترحيب التلقائي عند دخول العضو.", inline=False)
            
        await interaction.followup.send(embed=embed, ephemeral=True)

async def setup(bot):
    await bot.add_cog(Welcome(bot))