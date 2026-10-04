import discord
from discord.ext import commands
import json
import os
import sys
import shutil
import threading
import asyncio
import urllib.parse
import hmac
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import datetime

# ===== PyInstaller bootstrap: extract bundled resources next to the exe =====
if getattr(sys, 'frozen', False):
    try:
        _meipass = sys._MEIPASS
        _data_dir = os.path.join(os.path.dirname(os.path.abspath(sys.executable)), "bot_data")
        os.makedirs(_data_dir, exist_ok=True)
        for _name in ("cogs", "assets"):
            _src = os.path.join(_meipass, _name)
            _dst = os.path.join(_data_dir, _name)
            if os.path.exists(_src):
                if os.path.exists(_dst):
                    shutil.rmtree(_dst)
                shutil.copytree(_src, _dst)
        _cfg_src = os.path.join(_meipass, "config.json")
        _cfg_dst = os.path.join(_data_dir, "config.json")
        if os.path.exists(_cfg_src):
            shutil.copy2(_cfg_src, _cfg_dst)
        os.chdir(_data_dir)
        print(f"[+] Running as exe, using data folder: {_data_dir}")
    except Exception as e:
        print(f"[!] PyInstaller bootstrap error: {e}")

# Read settings from config.json
def load_config():
    try:
        with open('config.json', 'r', encoding='utf-8') as f:
            config = json.load(f)
    except Exception as e:
        print(f"Error loading config.json: {e}")
        return {}

    config['token'] = os.getenv('BOT_TOKEN', config.get('token', ''))
    config['client_secret'] = os.getenv('CLIENT_SECRET', config.get('client_secret', ''))
    config['api_secret'] = os.getenv('DISCORD_API_SECRET', config.get('api_secret', ''))

    if os.getenv('RAILWAY_PUBLIC_URL'):
        config['public_url'] = os.getenv('RAILWAY_PUBLIC_URL')

    return config

config = load_config()

# ================================================
# ===== Activation: swap waiting role -> member =====

async def activate_member(bot, guild_id, user_id):
    """Add the member role and remove the waiting/unverified roles."""
    try:
        guild = bot.get_guild(guild_id)
        if not guild:
            try:
                guild = await bot.fetch_guild(guild_id)
            except Exception as e:
                print(f"[Activation] Error fetching guild: {e}")

        if not guild:
            return False, "guild_not_found"

        member = guild.get_member(user_id)
        if not member:
            try:
                member = await guild.fetch_member(user_id)
            except discord.NotFound:
                return False, "user_not_in_guild"
            except Exception as e:
                print(f"[Activation] Error fetching member: {e}")

        member_role = guild.get_role(config.get("member_role_id"))
        waiting_role = guild.get_role(config.get("waiting_role_id"))
        unverified_role = guild.get_role(config.get("unverified_role_id"))

        if not member_role:
            return False, "member_role_not_found"

        await member.add_roles(member_role, reason="Account activated via website")

        if waiting_role and waiting_role in member.roles:
            await member.remove_roles(waiting_role, reason="Account activated via website")
        if unverified_role and unverified_role in member.roles:
            await member.remove_roles(unverified_role, reason="Account activated via website")

        # Send activation notification to the log channel
        log_channel_id = config.get("mod_action_log_channel_id")
        if not log_channel_id:
            log_channel_id = 1495348639327846470
        log_channel = guild.get_channel(log_channel_id)
        if not log_channel:
            try:
                log_channel = await guild.fetch_channel(log_channel_id)
            except Exception as e:
                print(f"[Activation] Failed to fetch log channel: {e}")
        if log_channel:
            embed = discord.Embed(
                title="✅ تم تفعيل حساب جديد",
                description=f"قام **{member.mention}** بتفعيل حسابه بنجاح",
                color=0x2ECC71,
                timestamp=datetime.now(),
            )
            embed.add_field(name="العضو", value=f"{member} (ID: {user_id})", inline=False)
            embed.add_field(name="الحساب", value=f"<@{user_id}>", inline=False)
            if member.display_avatar:
                embed.set_thumbnail(url=member.display_avatar.url)
            embed.set_footer(text="ARF Verification System")
            try:
                await log_channel.send(embed=embed)
                print(f"[Activation] Notification sent for {member}")
            except Exception as e:
                print(f"[Activation] Failed to send notification: {e}")

        print(f"[Activation] {member} (ID: {user_id}) activated in guild {guild_id}")
        return True, None
    except Exception as e:
        print(f"[Activation] Role assignment error: {e}")
        return False, "internal_error"

# ================================================

# ===== Web server: health check + /api/activate =====
class KeepAliveHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        body = json.dumps({"ok": True, "service": "erfanshop-bot"}).encode('utf-8')
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)

        if parsed.path != '/api/activate':
            self.send_json(404, {"ok": False, "error": "not_found"})
            return

        try:
            length = int(self.headers.get('Content-Length', 0) or 0)
            raw = self.rfile.read(length) if length > 0 else b''
            payload = json.loads(raw.decode('utf-8')) if raw else {}
        except Exception:
            self.send_json(400, {"ok": False, "error": "bad_json"})
            return

        secret = str(payload.get('secret', ''))
        user_id = str(payload.get('user_id', ''))
        expected = str(config.get('api_secret', ''))

        if not expected or not hmac.compare_digest(secret, expected):
            self.send_json(403, {"ok": False, "error": "bad_secret"})
            return

        if not user_id or not user_id.isdigit():
            self.send_json(400, {"ok": False, "error": "bad_user_id"})
            return

        try:
            guild_id = int(config.get('guild_id'))
        except (TypeError, ValueError):
            self.send_json(500, {"ok": False, "error": "guild_id_missing"})
            return

        future = asyncio.run_coroutine_threadsafe(
            activate_member(bot, guild_id, int(user_id)),
            bot.loop
        )
        try:
            success, error = future.result(timeout=15)
        except Exception as e:
            print(f"[Activation] Async error: {e}")
            self.send_json(500, {"ok": False, "error": "internal_error"})
            return

        if success:
            self.send_json(200, {"ok": True})
        else:
            self.send_json(400, {"ok": False, "error": error})

    def send_json(self, status, data):
        body = json.dumps(data).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        pass  # Suppress default HTTP logs

def run_keep_alive():
    port = int(os.environ.get('PORT', 10000))
    server = HTTPServer(('0.0.0.0', port), KeepAliveHandler)
    print(f"Keep-alive & activation server running on port {port}")
    server.serve_forever()

def start_keep_alive():
    thread = threading.Thread(target=run_keep_alive, daemon=True)
    thread.start()
# ========================================

# Global command permission check
def is_admin():
    async def predicate(interaction: discord.Interaction) -> bool:
        config = load_config()
        admin_role_id = config.get("admin_role_id")
        if interaction.user.guild_permissions.administrator:
            return True
        if admin_role_id:
            admin_role = interaction.guild.get_role(admin_role_id)
            if admin_role and admin_role in interaction.user.roles:
                return True
        await interaction.response.send_message(
            "❌ ليس لديك صلاحية استخدام أوامر البوت.", ephemeral=True
        )
        return False
    return predicate

class MRXBot(commands.Bot):
    def __init__(self):
        # Enable all Intents
        intents = discord.Intents.all()
        super().__init__(
            command_prefix=config.get('prefix', '!'),
            intents=intents,
            help_command=None # Optional: disable default help
        )

    async def setup_hook(self):
        # Load all Cogs
        for filename in os.listdir('./cogs'):
            if filename.endswith('.py'):
                try:
                    await self.load_extension(f'cogs.{filename[:-3]}')
                    print(f"Loaded extension: {filename}")
                except Exception as e:
                    print(f"Failed to load extension {filename}: {e}")
        
        # Sync Slash Commands
        await self.tree.sync()
        print("Slash commands synced successfully!")

bot = MRXBot()

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user} (ID: {bot.user.id})')
    print('------')
    await bot.change_presence(activity=discord.Game(name="ARF_"))

if __name__ == '__main__':
    token = os.getenv('BOT_TOKEN') or config.get('token')
    if not token or token == "YOUR_BOT_TOKEN_HERE":
        print("Please set the BOT_TOKEN environment variable in Railway or configure config.json")
        import time; time.sleep(999999)
    else:
        while True:
            try:
                start_keep_alive()  # Start HTTP server for Railway health check and activation
                bot.run(token)
            except Exception as e:
                print(f"Error starting the bot: {e}")
                import time; time.sleep(5)
