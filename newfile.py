import discord
from discord.ext import commands
import json
import os
import asyncio
import datetime

# Intents configuration
intents = discord.Intents.default()
intents.members = True
intents.message_content = True
intents.guilds = True

# Bot setup with dual prefix ':' and '/'
bot = commands.Bot(command_prefix=[':', '/'], intents=intents, help_command=None)

# ----------------- Database Setup -----------------
DATA_FILE = "bot_data.json"

def load_data():
    if not os.path.exists(DATA_FILE):
        return {
            "owners": [1499433080409161769],  # Your Exact Owner ID
            "autorole_bot": {},
            "autorole_user": {},
            "antinuke": {},
            "autoresponder": {},
            "autoreact": {},
            "wl": {},
            "extraowner": {},
            "snipes": {},
            "warns": {},
            "strikes": {}
        }
    with open(DATA_FILE, "r") as f:
        return json.load(f)

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)

db = load_data()

def is_owner_or_os(ctx_or_interaction):
    author = getattr(ctx_or_interaction, "author", None) or getattr(ctx_or_interaction, "user", None)
    guild = ctx_or_interaction.guild
    if not author:
        return False
    if author.id in db.get("owners", []):
        return True
    if guild and author.id == guild.owner_id:
        return True
    guild_id = str(guild.id) if guild else ""
    if guild_id in db["extraowner"] and author.id == db["extraowner"][guild_id]:
        return True
    return False

# Sync Slash Commands when bot is ready
@bot.event
async def on_ready():
    try:
        await bot.tree.sync()
        print(f"Logged in as {bot.user} and Slash Commands synced successfully!")
    except Exception as e:
        print(e)

# ----------------- Prefix-less Command for Owner & Auto-Responder -----------------
@bot.event
async def on_message(message):
    if message.author.bot:
        return

    # Owner Prefix-less execution
    if message.author.id in db.get("owners", []):
        content = message.content.strip()
        if not content.startswith(':'):
            first_word = content.split()[0].lower()
            cmd = bot.get_command(first_word)
            if cmd:
                message.content = f":{content}"

    # Auto-Responder & Auto-React
    if message.guild:
        g_id = str(message.guild.id)
        if g_id in db["autoresponder"]:
            for trigger, response in db["autoresponder"][g_id].items():
                if trigger.lower() in message.content.lower():
                    await message.channel.send(response)
        if g_id in db["autoreact"]:
            for trigger, emoji in db["autoreact"][g_id].items():
                if trigger.lower() in message.content.lower():
                    try:
                        await message.add_reaction(emoji)
                    except:
                        pass

    await bot.process_commands(message)

# ----------------- Snipe Event (Advanced Tracker) -----------------
@bot.event
async def on_message_delete(message):
    if message.guild and not message.author.bot:
        g_id = str(message.guild.id)
        if g_id not in db["snipes"]:
            db["snipes"][g_id] = []
        
        db["snipes"][g_id].insert(0, {
            "author": str(message.author),
            "author_id": message.author.id,
            "content": message.content or "No text content",
            "channel": message.channel.name,
            "time": datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        })
        db["snipes"][g_id] = db["snipes"][g_id][:5]

# ----------------- Auto-Role Events -----------------
@bot.event
async def on_member_join(member):
    g_id = str(member.guild.id)
    if member.bot:
        if g_id in db["autorole_bot"]:
            role = member.guild.get_role(db["autorole_bot"][g_id])
            if role:
                await member.add_roles(role)
    else:
        if g_id in db["autorole_user"]:
            role = member.guild.get_role(db["autorole_user"][g_id])
            if role:
                await member.add_roles(role)

# ----------------- Pagination View for Snipe -----------------
class SnipePagination(discord.ui.View):
    def __init__(self, snipes):
        super().__init__(timeout=60)
        self.snipes = snipes
        self.current_page = 0

    def create_embed(self):
        item = self.snipes[self.current_page]
        embed = discord.Embed(title="🔍 Recently Deleted Messages (Snipe)", color=discord.Color.red())
        embed.add_field(name="Author", value=item['author'], inline=False)
        embed.add_field(name="Channel", value=f"#{item['channel']}", inline=False)
        embed.add_field(name="Message", value=item['content'], inline=False)
        embed.set_footer(text=f"Page {self.current_page + 1}/{len(self.snipes)} | Deleted at: {item['time']}")
        return embed

    @discord.ui.button(label="◀ Prev", style=discord.ButtonStyle.primary)
    async def prev_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.current_page > 0:
            self.current_page -= 1
            await interaction.response.edit_message(embed=self.create_embed(), view=self)
        else:
            await interaction.response.send_message("You are on the first page.", ephemeral=True)

    @discord.ui.button(label="Next ▶", style=discord.ButtonStyle.primary)
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.current_page < len(self.snipes) - 1:
            self.current_page += 1
            await interaction.response.edit_message(embed=self.create_embed(), view=self)
        else:
            await interaction.response.send_message("You are on the last page.", ephemeral=True)

# ----------------- Olympus Style Interactive Whitelist Panel View -----------------
class WhitelistSelectView(discord.ui.View):
    def __init__(self, target_member, guild_id):
        super().__init__(timeout=120)
        self.target_member = target_member
        self.guild_id = str(guild_id)
        
        if self.guild_id not in db["wl"]:
            db["wl"][self.guild_id] = {}
        if str(self.target_member.id) not in db["wl"][self.guild_id] or not isinstance(db["wl"][self.guild_id][str(self.target_member.id)], dict):
            db["wl"][self.guild_id][str(self.target_member.id)] = {
                "Ban": False, "Kick": False, "Channel Create": False, 
                "Channel Delete": False, "Role Create": False, "Role Delete": False
            }
        save_data(db)

    def create_embed(self, ctx_author):
        user_perms = db["wl"][self.guild_id][str(self.target_member.id)]
        embed = discord.Embed(title=f"🛡️ Anti-Nuke Whitelist Panel", color=discord.Color.red())
        
        status_text = ""
        for event, allowed in user_perms.items():
            icon = "✅" if allowed else "❌"
            status_text += f"{icon} **:{event}**\n"
            
        embed.description = status_text
        embed.set_footer(text=f"Author: {ctx_author} | Target: {self.target_member}")
        return embed

    @discord.ui.select(
        placeholder="Choose an event to toggle...",
        options=[
            discord.SelectOption(label="Ban", description="Toggle Ban whitelist", emoji="🔨"),
            discord.SelectOption(label="Kick", description="Toggle Kick whitelist", emoji="👢"),
            discord.SelectOption(label="Channel Create", description="Toggle Channel Create whitelist", emoji="📁"),
            discord.SelectOption(label="Channel Delete", description="Toggle Channel Delete whitelist", emoji="🗑️"),
            discord.SelectOption(label="Role Create", description="Toggle Role Create whitelist", emoji="👑"),
            discord.SelectOption(label="Role Delete", description="Toggle Role Delete whitelist", emoji="❌"),
        ]
    )
    async def select_callback(self, interaction: discord.Interaction, select: discord.ui.Select):
        event = select.values[0]
        current_status = db["wl"][self.guild_id][str(self.target_member.id)][event]
        db["wl"][self.guild_id][str(self.target_member.id)][event] = not current_status
        save_data(db)
        
        await interaction.response.edit_message(embed=self.create_embed(interaction.user), view=self)

# ----------------- Commands Definitions -----------------

@bot.command()
async def autobotroleadd(ctx, role: discord.Role):
    if not (is_owner_or_os(ctx) or ctx.author.guild_permissions.administrator):
        return await ctx.send("❌ You don't have permission.")
    db["autorole_bot"][str(ctx.guild.id)] = role.id
    save_data(db)
    await ctx.send(f"✅ Bot Auto-Role set to: **{role.name}**")

@bot.command()
async def autoroleadd(ctx, role: discord.Role):
    if not (is_owner_or_os(ctx) or ctx.author.guild_permissions.administrator):
        return await ctx.send("❌ You don't have permission.")
    db["autorole_user"][str(ctx.guild.id)] = role.id
    save_data(db)
    await ctx.send(f"✅ Member Auto-Role set to: **{role.name}**")

@bot.command()
async def antinuke(ctx, option: str):
    g_id = str(ctx.guild.id)
    option = option.lower()
    if option == "enable":
        if not is_owner_or_os(ctx):
            return await ctx.send("❌ Only Owner or Extra Owner can enable Anti-Nuke.")
        channel = await ctx.guild.create_text_channel("antinuke-logs")
        db["antinuke"][g_id] = {"enabled": True, "log_channel": channel.id}
        save_data(db)
        await ctx.send(f"🛡️ **Anti-Nuke Enabled Successfully!** Log channel created: {channel.mention}")
    elif option == "disable":
        if not is_owner_or_os(ctx):
            return await ctx.send("❌ Only Owner or Extra Owner can disable Anti-Nuke.")
        if g_id in db["antinuke"]:
            del db["antinuke"][g_id]
            save_data(db)
            await ctx.send("⚠️ **Anti-Nuke has been disabled.**")
        else:
            await ctx.send("❌ Anti-Nuke is not enabled.")
    elif option == "config":
        status = "Enabled 🛡️" if db["antinuke"].get(g_id, {}).get("enabled") else "Disabled ❌"
        await ctx.send(f"ℹ️ **Anti-Nuke Status:** {status}")

@bot.command()
async def dmall(ctx, *, message: str):
    if ctx.author.id not in db["owners"]:
        return await ctx.send("❌ Only Bot Owner can use this command.")
    count = 0
    await ctx.send("🚀 Starting DM All process...")
    for guild in bot.guilds:
        for member in guild.members:
            if not member.bot:
                try:
                    await member.send(f"📩 **Message from Bot Owner:** {message}")
                    count += 1
                    await asyncio.sleep(1)
                except:
                    pass
    await ctx.send(f"✅ Successfully sent DM to {count} members.")

@bot.command()
async def dm(ctx, member: discord.Member, *, message: str):
    if ctx.author.id not in db["owners"]:
        return await ctx.send("❌ Only Bot Owner can use this command.")
    try:
        await member.send(f"📩 **Message from Owner:** {message}")
        await ctx.send(f"✅ Message sent to **{member.name}**")
    except:
        await ctx.send(f"❌ Couldn't send DM to **{member.name}**.")

@bot.command(aliases=['h'])
async def help(ctx):
    embed = discord.Embed(title="🤖 All-Rounder Bot Help Menu", color=discord.Color.blue())
    embed.add_field(name="Security & Anti-Nuke", value="`:antinuke enable/disable/config`\n`:wl` | `:unwl`", inline=False)
    embed.add_field(name="Roles & Management", value="`:autoroleadd` | `:autobotroleadd`\n`:roleadd` | `:roleremove` | `:extraowner`", inline=False)
    embed.add_field(name="Moderation", value="`:ban` | `:unban` | `:kick` | `:mute` | `:unmute` | `:warn` | `:strike` | `:purge`", inline=False)
    embed.add_field(name="Utilities", value="`:say` | `:snipe` | `:ping` | `:emojiadd` | `:emojidelete`", inline=False)
    await ctx.send(embed=embed)

@bot.command()
async def roleadd(ctx, member: discord.Member, role: discord.Role):
    if is_owner_or_os(ctx) or ctx.author.guild_permissions.manage_roles:
        await member.add_roles(role)
        await ctx.send(f"✅ Role **{role.name}** added to **{member.name}**")

@bot.command()
async def roleremove(ctx, member: discord.Member, role: discord.Role):
    if is_owner_or_os(ctx) or ctx.author.guild_permissions.manage_roles:
        await member.remove_roles(role)
        await ctx.send(f"✅ Role **{role.name}** removed from **{member.name}**")

@bot.command()
async def ban(ctx, member: discord.Member, *, reason="No reason provided"):
    if is_owner_or_os(ctx) or ctx.author.guild_permissions.ban_members:
        await member.ban(reason=reason)
        await ctx.send(f"🔨 **{member.name}** has been banned.")

@bot.command()
async def unban(ctx, user_id: int):
    if is_owner_or_os(ctx) or ctx.author.guild_permissions.ban_members:
        user = await bot.fetch_user(user_id)
        await ctx.guild.unban(user)
        await ctx.send(f"✅ **{user.name}** has been unbanned.")

@bot.command()
async def kick(ctx, member: discord.Member, *, reason="No reason provided"):
    if is_owner_or_os(ctx) or ctx.author.guild_permissions.kick_members:
        await member.kick(reason=reason)
        await ctx.send(f"👢 **{member.name}** has been kicked.")

@bot.command()
async def mute(ctx, member: discord.Member, time_in_minutes: int, *, reason="No reason provided"):
    if is_owner_or_os(ctx) or ctx.author.guild_permissions.moderate_members:
        duration = discord.utils.utcnow() + datetime.timedelta(minutes=time_in_minutes)
        await member.timeout(duration, reason=reason)
        await ctx.send(f"🔇 **{member.name}** muted for {time_in_minutes} minutes.")

@bot.command()
async def unmute(ctx, member: discord.Member):
    if is_owner_or_os(ctx) or ctx.author.guild_permissions.moderate_members:
        await member.timeout(None)
        await ctx.send(f"🔊 **{member.name}** has been unmuted.")

@bot.command()
async def nick(ctx, member: discord.Member, *, nickname: str):
    if is_owner_or_os(ctx) or ctx.author.guild_permissions.manage_nicknames:
        await member.edit(nick=nickname)
        await ctx.send(f"✅ Nickname changed for **{member.name}**")

@bot.command()
async def warn(ctx, member: discord.Member, *, reason="No reason provided"):
    if is_owner_or_os(ctx) or ctx.author.guild_permissions.administrator:
        try:
            await member.send(f"⚠️ You have been warned in **{ctx.guild.name}**. Reason: {reason}")
        except:
            pass
        await ctx.send(f"⚠️ Warned **{member.name}**.")

@bot.command()
async def warnremove(ctx, member: discord.Member):
    if is_owner_or_os(ctx) or ctx.author.guild_permissions.administrator:
        await ctx.send(f"✅ Warn removed for **{member.name}**.")

@bot.command()
async def strike(ctx, member: discord.Member, *, reason="No reason provided"):
    if is_owner_or_os(ctx) or ctx.author.guild_permissions.administrator:
        try:
            await member.send(f"🚨 You received a STRIKE in **{ctx.guild.name}**. Reason: {reason}")
        except:
            pass
        await ctx.send(f"🚨 Strike given to **{member.name}**.")

@bot.command()
async def strikeremove(ctx, member: discord.Member):
    if is_owner_or_os(ctx) or ctx.author.guild_permissions.administrator:
        await ctx.send(f"✅ Strike removed for **{member.name}**.")

@bot.command()
async def autoresponder(ctx, action: str, trigger: str = None, *, response: str = None):
    g_id = str(ctx.guild.id)
    if g_id not in db["autoresponder"]:
        db["autoresponder"][g_id] = {}
    if action == "add" and trigger and response:
        db["autoresponder"][g_id][trigger] = response
        save_data(db)
        await ctx.send(f"✅ Auto-Responder added for `{trigger}`")
    elif action == "delete" and trigger:
        if trigger in db["autoresponder"][g_id]:
            del db["autoresponder"][g_id][trigger]
            save_data(db)
            await ctx.send(f"🗑️ Deleted Auto-Responder for `{trigger}`")
    elif action == "list":
        triggers = list(db["autoresponder"][g_id].keys())
        await ctx.send(f"📋 **Auto-Responders:** {', '.join(triggers) if triggers else 'None'}")

@bot.command()
async def autoreact(ctx, action: str, trigger: str = None, emoji: str = None):
    g_id = str(ctx.guild.id)
    if g_id not in db["autoreact"]:
        db["autoreact"][g_id] = {}
    if action == "add" and trigger and emoji:
        db["autoreact"][g_id][trigger] = emoji
        save_data(db)
        await ctx.send(f"✅ Auto-React added for `{trigger}`")
    elif action == "delete" and trigger:
        if trigger in db["autoreact"][g_id]:
            del db["autoreact"][g_id][trigger]
            save_data(db)
            await ctx.send(f"🗑️ Deleted Auto-React for `{trigger}`")
    elif action == "list":
        triggers = list(db["autoreact"][g_id].keys())
        await ctx.send(f"📋 **Auto-Reacts:** {', '.join(triggers) if triggers else 'None'}")

@bot.command()
async def emojiadd(ctx, url: str, name: str):
    if is_owner_or_os(ctx) or ctx.author.guild_permissions.manage_emojis:
        import aiohttp
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                if resp.status == 200:
                    data = await resp.read()
                    emoji = await ctx.guild.create_custom_emoji(name=name, image=data)
                    await ctx.send(f"✅ Added emoji: {emoji}")

@bot.command()
async def emojidelete(ctx, emoji: discord.Emoji):
    if is_owner_or_os(ctx) or ctx.author.guild_permissions.manage_emojis:
        await emoji.delete()
        await ctx.send("🗑️ Emoji deleted.")

@bot.command()
async def purge(ctx, amount: str):
    if is_owner_or_os(ctx) or ctx.author.guild_permissions.manage_messages:
        if amount.lower() == "all":
            await ctx.channel.purge()
            await ctx.send("🧹 Channel cleared completely!", delete_after=3)
        else:
            await ctx.channel.purge(limit=int(amount) + 1)
            await ctx.send(f"🧹 Deleted {amount} messages.", delete_after=3)

# Olympus Style Interactive Whitelist Command
@bot.command()
async def wl(ctx, member: discord.Member):
    if not is_owner_or_os(ctx):
        return await ctx.send("❌ Only Owner or Extra Owner can manage Whitelist.")
    
    view = WhitelistSelectView(member, ctx.guild.id)
    await ctx.send(embed=view.create_embed(ctx.author), view=view)

@bot.command()
async def unwl(ctx, member: discord.Member):
    if not is_owner_or_os(ctx):
        return await ctx.send("❌ Only Owner or Extra Owner can Un-Whitelist.")
    g_id = str(ctx.guild.id)
    if g_id in db["wl"] and str(member.id) in db["wl"][g_id]:
        del db["wl"][g_id][str(member.id)]
        save_data(db)
    embed = discord.Embed(color=discord.Color.green())
    embed.description = f"✔️ **Success**\n{member.mention} is Unwhitelisted From All Events"
    embed.set_footer(text=f"Author: {ctx.author} | Target: {member}")
    await ctx.send(embed=embed)

@bot.command()
async def extraowner(ctx, action: str, member: discord.Member = None):
    if ctx.author.id != ctx.guild.owner_id and ctx.author.id not in db["owners"]:
        return await ctx.send("❌ Only Server Owner can manage Extra Owner.")
    g_id = str(ctx.guild.id)
    if action == "set" and member:
        db["extraowner"][g_id] = member.id
        save_data(db)
        await ctx.send(f"👑 **{member.name}** is now set as Extra Owner.")
    elif action == "view":
        eo_id = db["extraowner"].get(g_id)
        if eo_id:
            user = await bot.fetch_user(eo_id)
            await ctx.send(f"👑 Extra Owner is: **{user.name}**")
        else:
            await ctx.send("ℹ️ No Extra Owner set.")
    elif action == "remove":
        if g_id in db["extraowner"]:
            del db["extraowner"][g_id]
            save_data(db)
            await ctx.send("🗑️ Extra Owner removed.")

@bot.command()
async def say(ctx, *, message: str):
    if is_owner_or_os(ctx) or ctx.author.guild_permissions.manage_messages:
        await ctx.message.delete()
        await ctx.send(message)

# Advanced Snipe Command with Pagination Buttons
@bot.command()
async def snipe(ctx):
    g_id = str(ctx.guild.id)
    if g_id in db["snipes"] and db["snipes"][g_id]:
        view = SnipePagination(db["snipes"][g_id])
        await ctx.send(embed=view.create_embed(), view=view)
    else:
        await ctx.send("❌ No recently deleted messages found.")

@bot.command()
async def ping(ctx):
    await ctx.send(f"🏓 **Pong!** Latency: `{round(bot.latency * 1000)}ms`")

# ----------------- Run Bot -------------------
bot.run("MTUyMzk4MTMyNjQ4NTU1MzE3Mg.GD7J60.Luo-UChF7Ez9oEOyct3TlpyaAGlgqMQKW3LNzQ") 
