import asyncio
import os
import discord
from dotenv import load_dotenv

load_dotenv("../DiscordBot/.env.bot.facebook")
token = os.getenv("DISCORD_TOKEN")
channel_id = int(os.getenv("DISCORD_CHANNEL_ID", "0"))

print(f"Token: {token[:15]}...")
print(f"Channel ID: {channel_id}")

client = discord.Client(intents=discord.Intents.default())

@client.event
async def on_ready():
    print(f"✅ Logged in as {client.user}")
    channel = client.get_channel(channel_id)
    if not channel:
        try:
            channel = await client.fetch_channel(channel_id)
        except Exception as e:
            print(f"❌ Failed to fetch channel: {e}")
            channel = None
            
    if channel:
        print(f"✅ Found channel: {channel.name} (Guild: {channel.guild.name})")
        try:
            await channel.send("🧪 Test connection from B2B Matching Agent!")
            print("✅ Test message sent successfully!")
        except Exception as e:
            print(f"❌ Failed to send message: {e}")
    else:
        print("❌ Channel not found!")
    await client.close()

if __name__ == "__main__":
    asyncio.run(client.start(token))
