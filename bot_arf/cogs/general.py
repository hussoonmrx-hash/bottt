import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime

class TitleModal(discord.ui.Modal, title='Title Message | رسالة منسقة'):
    msg_title = discord.ui.TextInput(
        label='Title | العنوان',
        style=discord.TextStyle.short,
        required=True,
        placeholder="عنوان الرسالة..."
    )
    msg_content = discord.ui.TextInput(
        label='Message Content | محتوى الرسالة',
        style=discord.TextStyle.long,
        required=True,
        placeholder="اكتب رسالتك هنا... (يدعم الأسطر المتعددة)",
        max_length=4000
    )
    msg_color = discord.ui.TextInput(
        label='Hex Color | لون الإطار (Optional)',
        style=discord.TextStyle.short,
        required=False,
        placeholder="مثال: FF0000 أو 5865F2"
    )
    msg_footer = discord.ui.TextInput(
        label='Footer | النص السفلي (Optional)',
        style=discord.TextStyle.short,
        required=False,
        placeholder="نص يظهر في أسفل الرسالة..."
    )
    msg_author = discord.ui.TextInput(
        label='Author Name | اسم الكاتب (Optional)',
        style=discord.TextStyle.short,
        required=False,
        placeholder="مثال: الإدارة العامة"
    )

    def __init__(self, bot, image, thumbnail, file, mention, hidden_mention):
        super().__init__()
        self.bot = bot
        self.image = image
        self.thumbnail = thumbnail
        self.file = file
        self.mention = mention
        self.hidden_mention = hidden_mention

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        formatted_description = self.msg_content.value.replace("\\n", "\n")
        ping_content = ""
        if self.mention and self.mention.value == "everyone":
            ping_content = "@everyone"
        elif self.mention and self.mention.value == "here":
            ping_content = "@here"
        if ping_content and self.hidden_mention:
            ping_content = f"||{ping_content}||"

        files_to_send = []
        embed_color = 0x2B2D31
        if self.msg_color.value:
            try:
                hex_str = self.msg_color.value.lstrip('#')
                embed_color = int(hex_str, 16)
            except:
                pass

        embed = discord.Embed(description=formatted_description, color=embed_color)
        embed.title = self.msg_title.value

        if self.msg_author.value:
            embed.set_author(
                name=self.msg_author.value,
                icon_url=interaction.guild.icon.url if interaction.guild.icon else self.bot.user.display_avatar.url
            )

        if self.image:
            embed.set_image(url=self.image.url)
        if self.thumbnail:
            embed.set_thumbnail(url=self.thumbnail.url)

        if self.file:
            try:
                file_data = await self.file.to_file()
                files_to_send.append(file_data)
                embed.add_field(
                    name="📁 الملف المرفق | Attached File",
                    value=f"└ [{self.file.filename}]({self.file.url})",
                    inline=False
                )
            except Exception as e:
                print(f"[Title Command] Error attaching file: {e}")

        guild_icon = interaction.guild.icon.url if interaction.guild.icon else self.bot.user.display_avatar.url
        footer = self.msg_footer.value if self.msg_footer.value else "رسالة رسمية من النظام • ARF System Message"
        embed.set_footer(text=footer, icon_url=guild_icon)
        embed.timestamp = datetime.utcnow()

        await interaction.channel.send(content=ping_content if ping_content else None, embed=embed, files=files_to_send)
        await interaction.followup.send("✅ تم إرسال الرسالة المنسقة بنجاح!", ephemeral=True)
        self.bot.dispatch("admin_update", interaction.user, self.msg_content.value, interaction.channel)


class MsgModal(discord.ui.Modal, title='Quick Message | رسالة سريعة'):
    msg_content = discord.ui.TextInput(
        label='Message | الرسالة',
        style=discord.TextStyle.long,
        required=True,
        placeholder="اكتب رسالتك هنا... اضغط Enter لعمل مسافة للأسفل",
        max_length=4000
    )

    def __init__(self, bot, mention, hidden_mention, image, file):
        super().__init__()
        self.bot = bot
        self.mention = mention
        self.hidden_mention = hidden_mention
        self.image = image
        self.file = file

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        formatted_message = self.msg_content.value.replace("\\n", "\n")
        ping_content = ""
        if self.mention and self.mention.value == "everyone":
            ping_content = "@everyone"
        elif self.mention and self.mention.value == "here":
            ping_content = "@here"
        if ping_content and self.hidden_mention:
            ping_content = f"||{ping_content}||"

        full_content = ""
        if ping_content:
            full_content += f"{ping_content}\n"
        full_content += formatted_message

        files_to_send = []
        if self.image:
            try: files_to_send.append(await self.image.to_file())
            except: pass
        if self.file:
            try: files_to_send.append(await self.file.to_file())
            except: pass

        await interaction.channel.send(content=full_content, files=files_to_send)
        await interaction.followup.send("✅ تم إرسال الرسالة بنجاح!", ephemeral=True)
        self.bot.dispatch("admin_update", interaction.user, self.msg_content.value, interaction.channel)

class General(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.bot_color = 0x2b2d31

    @app_commands.command(name="taytel", description="إرسال رسالة منسقة مع عنوان وبوردر | Send styled embed message with title")
    @app_commands.describe(
        mention="منشن مرفق مع الرسالة | Mention tag",
        hidden_mention="إخفاء المنشن | Hide mention in spoiler tags",
        image="صورة كبيرة | Large image",
        thumbnail="صورة صغيرة | Small thumbnail",
        file="ملف مرفق | File attachment"
    )
    @app_commands.choices(
        mention=[
            app_commands.Choice(name="None (بدون منشن)", value="none"),
            app_commands.Choice(name="@everyone (للجميع)", value="everyone"),
            app_commands.Choice(name="@here (للمتواجدين)", value="here")
        ]
    )
    @app_commands.default_permissions(manage_messages=True)
    async def taytel_command(
        self,
        interaction: discord.Interaction,
        mention: app_commands.Choice[str] = None,
        hidden_mention: bool = False,
        image: discord.Attachment = None,
        thumbnail: discord.Attachment = None,
        file: discord.Attachment = None
    ):
        modal = TitleModal(self.bot, image, thumbnail, file, mention, hidden_mention)
        await interaction.response.send_modal(modal)

    @app_commands.command(name="masg", description="إرسال رسالة نصية عادية بدون بوردر | Send plain text message")
    @app_commands.describe(
        message="الرسالة السريعة (اتركها فارغة لفتح نافذة الكتابة) | Quick message (leave empty for modal)",
        mention="منشن مرفق مع الرسالة | Mention tag",
        hidden_mention="إخفاء المنشن | Hide mention in spoiler tags",
        image="صورة مرفقة | Attachment image",
        file="ملف مرفق | File attachment"
    )
    @app_commands.choices(
        mention=[
            app_commands.Choice(name="None (بدون منشن)", value="none"),
            app_commands.Choice(name="@everyone (للجميع)", value="everyone"),
            app_commands.Choice(name="@here (للمتواجدين)", value="here")
        ]
    )
    @app_commands.default_permissions(manage_messages=True)
    async def masg_command(
        self,
        interaction: discord.Interaction,
        message: str = None,
        mention: app_commands.Choice[str] = None,
        hidden_mention: bool = False,
        image: discord.Attachment = None,
        file: discord.Attachment = None
    ):
        if not message:
            modal = MsgModal(self.bot, mention, hidden_mention, image, file)
            await interaction.response.send_modal(modal)
            return

        await interaction.response.defer(ephemeral=True)

        formatted_message = message.replace("\\n", "\n")
        ping_content = ""
        if mention and mention.value == "everyone":
            ping_content = "@everyone"
        elif mention and mention.value == "here":
            ping_content = "@here"
        if ping_content and hidden_mention:
            ping_content = f"||{ping_content}||"

        full_content = ""
        if ping_content:
            full_content += f"{ping_content}\n"
        full_content += formatted_message

        files_to_send = []
        if image:
            try: files_to_send.append(await image.to_file())
            except: pass
        if file:
            try: files_to_send.append(await file.to_file())
            except: pass

        await interaction.channel.send(content=full_content, files=files_to_send)
        await interaction.followup.send("✅ تم إرسال الرسالة بنجاح!", ephemeral=True)
        self.bot.dispatch("admin_update", interaction.user, message, interaction.channel)

    @app_commands.command(name="ping", description="Check the bot's latency")
    async def ping(self, interaction: discord.Interaction):
        latency = round(self.bot.latency * 1000)

        # Color based on latency
        if latency < 100:
            color = 0x2ECC71  # Green
            status = "Excellent"
            emoji = "🟢"
        elif latency < 200:
            color = 0xF1C40F  # Yellow
            status = "Good"
            emoji = "🟡"
        else:
            color = 0xE74C3C  # Red
            status = "High"
            emoji = "🔴"

        embed = discord.Embed(
            title="🏓  Pong!",
            description=(
                f"**Latency:** `{latency}ms` {emoji}\n"
                f"**Status:** {status}\n"
                f"**Uptime:** Online"
            ),
            color=color
        )
        embed.set_footer(
            text=f"Requested by {interaction.user.display_name}",
            icon_url=interaction.user.display_avatar.url
        )
        embed.timestamp = datetime.utcnow()
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="serverinfo", description="Display detailed information about this server")
    async def serverinfo(self, interaction: discord.Interaction):
        guild = interaction.guild
        created_time = int(guild.created_at.timestamp())
        
        embed = discord.Embed(
            title=f"Server Info — {guild.name}",
            color=self.bot_color
        )
        
        if guild.icon:
            embed.set_thumbnail(url=guild.icon.url)
        if guild.banner:
            embed.set_image(url=guild.banner.url)

        embed.add_field(name="Owner", value=f"{guild.owner.mention} ({guild.owner.id})", inline=True)
        embed.add_field(name="Created", value=f"<t:{created_time}:F> (<t:{created_time}:R>)", inline=True)
        embed.add_field(name="Verification Level", value=f"`{guild.verification_level.name.title()}`", inline=True)
        
        embed.add_field(name="Members Count", value=f"`{guild.member_count}` members", inline=True)
        embed.add_field(name="Roles Count", value=f"`{len(guild.roles)}` roles", inline=True)
        embed.add_field(name="Boost status", value=f"Tier `{guild.premium_tier}` ({guild.premium_subscription_count} boosts)", inline=True)
        
        text_ch = len(guild.text_channels)
        voice_ch = len(guild.voice_channels)
        categories = len(guild.categories)
        embed.add_field(name="Channels", value=f"`{text_ch}` Text | `{voice_ch}` Voice | `{categories}` Categories", inline=False)
        
        embed.set_footer(text=f"Requested by {interaction.user.display_name}", icon_url=interaction.user.display_avatar.url)
        embed.timestamp = datetime.utcnow()
        
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="userinfo", description="Display detailed information about a member")
    @app_commands.describe(member="The member to inspect (defaults to you)")
    async def userinfo(self, interaction: discord.Interaction, member: discord.Member = None):
        if not member:
            member = interaction.user
            
        created_time = int(member.created_at.timestamp())
        joined_time = int(member.joined_at.timestamp())
        
        embed = discord.Embed(
            title=f"User Info — {member.display_name}",
            color=member.color if member.color.value != 0 else self.bot_color
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        
        # User details
        embed.add_field(name="Username", value=f"`{member.name}`", inline=True)
        embed.add_field(name="ID", value=f"`{member.id}`", inline=True)
        embed.add_field(name="Nickname", value=f"`{member.nick or 'None'}`", inline=True)
        
        embed.add_field(name="Account Created", value=f"<t:{created_time}:F> (<t:{created_time}:R>)", inline=False)
        embed.add_field(name="Joined Server", value=f"<t:{joined_time}:F> (<t:{joined_time}:R>)", inline=False)
        
        roles = [role.mention for role in member.roles if role != interaction.guild.default_role]
        roles_str = ", ".join(roles) if roles else "None"
        if len(roles_str) > 1024:
            roles_str = f"{len(roles)} roles"
            
        embed.add_field(name=f"Roles ({len(roles)})", value=roles_str, inline=False)
        embed.add_field(name="Top Role", value=member.top_role.mention, inline=True)
        
        embed.set_footer(text=f"Requested by {interaction.user.display_name}", icon_url=interaction.user.display_avatar.url)
        embed.timestamp = datetime.utcnow()
        
        await interaction.response.send_message(embed=embed)


async def setup(bot):
    await bot.add_cog(General(bot))
