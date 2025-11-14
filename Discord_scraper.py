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

# ==========================================
# CONFIGURATION - EDIT THIS SECTION
# ==========================================

# ⚠️ DEVELOPERS: Configure your target channels here
# Add the channel IDs you want to scrape (right-click channel → Copy ID)
TARGET_CHANNEL_IDS = [
    # Add your channel IDs here:
    # 123456789012345678,  # Example: #general
    # 234567890123456789,  # Example: #announcements
    # 345678901234567890,  # Example: #chat
]

# OR use channel names (less reliable if channels are renamed)
TARGET_CHANNEL_NAMES = [
    # Add your channel names here:
    # 'general',
    # 'announcements', 
    # 'chat',
]

# Default date range: 1 year ago to now
# Change these if you want different defaults
DEFAULT_DAYS_BACK = 365  # 1 year

# ==========================================
# END CONFIGURATION
# ==========================================

# Global database manager instance
db_manager = None

# ==========================================
# HELPER FUNCTIONS
# ==========================================

def get_target_channels(guild):
    """
    Get the configured target channels from the server
    Returns list of discord.TextChannel objects
    """
    channels = []
    
    # Get channels by ID (most reliable)
    for channel_id in TARGET_CHANNEL_IDS:
        channel = guild.get_channel(channel_id)
        if channel and isinstance(channel, discord.TextChannel):
            channels.append(channel)
        else:
            print(f"⚠️ Channel ID {channel_id} not found or not a text channel")
    
    # Get channels by name (if IDs list is empty)
    if not channels and TARGET_CHANNEL_NAMES:
        for channel_name in TARGET_CHANNEL_NAMES:
            channel = discord.utils.get(guild.text_channels, name=channel_name)
            if channel:
                channels.append(channel)
            else:
                print(f"⚠️ Channel '{channel_name}' not found")
    
    return channels

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
async def scrape_configured_channels(ctx, start_date: str = None, end_date: str = None):
    """
    🎯 MAIN SCRAPING COMMAND - Scrapes all configured channels with date range
    
    Usage:
        !scrape                              # Scrape configured channels - last 1 year (default)
        !scrape 2025-01-01 2025-01-31       # Scrape configured channels - custom date range
        !scrape 2024-06-01                  # Scrape from June 2024 to now
    
    ⚠️ Channels to scrape are configured in the code by developers
    Default date range: 1 year ago to now
    """
    try:
        from datetime import timedelta
        
        # Get configured channels
        target_channels = get_target_channels(ctx.guild)
        
        if not target_channels:
            await ctx.send(
                "❌ **No channels configured!**\n"
                "Developers need to add channel IDs or names in the code.\n"
                "Check `TARGET_CHANNEL_IDS` or `TARGET_CHANNEL_NAMES` in the configuration section."
            )
            return
        
        # Set date range (default: 1 year ago to now)
        if start_date is None:
            after_date = datetime.now() - timedelta(days=DEFAULT_DAYS_BACK)
            before_date = datetime.now()
            start_date_str = after_date.strftime("%Y-%m-%d")
            end_date_str = before_date.strftime("%Y-%m-%d")
        else:
            after_date = datetime.strptime(start_date, "%Y-%m-%d")
            
            if end_date:
                before_date = datetime.strptime(end_date, "%Y-%m-%d")
                end_date_str = end_date
            else:
                before_date = datetime.now()
                end_date_str = "now"
            
            start_date_str = start_date
        
        # Validate date range
        if after_date > before_date:
            await ctx.send("❌ Start date must be before end date!")
            return
        
        # Display scraping info
        channel_list = ", ".join([f"#{ch.name}" for ch in target_channels])
        
        embed = discord.Embed(
            title="🔍 Starting Configured Channel Scrape",
            color=discord.Color.blue()
        )
        embed.add_field(name="📍 Channels", value=channel_list, inline=False)
        embed.add_field(name="📅 Date Range", value=f"{start_date_str} → {end_date_str}", inline=False)
        embed.add_field(name="📊 Status", value="Processing...", inline=False)
        
        status_message = await ctx.send(embed=embed)
        
        # Scrape all configured channels
        total_inserted = 0
        total_skipped = 0
        results = []
        
        for channel in target_channels:
            try:
                # Collect messages from this channel
                messages = []
                async for msg in channel.history(after=after_date, before=before_date, limit=None):
                    messages.append(msg)
                
                if messages:
                    # Batch process
                    inserted, skipped = batch_process_messages(messages, db_manager)
                    total_inserted += inserted
                    total_skipped += skipped
                    
                    results.append(f"✅ #{channel.name}: {inserted} messages")
                else:
                    results.append(f"⚠️ #{channel.name}: No messages in date range")
                
                # Small delay to avoid rate limits
                await asyncio.sleep(1)
                
            except discord.Forbidden:
                results.append(f"❌ #{channel.name}: No access")
            except Exception as e:
                results.append(f"❌ #{channel.name}: {str(e)}")
        
        # Update final status
        final_embed = discord.Embed(
            title="✅ Scraping Complete!",
            color=discord.Color.green()
        )
        final_embed.add_field(name="📍 Channels", value=channel_list, inline=False)
        final_embed.add_field(name="📅 Date Range", value=f"{start_date_str} → {end_date_str}", inline=False)
        final_embed.add_field(name="📝 Total Inserted", value=total_inserted, inline=True)
        final_embed.add_field(name="⏭️ Total Skipped", value=total_skipped, inline=True)
        final_embed.add_field(name="📊 Results", value="\n".join(results[:10]), inline=False)  # Show first 10
        
        await status_message.edit(embed=final_embed)
        
        # Send detailed results if many channels
        if len(results) > 10:
            await ctx.send("**Remaining Results:**\n" + "\n".join(results[10:]))
        
    except ValueError:
        await ctx.send("❌ Invalid date format! Use: YYYY-MM-DD (example: 2025-01-15)")
    except Exception as e:
        await ctx.send(f"❌ Error: {str(e)}")

@bot.command(name='config')
async def show_config(ctx):
    """
    Show current bot configuration (channels and date settings)
    
    Usage: !config
    """
    target_channels = get_target_channels(ctx.guild)
    
    embed = discord.Embed(
        title="⚙️ Bot Configuration",
        description="Current scraping settings",
        color=discord.Color.purple()
    )
    
    # Show configured channels
    if target_channels:
        channel_list = "\n".join([f"• #{ch.name} (ID: {ch.id})" for ch in target_channels])
        embed.add_field(name="📍 Configured Channels", value=channel_list, inline=False)
    else:
        embed.add_field(
            name="📍 Configured Channels", 
            value="❌ No channels configured!\nDevelopers need to set `TARGET_CHANNEL_IDS` or `TARGET_CHANNEL_NAMES`",
            inline=False
        )
    
    # Show date settings
    embed.add_field(
        name="📅 Default Date Range",
        value=f"Last {DEFAULT_DAYS_BACK} days ({DEFAULT_DAYS_BACK // 365} year{'s' if DEFAULT_DAYS_BACK > 365 else ''})",
        inline=False
    )
    
    # Show what would be scraped with default
    from datetime import timedelta
    default_start = datetime.now() - timedelta(days=DEFAULT_DAYS_BACK)
    embed.add_field(
        name="📆 Current Default Dates",
        value=f"From: {default_start.strftime('%Y-%m-%d')}\nTo: {datetime.now().strftime('%Y-%m-%d')}",
        inline=False
    )
    
    # Show command
    embed.add_field(
        name="🎯 Main Command",
        value="`!scrape` - Scrapes configured channels with default date range\n`!scrape 2025-01-01 2025-01-31` - Custom dates",
        inline=False
    )
    
    embed.set_footer(text="💡 Use !scrape_help for all commands")
    
    await ctx.send(embed=embed)

@bot.command(name='scrape_date')
async def scrape_date_range(ctx, start_date: str = None, end_date: str = None, limit: int = None):
    """
    Scrape messages from a DATE RANGE
    
    Usage:
        !scrape_date                              # Last 1 year (default)
        !scrape_date 2025-01-01 2025-01-31        # January 2025
        !scrape_date 2024-12-25                   # From Dec 25 to now
        !scrape_date 2025-01-01 2025-01-31 5000   # With limit
    
    Date format: YYYY-MM-DD
    Default: 1 year ago to now
    """
    try:
        from datetime import timedelta
        
        # Default: 1 year ago to now
        if start_date is None:
            after_date = datetime.now() - timedelta(days=365)
            before_date = datetime.now()
            start_date = after_date.strftime("%Y-%m-%d")
            end_date = before_date.strftime("%Y-%m-%d")
        else:
            # Parse start date
            after_date = datetime.strptime(start_date, "%Y-%m-%d")
            
            # Parse end date (or use now)
            if end_date:
                before_date = datetime.strptime(end_date, "%Y-%m-%d")
            else:
                before_date = datetime.now()
        
        # Validate date range
        if after_date > before_date:
            await ctx.send("❌ Start date must be before end date!")
            return
        
        await ctx.send(
            f"🔍 Scraping messages from **{start_date}** to **{end_date or 'now'}**...\n"
            f"Channel: {ctx.channel.mention}"
        )
        
        # Collect messages in date range
        messages = []
        async for msg in ctx.channel.history(after=after_date, before=before_date, limit=limit):
            messages.append(msg)
        
        if not messages:
            await ctx.send("No messages found in this date range!")
            return
        
        inserted, skipped = batch_process_messages(messages, db_manager)
        
        await ctx.send(
            f"✅ **Date range scraping complete!**\n"
            f"📅 Range: {start_date} to {end_date or 'now'}\n"
            f"📝 Inserted: {inserted}\n"
            f"⏭️ Skipped (empty): {skipped}"
        )
        
    except ValueError:
        await ctx.send("❌ Invalid date format! Use: YYYY-MM-DD (example: 2025-01-15)")
    except Exception as e:
        await ctx.send(f"❌ Error: {str(e)}")

@bot.command(name='scrape_channel_date')
async def scrape_channel_with_date(ctx, channel: discord.TextChannel, start_date: str = None, end_date: str = None, limit: int = None):
    """
    Scrape SPECIFIC CHANNEL with DATE RANGE
    
    Usage:
        !scrape_channel_date #general                      # Last 1 year (default)
        !scrape_channel_date #general 2025-01-01 2025-01-31
        !scrape_channel_date #announcements 2024-12-01
        !scrape_channel_date #chat 2025-01-01 2025-01-15 1000
    
    Default: 1 year ago to now
    Combines channel selection + date filtering
    """
    try:
        from datetime import timedelta
        
        # Default: 1 year ago to now
        if start_date is None:
            after_date = datetime.now() - timedelta(days=365)
            before_date = datetime.now()
            start_date = after_date.strftime("%Y-%m-%d")
            end_date = before_date.strftime("%Y-%m-%d")
        else:
            # Parse dates
            after_date = datetime.strptime(start_date, "%Y-%m-%d")
            
            if end_date:
                before_date = datetime.strptime(end_date, "%Y-%m-%d")
            else:
                before_date = datetime.now()
        
        if after_date > before_date:
            await ctx.send("❌ Start date must be before end date!")
            return
        
        await ctx.send(
            f"🔍 Scraping {channel.mention}\n"
            f"📅 From: **{start_date}** to **{end_date or 'now'}**..."
        )
        
        # Collect messages
        messages = []
        async for msg in channel.history(after=after_date, before=before_date, limit=limit):
            messages.append(msg)
        
        if not messages:
            await ctx.send(f"No messages found in {channel.mention} for this date range!")
            return
        
        inserted, skipped = batch_process_messages(messages, db_manager)
        
        await ctx.send(
            f"✅ **Scraping complete!**\n"
            f"📍 Channel: {channel.name}\n"
            f"📅 Range: {start_date} to {end_date or 'now'}\n"
            f"📝 Inserted: {inserted}\n"
            f"⏭️ Skipped (empty): {skipped}"
        )
        
    except discord.Forbidden:
        await ctx.send(f"❌ I don't have permission to read {channel.mention}")
    except ValueError:
        await ctx.send("❌ Invalid date format! Use: YYYY-MM-DD")
    except Exception as e:
        await ctx.send(f"❌ Error: {str(e)}")

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

@bot.command(name='scrape_all_date')
@commands.has_permissions(administrator=True)
async def scrape_all_channels_date(ctx, start_date: str = None, end_date: str = None):
    """
    Scrape ALL channels in server with DATE RANGE
    
    Usage:
        !scrape_all_date                          # Last 1 year (default)
        !scrape_all_date 2025-01-01 2025-01-31
        !scrape_all_date 2024-12-01
    
    Default: 1 year ago to now
    This will scrape every channel the bot can access
    """
    try:
        from datetime import timedelta
        
        # Default: 1 year ago to now
        if start_date is None:
            after_date = datetime.now() - timedelta(days=365)
            before_date = datetime.now()
            start_date = after_date.strftime("%Y-%m-%d")
            end_date = before_date.strftime("%Y-%m-%d")
        else:
            # Parse dates
            after_date = datetime.strptime(start_date, "%Y-%m-%d")
            
            if end_date:
                before_date = datetime.strptime(end_date, "%Y-%m-%d")
            else:
                before_date = datetime.now()
        
        if after_date > before_date:
            await ctx.send("❌ Start date must be before end date!")
            return
        
        await ctx.send(
            f"🔍 Starting server-wide scrape\n"
            f"📅 Date range: **{start_date}** to **{end_date or 'now'}**..."
        )
        
        total_inserted = 0
        total_skipped = 0
        channels_scraped = 0
        
        for channel in ctx.guild.text_channels:
            try:
                messages = []
                async for msg in channel.history(after=after_date, before=before_date, limit=None):
                    messages.append(msg)
                
                if messages:
                    inserted, skipped = batch_process_messages(messages, db_manager)
                    total_inserted += inserted
                    total_skipped += skipped
                    channels_scraped += 1
                    
                    await ctx.send(f"✅ #{channel.name}: {inserted} messages")
                
                await asyncio.sleep(1)
                
            except discord.Forbidden:
                await ctx.send(f"⚠️ No access to #{channel.name}")
            except Exception as e:
                await ctx.send(f"❌ Error in #{channel.name}: {str(e)}")
        
        await ctx.send(
            f"🎉 **Server-wide date scrape complete!**\n"
            f"📍 Channels: {channels_scraped}\n"
            f"📅 Range: {start_date} to {end_date or 'now'}\n"
            f"📝 Total inserted: {total_inserted}\n"
            f"⏭️ Total skipped: {total_skipped}"
        )
        
    except ValueError:
        await ctx.send("❌ Invalid date format! Use: YYYY-MM-DD")
    except Exception as e:
        await ctx.send(f"❌ Error: {str(e)}")

@bot.command(name='scrape_channels')
@commands.has_permissions(administrator=True)
async def scrape_multiple_channels(ctx, *channels: discord.TextChannel, limit: int = 500):
    """
    Scrape MULTIPLE specific channels at once
    
    Usage:
        !scrape_channels #general #announcements #chat 1000
        !scrape_channels #general #news
    
    You can mention as many channels as you want
    """
    if not channels:
        await ctx.send("❌ Please mention at least one channel!\nExample: `!scrape_channels #general #chat`")
        return
    
    await ctx.send(f"🔍 Scraping {len(channels)} channels...")
    
    total_inserted = 0
    total_skipped = 0
    
    for channel in channels:
        try:
            messages = []
            async for msg in channel.history(limit=limit):
                messages.append(msg)
            
            inserted, skipped = batch_process_messages(messages, db_manager)
            total_inserted += inserted
            total_skipped += skipped
            
            await ctx.send(f"✅ {channel.mention}: {inserted} messages")
            await asyncio.sleep(1)
            
        except discord.Forbidden:
            await ctx.send(f"⚠️ No access to {channel.mention}")
        except Exception as e:
            await ctx.send(f"❌ Error in {channel.mention}: {str(e)}")
    
    await ctx.send(
        f"🎉 **Multi-channel scrape complete!**\n"
        f"📝 Total inserted: {total_inserted}\n"
        f"⏭️ Total skipped: {total_skipped}"
    )

@bot.command(name='scrape_last_days')
async def scrape_last_days(ctx, days: int, limit: int = None):
    """
    Scrape messages from the LAST X DAYS
    
    Usage:
        !scrape_last_days 7        # Last week
        !scrape_last_days 30       # Last month
        !scrape_last_days 1        # Last 24 hours
    
    Scrapes from current channel
    """
    if days < 1:
        await ctx.send("❌ Days must be at least 1!")
        return
    
    try:
        from datetime import timedelta
        
        after_date = datetime.now() - timedelta(days=days)
        
        await ctx.send(f"🔍 Scraping messages from last **{days} days**...")
        
        messages = []
        async for msg in ctx.channel.history(after=after_date, limit=limit):
            messages.append(msg)
        
        if not messages:
            await ctx.send(f"No messages found in the last {days} days!")
            return
        
        inserted, skipped = batch_process_messages(messages, db_manager)
        
        await ctx.send(
            f"✅ **Scraping complete!**\n"
            f"📅 Last {days} days\n"
            f"📝 Inserted: {inserted}\n"
            f"⏭️ Skipped (empty): {skipped}"
        )
        
    except Exception as e:
        await ctx.send(f"❌ Error: {str(e)}")

@bot.command(name='scrape_help')
async def scrape_help(ctx):
    """
    Show all scraping commands with examples
    """
    embed = discord.Embed(
        title="📚 Scraping Commands Guide",
        description="All available commands for scraping Discord messages",
        color=discord.Color.blue()
    )
    
    embed.add_field(
        name="🎯 Main Command (Configured Channels)",
        value=(
            "`!scrape` - Scrape configured channels (last 1 year)\n"
            "`!scrape 2025-01-01 2025-01-31` - Custom date range\n"
            "`!scrape 2024-06-01` - From specific date to now\n\n"
            "💡 Channels are pre-configured by developers\n"
            "Use `!config` to see which channels will be scraped"
        ),
        inline=False
    )
    
    embed.add_field(
        name="⚙️ Configuration & Info",
        value=(
            "`!config` - Show configured channels and settings\n"
            "`!view 10` - View 10 recent messages from database\n"
            "`!stats` - Database statistics\n"
            "`!compare` - See before/after message cleaning"
        ),
        inline=False
    )
    
    embed.add_field(
        name="📤 Export",
        value=(
            "`!export 1000` - Export data to JSON file"
        ),
        inline=False
    )
    
    embed.add_field(
        name="🔧 Advanced (Optional)",
        value=(
            "`!scrape_date` - Scrape current channel only\n"
            "`!scrape_last_days 7` - Last 7 days from current channel\n"
            "`!scrape_slow 100` - One-by-one mode (debugging)"
        ),
        inline=False
    )
    
    embed.set_footer(text="💡 Date format: YYYY-MM-DD (example: 2025-01-15) | Default: Last 1 year")
    
    await ctx.send(embed=embed)
    
    await ctx.send(embed=embed)

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
