import discord
from discord.ext import commands
import re
from datetime import datetime
import json
import asyncio

# Import your existing database manager
from Db_scraper import DiscordDatabaseManager  # Update with your actual filename

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

# Global database manager instance
db_manager = None

# ==========================================
# DATA CLEANING FUNCTIONS (TEXT + DATE ONLY)
# ==========================================

def clean_message_content(message):
    """
    Clean Discord message to get ONLY pure text
    Removes: mentions, emojis, URLs, markdown, etc.
    """
    if not message.content:
        return ""
    
    text = message.content
    
    # Remove Discord user mentions (<@123456789>)
    text = re.sub(r'<@!?\d+>', '', text)
    
    # Remove role mentions (<@&123456789>)
    text = re.sub(r'<@&\d+>', '', text)
    
    # Remove channel mentions (<#123456789>)
    text = re.sub(r'<#\d+>', '', text)
    
    # Remove custom Discord emojis (<:emoji_name:123456789>)
    text = re.sub(r'<a?:\w+:\d+>', '', text)
    
    # Remove standard emojis (Unicode)
    emoji_pattern = re.compile(
        "["
        u"\U0001F600-\U0001F64F"  # emoticons
        u"\U0001F300-\U0001F5FF"  # symbols & pictographs
        u"\U0001F680-\U0001F6FF"  # transport & map symbols
        u"\U0001F1E0-\U0001F1FF"  # flags
        u"\U00002702-\U000027B0"
        u"\U000024C2-\U0001F251"
        u"\U0001F900-\U0001F9FF"
        u"\U0001FA00-\U0001FA6F"
        "]+", flags=re.UNICODE
    )
    text = emoji_pattern.sub('', text)
    
    # Remove URLs
    text = re.sub(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+', '', text)
    
    # Remove code blocks
    text = re.sub(r'```[\s\S]*?```', '', text)
    text = re.sub(r'`[^`]+`', '', text)
    
    # Remove markdown formatting
    text = re.sub(r'\*\*([^*]+)\*\*', r'\1', text)  # Bold
    text = re.sub(r'__([^_]+)__', r'\1', text)      # Underline
    text = re.sub(r'\*([^*]+)\*', r'\1', text)      # Italic
    text = re.sub(r'_([^_]+)_', r'\1', text)        # Italic
    text = re.sub(r'~~([^~]+)~~', r'\1', text)      # Strikethrough
    text = re.sub(r'\|\|([^|]+)\|\|', r'\1', text)  # Spoiler
    
    # Remove quote markers
    text = re.sub(r'^>\s*', '', text, flags=re.MULTILINE)
    
    # Remove zero-width characters
    text = re.sub(r'[\u200b-\u200d\ufeff\u2060\u180e]', '', text)
    
    # Clean up whitespace
    text = re.sub(r' +', ' ', text)
    text = re.sub(r'\n+', '\n', text)
    text = text.strip()
    
    return text

def format_date(timestamp):
    """
    Convert Discord timestamp to your database format
    Returns: "YYYY-MM-DD HH:MM:SS"
    """
    if not timestamp:
        return None
    return timestamp.strftime("%Y-%m-%d %H:%M:%S")

def validate_cleaned_message(text, timestamp):
    """Check if message is valid after cleaning"""
    if not text or len(text.strip()) == 0:
        return False
    if not timestamp:
        return False
    return True

# ==========================================
# SINGLE MESSAGE PROCESSING
# ==========================================

def process_and_store_message(message, db):
    """
    Clean message and store using YOUR database manager
    
    Args:
        message: Discord message object
        db: Your DiscordDatabaseManager instance
    """
    # Clean the text
    cleaned_text = clean_message_content(message)
    
    # Format the date
    formatted_date = format_date(message.created_at)
    
    # Validate
    if not validate_cleaned_message(cleaned_text, formatted_date):
        print(f"⚠️ Skipping message {message.id} (empty after cleaning)")
        return False
    
    # Store using YOUR database manager method
    success = db.add_announcement(
        message_id=str(message.id),
        content=cleaned_text,
        posted_date=formatted_date
    )
    
    if success:
        print(f"✅ Stored: '{cleaned_text[:50]}...' | {formatted_date}")
        return True
    else:
        print(f"❌ Failed to store message {message.id}")
        return False

# ==========================================
# BATCH PROCESSING (EFFICIENT FOR LARGE DATASETS)
# ==========================================

def batch_process_messages(messages, db):
    """
    Process multiple messages at once - MORE EFFICIENT
    
    How it works:
    1. Collect and clean ALL messages first (in memory)
    2. Insert them ALL at once into database
    3. Much faster than one-by-one
    
    Args:
        messages: List of Discord message objects
        db: Your DiscordDatabaseManager instance
    
    Returns:
        (inserted_count, skipped_count)
    """
    print(f"🔄 Starting batch processing of {len(messages)} messages...")
    
    # STEP 1: Clean all messages and collect valid ones
    batch_data = []
    skipped = 0
    
    for message in messages:
        # Clean each message
        cleaned_text = clean_message_content(message)
        formatted_date = format_date(message.created_at)
        
        # Skip if invalid
        if not validate_cleaned_message(cleaned_text, formatted_date):
            skipped += 1
            continue
        
        # Add to batch (not inserting yet - just collecting!)
        batch_data.append({
            'message_id': str(message.id),
            'content': cleaned_text,
            'date': formatted_date
        })
    
    # STEP 2: Insert ALL valid messages at once
    inserted = 0
    for data in batch_data:
        success = db.add_announcement(
            message_id=data['message_id'],
            content=data['content'],
            posted_date=data['date']
        )
        if success:
            inserted += 1
    
    print(f"✅ Batch complete: {inserted} inserted, {skipped} skipped")
    return inserted, skipped

# ==========================================
# BOT SETUP AND COMMANDS
# ==========================================

@bot.event
async def on_ready():
    """Initialize bot and database when ready"""
    global db_manager
    
    print(f'🤖 {bot.user} is connected!')
    
    # Initialize YOUR database manager
    db_manager = DiscordDatabaseManager(
        db_name='discord_data.db',           # Your database file name
        db_channel_name='scraped_messages'   # Your channel name
    )
    
    print("✅ Database manager initialized!")

@bot.event
async def on_message(message):
    """
    Store every new message in real-time (one-by-one)
    Good for: Live messages as they arrive
    """
    if message.author == bot.user:
        await bot.process_commands(message)
        return
    
    # Process single message immediately
    process_and_store_message(message, db_manager)
    
    await bot.process_commands(message)

@bot.command(name='scrape')
async def scrape_messages(ctx, limit: int = 100):
    """
    Scrape messages from current channel using BATCH PROCESSING
    
    Usage: !scrape 500
    
    Why batch? Much faster for large amounts!
    - One-by-one: ~30 seconds for 500 messages
    - Batch: ~2 seconds for 500 messages
    """
    await ctx.send(f"🔍 Scraping {limit} messages (batch mode)...")
    
    # STEP 1: Collect ALL messages first (don't process yet)
    messages = []
    async for msg in ctx.channel.history(limit=limit):
        messages.append(msg)
    
    # STEP 2: Process ALL at once (batch processing)
    inserted, skipped = batch_process_messages(messages, db_manager)
    
    await ctx.send(
        f"✅ **Batch scraping complete!**\n"
        f"📝 Inserted: {inserted}\n"
        f"⏭️ Skipped (empty): {skipped}"
    )

@bot.command(name='scrape_slow')
async def scrape_one_by_one(ctx, limit: int = 100):
    """
    Scrape messages ONE-BY-ONE (slower but uses less memory)
    
    Usage: !scrape_slow 100
    
    Use this when:
    - Memory is limited
    - You want to see progress in real-time
    - Small amounts of data
    """
    await ctx.send(f"🔍 Scraping {limit} messages (one-by-one mode)...")
    
    inserted = 0
    skipped = 0
    
    # Process each message immediately as we get it
    async for message in ctx.channel.history(limit=limit):
        success = process_and_store_message(message, db_manager)
        if success:
            inserted += 1
        else:
            skipped += 1
        
        # Show progress every 50 messages
        if (inserted + skipped) % 50 == 0:
            await ctx.send(f"Progress: {inserted + skipped}/{limit}...")
    
    await ctx.send(
        f"✅ **One-by-one scraping complete!**\n"
        f"📝 Inserted: {inserted}\n"
        f"⏭️ Skipped: {skipped}"
    )

@bot.command(name='scrape_all')
@commands.has_permissions(administrator=True)
async def scrape_all_channels(ctx, limit_per_channel: int = 500):
    """
    Scrape all text channels in the server
    
    Usage: !scrape_all 1000
    """
    await ctx.send("🔍 Starting server-wide scrape...")
    
    total_inserted = 0
    total_skipped = 0
    
    for channel in ctx.guild.text_channels:
        try:
            # Collect messages from this channel
            messages = []
            async for msg in channel.history(limit=limit_per_channel):
                messages.append(msg)
            
            # Batch process
            inserted, skipped = batch_process_messages(messages, db_manager)
            total_inserted += inserted
            total_skipped += skipped
            
            await ctx.send(f"✅ #{channel.name}: {inserted} messages")
            
            # Small delay to avoid rate limits
            await asyncio.sleep(1)
            
        except discord.Forbidden:
            await ctx.send(f"⚠️ No access to #{channel.name}")
        except Exception as e:
            await ctx.send(f"❌ Error in #{channel.name}: {str(e)}")
    
    await ctx.send(
        f"🎉 **Server scrape complete!**\n"
        f"📝 Total inserted: {total_inserted}\n"
        f"⏭️ Total skipped: {total_skipped}"
    )

@bot.command(name='view')
async def view_messages(ctx, limit: int = 5):
    """
    View recent messages from YOUR database
    
    Usage: !view 10
    """
    # Use YOUR database manager method
    results = db_manager.get_recent_announcements(limit=limit)
    
    if results:
        embed = discord.Embed(
            title=f"📋 Latest {len(results)} Messages",
            color=discord.Color.blue()
        )
        
        for row in results:
            text = row['data_announcement']
            date = row['data_date']
            preview = text[:150] + "..." if len(text) > 150 else text
            embed.add_field(
                name=date,
                value=preview,
                inline=False
            )
        
        await ctx.send(embed=embed)
    else:
        await ctx.send("No messages in database yet!")

@bot.command(name='stats')
async def show_stats(ctx):
    """
    Show database statistics using YOUR database manager
    
    Usage: !stats
    """
    # Use YOUR database manager method
    total = db_manager.get_announcement_count()
    
    embed = discord.Embed(title="📊 Database Statistics", color=discord.Color.gold())
    embed.add_field(name="Total Messages", value=total, inline=True)
    
    # Get recent messages for more stats
    recent = db_manager.get_recent_announcements(limit=100)
    if recent:
        avg_length = sum(len(r['data_announcement']) for r in recent) / len(recent)
        embed.add_field(name="Avg Text Length (last 100)", value=f"{avg_length:.0f} chars", inline=True)
    
    await ctx.send(embed=embed)

@bot.command(name='compare')
async def compare_before_after(ctx):
    """
    Show comparison of raw vs cleaned message
    
    Usage: !compare
    """
    # Get last message before this command
    messages = [msg async for msg in ctx.channel.history(limit=2)]
    if len(messages) < 2:
        await ctx.send("Not enough messages to compare!")
        return
    
    raw_msg = messages[1]
    cleaned = clean_message_content(raw_msg)
    
    embed = discord.Embed(title="🔍 Before & After Cleaning", color=discord.Color.green())
    
    embed.add_field(
        name="❌ BEFORE (Raw)",
        value=f"```{raw_msg.content[:500] if raw_msg.content else '*empty*'}```",
        inline=False
    )
    
    embed.add_field(
        name="✅ AFTER (Cleaned)",
        value=f"```{cleaned[:500] if cleaned else '*empty after cleaning*'}```",
        inline=False
    )
    
    embed.add_field(
        name="📅 Date",
        value=format_date(raw_msg.created_at),
        inline=False
    )
    
    await ctx.send(embed=embed)

@bot.command(name='export')
async def export_data(ctx, limit: int = 1000):
    """
    Export data from YOUR database to JSON
    
    Usage: !export 500
    """
    results = db_manager.get_recent_announcements(limit=limit)
    
    if not results:
        await ctx.send("No data to export!")
        return
    
    # Convert to JSON format
    data = []
    for row in results:
        data.append({
            'id': row['data_id'],
            'text': row['data_announcement'],
            'date': row['data_date']
        })
    
    filename = f'discord_export_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
    
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    
    await ctx.send(f"✅ Exported {len(data)} messages to {filename}")
    await ctx.send(file=discord.File(filename))

@bot.event
async def on_disconnect():
    """Clean up database connection when bot stops"""
    if db_manager:
        db_manager.close()

if __name__ == "__main__":
    TOKEN = 'YOUR_BOT_TOKEN_HERE'
    
    try:
        bot.run(TOKEN)
    finally:
        # Ensure database is closed on shutdown
        if db_manager:
            db_manager.close()
