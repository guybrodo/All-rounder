import discord
from discord.ext import commands

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix=':', intents=intents)

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}!")

@bot.command()
async def ping(ctx):
    await ctx.send("Pong! 🏓")

bot.run("MTUyMzk4MTMyNjQ4NTU1MzE3Mg.GD7J60.Luo-UChF7Ez9oEOyct3TlpyaAGlgqMQKW3LNzQ")
