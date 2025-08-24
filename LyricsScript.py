import asyncio
import aiohttp

# Core lyric-fetching logic
async def fetch_lyrics(bot):
    """Fetch lyrics for the currently playing song."""
    try:
        song = bot.config.get("spotify_song")
        if not song:
            return "# No song currently playing"

        print(f"Fetching lyrics for: {song}", type_="INFO")

        # Try Genius API if key is configured
        genius_key = getConfigData().get("lyrics_genius_key", "")
        if genius_key:
            try:
                async with aiohttp.ClientSession() as session:
                    headers = {"Authorization": f"Bearer {genius_key}"}
                    # URL encode the song title for the search
                    encoded_song = song.replace(' ', '%20').replace('&', '%26')
                    search_url = f"https://api.genius.com/search?q={encoded_song}"
                    
                    async with session.get(search_url, headers=headers, timeout=10) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            
                            if data.get("response", {}).get("hits"):
                                song_path = data["response"]["hits"][0]["result"]["path"]
                                lyrics_url = f"https://genius.com{song_path}"
                                print(f"Found Genius lyrics URL for: {song}", type_="SUCCESS")
                                return f"# Lyrics for **{song}**\n{lyrics_url}"
                            else:
                                print(f"No Genius results found for: {song}", type_="INFO")
                        else:
                            print(f"Genius API returned status {resp.status}", type_="ERROR")
                            
            except aiohttp.ClientError as e:
                print(f"Error fetching from Genius API: {e}", type_="ERROR")
            except Exception as e:
                print(f"Unexpected error with Genius API: {e}", type_="ERROR")

        # Fallback behavior
        use_fallback = getConfigData().get("lyrics_use_fallback", True)
        if use_fallback:
            # Create a search-friendly version of the song title
            search_song = song.replace(' ', '+').replace('&', '%26')
            fallback_url = f"https://genius.com/search?q={search_song}"
            print(f"Using fallback search for: {song}", type_="INFO")
            return f"# Search lyrics for **{song}**\n{fallback_url}"
        
        return "# Lyrics not found"
        
    except Exception as e:
        print(f"Error in fetch_lyrics: {e}", type_="ERROR")
        return "# Error fetching lyrics"

# Initialize default config values
if getConfigData().get("lyrics_genius_key") is None:
    updateConfigData("lyrics_genius_key", "")
if getConfigData().get("lyrics_use_fallback") is None:
    updateConfigData("lyrics_use_fallback", True)

# Main lyrics command
@bot.command(
    name="lyrics",
    aliases=["ly", "lyric"],
    usage="[setkey <api_key>] [config] [toggleapi]",
    description="Get lyrics for currently playing song or manage lyrics settings"
)
async def lyrics_command(ctx, *, args: str = ""):
    await ctx.message.delete()
    
    args = args.strip().lower()
    parts = args.split(maxsplit=1) if args else []
    subcommand = parts[0] if parts else ""
    
    if subcommand == "setkey":
        if len(parts) < 2:
            await ctx.send("# Usage: `lyrics setkey <your_genius_api_key>`")
            return
            
        api_key = parts[1].strip()
        if len(api_key) < 10:  # Basic validation
            await ctx.send("# Invalid API key format")
            return
            
        updateConfigData("lyrics_genius_key", api_key)
        await ctx.send("# Genius API key saved successfully")
        print(f"Genius API key updated by user {ctx.author}", type_="SUCCESS")
        
    elif subcommand == "config":
        genius_key = getConfigData().get("lyrics_genius_key", "")
        fallback = getConfigData().get("lyrics_use_fallback", True)
        
        config_msg = f"""# **Lyrics Configuration**
**Genius API Key:** {'✅ Set' if genius_key else '❌ Not set'}
**Fallback Mode:** {'✅ Enabled' if fallback else '❌ Disabled'}

*Get a free Genius API key at: https://genius.com/api-clients*"""
        
        await ctx.send(config_msg)
        
    elif subcommand == "toggleapi":
        current_fallback = getConfigData().get("lyrics_use_fallback", True)
        new_fallback = not current_fallback
        updateConfigData("lyrics_use_fallback", new_fallback)
        
        status = "enabled" if new_fallback else "disabled"
        await ctx.send(f"# Fallback Genius API: {status}")
        print(f"Fallback mode {status} by user {ctx.author}", type_="INFO")
        
    else:
        # Default action: fetch lyrics
        try:
            msg = await ctx.send("# 🎵 Fetching lyrics...")
            lyrics_result = await fetch_lyrics(ctx.bot)
            await msg.edit(content=lyrics_result)
        except Exception as e:
            print(f"Error in lyrics command: {e}", type_="ERROR")
            await ctx.send("# Error fetching lyrics")

print("Lyrics script loaded successfully from GitHub", type_="SUCCESS")