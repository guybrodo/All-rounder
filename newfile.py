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
bot.run("MTUyMzk4MTMyNjQ4NTU1MzE3Mg.Gogl_y.Z-qH1cdYSaIuk0wTLxF4hSCsWBVAz9_u0m38MY")
