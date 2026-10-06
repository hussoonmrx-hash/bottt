import discord
from discord.ext import commands
from discord import app_commands
import asyncio

class Broadcast(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="broadcast", description="إرسال رسالة جماعية عبر الرسائل الخاصة (للجميع أو لرتبة محددة)")
    @app_commands.describe(
        message="نص الرسالة المراد إرسالها",
        role="اختر رتبة معينة للإرسال لأعضائها فقط (اتركه فارغاً للإرسال للجميع)"
    )
    @app_commands.default_permissions(administrator=True)
    async def broadcast(self, interaction: discord.Interaction, message: str, role: discord.Role = None):
        print(f"Broadcast command triggered by {interaction.user}")
        target_name = role.name if role else "جميع الأعضاء"
        await interaction.response.send_message(f"بدأت عملية الإرسال لـ **{target_name}**. قد تستغرق هذه العملية بعض الوقت...", ephemeral=True)
        
        count = 0
        failed = 0
        
        members = role.members if role else interaction.guild.members
        print(f"Total members found: {len(members)}")
        for member in members:
            if member.bot:
                continue
            
            try:
                embed = discord.Embed(
                    title=f"رسالة إدارية من سيرفر: {interaction.guild.name}",
                    description=message,
                    color=0x2b2d31
                )
                if interaction.guild.icon:
                    embed.set_thumbnail(url=interaction.guild.icon.url)
                
                await member.send(embed=embed)
                count += 1
                await asyncio.sleep(1)  # لتفادي حظر البوت مؤقتاً من ديسكورد (Rate Limit)
            except Exception as e:
                failed += 1
                
        await interaction.followup.send(
            f"اكتملت عملية الإرسال بنجاح.\n\n"
            f"عدد الرسائل المرسلة: {count}\n"
            f"عدد الرسائل الفاشلة: {failed} (غالباً بسبب إغلاق العضو للرسائل الخاصة)", 
            ephemeral=True
        )

    @app_commands.command(name="broadcast_test", description="تجربة نظام الإرسال الجماعي (تصل إليك فقط)")
    @app_commands.describe(message="نص الرسالة التجريبية")
    @app_commands.default_permissions(administrator=True)
    async def broadcast_test(self, interaction: discord.Interaction, message: str):
        print(f"Broadcast Test triggered by {interaction.user}")
        await interaction.response.defer(ephemeral=True)
        try:
            embed = discord.Embed(
                title=f"معاينة الإرسال الجماعي | Test Broadcast",
                description=message,
                color=0x2b2d31
            )
            if interaction.guild.icon:
                embed.set_thumbnail(url=interaction.guild.icon.url)
                
            await interaction.user.send(embed=embed)
            await interaction.followup.send("تم إرسال رسالة المعاينة إلى حسابك الخاص بنجاح.")
        except Exception as e:
            print(f"Broadcast Test Error: {e}")
            await interaction.followup.send(f"تعذر إرسال الرسالة. يرجى التأكد من تفعيل خيار استقبال الرسائل الخاصة في إعدادات حسابك.\nالخطأ: {e}")

    # --- نسخة الأوامر العادية (Prefix Commands) ---
    
    @commands.command(name="bc_test")
    @commands.has_permissions(administrator=True)
    async def bc_test_prefix(self, ctx, *, message: str):
        print(f"bc_test prefix command triggered by {ctx.author}")
        try:
            embed = discord.Embed(
                title=f"معاينة الإرسال الجماعي | Test Broadcast",
                description=message,
                color=0x2b2d31
            )
            if ctx.guild.icon:
                embed.set_thumbnail(url=ctx.guild.icon.url)
            
            await ctx.author.send(embed=embed)
            print("DM sent successfully")
            await ctx.send("تم إرسال رسالة المعاينة إلى حسابك الخاص بنجاح.")
        except discord.Forbidden:
            print("DM blocked - user has DMs closed")
            await ctx.send("تعذر إرسال الرسالة: يرجى التأكد من فتح الرسائل الخاصة في إعدادات الخصوصية للسيرفر.")
        except Exception as e:
            print(f"bc_test error: {e}")
            await ctx.send(f"حدث خطأ غير متوقع: {e}")

    @commands.command(name="bc_all")
    @commands.has_permissions(administrator=True)
    async def bc_all_prefix(self, ctx, *, message: str):
        msg = await ctx.send("بدأت عملية الإرسال الجماعي...")
        count = 0
        failed = 0
        for member in ctx.guild.members:
            if member.bot: 
                continue
            try:
                embed = discord.Embed(
                    title=f"رسالة إدارية من سيرفر: {ctx.guild.name}",
                    description=message,
                    color=0x2b2d31
                )
                if ctx.guild.icon:
                    embed.set_thumbnail(url=ctx.guild.icon.url)
                    
                await member.send(embed=embed)
                count += 1
                await asyncio.sleep(0.5)
            except:
                failed += 1
        await msg.edit(content=f"اكتملت عملية الإرسال بنجاح.\nعدد الرسائل المرسلة: {count}\nعدد الرسائل الفاشلة: {failed}")

async def setup(bot):
    await bot.add_cog(Broadcast(bot))
