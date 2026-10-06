import discord
from discord.ext import commands
from discord import app_commands
import os

ASSETS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets")
TICKET_IMAGE = os.path.join(ASSETS_DIR, "ticket.png")


class Spes(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="spes", description="إرسال صورة التذكرة")
    @app_commands.describe(option="اختيار")
    @app_commands.choices(option=[
        app_commands.Choice(name="spes ticket", value="ticket"),
    ])
    async def spes(self, interaction: discord.Interaction, option: str):
        if not os.path.exists(TICKET_IMAGE):
            await interaction.response.send_message("الصورة غير موجودة.", ephemeral=True)
            return

        file = discord.File(TICKET_IMAGE, filename="ticket.png")
        await interaction.response.send_message(file=file)


async def setup(bot):
    await bot.add_cog(Spes(bot))
