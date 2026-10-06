import discord
import json
import asyncio

def load_config():
    try:
        with open('config.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading config.json: {e}")
        return {}

async def get_server_channels():
    config = load_config()
    token = config.get('token')
    guild_id = config.get('guild_id')
    
    if not token:
        print("Error: No token found in config.json")
        return
    
    if not guild_id:
        print("Error: No guild_id found in config.json")
        return
    
    intents = discord.Intents.all()
    client = discord.Client(intents=intents)
    
    @client.event
    async def on_ready():
        print(f'Logged in as {client.user} (ID: {client.user.id})')
        print('------')
        
        guild = client.get_guild(int(guild_id))
        if not guild:
            print(f"Error: Guild with ID {guild_id} not found")
            await client.close()
            return
        
        print(f'\n=== Server: {guild.name} ===\n')
        
        # Get all channels
        channels_data = {
            "text_channels": [],
            "voice_channels": [],
            "categories": []
        }
        
        # Categories
        print('=== Categories ===')
        for category in guild.categories:
            print(f'Category: {category.name} (ID: {category.id})')
            channels_data["categories"].append({
                "name": category.name,
                "id": str(category.id)
            })
        
        # Text Channels
        print('\n=== Text Channels ===')
        for channel in guild.text_channels:
            category_name = channel.category.name if channel.category else "No Category"
            print(f'Text: {channel.name} (ID: {channel.id}) | Category: {category_name}')
            channels_data["text_channels"].append({
                "name": channel.name,
                "id": str(channel.id),
                "category": category_name
            })
        
        # Voice Channels
        print('\n=== Voice Channels ===')
        for channel in guild.voice_channels:
            category_name = channel.category.name if channel.category else "No Category"
            print(f'Voice: {channel.name} (ID: {channel.id}) | Category: {category_name}')
            channels_data["voice_channels"].append({
                "name": channel.name,
                "id": str(channel.id),
                "category": category_name
            })
        
        # Save to JSON file
        with open('channels_list.json', 'w', encoding='utf-8') as f:
            json.dump(channels_data, f, ensure_ascii=False, indent=2)
        
        print(f'\n=== Channels data saved to channels_list.json ===')
        
        await client.close()
    
    try:
        await client.start(token)
    except Exception as e:
        print(f"Error: {e}")

if __name__ == '__main__':
    asyncio.run(get_server_channels())
