import discord
from discord.ext import commands
from discord import app_commands
import json
import os
import sys
import threading
import asyncio
import urllib.parse
import requests
import hmac
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import datetime

# Read settings from config.json + environment variables
def load_config():
    try:
        with open('config.json', 'r', encoding='utf-8') as f:
            config = json.load(f)
    except Exception as e:
        print(f"Error loading config.json: {e}")
        config = {}

    config['token'] = os.getenv('BOT_TOKEN', config.get('token', ''))
    config['client_secret'] = os.getenv('CLIENT_SECRET', config.get('client_secret', ''))
    config['api_secret'] = os.getenv('DISCORD_API_SECRET', config.get('api_secret', ''))

    if os.getenv('RAILWAY_PUBLIC_URL'):
        base = os.getenv('RAILWAY_PUBLIC_URL')
        config['redirect_uri'] = f"{base}/callback"
        config['verify_url'] = base

    return config

config = load_config()

# ===== HTML Views for Verification System =====

def get_landing_html(oauth_url):
    return f"""<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>تفعيل الحساب | Verification</title>
    <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;800&family=Cairo:wght@400;600;700&display=swap" rel="stylesheet">
    <style>
        * {{
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }}
        body {{
            font-family: 'Cairo', 'Outfit', sans-serif;
            background: linear-gradient(135deg, #0f0c20 0%, #15102a 50%, #060214 100%);
            color: #ffffff;
            height: 100vh;
            display: flex;
            justify-content: center;
            align-items: center;
            overflow: hidden;
        }}
        .container {{
            background: rgba(255, 255, 255, 0.03);
            backdrop-filter: blur(16px);
            -webkit-backdrop-filter: blur(16px);
            border: 1px solid rgba(255, 255, 255, 0.08);
            border-radius: 24px;
            padding: 40px 30px;
            width: 90%;
            max-width: 440px;
            text-align: center;
            box-shadow: 0 20px 50px rgba(0, 0, 0, 0.4);
            animation: fadeIn 0.8s ease-out;
        }}
        @keyframes fadeIn {{
            from {{ opacity: 0; transform: translateY(20px); }}
            to {{ opacity: 1; transform: translateY(0); }}
        }}
        .icon-container {{
            width: 90px;
            height: 90px;
            background: linear-gradient(135deg, #5865F2 0%, #4752c4 100%);
            border-radius: 50%;
            display: flex;
            justify-content: center;
            align-items: center;
            margin: 0 auto 24px auto;
            box-shadow: 0 10px 25px rgba(88, 101, 242, 0.35);
        }}
        .icon-container svg {{
            width: 45px;
            height: 45px;
            fill: #ffffff;
        }}
        h1 {{
            font-size: 26px;
            font-weight: 700;
            margin-bottom: 12px;
            background: linear-gradient(to left, #ffffff, #b9bbbe);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }}
        p {{
            font-size: 15px;
            color: #b9bbbe;
            line-height: 1.6;
            margin-bottom: 30px;
        }}
        .btn {{
            display: inline-block;
            background: linear-gradient(135deg, #5865F2 0%, #404eed 100%);
            color: #ffffff;
            text-decoration: none;
            padding: 14px 28px;
            border-radius: 12px;
            font-weight: 600;
            font-size: 16px;
            transition: all 0.3s ease;
            box-shadow: 0 8px 20px rgba(88, 101, 242, 0.25);
            width: 100%;
        }}
        .btn:hover {{
            transform: translateY(-2px);
            box-shadow: 0 12px 25px rgba(88, 101, 242, 0.4);
            background: linear-gradient(135deg, #6c79f5 0%, #4d5af7 100%);
        }}
        .footer {{
            margin-top: 30px;
            font-size: 12px;
            color: rgba(255, 255, 255, 0.2);
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="icon-container">
            <svg viewBox="0 0 127.14 96.36">
                <path d="M107.7,8.07A105.15,105.15,0,0,0,77.26,0a77.19,77.19,0,0,0-3.3,6.83A96.67,96.67,0,0,0,53.22,6.83,77.19,77.19,0,0,0,49.88,0,105.15,105.15,0,0,0,19.44,8.07C3.66,31.58-1.95,54.65,1,77.53a105.54,105.54,0,0,0,32,16.17,79,79,0,0,0,6.77-11,68.21,68.21,0,0,1-10.68-5.12c.91-.66,1.8-1.34,2.65-2a75.58,75.58,0,0,0,64,0c.85.71,1.74,1.39,2.65,2a67.8,67.8,0,0,1-10.69,5.12,79.8,79.8,0,0,0,6.77,11,105.54,105.54,0,0,0,32-16.17C129.92,50.19,123.63,27.35,107.7,8.07ZM42.45,65.69C36.18,65.69,31,60,31,53S36.18,40.36,42.45,40.36,53.83,46,53.83,53,48.72,65.69,42.45,65.69Zm42.24,0C78.41,65.69,73.24,60,73.24,53S78.41,40.36,84.69,40.36,96.07,46,96.07,53,91,65.69,84.69,65.69Z"/>
            </svg>
        </div>
        <h1>تفعيل الحساب</h1>
        <p>مرحباً بك في سيرفر ARF! اضغط على الزر أدناه لتسجيل الدخول وتفعيل حسابك لتتمكن من الدخول لباقي قنوات السيرفر.</p>
        <a href="{oauth_url}" class="btn">التفعيل بواسطة ديسكورد</a>
        <div class="footer">ARF Verification System</div>
    </div>
</body>
</html>"""

def get_success_html(username):
    return f"""<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>تم التفعيل بنجاح | Success</title>
    <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;800&family=Cairo:wght@400;600;700&display=swap" rel="stylesheet">
    <style>
        * {{
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }}
        body {{
            font-family: 'Cairo', 'Outfit', sans-serif;
            background: linear-gradient(135deg, #081a12 0%, #0c2015 50%, #030a07 100%);
            color: #ffffff;
            height: 100vh;
            display: flex;
            justify-content: center;
            align-items: center;
            overflow: hidden;
        }}
        .container {{
            background: rgba(255, 255, 255, 0.03);
            backdrop-filter: blur(16px);
            -webkit-backdrop-filter: blur(16px);
            border: 1px solid rgba(255, 255, 255, 0.08);
            border-radius: 24px;
            padding: 40px 30px;
            width: 90%;
            max-width: 440px;
            text-align: center;
            box-shadow: 0 20px 50px rgba(0, 0, 0, 0.4);
            animation: fadeIn 0.8s ease-out;
        }}
        @keyframes fadeIn {{
            from {{ opacity: 0; transform: translateY(20px); }}
            to {{ opacity: 1; transform: translateY(0); }}
        }}
        .icon-container {{
            width: 90px;
            height: 90px;
            background: linear-gradient(135deg, #2ecc71 0%, #27ae60 100%);
            border-radius: 50%;
            display: flex;
            justify-content: center;
            align-items: center;
            margin: 0 auto 24px auto;
            box-shadow: 0 10px 25px rgba(46, 204, 113, 0.35);
        }}
        .icon-container svg {{
            width: 45px;
            height: 45px;
            fill: #ffffff;
        }}
        h1 {{
            font-size: 26px;
            font-weight: 700;
            margin-bottom: 12px;
            color: #2ecc71;
        }}
        p {{
            font-size: 15px;
            color: #b9bbbe;
            line-height: 1.6;
            margin-bottom: 20px;
        }}
        .username {{
            font-weight: 700;
            color: #ffffff;
            background: rgba(46, 204, 113, 0.1);
            padding: 4px 12px;
            border-radius: 6px;
            border: 1px solid rgba(46, 204, 113, 0.2);
            display: inline-block;
            margin-bottom: 10px;
        }}
        .footer {{
            margin-top: 30px;
            font-size: 12px;
            color: rgba(255, 255, 255, 0.2);
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="icon-container">
            <svg viewBox="0 0 24 24">
                <path d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z"/>
            </svg>
        </div>
        <h1>تم التفعيل بنجاح!</h1>
        <div class="username">@{username}</div>
        <p>لقد تم تفعيل حسابك وإعطاؤك الصلاحيات في السيرفر. يمكنك الآن إغلاق هذه الصفحة والعودة للدخول والقراءة والتفاعل في ديسكورد!</p>
        <div class="footer">ARF Verification System</div>
    </div>
    <canvas id="confetti" style="position: absolute; top:0; left:0; width:100%; height:100%; pointer-events:none; z-index:-1;"></canvas>
    <script>
        const canvas = document.getElementById('confetti');
        const ctx = canvas.getContext('2d');
        let width = canvas.width = window.innerWidth;
        let height = canvas.height = window.innerHeight;
        
        window.addEventListener('resize', () => {{
            width = canvas.width = window.innerWidth;
            height = canvas.height = window.innerHeight;
        }});

        const colors = ['#2ecc71', '#3498db', '#f1c40f', '#e74c3c', '#9b59b6', '#e67e22'];
        const particles = [];
        
        for (let i = 0; i < 150; i++) {{
            particles.push({{
                x: Math.random() * width,
                y: Math.random() * height - height,
                r: Math.random() * 6 + 4,
                d: Math.random() * height,
                color: colors[Math.floor(Math.random() * colors.length)],
                tilt: Math.random() * 10 - 5,
                tiltAngleIncremental: Math.random() * 0.07 + 0.02,
                tiltAngle: 0
            }});
        }}
        
        function draw() {{
            ctx.clearRect(0, 0, width, height);
            particles.forEach((p, idx) => {{
                p.tiltAngle += p.tiltAngleIncremental;
                p.y += (Math.cos(p.d) + 3 + p.r / 2) / 2;
                p.x += Math.sin(p.tiltAngle);
                p.tilt = Math.sin(p.tiltAngle - idx / 3) * 15;
                
                ctx.beginPath();
                ctx.lineWidth = p.r;
                ctx.strokeStyle = p.color;
                ctx.moveTo(p.x + p.tilt + p.r / 2, p.y);
                ctx.lineTo(p.x + p.tilt, p.y + p.tilt + p.r / 2);
                ctx.stroke();
                
                if (p.y > height) {{
                    particles[idx] = {{
                        x: Math.random() * width,
                        y: -20,
                        r: p.r,
                        d: p.d,
                        color: p.color,
                        tilt: p.tilt,
                        tiltAngleIncremental: p.tiltAngleIncremental,
                        tiltAngle: p.tiltAngle
                    }};
                }}
            }});
            requestAnimationFrame(draw);
        }}
        draw();
    </script>
</body>
</html>"""

def get_error_html(error_message):
    return f"""<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>خطأ في التفعيل | Error</title>
    <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;800&family=Cairo:wght@400;600;700&display=swap" rel="stylesheet">
    <style>
        * {{
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }}
        body {{
            font-family: 'Cairo', 'Outfit', sans-serif;
            background: linear-gradient(135deg, #240a0a 0%, #1a0808 50%, #0d0303 100%);
            color: #ffffff;
            height: 100vh;
            display: flex;
            justify-content: center;
            align-items: center;
            overflow: hidden;
        }}
        .container {{
            background: rgba(255, 255, 255, 0.03);
            backdrop-filter: blur(16px);
            -webkit-backdrop-filter: blur(16px);
            border: 1px solid rgba(255, 255, 255, 0.08);
            border-radius: 24px;
            padding: 40px 30px;
            width: 90%;
            max-width: 440px;
            text-align: center;
            box-shadow: 0 20px 50px rgba(0, 0, 0, 0.4);
            animation: fadeIn 0.8s ease-out;
        }}
        @keyframes fadeIn {{
            from {{ opacity: 0; transform: translateY(20px); }}
            to {{ opacity: 1; transform: translateY(0); }}
        }}
        .icon-container {{
            width: 90px;
            height: 90px;
            background: linear-gradient(135deg, #e74c3c 0%, #c0392b 100%);
            border-radius: 50%;
            display: flex;
            justify-content: center;
            align-items: center;
            margin: 0 auto 24px auto;
            box-shadow: 0 10px 25px rgba(231, 76, 60, 0.35);
        }}
        .icon-container svg {{
            width: 45px;
            height: 45px;
            fill: #ffffff;
        }}
        h1 {{
            font-size: 26px;
            font-weight: 700;
            margin-bottom: 12px;
            color: #e74c3c;
        }}
        p {{
            font-size: 15px;
            color: #b9bbbe;
            line-height: 1.6;
            margin-bottom: 20px;
        }}
        .footer {{
            margin-top: 30px;
            font-size: 12px;
            color: rgba(255, 255, 255, 0.2);
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="icon-container">
            <svg viewBox="0 0 24 24">
                <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1 15h-2v-2h2v2zm0-4h-2V7h2v6z"/>
            </svg>
        </div>
        <h1>فشل تفعيل الحساب</h1>
        <p>{error_message}</p>
        <div class="footer">ARF Verification System</div>
    </div>
</body>
</html>"""

# =======================================

# ====================================================
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

        if not member:
            return False, "user_not_in_guild"

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
    port = int(os.getenv('PORT', 10000))
    server = HTTPServer(('0.0.0.0', port), KeepAliveHandler)
    print(f"Keep-alive & activation server running on port {port}")
    server.serve_forever()

def start_keep_alive():
    thread = threading.Thread(target=run_keep_alive, daemon=True)
    thread.start()

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
    return app_commands.check(predicate)

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
        # Global admin check for all slash commands
        self.tree.add_check(is_admin())

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
    import time
    raw_token = os.getenv('BOT_TOKEN') or config.get('token') or ''
    token = raw_token.strip().strip('"').strip("'")
    if not token or token == "YOUR_BOT_TOKEN_HERE":
        print("Please set the BOT_TOKEN environment variable in Railway or configure config.json")
        time.sleep(999999)
    else:
        print(f"Token loaded: {token[:8]}...{token[-4:]} (length: {len(token)})")
        start_keep_alive()
        try:
            bot.run(token)
        except discord.LoginFailure:
            print("LoginFailure: التوكن غلط او ملغي.")
            time.sleep(999999)
        except discord.PrivilegedIntentsRequired:
            print("PrivilegedIntentsRequired: فعل Intents من Developer Portal.")
            time.sleep(999999)
        except Exception as e:
            print(f"Error starting the bot: {e}")
            raise
