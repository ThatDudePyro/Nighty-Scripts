import asyncio
import aiohttp

def calculate_similarity(str1, str2):
    """Calculate similarity between two strings using simple matching."""
    str1 = str1.lower().strip()
    str2 = str2.lower().strip()
    
    # Exact match
    if str1 == str2:
        return 100
    
    # Check if one contains the other
    if str1 in str2 or str2 in str1:
        return 80
    
    # Word-based matching
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
    
    for hit in hits:
        result = hit.get("result", {})
        genius_title = result.get("title", "")
        genius_artist = result.get("primary_artist", {}).get("name", "")
        
        # Calculate title similarity
        title_score = calculate_similarity(song_title, genius_title)
        
        # Calculate artist similarity
        artist_score = calculate_similarity(artist_name, genius_artist) if artist_name else 50
        
        # Combined score (title is more important)
        combined_score = (title_score * 0.7) + (artist_score * 0.3)
        
        print(f"Match candidate: '{genius_title}' by '{genius_artist}' - Score: {combined_score:.1f}", type_="INFO")
        
        if combined_score > best_score:
            best_score = combined_score
            best_match = result
    
    return best_match, best_score

# Core lyric-fetching logic with enhanced debugging
async def fetch_lyrics(bot):
    """Fetch lyrics for the currently playing song."""
    try:
        # Debug: Check bot config
        print(f"Bot config keys: {list(bot.config.keys()) if hasattr(bot, 'config') else 'No config found'}", type_="INFO")
        
        song = bot.config.get("spotify_song") if hasattr(bot, 'config') else None
        artist = bot.config.get("spotify_artist", "") if hasattr(bot, 'config') else ""
        
        print(f"Raw song data: '{song}'", type_="INFO")
        print(f"Raw artist data: '{artist}'", type_="INFO")
        
        if not song:
            print("No spotify_song found in bot config", type_="ERROR")
            return "# No song currently playing"

        display_info = f"**{song}**" + (f" by **{artist}**" if artist else "")
        print(f"Fetching lyrics for: {song}" + (f" by {artist}" if artist else ""), type_="INFO")

        # Try Genius API if key is configured
        genius_key = getConfigData().get("lyrics_genius_key", "")
        print(f"Genius API key configured: {'Yes' if genius_key else 'No'}", type_="INFO")
        
        if genius_key:
            try:
                # Create search query with both song and artist
                search_query = song
                if artist:
                    search_query += f" {artist}"
                
                print(f"Search query: '{search_query}'", type_="INFO")
                
                # URL encode the search query
                encoded_query = search_query.replace(' ', '%20').replace('&', '%26')
                search_url = f"https://api.genius.com/search?q={encoded_query}"
                
                print(f"Genius API URL: {search_url}", type_="INFO")
                
                async with aiohttp.ClientSession() as session:
                    headers = {"Authorization": f"Bearer {genius_key}"}
                    
                    async with session.get(search_url, headers=headers, timeout=10) as resp:
                        print(f"Genius API response status: {resp.status}", type_="INFO")
                        
                        if resp.status == 200:
                            data = await resp.json()
                            hits = data.get("response", {}).get("hits", [])
                            
                            print(f"Genius API returned {len(hits)} results", type_="INFO")
                            
                            if hits:
                                # Find the best matching song
                                best_match, best_score = find_best_match(song, artist, hits)
                                
                                if best_match and best_score > 30:  # Minimum threshold
                                    song_path = best_match.get("path", "")
                                    genius_title = best_match.get("title", "")
                                    genius_artist = best_match.get("primary_artist", {}).get("name", "")
                                    
                                    lyrics_url = f"https://genius.com{song_path}"
                                    match_info = f"'{genius_title}' by '{genius_artist}' (Match: {best_score:.1f}%)"
                                    
                                    print(f"Best match found: {match_info}", type_="SUCCESS")
                                    return f"# Lyrics for {display_info}\n**Found:** {match_info}\n{lyrics_url}"
                                else:
                                    print(f"No good matches found (best score: {best_score:.1f}%)", type_="INFO")
                            else:
                                print(f"No Genius results found for: {search_query}", type_="INFO")
                        elif resp.status == 401:
                            print("Genius API returned 401 - Invalid API key", type_="ERROR")
                            return "# Invalid Genius API key - check your configuration"
                        elif resp.status == 403:
                            print("Genius API returned 403 - Access forbidden", type_="ERROR")
                            return "# Genius API access forbidden - check your API key"
                        else:
                            print(f"Genius API returned status {resp.status}", type_="ERROR")
                            response_text = await resp.text()
                            print(f"Response body: {response_text[:200]}", type_="ERROR")
                            
            except aiohttp.ClientError as e:
                print(f"aiohttp ClientError: {e}", type_="ERROR")
                return f"# Network error: {str(e)}"
            except asyncio.TimeoutError:
                print("Genius API request timed out", type_="ERROR")
                return "# Request timed out - try again"
            except Exception as e:
                print(f"Unexpected error with Genius API: {e}", type_="ERROR")
                return f"# API error: {str(e)}"

        # Fallback behavior
        use_fallback = getConfigData().get("lyrics_use_fallback", True)
        print(f"Using fallback: {use_fallback}", type_="INFO")
        
        if use_fallback:
            # Create a search-friendly version including artist
            search_query = song
            if artist:
                search_query += f" {artist}"
            search_encoded = search_query.replace(' ', '+').replace('&', '%26')
            fallback_url = f"https://genius.com/search?q={search_encoded}"
            print(f"Using fallback search for: {search_query}", type_="INFO")
            return f"# Search lyrics for {display_info}\n{fallback_url}"
        
        return "# Lyrics not found"
        
    except Exception as e:
        print(f"Critical error in fetch_lyrics: {e}", type_="ERROR")
        import traceback
        print(f"Traceback: {traceback.format_exc()}", type_="ERROR")
        return f"# Critical error: {str(e)}"

# Initialize default config values
if getConfigData().get("lyrics_genius_key") is None:
    updateConfigData("lyrics_genius_key", "")
if getConfigData().get("lyrics_use_fallback") is None:
    updateConfigData("lyrics_use_fallback", True)

# Main lyrics command
@bot.command(
    name="lyrics",
    aliases=["ly", "lyric"],
    usage="[setkey <api_key>] [config] [toggleapi] [debug]",
    description="Get lyrics for currently playing song or manage lyrics settings"
)
async def lyrics_command(ctx, *, args: str = ""):
    await ctx.message.delete()
    
    args = args.strip().lower()
    parts = args.split(maxsplit=1) if args else []
    subcommand = parts[0] if parts else ""
    
    if subcommand == "debug":
        # Show debug information
        genius_key = getConfigData().get("lyrics_genius_key", "")
        fallback = getConfigData().get("lyrics_use_fallback", True)
        
        # Check bot config
        bot_config_keys = list(ctx.bot.config.keys()) if hasattr(ctx.bot, 'config') else []
        song = ctx.bot.config.get("spotify_song", "Not found") if hasattr(ctx.bot, 'config') else "No config"
        artist = ctx.bot.config.get("spotify_artist", "Not found") if hasattr(ctx.bot, 'config') else "No config"
        
        debug_msg = f"""# **Lyrics Debug Information**

**Configuration:**
- Genius Key: {'✅ Set (' + str(len(genius_key)) + ' chars)' if genius_key else '❌ Not set'}
- Fallback Mode: {'✅ Enabled' if fallback else '❌ Disabled'}

**Bot Spotify Data:**
- Config Available: {'✅ Yes' if hasattr(ctx.bot, 'config') else '❌ No'}
- Config Keys: {', '.join(bot_config_keys[:5])}{'...' if len(bot_config_keys) > 5 else ''}
- Current Song: `{song}`
- Current Artist: `{artist}`

**Troubleshooting:**
- Make sure Spotify is connected and playing
- Verify Genius API key is valid
- Check if Nighty's Spotify integration is enabled"""

        await ctx.send(debug_msg)
        return
    
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

*Get a free Genius API key at: https://genius.com/api-clients*
*Use `lyrics debug` for detailed troubleshooting*"""
        
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
            import traceback
            print(f"Command traceback: {traceback.format_exc()}", type_="ERROR")
            await ctx.send(f"# Command error: {str(e)}")

print("Lyrics script with debugging loaded successfully from GitHub", type_="SUCCESS")