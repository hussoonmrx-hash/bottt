import discord
from discord.ext import commands
from discord import app_commands, ui
import json

class PollView(ui.View):
    def __init__(self, options):
        super().__init__(timeout=None)
        self.options = options
        self.votes = {option: 0 for option in options}
        self.voters = []

        for option in options:
            btn = ui.Button(label=option, style=discord.ButtonStyle.secondary, custom_id=f"poll_{option}")
            btn.callback = self.make_callback(option)
            self.add_item(btn)

    def make_callback(self, option):
        async def callback(interaction: discord.Interaction):
            if interaction.user.id in self.voters:
                await interaction.response.send_message("❌ You have already voted!", ephemeral=True)
                return
            
            self.votes[option] += 1
            self.voters.append(interaction.user.id)
            
            embed = interaction.message.embeds[0]
            new_desc = ""
            for opt, count in self.votes.items():
                new_desc += f"**{opt}**: {count} votes\n"
            
            embed.description = new_desc
            await interaction.response.edit_message(embed=embed, view=self)
        return callback

class Utility(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="poll", description="Create a poll with buttons")
    @app_commands.describe(question="The question for the poll", options="Options separated by commas (e.g. Yes, No, Maybe)")
    async def poll(self, interaction: discord.Interaction, question: str, options: str):
        opt_list = [opt.strip() for opt in options.split(',')]
        if len(opt_list) < 2 or len(opt_list) > 5:
            await interaction.response.send_message("❌ Please provide between 2 and 5 options.", ephemeral=True)
            return

        embed = discord.Embed(title=f"📊 {question}", description="", color=0x2b2d31)
        for opt in opt_list:
            embed.description += f"**{opt}**: 0 votes\n"
        
        embed.set_footer(text=f"Poll by {interaction.user.display_name}", icon_url=interaction.user.display_avatar.url)
        
        view = PollView(opt_list)
        await interaction.response.send_message(embed=embed, view=view)

    @app_commands.command(name="clear_channel", description="Delete and recreate the current channel (Wipe all messages)")
    @app_commands.default_permissions(administrator=True)
    async def clear_channel(self, interaction: discord.Interaction):
        await interaction.response.send_message("⚠️ This will delete all messages in this channel. Are you sure? Type 'CONFIRM' in chat to proceed.", ephemeral=True)
        
        def check(m):
            return m.author == interaction.user and m.channel == interaction.channel and m.content == 'CONFIRM'
        
        try:
            await self.bot.wait_for('message', check=check, timeout=30.0)
            new_channel = await interaction.channel.clone(reason="Channel Wipe")
            await interaction.channel.delete(reason="Channel Wipe")
            await new_channel.send("✨ Channel has been cleared!")
        except asyncio.TimeoutError:
            await interaction.followup.send("❌ Clear cancelled or timed out.", ephemeral=True)

async def setup(bot):
    await bot.add_cog(Utility(bot))
