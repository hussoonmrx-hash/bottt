import discord
from discord.ext import commands
import json
import os

class VerifyView(discord.ui.View):
    def __init__(self, verify_url):
        super().__init__(timeout=None)
        self.add_item(discord.ui.Button(
            label="تفعيل الحساب",
            style=discord.ButtonStyle.success,
            url=verify_url,
            emoji="✅"
        ))

class Verify(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def get_config(self):
        try:
            with open('config.json', 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return {}

    @commands.hybrid_command(name="verify", aliases=["setup_verify"], description="إعداد رسالة التفعيل | Setup verification message")
    @commands.has_permissions(administrator=True)
    async def verify(self, ctx: commands.Context):
        config = self.get_config()
        verify_url = config.get("verify_url", "https://erfanshop.amalarab.com/activate")

        embed = discord.Embed(
            title="يا هلا بيك في سيرفر ARF",
            description=(
                "عشان تفتح لك كل الرومات، اضغط على زر **«تفعيل»** إلي تحت.\n\n"
                "منور السيرفر! ❤️"
            ),
            color=0x2B2D31
        )
        embed.set_footer(text="ARF Server Verification")

        banner_path = 'assets/verify_banner.png'
        file = None
        if os.path.exists(banner_path):
            file = discord.File(banner_path, filename="verify_banner.png")
            embed.set_image(url="attachment://verify_banner.png")

        view = VerifyView(verify_url)
        if file:
            await ctx.send(embed=embed, view=view, file=file)
        else:
            await ctx.send(embed=embed, view=view)
        if not ctx.interaction and ctx.message:
            try:
                await ctx.message.delete()
            except:
                pass

async def setup(bot):
    await bot.add_cog(Verify(bot))