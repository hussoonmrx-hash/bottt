import discord
from discord.ext import commands, tasks
from discord import app_commands
import asyncio
import json
import io
from datetime import datetime, timezone, timedelta
from fpdf import FPDF

TICKET_COUNTER_FILE = "ticket_counter.json"


def load_ticket_counter():
    try:
        with open(TICKET_COUNTER_FILE, 'r') as f:
            data = json.load(f)
            return data.get("counter", 0)
    except:
        return 0


def save_ticket_counter(counter):
    try:
        with open(TICKET_COUNTER_FILE, 'w') as f:
            json.dump({"counter": counter}, f)
    except:
        pass


active_tickets = {}
pending_ticket_creation = set()
ticket_custom_timeouts = {}
ticket_created_at = {}  # {channel_id: datetime} لتقييد زر الإغلاق ساعة

COLOR_PRIMARY = 0x2B2D31
COLOR_CLOSE = 0x99AAB5
COLOR_ESCALATE = 0xB08968
COLOR_WARNING = 0xC9A66B


def get_config():
    try:
        with open('config.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return {}


def get_explicit_mentions(message: discord.Message):
    if not message.content:
        return [], []
    import re
    explicit_user_ids = set(re.findall(r'<@!?(\d+)>', message.content))
    explicit_role_ids = set(re.findall(r'<@&(\d+)>', message.content))
    exp_users = [u for u in message.mentions if str(u.id) in explicit_user_ids]
    exp_roles = [r for r in message.role_mentions if str(r.id) in explicit_role_ids]
    return exp_users, exp_roles


def get_ticket_category(guild, category_type):
    config = get_config()
    category_map = {
        "inquiry": "ticket_inquiry_category_id",
        "purchase": "ticket_purchase_category_id",
        "support": "ticket_support_category_id",
    }
    cat_key = category_map.get(category_type, "ticket_category_id")
    cat_id = config.get(cat_key) or config.get("ticket_category_id")
    if not cat_id:
        return None
    ch = guild.get_channel(cat_id)
    if not ch:
        return None
    if isinstance(ch, discord.CategoryChannel):
        return ch
    elif hasattr(ch, 'category') and ch.category:
        return ch.category
    return None


def _find_arabic_font():
    import os
    font_paths = [
        "C:/Windows/Fonts/arial.ttf",
        "C:/Windows/Fonts/arial.ttf",
        "C:/Windows/Fonts/tahoma.ttf",
        "C:/Windows/Fonts/Tahoma.ttf",
        "C:/Windows/Fonts/calibri.ttf",
        "C:/Windows/Fonts/simhei.ttf",
    ]
    for p in font_paths:
        if os.path.exists(p):
            return p
    return None


# ============================
# PDF Transcript Generator
# ============================
def generate_pdf_transcript(channel_name, guild_name, messages, closed_by=None, reason="بدون سبب"):
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)

    arabic_font = _find_arabic_font()
    if arabic_font:
        pdf.add_font("Arabic", "", arabic_font, uni=True)
        pdf.add_font("Arabic", "B", arabic_font, uni=True)
        font_name = "Arabic"
    else:
        font_name = "Helvetica"

    pdf.add_page()

    # Header
    pdf.set_fill_color(32, 34, 37)
    pdf.rect(0, 0, 210, 30, 'F')
    pdf.set_font(font_name, "B", 16)
    pdf.set_text_color(255, 255, 255)
    pdf.set_xy(10, 8)
    pdf.cell(0, 10, f"Transcript - {channel_name}", ln=True)
    pdf.set_font(font_name, "", 10)
    pdf.set_text_color(185, 187, 190)
    pdf.set_xy(10, 20)
    pdf.cell(0, 8, f"{guild_name} | {len(messages)} messages", ln=True)

    # Info bar
    pdf.set_fill_color(47, 49, 54)
    pdf.rect(0, 30, 210, 12, 'F')
    closed_by_str = f"{closed_by.name}" if closed_by else "Auto-Closed"
    pdf.set_font(font_name, "", 9)
    pdf.set_text_color(185, 187, 190)
    pdf.set_xy(10, 32)
    pdf.cell(0, 8, f"Closed by: {closed_by_str}  |  Reason: {reason}  |  Date: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}", ln=True)

    pdf.set_y(45)

    # Messages
    for msg in messages:
        timestamp = msg.created_at.strftime("%Y-%m-%d %H:%M")
        author = msg.author.name
        content = msg.content if msg.content else ""

        if content:
            pdf.set_font(font_name, "B", 10)
            pdf.set_text_color(255, 255, 255)
            pdf.cell(0, 6, f"[{timestamp}] {author}:", ln=True)

            pdf.set_font(font_name, "", 9)
            pdf.set_text_color(220, 221, 222)
            clean = content.replace("\x00", "")
            if pdf.get_string_width(clean) > 180:
                pdf.multi_cell(180, 5, clean)
            else:
                pdf.cell(0, 5, clean, ln=True)
            pdf.ln(2)

        if msg.attachments:
            pdf.set_font(font_name, "", 8)
            pdf.set_text_color(0, 175, 244)
            for att in msg.attachments:
                pdf.cell(0, 5, f"[Attachment: {att.filename}]", ln=True)
            pdf.ln(1)

        if msg.embeds:
            for emb in msg.embeds:
                pdf.set_font(font_name, "B", 9)
                pdf.set_text_color(88, 101, 242)
                if emb.title:
                    pdf.cell(0, 5, f"[Embed: {emb.title}]", ln=True)
                if emb.description:
                    pdf.set_font(font_name, "", 8)
                    pdf.set_text_color(185, 187, 190)
                    desc = emb.description.replace("\x00", "")
                    pdf.multi_cell(180, 4, desc)
                pdf.ln(1)

        # Separator
        pdf.set_draw_color(64, 68, 75)
        pdf.line(10, pdf.get_y(), 200, pdf.get_y())
        pdf.ln(2)

    # Footer
    pdf.set_fill_color(32, 34, 37)
    pdf.rect(0, 277, 210, 20, 'F')
    pdf.set_font(font_name, "", 8)
    pdf.set_text_color(114, 118, 125)
    pdf.set_xy(10, 280)
    pdf.cell(0, 8, "ARF Support System - Transcript Generated", ln=True)

    return pdf.output()


async def save_transcript(bot, channel, guild, closed_by=None, reason="بدون سبب"):
    try:
        messages = [msg async for msg in channel.history(limit=None, oldest_first=True)]

        user_msgs = [m for m in messages if not m.author.bot]
        if len(user_msgs) == 0:
            return

        transcript_channel_id = 1495348639327846470
        transcript_channel = guild.get_channel(transcript_channel_id)
        if not transcript_channel:
            try:
                transcript_channel = await guild.fetch_channel(transcript_channel_id)
            except:
                return

        pdf_bytes = generate_pdf_transcript(channel.name, guild.name, messages, closed_by, reason)
        file_buffer = io.BytesIO(pdf_bytes)
        file = discord.File(fp=file_buffer, filename=f"{channel.name}-transcript.pdf")

        embed = discord.Embed(
            title="نسخة التذكرة",
            description=(
                f"**التذكرة:** `{channel.name}`\n"
                f"**أغلق بواسطة:** {closed_by.mention if closed_by else 'Auto-Closed'}\n"
                f"**السبب:** {reason}\n"
                f"**عدد الرسائل:** {len(messages)}"
            ),
            color=0x2b2d31,
            timestamp=datetime.utcnow()
        )
        if guild.icon:
            embed.set_thumbnail(url=guild.icon.url)

        await transcript_channel.send(embed=embed, file=file)
    except Exception as e:
        print(f"[Transcript Error]: {e}")


# ============================
# Ticket Controls View
# ============================
class TicketControlsView(discord.ui.View):
    def __init__(self, bot):
        super().__init__(timeout=None)
        self.bot = bot

    @discord.ui.button(label="Close Ticket", style=discord.ButtonStyle.secondary, custom_id="close_ticket_btn")
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        # حماية: لا يمكن لصاحب التذكرة إغلاقها قبل مرور ساعة، الأدمن مستثنى
        try:
            config = get_config()
            admin_role_id = config.get("admin_role_id")
            is_staff = (
                interaction.user.guild_permissions.administrator
                or interaction.user.guild_permissions.manage_messages
                or interaction.user.guild_permissions.manage_channels
                or (admin_role_id and any(r.id == admin_role_id for r in interaction.user.roles))
            )
            if not is_staff:
                created = ticket_created_at.get(interaction.channel.id)
                if created:
                    now = datetime.now(timezone.utc)
                    elapsed = (now - created).total_seconds()
                    if elapsed < 3600:
                        remaining = int(3600 - elapsed)
                        mins = remaining // 60
                        secs = remaining % 60
                        await interaction.response.send_message(
                            f"⏳ لا يمكنك إغلاق التذكرة قبل مرور **ساعة** من فتحها. المتبقي: **{mins} دقيقة و {secs} ثانية**. الأدمن يمكنه الإغلاق فوراً.",
                            ephemeral=True
                        )
                        return
        except Exception:
            pass

        embed = discord.Embed(
            title="🔒 إغلاق التذكرة",
            description=(
                "سوف يتم إغلاق هذه التذكرة خلال 5 ثوانٍ...\n\n"
                f"**أغلقت بواسطة:** {interaction.user.mention}\n\n"
                "شكراً لتواصلك مع **دعم ARF** ❤️"
            ),
            color=COLOR_CLOSE
        )
        embed.set_footer(text="ARF Support System")
        embed.timestamp = datetime.now(timezone.utc)
        await interaction.response.send_message(embed=embed)

        for uid, cid in list(active_tickets.items()):
            if cid == interaction.channel.id:
                del active_tickets[uid]
                break
        ticket_created_at.pop(interaction.channel.id, None)
        ticket_custom_timeouts.pop(interaction.channel.id, None)

        await save_transcript(self.bot, interaction.channel, interaction.guild, closed_by=interaction.user, reason="Closed via Button")
        await asyncio.sleep(5)

        try:
            await interaction.channel.delete()
        except:
            pass

    @discord.ui.button(label="Escalate", style=discord.ButtonStyle.secondary, custom_id="escalate_ticket_btn")
    async def escalate_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            config = get_config()
            admin_role_id = config.get("admin_role_id")
            admin_role = interaction.guild.get_role(admin_role_id)
            mention = admin_role.mention if admin_role else "@here"

            embed = discord.Embed(
                title="Ticket Escalated",
                description=(
                    "This ticket has been escalated to the management team.\n"
                    "A staff member will review your case shortly.\n\n"
                    "Thank you for your patience."
                ),
                color=COLOR_ESCALATE
            )
            embed.set_footer(text="ARF Support System")
            embed.timestamp = datetime.utcnow()
            await interaction.response.send_message(content=mention, embed=embed)
            button.disabled = True
            await interaction.message.edit(view=self)
        except Exception as e:
            await interaction.response.send_message("An error occurred while escalating this ticket.", ephemeral=True)


# ============================
# Ticket Panel View
# ============================
class TicketPanelView(discord.ui.View):
    def __init__(self, bot):
        super().__init__(timeout=None)
        self.bot = bot

    @discord.ui.select(
        placeholder="اختر خيار من القسم...",
        min_values=1,
        max_values=1,
        custom_id="ticket_select_menu",
        options=[
            discord.SelectOption(label="استفسار", value="inquiry", emoji="❓"),
            discord.SelectOption(label="مشاكل", value="support", emoji="⚠️"),
            discord.SelectOption(label="شراء", value="purchase", emoji="🛒"),
        ]
    )
    async def select_ticket(self, interaction: discord.Interaction, select: discord.ui.Select):
        category_type = select.values[0]
        await self.open_ticket(interaction, category_type)

    async def open_ticket(self, interaction: discord.Interaction, category_type: str):
        guild = interaction.guild
        member = interaction.user

        if member.id in pending_ticket_creation:
            await interaction.response.send_message(
                "يتم حالياً إنشاء تذكرتك، يرجى الانتظار ثواني...",
                ephemeral=True
            )
            return

        if member.id in active_tickets:
            existing_channel = guild.get_channel(active_tickets[member.id])
            if existing_channel:
                await interaction.response.send_message(
                    f"لديك تذكرة مفتوحة بالفعل: {existing_channel.mention}\nيرجى إغلاقها أولاً قبل فتح تذكرة جديدة.",
                    ephemeral=True
                )
                return
            else:
                del active_tickets[member.id]

        pending_ticket_creation.add(member.id)
        try:
            counter = load_ticket_counter() + 1
            save_ticket_counter(counter)

            channel_name = f"ticket-{counter:04d}"

            overwrites = {
                guild.default_role: discord.PermissionOverwrite(read_messages=False),
                member: discord.PermissionOverwrite(
                    read_messages=True, send_messages=True,
                    attach_files=True, embed_links=True
                ),
                guild.me: discord.PermissionOverwrite(
                    read_messages=True, send_messages=True,
                    manage_channels=True
                )
            }

            config = get_config()
            admin_role_id = config.get("admin_role_id")
            if admin_role_id:
                admin_role = guild.get_role(admin_role_id)
                if admin_role:
                    overwrites[admin_role] = discord.PermissionOverwrite(
                        read_messages=True, send_messages=True,
                        manage_channels=True
                    )

            # Add merchant role access for purchase tickets only
            merchant_role_id = config.get("merchant_role_id")
            if category_type == "purchase" and merchant_role_id:
                merchant_role = guild.get_role(merchant_role_id)
                if merchant_role:
                    overwrites[merchant_role] = discord.PermissionOverwrite(
                        read_messages=True, send_messages=True,
                        attach_files=True, embed_links=True
                    )

            category = get_ticket_category(guild, category_type)

            ticket_channel = await guild.create_text_channel(
                name=channel_name,
                category=category,
                overwrites=overwrites
            )

            active_tickets[member.id] = ticket_channel.id
            ticket_created_at[ticket_channel.id] = datetime.now(timezone.utc)

            category_names = {
                "inquiry": ("استفسار", "استفسار"),
                "support": ("مشاكل", "مشاكل"),
                "purchase": ("شراء", "شراء"),
            }
            cat_ar = category_names.get(category_type, ("دعم", "دعم فني"))

            embed = discord.Embed(
                title=f"Ticket #{counter:04d} · {cat_ar}",
                description=(
                    f"أهلاً بك يا {member.mention} في مركز الدعم.\n\n"
                    "يرجى كتابة استفسارك هنا وسيقوم أحد الإداريين بالرد عليك في أقرب وقت.\n\n"
                    "**تنبيهات هامة:**\n"
                    "· **يُمنع منعاً باتاً فتح تذكرة بدون سبب واضح.**\n"
                    "· سيتم إغلاق التذاكر الفارغة تلقائياً بعد 5 دقائق."
                ),
                color=COLOR_PRIMARY
            )
            embed.set_footer(text=f"ARF Support · {cat_ar}")
            embed.timestamp = datetime.utcnow()

            await ticket_channel.send(
                embed=embed,
                view=TicketControlsView(self.bot)
            )

            await interaction.response.send_message(
                f"تم إنشاء تذكرتك بنجاح: {ticket_channel.mention}",
                ephemeral=True
            )

            asyncio.create_task(self._check_empty_ticket(guild, ticket_channel, member))

        except Exception as e:
            import traceback
            traceback.print_exc()
            try:
                await interaction.response.send_message(
                    f"حدث خطأ أثناء فتح التذكرة: {e}",
                    ephemeral=True
                )
            except:
                pass
        finally:
            pending_ticket_creation.discard(member.id)

    async def _check_empty_ticket(self, guild, ticket_channel, member):
        await asyncio.sleep(480)  # 8 دقائق (المجموع 10 مع التحذير)
        try:
            ch = guild.get_channel(ticket_channel.id)
            if not ch:
                return
            has_message = False
            async for msg in ch.history(limit=15):
                if msg.author.id == member.id and not msg.author.bot:
                    has_message = True
                    break
            if has_message:
                return
            warning_embed = discord.Embed(
                title="تذكير",
                description=(
                    f"{member.mention}، لم نلتقِ أي رسالة منك بعد.\n"
                    "يرجى توضيح سبب التذكرة أو سيتم إغلاقها تلقائياً بعد **دقيقتين**."
                ),
                color=COLOR_WARNING
            )
            warning_embed.set_footer(text="ARF Support System")
            await ch.send(embed=warning_embed)
        except:
            return

        await asyncio.sleep(120)  # دقيقتين إضافية = 10 دقائق إجمالي
        try:
            ch = guild.get_channel(ticket_channel.id)
            if not ch:
                return
            has_message = False
            async for msg in ch.history(limit=15):
                if msg.author.id == member.id and not msg.author.bot:
                    has_message = True
                    break
            if has_message:
                return
            # إرسال تنبيه خاص للعضو بدلاً من رسالة في القناة
            try:
                await member.send(
                    f"🔒 تم إغلاق تذكرتك **{ch.name}** في **{guild.name}** تلقائياً بسبب عدم إرسال أي رسالة خلال **10 دقائق**.\n"
                    f"تم إعطاؤك تايم آوت **30 دقيقة** لتجنب فتح تذاكر فارغة.\n"
                    f"يمكنك فتح تذكرة جديدة بعد انتهاء التايم إذا كنت بحاجة للمساعدة."
                )
            except discord.Forbidden:
                pass  # العضو مغلق DM
            except:
                pass
            # تايم 30 دقيقة لمن يفتح تذكرة فارغة
            try:
                guild_member = guild.get_member(member.id)
                if guild_member:
                    await guild_member.timeout(timedelta(minutes=30), reason="فتح تذكرة فارغة بدون كتابة لمدة 10 دقائق")
            except:
                pass
            if member.id in active_tickets:
                del active_tickets[member.id]
            ticket_created_at.pop(ch.id, None)
            ticket_custom_timeouts.pop(ch.id, None)
            await save_transcript(self.bot, ch, guild, closed_by=None, reason="Auto-closed (Empty ticket 10m) + 30m timeout")
            await asyncio.sleep(5)
            try:
                await ch.delete()
            except:
                pass
        except:
            pass


# ============================
# Tickets Cog
# ============================
class Tickets(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.ticket_inactivity_checker.start()
        self.spam_tracker = {}
        self.mention_tracker = {}

    def cog_unload(self):
        self.ticket_inactivity_checker.cancel()

    @tasks.loop(minutes=5)
    async def ticket_inactivity_checker(self):
        for uid, cid in list(active_tickets.items()):
            try:
                channel = self.bot.get_channel(cid)
                if not channel:
                    continue

                messages = [msg async for msg in channel.history(limit=100)]
                if not messages:
                    continue

                last_message = messages[0]

                # Check if any admin/staff member has sent a message in this ticket
                admin_has_replied = False
                config = get_config()
                admin_role_id = config.get("admin_role_id")

                for msg in messages:
                    if msg.author.bot:
                        continue
                    if isinstance(msg.author, discord.Member):
                        is_staff = (
                            msg.author.guild_permissions.administrator or
                            msg.author.guild_permissions.manage_messages or
                            msg.author.guild_permissions.manage_channels or
                            (admin_role_id and any(r.id == admin_role_id for r in msg.author.roles))
                        )
                        if is_staff:
                            admin_has_replied = True
                            break

                # If no admin/staff has replied yet, do NOT auto-close due to inactivity
                if not admin_has_replied:
                    continue

                # Determine ticket type by category
                config = get_config()
                purchase_category_id = config.get("ticket_purchase_category_id")
                inquiry_category_id = config.get("ticket_inquiry_category_id")
                support_category_id = config.get("ticket_support_category_id")

                is_purchase = False
                is_inquiry_or_support = False
                
                if channel.category_id == purchase_category_id:
                    is_purchase = True
                elif channel.category_id in (inquiry_category_id, support_category_id):
                    is_inquiry_or_support = True

                # Purchase tickets NEVER auto-close
                if is_purchase:
                    continue

                # For inquiry and support tickets: 5 hours (300 minutes) default timeout
                # For other tickets: 30 minutes default timeout
                default_timeout = 300 if is_inquiry_or_support else 30
                timeout_mins = ticket_custom_timeouts.get(cid, default_timeout)
                
                now = datetime.now(timezone.utc)
                if (now - last_message.created_at).total_seconds() < timeout_mins * 60:
                    continue

                close_embed = discord.Embed(
                    title="إغلاق التذكرة",
                    description=(
                        f"تم إغلاق هذه التذكرة تلقائياً بسبب عدم التفاعل لمدة {timeout_mins} دقيقة بعد رد الإدارة.\n"
                        "يمكنك فتح تذكرة جديدة في أي وقت إذا كنت بحاجة للمساعدة."
                    ),
                    color=COLOR_CLOSE
                )
                close_embed.set_footer(text="ARF Support System")
                await channel.send(embed=close_embed)

                if uid in active_tickets:
                    del active_tickets[uid]
                ticket_created_at.pop(cid, None)
                ticket_custom_timeouts.pop(cid, None)

                await save_transcript(self.bot, channel, channel.guild, closed_by=None, reason=f"Auto-closed (Inactivity Timeout {timeout_mins}min after Staff Reply)")
                await asyncio.sleep(5)
                try:
                    await channel.delete()
                except:
                    pass
            except Exception as e:
                print(f"[InactivityChecker Error] {e}")
                pass

    @ticket_inactivity_checker.before_loop
    async def before_checker(self):
        await self.bot.wait_until_ready()

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        ticket_channel_id = active_tickets.pop(member.id, None)
        ticket_created_at.pop(ticket_channel_id, None) if ticket_channel_id else None
        ticket_custom_timeouts.pop(ticket_channel_id, None) if ticket_channel_id else None
        if not ticket_channel_id:
            return
        channel = self.bot.get_channel(ticket_channel_id)
        if not channel:
            return
        try:
            close_embed = discord.Embed(
                title="إغلاق التذكرة",
                description="تم إغلاق هذه التذكرة تلقائياً بعد مغادرة صاحب التذكرة من السيرفر.",
                color=COLOR_CLOSE
            )
            close_embed.set_footer(text="ARF Support System")
            await channel.send(embed=close_embed)
            await save_transcript(self.bot, channel, channel.guild, closed_by=None, reason="Auto-closed (Member Left Server)")
            await asyncio.sleep(5)
            await channel.delete()
        except Exception:
            pass

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return
        if message.channel.id not in active_tickets.values():
            return

        channel_id = message.channel.id
        user_id = message.author.id
        now = datetime.now(datetime.timezone.utc)

        exp_users, exp_roles = get_explicit_mentions(message)
        config = get_config()
        admin_role_id = config.get("admin_role_id")
        has_explicit_admin_mentions = any(
            (u.guild_permissions.administrator or u.guild_permissions.manage_messages or (admin_role_id and any(r.id == admin_role_id for r in u.roles)))
            for u in exp_users
        ) or any(
            (admin_role_id and r.id == admin_role_id) or r.permissions.administrator
            for r in exp_roles
        )

        if has_explicit_admin_mentions:
            if channel_id not in self.mention_tracker:
                self.mention_tracker[channel_id] = {}
            if user_id not in self.mention_tracker[channel_id]:
                self.mention_tracker[channel_id][user_id] = []

            mention_timestamps = self.mention_tracker[channel_id][user_id]
            mention_timestamps.append(now)
            mention_timestamps = [t for t in mention_timestamps if (now - t).total_seconds() < 60]
            self.mention_tracker[channel_id][user_id] = mention_timestamps

            if len(mention_timestamps) >= 3:
                warning_embed = discord.Embed(
                    title="تنبيه",
                    description=(
                        f"{message.author.mention}، لقد تجاوزت الحد المسموح به من منشن الإدارة.\n"
                        "يرجى تقليل المنشنات لتجنب إغلاق التذكرة."
                    ),
                    color=COLOR_WARNING
                )
                warning_embed.set_footer(text="ARF Support System")
                await message.channel.send(embed=warning_embed)
                self.mention_tracker[channel_id][user_id] = []
                return

        if channel_id not in self.spam_tracker:
            self.spam_tracker[channel_id] = {}
        if user_id not in self.spam_tracker[channel_id]:
            self.spam_tracker[channel_id][user_id] = []

        spam_timestamps = self.spam_tracker[channel_id][user_id]
        spam_timestamps.append(now)
        spam_timestamps = [t for t in spam_timestamps if (now - t).total_seconds() < 60]
        self.spam_tracker[channel_id][user_id] = spam_timestamps

        if len(spam_timestamps) >= 3:
            warning_embed = discord.Embed(
                title="تنبيه",
                description=(
                    f"{message.author.mention}، لقد تجاوزت الحد المسموح به من الرسائل.\n"
                    "يرجى تقليل عدد الرسائل لتجنب إغلاق التذكرة."
                ),
                color=COLOR_WARNING
            )
            warning_embed.set_footer(text="ARF Support System")
            await message.channel.send(embed=warning_embed)
            self.spam_tracker[channel_id][user_id] = []

    @commands.hybrid_command(name="close", aliases=["close_ticket"], description="إغلاق التذكرة الحالية | Close current ticket")
    async def close_command(self, ctx: commands.Context, *, reason: str = "تم إغلاق التذكرة"):
        if ctx.channel.id not in active_tickets.values() and not (ctx.channel.name and ctx.channel.name.startswith("ticket-")):
            await ctx.send("❌ يمكن استخدام هذا الأمر فقط داخل تذكرة مفتوحة.", delete_after=5)
            return

        embed = discord.Embed(
            title="🔒 إغلاق التذكرة",
            description=(
                "سوف يتم إغلاق هذه التذكرة خلال 5 ثوانٍ...\n\n"
                f"**السبب:** `{reason}`\n"
                f"**بواسطة:** {ctx.author.mention}\n\n"
                "شكراً لتواصلك مع **دعم ARF** ❤️"
            ),
            color=COLOR_CLOSE
        )
        embed.set_footer(text="ARF Support System")
        embed.timestamp = datetime.now(timezone.utc)
        await ctx.send(embed=embed)

        for uid, cid in list(active_tickets.items()):
            if cid == ctx.channel.id:
                del active_tickets[uid]
                break
        ticket_created_at.pop(ctx.channel.id, None)
        ticket_custom_timeouts.pop(ctx.channel.id, None)

        await save_transcript(self.bot, ctx.channel, ctx.guild, closed_by=ctx.author, reason=reason)
        await asyncio.sleep(5)

        try:
            await ctx.channel.delete()
        except:
            pass

    @app_commands.command(name="extend_ticket", description="تمديد مدة الإغلاق التلقائي للتذكرة")
    @app_commands.default_permissions(manage_channels=True)
    @app_commands.choices(duration=[
        app_commands.Choice(name="1 Hour / ساعة", value=60),
        app_commands.Choice(name="12 Hours / ١٢ ساعة", value=720),
        app_commands.Choice(name="1 Day / يوم", value=1440),
        app_commands.Choice(name="2 Days / يومين", value=2880),
        app_commands.Choice(name="1 Week / أسبوع", value=10080),
        app_commands.Choice(name="Never Close / عدم الإغلاق أبداً", value=9999999)
    ])
    async def extend_ticket(self, interaction: discord.Interaction, duration: app_commands.Choice[int]):
        if interaction.channel.id not in active_tickets.values():
            await interaction.response.send_message("يُمكن استخدام هذا الأمر داخل تذكرة مفتوحة فقط.", ephemeral=True)
            return
        ticket_custom_timeouts[interaction.channel.id] = duration.value
        embed = discord.Embed(
            title="تم تمديد مدة الإغلاق التلقائي",
            description=f"تم تمديد فترة الإغلاق التلقائي لهذه التذكرة لتصبح: **{duration.name}** من وقت آخر تفاعل.",
            color=COLOR_PRIMARY
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="setup_ticket", description="إعداد لوحة التذاكر")
    @app_commands.default_permissions(administrator=True)
    async def setup_ticket(self, interaction: discord.Interaction):
        await interaction.response.send_message("تم إعداد نظام التذاكر بنجاح!", ephemeral=True)

        panel_embed = discord.Embed(
            title="فتح تذكرة | Erfan",
            description=(
                "### **مرحباً بك في مركز الدعم.**\n"
                "**الرجاء اختيار القسم المناسب أدناه لفتح تذكرة جديدة.**\n\n"
                "### **قوانين مركز الدعم:**\n"
                "**1. يُمنع منعاً باتاً فتح تذكرة بدون سبب واضح.**\n"
                "**2. في حال فتح تذكرة ولم تكتب شيئاً، سيتم إغلاق التذكرة تلقائياً بعد 5 دقائق.**\n"
                "**3. يرجى الاحترام المتبادل وتقدير أوقات الإدارة.**\n"
                "**4. تذاكر الشراء لا تُغلق تلقائياً.**"
            ),
            color=COLOR_PRIMARY
        )

        import os
        banner_path = 'assets/ticket_banner.png'
        file = None
        if os.path.exists(banner_path):
            file = discord.File(banner_path, filename="ticket_banner.png")
            panel_embed.set_image(url="attachment://ticket_banner.png")

        panel_embed.set_footer(text=f"{interaction.guild.name} Support Team")
        panel_embed.timestamp = datetime.utcnow()

        if file:
            await interaction.channel.send(file=file, embed=panel_embed, view=TicketPanelView(self.bot))
        else:
            await interaction.channel.send(embed=panel_embed, view=TicketPanelView(self.bot))


async def setup(bot):
    await bot.add_cog(Tickets(bot))
    bot.add_view(TicketPanelView(bot))
    bot.add_view(TicketControlsView(bot))
