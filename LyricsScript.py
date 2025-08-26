import asyncio
import aiohttp
import json
import os
from pathlib import Path

# Config file path
CONFIG_PATH = Path(os.path.expandvars(r"%APPDATA%\Nighty Selfbot\data\scripts\json\LyricsConfig.json"))

def load_config():
    """Load configuration from JSON file."""
    try:
        CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        
        if CONFIG_PATH.exists():
            with open(CONFIG_PATH, "r", encoding='utf-8') as f:
                config = json.load(f)
                return config
        else:
            default_config = {"genius_key": "", "use_fallback": True}
            save_config(default_config)
            return default_config
    except Exception as e:
        print(f"Error loading config: {e}", type_="ERROR")
        return {"genius_key": "", "use_fallback": True}

def save_config(config):
    """Save configuration to JSON file."""
    try:
        CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        
        with open(CONFIG_PATH, "w", encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        
        return True
    except Exception as e:
        print(f"Error saving config: {e}", type_="ERROR")
        return False

def get_config_value(key, default=None):
    """Get a single config value."""
    config = load_config()
    return config.get(key, default)

def set_config_value(key, value):
    """Set a single config value."""
    config = load_config()
    config[key] = value
    return save_config(config)

async def test_genius_api_key(api_key):
    """Test if the Genius API key is valid."""
    try:
        test_url = "https://api.genius.com/search?q=test"
        headers = {"Authorization": f"Bearer {api_key}"}
        
        async with aiohttp.ClientSession() as session:
            async with session.get(test_url, headers=headers, timeout=10) as resp:
                if resp.status == 200:
                    return True, "Valid"
                elif resp.status == 401:
                    return False, "Invalid API key"
                elif resp.status == 403:
                    return False, "Access forbidden"
                else:
                    return False, f"HTTP {resp.status}"
    except Exception as e:
        return False, f"Network error: {str(e)}"

def calculate_similarity(str1, str2):
    """Calculate similarity between two strings using simple matching."""
    if not str1 or not str2:
        return 0
        
    str1 = str1.lower().strip()
    str2 = str2.lower().strip()
    
    if str1 == str2:
        return 100
    
    if str1 in str2 or str2 in str1:
        return 80
    
    words1 = set(str1.split())
    words2 = set(str2.split())
    
    if not words1 or not words2:
        return 0
    
    intersection = len(words1.intersection(words2))
    union = len(words1.union(words2))
    
    return int((intersection / union) * 70)

def find_best_match(song_title, artist_name, hits):
    """Find the best matching song from Genius search results."""
    best_match = None
    best_score = 0
    
    for i, hit in enumerate(hits[:5]):
        result = hit.get("result", {})
        genius_title = result.get("title", "")
        genius_artist = result.get("primary_artist", {}).get("name", "")
        
        title_score = calculate_similarity(song_title, genius_title)
        artist_score = calculate_similarity(artist_name, genius_artist) if artist_name else 50
        combined_score = (title_score * 0.7) + (artist_score * 0.3)
        
        print(f"Match #{i+1}: '{genius_title}' by '{genius_artist}' - Score: {combined_score:.1f}%", type_="INFO")
        
        if combined_score > best_score:
            best_score = combined_score
            best_match = result
    
    return best_match, best_score

async def fetch_lyrics(bot):
    """Fetch lyrics for the currently playing song."""
    try:
        if not hasattr(bot, 'config'):
            return "# Bot configuration not available"
            
        song = bot.config.get("spotify_song")
        artist = bot.config.get("spotify_artist", "")
        
        if not song:
            return "# No song currently playing"

        if song:
            song = song.strip()
        if artist:
            artist = artist.strip()

        display_info = f"**{song}**" + (f" by **{artist}**" if artist else "")

        genius_key = get_config_value("genius_key", "")
        
        if genius_key:
            is_valid, validation_msg = await test_genius_api_key(genius_key)
            if not is_valid:
                return f"# Genius API key issue: {validation_msg}"
            
            try:
                search_query = song
                if artist:
                    search_query += f" {artist}"
                
                encoded_query = search_query.replace(' ', '%20').replace('&', '%26').replace('#', '%23')
                search_url = f"https://api.genius.com/search?q={encoded_query}"
                
                async with aiohttp.ClientSession() as session:
                    headers = {"Authorization": f"Bearer {genius_key}"}
                    
                    async with session.get(search_url, headers=headers, timeout=15) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            hits = data.get("response", {}).get("hits", [])
                            
                            if hits:
                                best_match, best_score = find_best_match(song, artist, hits)
                                
                                if best_match and best_score > 25:
                                    song_path = best_match.get("path", "")
                                    genius_title = best_match.get("title", "")
                                    genius_artist = best_match.get("primary_artist", {}).get("name", "")
                                    
                                    lyrics_url = f"https://genius.com{song_path}"
                                    match_info = f"'{genius_title}' by '{genius_artist}' (Match: {best_score:.1f}%)"
                                    
                                    return f"# Lyrics for {display_info}\n**Found:** {match_info}\n{lyrics_url}"
                        else:
                            return f"# Genius API error: HTTP {resp.status}"
                            
            except asyncio.TimeoutError:
                return "# Request timed out - try again"
            except Exception as e:
                return f"# API error: {str(e)}"

        use_fallback = get_config_value("use_fallback", True)
        
        if use_fallback:
            search_query = song
            if artist:
                search_query += f" {artist}"
            search_encoded = search_query.replace(' ', '+').replace('&', '%26')
            fallback_url = f"https://genius.com/search?q={search_encoded}"
            return f"# Search lyrics for {display_info}\n{fallback_url}"
        
        return "# Lyrics not found - enable fallback mode to get search links"
        
    except Exception as e:
        print(f"Critical error in fetch_lyrics: {e}", type_="ERROR")
        return f"# Critical error: {str(e)}"

@bot.command(
    name="lyrics",
    aliases=["ly", "lyric"],
    usage="[setkey <api_key>] [config] [toggle] [debug] [testkey]",
    description="Get lyrics for currently playing song or manage lyrics settings"
)
async def lyrics_command(ctx, *, args: str = ""):
    await ctx.message.delete()
    
    args = args.strip()
    parts = args.split(maxsplit=1) if args else []
    subcommand = parts[0].lower() if parts else ""
    
    if subcommand == "debug":
        config = load_config()
        genius_key = config.get("genius_key", "")
        fallback = config.get("use_fallback", True)
        
        bot_has_config = hasattr(ctx.bot, 'config')
        bot_config_keys = list(ctx.bot.config.keys()) if bot_has_config else []
        song = ctx.bot.config.get("spotify_song", "Not found") if bot_has_config else "No config"
        artist = ctx.bot.config.get("spotify_artist", "Not found") if bot_has_config else "No config"
        
        debug_msg = f"""# **Lyrics Debug Information**

**JSON Configuration:** `{CONFIG_PATH}`
- File exists: {'✅ Yes' if CONFIG_PATH.exists() else '❌ No'}
- Genius Key: {'✅ Set (' + str(len(genius_key)) + ' chars)' if genius_key else '❌ Not set'}
- Fallback Mode: {'✅ Enabled' if fallback else '❌ Disabled'}

**Bot Spotify Data:**
- Config Available: {'✅ Yes' if bot_has_config else '❌ No'}
- Available Keys: {', '.join(bot_config_keys[:10])}
- Current Song: `{str(song)[:50]}{'...' if len(str(song)) > 50 else ''}`
- Current Artist: `{str(artist)[:50]}{'...' if len(str(artist)) > 50 else ''}`

**Commands:**
- `lyrics testkey` - Test your API key
- `lyrics setkey <key>` - Set new API key
- `lyrics toggle` - Toggle fallback mode"""

        await ctx.send(debug_msg)
        return
    
    elif subcommand == "testkey":
        genius_key = get_config_value("genius_key", "")
        if not genius_key:
            await ctx.send("# No API key configured. Use `lyrics setkey <your_key>`")
            return
        
        msg = await ctx.send("# 🔑 Testing Genius API key...")
        is_valid, validation_msg = await test_genius_api_key(genius_key)
        
        if is_valid:
            await msg.edit(content="# ✅ API key is valid and working!")
        else:
            await msg.edit(content=f"# ❌ API key test failed: {validation_msg}")
        return
    
    elif subcommand == "setkey":
        if len(parts) < 2:
            await ctx.send("# Usage: `lyrics setkey <your_genius_api_key>`\n*Get a key at: https://genius.com/api-clients*")
            return
            
        api_key = parts[1].strip()
        if len(api_key) < 20:
            await ctx.send("# Invalid API key format - too short")
            return
        
        msg = await ctx.send("# 🔑 Testing new API key...")
        is_valid, validation_msg = await test_genius_api_key(api_key)
        
        if is_valid:
            if set_config_value("genius_key", api_key):
                await msg.edit(content="# ✅ Genius API key saved and validated successfully!")
            else:
                await msg.edit(content="# ❌ Failed to save API key to config file")
        else:
            await msg.edit(content=f"# ❌ API key validation failed: {validation_msg}")
        return
        
    elif subcommand == "config":
        config = load_config()
        genius_key = config.get("genius_key", "")
        fallback = config.get("use_fallback", True)
        
        config_msg = f"""# **Lyrics Configuration**
**Config File:** `{CONFIG_PATH}`
**Genius API Key:** {'✅ Set (' + str(len(genius_key)) + ' chars)' if genius_key else '❌ Not set'}
**Fallback Mode:** {'✅ Enabled' if fallback else '❌ Disabled'}

**Commands:**
- `lyrics setkey <key>` - Set API key
- `lyrics testkey` - Test current key
- `lyrics toggle` - Toggle fallback
- `lyrics debug` - Show debug info

*Get a free API key at: https://genius.com/api-clients*"""
        
        await ctx.send(config_msg)
        return
        
    elif subcommand == "toggle":
        current_fallback = get_config_value("use_fallback", True)
        new_fallback = not current_fallback
        
        if set_config_value("use_fallback", new_fallback):
            status = "enabled" if new_fallback else "disabled"
            await ctx.send(f"# Fallback mode {status}")
        else:
            await ctx.send("# Failed to update fallback setting")
        return
        
    else:
        try:
            msg = await ctx.send("# 🎵 Fetching lyrics...")
            lyrics_result = await fetch_lyrics(ctx.bot)
            await msg.edit(content=lyrics_result)
        except Exception as e:
            print(f"Error in lyrics command: {e}", type_="ERROR")
            await ctx.send(f"# Command error: {str(e)}")

print("Lyrics script loaded successfully from GitHub", type_="SUCCESS")