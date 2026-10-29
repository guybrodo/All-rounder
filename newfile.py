import discord
from discord import app_commands
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

# Bot setup with dual prefix ':' and slash support
class MyBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix=[':', '/'], intents=intents, help_command=None)

    async def setup_hook(self):
        await self.tree.sync()
        print("Slash commands synced successfully!")

bot = MyBot()

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

def is_owner_or_os(interaction_or_ctx):
    author = getattr(interaction_or_ctx, "author", None) or getattr(interaction_or_ctx, "user", None)
    guild = interaction_or_ctx.guild
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

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}!")

# ----------------- Prefix-less Command for Owner -----------------
@bot.event
async def on_message(message):
    if message.author.bot:
        return

    if message.author.id in db.get("owners", []):
        content = message.content.strip()
        if not content.startswith(':'):
            first_word = content.split()[0].lower()
            cmd = bot.get_command(first_word)
            if cmd:
                message.content = f":{content}"

    await bot.process_commands(message)

# ----------------- Snipe Event -----------------
@bot.event
async def on_message_delete(message):
    if message.guild and not message.author.bot:
        g_id = str(message.guild.id)
        if g_id not in db["snipes"]:
            db["snipes"][g_id] = []
        
        db["snipes"][g_id].insert(0, {
            "author": str(message.author),
            "content": message.content or "No text content",
            "channel": message.channel.name,
            "time": datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        })
        db["snipes"][g_id] = db["snipes"][g_id][:5]

# ----------------- Snipe Pagination View -----------------
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

# ----------------- Whitelist Select View (Olympus Style) -----------------
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

# ----------------- Hybrid Commands (Works with both : and /) -----------------

@bot.hybrid_command(name="wl", description="Open Olympus style whitelist panel for a member")
@app_commands.describe(member="The member to whitelist")
async def wl(ctx, member: discord.Member):
    if not is_owner_or_os(ctx):
        if ctx.interaction:
            return await ctx.send("❌ Only Owner or Extra Owner can manage Whitelist.", ephemeral=True)
        return await ctx.send("❌ Only Owner or Extra Owner can manage Whitelist.")
    
    view = WhitelistSelectView(member, ctx.guild.id)
    embed = view.create_embed(ctx.author if hasattr(ctx, "author") else ctx.user)
    if ctx.interaction:
        await ctx.send(embed=embed, view=view)
    else:
        await ctx.send(embed=embed, view=view)

@bot.hybrid_command(name="snipe", description="View recently deleted messages with pagination")
async def snipe(ctx):
    g_id = str(ctx.guild.id)
    if g_id in db["snipes"] and db["snipes"][g_id]:
        view = SnipePagination(db["snipes"][g_id])
        if ctx.interaction:
            await ctx.send(embed=view.create_embed(), view=view)
        else:
            await ctx.send(embed=view.create_embed(), view=view)
    else:
        if ctx.interaction:
            await ctx.send("❌ No recently deleted messages found.", ephemeral=True)
        else:
            await ctx.send("❌ No recently deleted messages found.")

@bot.hybrid_command(name="ping", description="Check bot latency")
async def ping(ctx):
    latency = round(bot.latency * 1000)
    if ctx.interaction:
        await ctx.send(f"🏓 **Pong!** Latency: `{latency}ms`")
    else:
        await ctx.send(f"🏓 **Pong!** Latency: `{latency}ms`")

@bot.hybrid_command(name="help", description="Show bot help menu")
async def help(ctx):
    embed = discord.Embed(title="🤖 All-Rounder Bot Help Menu", color=discord.Color.blue())
    embed.add_field(name="Commands Available", value="`/wl` | `/snipe` | `/ping` | `:` commands", inline=False)
    if ctx.interaction:
        await ctx.send(embed=embed)
    else:
        await ctx.send(embed=embed)

# ----------------- Run Bot -----------------
bot.run("MTUyMzk4MTMyNjQ4NTU1MzE3Mg.GD7J60.Luo-UChF7Ez9oEOyct3TlpyaAGlgqMQKW3LNzQ")
