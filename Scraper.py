# Import standard libraries
import os          # for reading environment variables (like token, channel ID)
import json        # to save messages in JSON format
import asyncio     # to handle async functions (Discord API uses async)
from dotenv import load_dotenv  # to load .env file securely (so token isn’t hardcoded)
import discord     # main Discord API library

# Load environment variables from .env file
load_dotenv()

# Read the bot token and channel ID from environment variables
TOKEN = os.getenv("DISCORD_TOKEN")          # your bot token
CHANNEL_ID = int(os.getenv("CHANNEL_ID"))   # channel to scrape (must be int)

# Define the “intents” — permissions for what the bot can access
intents = discord.Intents.default()         # start with default permissions
intents.message_content = True              # allow bot to read message text (critical for scraping)

# Create a Discord client instance (the bot connection)
client = discord.Client(intents=intents)

# -------------------------------
# Define a function to export all messages from a given channel
# -------------------------------
async def export_channel(channel_id, outpath="discord_messages.jsonl", limit=None):
    # Fetch the channel object using its ID
    channel = await client.fetch_channel(channel_id)
    print(f"Exporting messages from: {channel.name}")

    # Open a new file to save exported messages (JSON Lines format)
    with open(outpath, "w", encoding="utf-8") as f:
        # Loop through all messages in the channel (oldest first)
        # limit=None means "fetch all messages"
        async for msg in channel.history(limit=limit, oldest_first=True):
            # Create a dictionary (JSON record) for each message
            record = {
                "id": msg.id,                                 # unique message ID
                "timestamp": msg.created_at.isoformat(),       # time message was created
                "author": str(msg.author),                     # who sent it (username#discriminator)
                "content": msg.content,                        # message text
                "attachments": [a.url for a in msg.attachments], # any attached files (links)
                "reactions": [str(r) for r in msg.reactions]     # list of reactions (emoji, etc.)
            }
            # Write the message record to the file (one JSON object per line)
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    # Print confirmation message when done
    print(f"✅ Done. Saved to {outpath}")

# -------------------------------
# Define what happens when the bot successfully connects (“on_ready” event)
# -------------------------------
@client.event
async def on_ready():
    print(f"Logged in as {client.user}")        # show bot name in console
    await export_channel(CHANNEL_ID)            # run the export function for your chosen channel
    await client.close()                        # close the bot connection after export finishes

# -------------------------------
# Start the bot (login and connect to Discord)
# -------------------------------
client.run(TOKEN)
