import discord
from discord.ext import commands
import csv
import re
from datetime import datetime, timedelta
import asyncio

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

# ==========================================
# CONFIGURATION - EDIT THIS SECTION
# ==========================================

# Configure your target channels here
TARGET_CHANNEL_IDS = [
    # Add your channel IDs here:
    # 123456789012345678,  # Example: #general
    # 234567890123456789,  # Example: #announcements
]

TARGET_CHANNEL_NAMES = [
    # Or use channel names:
    # 'general',
    # 'announcements',
]

# Default date range: 1 year ago to now
DEFAULT_DAYS_BACK = 365

# Output file settings
OUTPUT_FILENAME = 'discord_messages.csv'  # Change this if you want

# ==========================================
# END CONFIGURATION
# ==========================================

def clean_message_content(message):
    """
    Clean Discord message to get ONLY pure text
    Removes: mentions, emojis, URLs, markdown, etc.
    """
    if not message.content:
        return ""
    
    text = message.content
    
    # Remove Discord mentions
    text = re.sub(r'<@!?\d+>', '', text)  # User mentions
    text = re.sub(r'<@&\d+>', '', text)   # Role mentions
    text = re.sub(r'<#\d+>', '', text)    # Channel mentions
    
    # Remove emojis
    text = re.sub(r'<a?:\w+:\d+>', '', text)  # Custom Discord emojis
    
    emoji_pattern = re.compile(
        "["
        u"\U0001F600-\U0001F64F"
        u"\U0001F300-\U0001F5FF"
        u"\U0001F680-\U0001F6FF"
        u"\U0001F1E0-\U0001F1FF"
        u"\U00002702-\U000027B0"
        u"\U000024C2-\U0001F251"
        u"\U0001F900-\U0001F9FF"
        u"\U0001FA00-\U0001FA6F"
        "]+", flags=re.UNICODE
    )
    text = emoji_pattern.sub('', text)
    
    # Remove URLs
    text = re.sub(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+', '', text)
    
    # Remove code blocks and inline code
    text = re.sub(r'```[\s\S]*?```', '', text)
    text = re.sub(r'`[^`]+`', '', text)
    
    # Remove markdown formatting
    text = re.sub(r'\*\*([^*]+)\*\*', r'\1', text)
    text = re.sub(r'__([^_]+)__', r'\1', text)
    text = re.sub(r'\*([^*]+)\*', r'\1', text)
    text = re.sub(r'_([^_]+)_', r'\1', text)
    text = re.sub(r'~~([^~]+)~~', r'\1', text)
    text = re.sub(r'\|\|([^|]+)\|\|', r'\1', text)
    
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
    """Convert Discord timestamp to string"""
    return timestamp.strftime("%Y-%m-%d %H:%M:%S")

def get_target_channels(guild):
    """Get configured target channels"""
    channels = []
    
    for channel_id in TARGET_CHANNEL_IDS:
        channel = guild.get_channel(channel_id)
        if channel and isinstance(channel, discord.TextChannel):
            channels.append(channel)
    
    if not channels and TARGET_CHANNEL_NAMES:
        for channel_name in TARGET_CHANNEL_NAMES:
            channel = discord.utils.get(guild.text_channels, name=channel_name)
            if channel:
                channels.append(channel)
    
    return channels

@bot.event
async def on_ready():
    """
    Bot starts and immediately begins scraping
    No commands needed - automatic on startup
    """
    print(f'🤖 {bot.user} is connected!')
    print(f'📁 Output file: {OUTPUT_FILENAME}')
    
    # Automatically start scraping
    print("\n🚀 Auto-starting scrape process...\n")
    
    try:
        # Get the first guild (server) the bot is in
        guild = bot.guilds[0] if bot.guilds else None
        
        if not guild:
            print("❌ Bot is not in any servers!")
            await bot.close()
            return
        
        # Run the scrape function automatically
        await auto_scrape(guild)
        
    except Exception as e:
        print(f"❌ Error during auto-scrape: {e}")
    finally:
        # Close the bot after scraping is done
        print("\n✅ Scraping complete. Shutting down bot...")
        await bot.close()

async def auto_scrape(guild, start_date=None, end_date=None):
    """
    Automatic scraping function - runs without command
    """
    try:
        # Get configured channels
        target_channels = get_target_channels(guild)
        
        if not target_channels:
            print("❌ No channels configured!")
            print("Add channel IDs or names in the configuration section.")
            return
        
        # Set date range
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
        
        if after_date > before_date:
            print("❌ Start date must be before end date!")
            return
        
        # Display info in terminal only
        channel_list = ", ".join([f"#{ch.name}" for ch in target_channels])
        
        print("\n" + "="*60)
        print("🔍 Starting CSV Export")
        print("="*60)
        print(f"📍 Channels: {channel_list}")
        print(f"📅 Date Range: {start_date_str} → {end_date_str}")
        print(f"📊 Status: Collecting messages...")
        print("="*60 + "\n")
        
        # Collect all messages
        all_data = []
        channel_stats = []
        
        for channel in target_channels:
            try:
                count = 0
                print(f"⏳ Scraping #{channel.name}...")
                
                async for msg in channel.history(after=after_date, before=before_date, limit=None):
                    cleaned_text = clean_message_content(msg)
                    
                    if cleaned_text:  # Only add non-empty messages
                        all_data.append({
                            'channel': channel.name,
                            'text': cleaned_text,
                            'date': format_date(msg.created_at),
                            'message_id': str(msg.id),
                            'author': msg.author.name
                        })
                        count += 1
                
                channel_stats.append(f"✅ #{channel.name}: {count} messages")
                print(f"✅ #{channel.name}: {count} messages collected")
                await asyncio.sleep(1)
                
            except discord.Forbidden:
                channel_stats.append(f"❌ #{channel.name}: No access")
                print(f"❌ #{channel.name}: No access")
            except Exception as e:
                channel_stats.append(f"❌ #{channel.name}: {str(e)}")
                print(f"❌ #{channel.name}: {str(e)}")
        
        # Write to CSV
        if all_data:
            # Generate filename with timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"discord_messages_{timestamp}.csv"
            
            with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
                fieldnames = ['channel', 'text', 'date', 'message_id', 'author']
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                
                writer.writeheader()
                writer.writerows(all_data)
            
            # Display final results in terminal only
            print("\n" + "="*60)
            print("✅ CSV Export Complete!")
            print("="*60)
            print(f"📍 Channels: {channel_list}")
            print(f"📅 Date Range: {start_date_str} → {end_date_str}")
            print(f"📝 Total Messages: {len(all_data)}")
            print(f"📁 File: {filename}")
            print("\n📊 Results:")
            for stat in channel_stats:
                print(f"   {stat}")
            print("="*60 + "\n")
            
        else:
            print("\n❌ No messages found in the specified date range!\n")
        
    except ValueError:
        print("❌ Invalid date format! Use: YYYY-MM-DD")
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        print(f"Error details: {e}")

@bot.command(name='scrape')
async def scrape_to_csv(ctx, start_date: str = None, end_date: str = None):
    """
    🎯 MAIN COMMAND - Scrape configured channels directly to CSV
    
    Usage:
        !scrape                              # Last 1 year (default)
        !scrape 2025-01-01 2025-01-31       # Custom date range
        !scrape 2024-06-01                  # From specific date to now
    
    Creates: discord_messages.csv with all scraped data
    Saves silently without sending messages to Discord
    """
    try:
        # Get configured channels
        target_channels = get_target_channels(ctx.guild)
        
        if not target_channels:
            print("❌ No channels configured!")
            print("Add channel IDs or names in the configuration section.")
            return
        
        # Set date range
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
        
        if after_date > before_date:
            print("❌ Start date must be before end date!")
            return
        
        # Display info in terminal only
        channel_list = ", ".join([f"#{ch.name}" for ch in target_channels])
        
        print("\n" + "="*60)
        print("🔍 Starting CSV Export")
        print("="*60)
        print(f"📍 Channels: {channel_list}")
        print(f"📅 Date Range: {start_date_str} → {end_date_str}")
        print(f"📊 Status: Collecting messages...")
        print("="*60 + "\n")
        
        # Collect all messages
        all_data = []
        channel_stats = []
        
        for channel in target_channels:
            try:
                count = 0
                print(f"⏳ Scraping #{channel.name}...")
                
                async for msg in channel.history(after=after_date, before=before_date, limit=None):
                    cleaned_text = clean_message_content(msg)
                    
                    if cleaned_text:  # Only add non-empty messages
                        all_data.append({
                            'channel': channel.name,
                            'text': cleaned_text,
                            'date': format_date(msg.created_at),
                            'message_id': str(msg.id),
                            'author': msg.author.name
                        })
                        count += 1
                
                channel_stats.append(f"✅ #{channel.name}: {count} messages")
                print(f"✅ #{channel.name}: {count} messages collected")
                await asyncio.sleep(1)
                
            except discord.Forbidden:
                channel_stats.append(f"❌ #{channel.name}: No access")
                print(f"❌ #{channel.name}: No access")
            except Exception as e:
                channel_stats.append(f"❌ #{channel.name}: {str(e)}")
                print(f"❌ #{channel.name}: {str(e)}")
        
        # Write to CSV
        if all_data:
            # Generate filename with timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"discord_messages_{timestamp}.csv"
            
            with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
                fieldnames = ['channel', 'text', 'date', 'message_id', 'author']
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                
                writer.writeheader()
                writer.writerows(all_data)
            
            # Display final results in terminal only
            print("\n" + "="*60)
            print("✅ CSV Export Complete!")
            print("="*60)
            print(f"📍 Channels: {channel_list}")
            print(f"📅 Date Range: {start_date_str} → {end_date_str}")
            print(f"📝 Total Messages: {len(all_data)}")
            print(f"📁 File: {filename}")
            print("\n📊 Results:")
            for stat in channel_stats:
                print(f"   {stat}")
            print("="*60 + "\n")
            
        else:
            print("\n❌ No messages found in the specified date range!\n")
        
    except ValueError:
        print("❌ Invalid date format! Use: YYYY-MM-DD")
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        print(f"Error details: {e}")

@bot.command(name='config')
async def show_config(ctx):
    """Show current configuration"""
    target_channels = get_target_channels(ctx.guild)
    
    print("\n" + "="*60)
    print("⚙️ Bot Configuration")
    print("="*60)
    
    if target_channels:
        print("📍 Configured Channels:")
        for ch in target_channels:
            print(f"   • #{ch.name} (ID: {ch.id})")
    else:
        print("📍 Configured Channels: ❌ None")
    
    print(f"\n📅 Default Date Range: Last {DEFAULT_DAYS_BACK} days")
    
    default_start = datetime.now() - timedelta(days=DEFAULT_DAYS_BACK)
    print(f"📆 Current Default Dates:")
    print(f"   From: {default_start.strftime('%Y-%m-%d')}")
    print(f"   To: {datetime.now().strftime('%Y-%m-%d')}")
    
    print(f"\n📁 Output File: discord_messages_[timestamp].csv")
    print("="*60 + "\n")

@bot.command(name='preview')
async def preview_last_messages(ctx, limit: int = 5):
    """
    Preview what the cleaned data looks like
    
    Usage: !preview 10
    """
    messages = []
    async for msg in ctx.channel.history(limit=limit):
        messages.append(msg)
    
    print("\n" + "="*60)
    print(f"🔍 Preview: Last {len(messages)} Messages (Cleaned)")
    print("="*60)
    
    for i, msg in enumerate(messages, 1):
        raw = msg.content[:100] if msg.content else "*empty*"
        cleaned = clean_message_content(msg)
        cleaned_preview = cleaned[:100] if cleaned else "*empty after cleaning*"
        
        print(f"\n{i}. Raw: {raw}...")
        print(f"   Cleaned: {cleaned_preview}...")
    
    print("="*60 + "\n")

@bot.command(name='help_scrape')
async def help_command(ctx):
    """Show help information"""
    print("\n" + "="*60)
    print("📚 Discord CSV Scraper - Help")
    print("="*60)
    
    print("\n🎯 Main Command:")
    print("   !scrape - Scrape configured channels (last 1 year)")
    print("   !scrape 2025-01-01 2025-01-31 - Custom date range")
    print("   !scrape 2024-06-01 - From specific date to now")
    print("\n   💡 Channels are pre-configured by developers")
    print("   Use !config to see which channels will be scraped")
    
    print("\n⚙️ Configuration & Info:")
    print("   !config - Show configured channels and settings")
    print("   !preview 10 - Preview cleaned messages")
    
    print("\n📁 Output:")
    print("   Creates: discord_messages_[timestamp].csv")
    print("   Columns: channel, text, date, message_id, author")
    
    print("\n💡 Date format: YYYY-MM-DD (example: 2025-01-15)")
    print("   Default: Last 1 year")
    print("="*60 + "\n")

if __name__ == "__main__":
    import os
    from dotenv import load_dotenv
    
    print("\n" + "="*60)
    print("🚀 Discord CSV Scraper - Auto Mode")
    print("="*60)
    print("Bot will automatically scrape on startup")
    print("No commands needed - just sit back and wait!")
    print("="*60 + "\n")
    
    load_dotenv()
    TOKEN = ''#add the bot token
    
    if not TOKEN:
        TOKEN = input("Enter your Discord bot token: ").strip()
    
    try:
        bot.run(TOKEN)
    except KeyboardInterrupt:
        print("\n\n⚠️ Bot stopped by user (Ctrl+C)")
    except Exception as e:
        print(f"❌ Error starting bot: {e}")
