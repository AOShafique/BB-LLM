import json
import pandas as pd

# Load scraped data
with open('discord_messages.json', 'r', encoding='utf-8') as f:
    messages = json.load(f)

# Convert to DataFrame for easier processing
df = pd.DataFrame(messages)

# Clean the data
def clean_message(text):
    if not text:
        return ""
    # Remove bot commands
    if text.startswith('!') or text.startswith('/'):
        return ""
    # Remove mentions (optional)
    # text = re.sub(r'<@!?\d+>', '', text)
    return text.strip()

df['content'] = df['content'].apply(clean_message)
df = df[df['content'] != ""]  # Remove empty messages

# Sort by timestamp
df['timestamp'] = pd.to_datetime(df['timestamp'])
df = df.sort_values('timestamp')

print(f"Cleaned dataset: {len(df)} messages")
