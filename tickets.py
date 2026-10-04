import discord
from discord.ext import commands
from discord import app_commands
import asyncio
import json
from datetime import datetime

# ============================
# Ticket counter (persisted in file)
# ============================
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

# ============================
# Active tickets tracker
# ============================
active_tickets = {}  # {user_id: channel_id}

# ============================
# Unified, calm color palette
# ============================
COLOR_PRIMARY = 0x2B2D31   # neutral dark (panel / rules)
COLOR_CLOSE = 0x99AAB5     # soft gray (closing)
COLOR_ESCALATE = 0xB08968  # muted bronze (escalation)
COLOR_WARNING = 0xC9A66B   # soft amber (reminder)

SECTION_COLORS = {
    "purchase": 0x8FBC8F,   # muted sage green
    "inquiry": 0x6C8EBF,    # muted blue
    "support": 0xC9A66B,    # muted amber
    "other": 0x9B8AA6,      # muted mauve
}

SECTION_LABELS = {
    "purchase": "Purchase",
    "inquiry": "Inquiry",
    "support": "Support",
    "other": "Other",
}


class TicketControlsView(discord.ui.View):
    def __init__(self, bot):
        super().__init__(timeout=None)
        self.bot = bot

    @discord.ui.button(label="Close Ticket", style=discord.ButtonStyle.secondary, custom_id="close_ticket_btn")
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(
            title="Closing Ticket",
            description=(
                "This ticket will be closed shortly.\n\n"
                "Thank you for reaching out to **ARF Support**."
            ),
            color=COLOR_CLOSE
        )
        embed.set_footer(text="ARF Support System")
        embed.timestamp = datetime.utcnow()
        await interaction.response.send_message(embed=embed)

        # Remove from active tickets
        for uid, cid in list(active_tickets.items()):
            if cid == interaction.channel.id:
                del active_tickets[uid]
                break

        await asyncio.sleep(5)
        try:
            await interaction.channel.delete()
        except:
            pass

    @discord.ui.button(label="Escalate", style=discord.ButtonStyle.secondary, custom_id="escalate_ticket_btn")
    async def escalate_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            with open('config.json', 'r', encoding='utf-8') as f:
                config = json.load(f)
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


class TicketSelect(discord.ui.Select):
    def __init__(self, bot):
        self.bot = bot
        options = [
            discord.SelectOption(
                label="Purchase",
                description="Buy services or tools",
                value="purchase",
            ),
            discord.SelectOption(
                label="Inquiry",
                description="General question or inquiry",
                value="inquiry",
            ),
            discord.SelectOption(
                label="Support",
                description="Technical or programming issues",
                value="support",
            ),
            discord.SelectOption(
                label="Other",
                description="Any other topic",
                value="other",
            ),
        ]
        super().__init__(
            placeholder="Select a category to open a ticket...",
            min_values=1, max_values=1, options=options, custom_id="ticket_select_menu"
        )

    async def callback(self, interaction: discord.Interaction):
        guild = interaction.guild
        member = interaction.user
        category_value = self.values[0]

        # ── Prevent duplicate tickets ──
        if member.id in active_tickets:
            existing_channel = guild.get_channel(active_tickets[member.id])
            if existing_channel:
                await interaction.response.send_message(
                    f"You already have an open ticket: {existing_channel.mention}\n"
                    f"Please close it before opening a new one.",
                    ephemeral=True
                )
                return
            else:
                del active_tickets[member.id]

        # ── Ticket counter ──
        counter = load_ticket_counter() + 1
        save_ticket_counter(counter)

        # ── Channel name (English, clean) ──
        channel_name = f"ticket-{category_value}-{counter:04d}"

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

        # ── Load config once ──
        try:
            with open('config.json', 'r', encoding='utf-8') as f:
                config = json.load(f)
        except:
            config = {}

        # ── Add admin role to overwrites (only if valid) ──
        admin_role_id = config.get("admin_role_id")
        if admin_role_id:
            admin_role = guild.get_role(admin_role_id)
            if admin_role:
                overwrites[admin_role] = discord.PermissionOverwrite(
                    read_messages=True, send_messages=True,
                    manage_channels=True
                )

        # ── Get category ──
        # The configured ID could be a Category or a text channel.
        # If it's a text channel, we use its parent category.
        category = None
        cat_id = config.get("ticket_category_id")
        if cat_id:
            try:
                ch = guild.get_channel(cat_id)
                if not ch:
                    ch = await guild.fetch_channel(cat_id)
            except Exception as fe:
                print(f"[Ticket Error] Failed to fetch channel/category {cat_id}: {fe}")
                ch = None

            if ch:
                if isinstance(ch, discord.CategoryChannel):
                    category = ch
                elif hasattr(ch, 'category') and ch.category:
                    category = ch.category

        try:
            # ── Create ticket channel under the category ──
            ticket_channel = await guild.create_text_channel(
                name=channel_name,
                category=category,
                overwrites=overwrites
            )

            # Track active ticket
            active_tickets[member.id] = ticket_channel.id

            # ── Welcome embed ──
            color = SECTION_COLORS.get(category_value, COLOR_PRIMARY)
            label = SECTION_LABELS.get(category_value, category_value.title())

            embed = discord.Embed(
                title=f"Ticket #{counter:04d} · {label}",
                description=(
                    f"Welcome, {member.mention}.\n\n"
                    "Please describe your request and a staff member will "
                    "be with you shortly.\n\n"
                    "**A few notes before you start:**\n"
                    "· Be clear and specific about your issue\n"
                    "· Share any relevant details or screenshots\n"
                    "· Please be patient while we review your ticket"
                ),
                color=color
            )
            embed.set_footer(text="ARF Support · Use the buttons below to manage this ticket")
            embed.timestamp = datetime.utcnow()

            await ticket_channel.send(
                content=f"{member.mention}",
                embed=embed,
                view=TicketControlsView(self.bot)
            )
            await interaction.response.send_message(
                f"Your ticket has been created: {ticket_channel.mention}",
                ephemeral=True
            )

            # ── Empty ticket protection (background task) ──
            asyncio.create_task(self._check_empty_ticket(guild, ticket_channel, member))

        except Exception as e:
            import traceback
            print(f"[Ticket Error] Detailed traceback:")
            traceback.print_exc()
            try:
                await interaction.response.send_message(
                    f"An error occurred while creating the ticket: {e}",
                    ephemeral=True
                )
            except:
                pass

    async def _check_empty_ticket(self, guild, ticket_channel, member):
        """Background task to auto-close empty tickets."""
        await asyncio.sleep(180)  # 3 minutes

        # Check if user sent any message
        try:
            ch = guild.get_channel(ticket_channel.id)
            if not ch:
                return

            has_message = False
            async for msg in ch.history(limit=10):
                if msg.author.id == member.id and not msg.author.bot:
                    has_message = True
                    break

            if has_message:
                return

            warning_embed = discord.Embed(
                title="Reminder",
                description=(
                    f"{member.mention}, we haven't heard from you yet.\n\n"
                    "Please describe your issue, or this ticket will be "
                    "closed automatically in **2 minutes**."
                ),
                color=COLOR_WARNING
            )
            warning_embed.set_footer(text="ARF Support System")
            await ch.send(embed=warning_embed)
        except:
            return

        # Wait 2 more minutes
        await asyncio.sleep(120)

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

            close_embed = discord.Embed(
                title="Ticket Closed",
                description=(
                    "This ticket was closed automatically due to inactivity.\n"
                    "Feel free to open a new one whenever you need assistance."
                ),
                color=COLOR_CLOSE
            )
            close_embed.set_footer(text="ARF Support System")
            await ch.send(embed=close_embed)
            if member.id in active_tickets:
                del active_tickets[member.id]
            await asyncio.sleep(5)
            await ch.delete()
        except:
            pass


class TicketPanelView(discord.ui.View):
    def __init__(self, bot):
        super().__init__(timeout=None)
        self.add_item(TicketSelect(bot))


class Tickets(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="setup_ticket", description="Setup the ticket system panel")
    @app_commands.default_permissions(administrator=True)
    async def setup_ticket(self, interaction: discord.Interaction):
        # Respond first to avoid interaction timeout
        await interaction.response.send_message("Ticket system has been set up successfully.", ephemeral=True)

        # ── Rules Embed ──
        rules_embed = discord.Embed(
            title="Ticket Guidelines",
            description=(
                "Please read the following before opening a ticket:\n\n"
                "**1.** Don't open a ticket without a clear reason\n"
                "**2.** Avoid opening a ticket by mistake\n"
                "**3.** Please keep to a single open ticket at a time\n"
                "**4.** Describe your issue clearly when you open a ticket\n"
                "**5.** Be patient while waiting for a response\n"
                "**6.** Empty tickets are closed automatically after 5 minutes"
            ),
            color=COLOR_PRIMARY
        )
        rules_embed.set_footer(text="ARF Support · Please follow these guidelines")

        # ── Panel Embed ──
        panel_embed = discord.Embed(
            title="Support Center",
            description=(
                "Need help? Select a category below to open a ticket.\n\n"
                "**Purchase** — Buy services or tools\n"
                "**Inquiry** — General questions\n"
                "**Support** — Technical issues\n"
                "**Other** — Anything else"
            ),
            color=COLOR_PRIMARY
        )
        panel_embed.set_footer(text="ARF Support Services")
        panel_embed.timestamp = datetime.utcnow()

        await interaction.channel.send(embed=rules_embed)
        await interaction.channel.send(embed=panel_embed, view=TicketPanelView(self.bot))


async def setup(bot):
    await bot.add_cog(Tickets(bot))
    bot.add_view(TicketPanelView(bot))
    bot.add_view(TicketControlsView(bot))
