import discord
import os
from discord.ext import commands

def main():

    intents = discord.Intents.default()

    client = commands.Bot(command_prefix = "!", intents = intents)

    @client.event
    async def on_ready():
        print("Bot Loaded")

    client.load_extension("leaderboard")

    key = os.getenv("DISCORD_KEY")
    if(key):
        client.run(key)
    else:
        print("Error: DISCORD_KEY environment variable not found")


if __name__ == "__main__":
    main()  