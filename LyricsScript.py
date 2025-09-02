def lyrics():
    import asyncio
    import aiohttp
    import json
    import os
    import re
    import time
    from pathlib import Path
    from typing import Dict, List, Tuple, Optional, Any
    
    # Config file path
    CONFIG_PATH = Path(os.path.expandvars(r"%APPDATA%\Nighty Selfbot\data\scripts\json\LyricsConfig.json"))

    # Cache for API responses (in-memory)
    lyrics_cache: Dict[str, Dict[str, Any]] = {}
    CACHE_EXPIRY = 3600  # 1 hour in seconds

    def load_config() -> Dict[str, Any]:
        """Load configuration from JSON file with better error handling."""
        try:
            CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
            
            if CONFIG_PATH.exists():
                with open(CONFIG_PATH, "r", encoding='utf-8') as f:
                    config = json.load(f)
                    # Validate config structure
                    required_keys = {"genius_key", "use_fallback"}
                    for key in required_keys:
                        if key not in config:
                            config[key] = "" if key == "genius_key" else True
                    return config
            else:
                default_config = {
                    "genius_key": "", 
                    "use_fallback": True,
                    "cache_enabled": True,
                    "max_retries": 3,
                    "timeout": 15,
                    "match_threshold": 25
                }
                save_config(default_config)
                return default_config
        except (json.JSONDecodeError, PermissionError) as e:
            print(f"Error loading config: {e}", type_="ERROR")
            return {
                "genius_key": "", 
                "use_fallback": True, 
                "cache_enabled": True,
                "max_retries": 3,
                "timeout": 15,
                "match_threshold": 25
            }

    def save_config(config: Dict[str, Any]) -> bool:
        """Save configuration to JSON file with atomic write."""
        try:
            CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
            
            # Atomic write using temporary file
            temp_path = CONFIG_PATH.with_suffix('.tmp')
            with open(temp_path, "w", encoding='utf-8') as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
            
            # Replace original file
            temp_path.replace(CONFIG_PATH)
            return True
        except Exception as e:
            print(f"Error saving config: {e}", type_="ERROR")
            return False

    def get_config_value(key: str, default: Any = None) -> Any:
        """Get a single config value with type safety."""
        config = load_config()
        return config.get(key, default)

    def set_config_value(key: str, value: Any) -> bool:
        """Set a single config value with validation."""
        config = load_config()
        print(f"{key}, {value}")
        
        # Validate certain config values
        if not isinstance(value,str):
         if key == "timeout" and not isinstance(value, (int, float)) or value <= 0:
            print(f"Invalid timeout value: {value}", type_="ERROR")
            return False
         if key == "max_retries" and not isinstance(value, int) or value < 0:
            print(f"Invalid max_retries value: {value}", type_="ERROR")
            return False
         if key == "match_threshold" and not isinstance(value, (int, float)) or not 0 <= value <= 100:
            print(f"Invalid match_threshold value: {value}", type_="ERROR")
            return False
        
        config[key] = value
        return save_config(config)

    def clean_song_title(title: str) -> str:
        """Clean song title for better matching."""
        if not title:
            return ""
        
        # Remove common suffixes and prefixes
        title = re.sub(r'\s*\(.*?\)\s*', ' ', title)  # Remove parentheses content
        title = re.sub(r'\s*\[.*?\]\s*', ' ', title)  # Remove bracket content
        title = re.sub(r'\s*-\s*(feat|ft|featuring).*', '', title, flags=re.IGNORECASE)
        title = re.sub(r'\s*-\s*remaster.*', '', title, flags=re.IGNORECASE)
        title = re.sub(r'\s*-\s*radio edit.*', '', title, flags=re.IGNORECASE)
        title = re.sub(r'\s+', ' ', title).strip()  # Normalize whitespace
        
        return title

    async def test_genius_api_key(api_key: str) -> Tuple[bool, str]:
        """Test if the Genius API key is valid with retry logic."""
        max_retries = get_config_value("max_retries", 3)
        timeout = get_config_value("timeout", 15)
        
        for attempt in range(max_retries):
            try:
                test_url = "https://api.genius.com/search?q=test"
                headers = {"Authorization": f"Bearer {api_key}"}
                
                async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=timeout)) as session:
                    async with session.get(test_url, headers=headers) as resp:
                        if resp.status == 200:
                            return True, "Valid"
                        elif resp.status == 401:
                            return False, "Invalid API key"
                        elif resp.status == 403:
                            return False, "Access forbidden"
                        elif resp.status == 429:
                            if attempt < max_retries - 1:
                                await asyncio.sleep(2 ** attempt)  # Exponential backoff
                                continue
                            return False, "Rate limited"
                        else:
                            return False, f"HTTP {resp.status}"
            except asyncio.TimeoutError:
                if attempt < max_retries - 1:
                    continue
                return False, "Request timeout"
            except Exception as e:
                if attempt < max_retries - 1:
                    continue
                return False, f"Network error: {str(e)}"
        
        return False, "Max retries exceeded"

    def calculate_similarity(str1: str, str2: str) -> float:
        """Enhanced similarity calculation with fuzzy matching."""
        if not str1 or not str2:
            return 0.0
            
        str1 = str1.lower().strip()
        str2 = str2.lower().strip()
        
        if str1 == str2:
            return 100.0
        
        # Check for substring matches
        if str1 in str2 or str2 in str1:
            shorter = min(len(str1), len(str2))
            longer = max(len(str1), len(str2))
            return min(95.0, (shorter / longer) * 100)
        
        # Word-based similarity
        words1 = set(str1.split())
        words2 = set(str2.split())
        
        if not words1 or not words2:
            return 0.0
        
        intersection = len(words1.intersection(words2))
        union = len(words1.union(words2))
        jaccard = intersection / union
        
        # Bonus for partial word matches
        partial_matches = 0
        for w1 in words1:
            for w2 in words2:
                if len(w1) >= 3 and len(w2) >= 3:
                    if w1 in w2 or w2 in w1:
                        partial_matches += 1
        
        partial_score = min(20, partial_matches * 5)
        base_score = jaccard * 70
        
        return min(100.0, base_score + partial_score)

    def find_best_match(song_title: str, artist_name: str, hits: List[Dict]) -> Tuple[Optional[Dict], float]:
        """Find the best matching song with improved scoring."""
        if not hits:
            return None, 0.0
        
        # Clean the input for better matching
        clean_title = clean_song_title(song_title)
        clean_artist = artist_name.strip() if artist_name else ""
        
        best_match = None
        best_score = 0.0
        match_threshold = get_config_value("match_threshold", 25)
        
        print(f"Searching for: '{clean_title}' by '{clean_artist}'", type_="INFO")
        
        for i, hit in enumerate(hits[:10]):  # Check more results
            result = hit.get("result", {})
            genius_title = result.get("title", "")
            genius_artist = result.get("primary_artist", {}).get("name", "")
            
            # Clean genius data for comparison
            clean_genius_title = clean_song_title(genius_title)
            
            title_score = calculate_similarity(clean_title, clean_genius_title)
            artist_score = calculate_similarity(clean_artist, genius_artist) if clean_artist else 50.0
            
            # Weight title more heavily than artist
            combined_score = (title_score * 0.75) + (artist_score * 0.25)
            
            print(f"Match #{i+1}: '{genius_title}' by '{genius_artist}' - Score: {combined_score:.1f}%", type_="INFO")
            
            if combined_score > best_score and combined_score >= match_threshold:
                best_score = combined_score
                best_match = result
        
        return best_match, best_score

    def get_cache_key(song: str, artist: str) -> str:
        """Generate cache key for song/artist combination."""
        return f"{song.lower().strip()}|{artist.lower().strip() if artist else ''}"

    def is_cache_valid(cache_entry: Dict[str, Any]) -> bool:
        """Check if cache entry is still valid."""
        return time.time() - cache_entry.get("timestamp", 0) < CACHE_EXPIRY

    def get_from_cache(song: str, artist: str) -> Optional[str]:
        """Get result from cache if available and valid."""
        if not get_config_value("cache_enabled", True):
            return None
        
        cache_key = get_cache_key(song, artist)
        if cache_key in lyrics_cache and is_cache_valid(lyrics_cache[cache_key]):
            print("Using cached result", type_="INFO")
            return lyrics_cache[cache_key]["result"]
        return None

    def save_to_cache(song: str, artist: str, result: str) -> None:
        """Save result to cache."""
        if not get_config_value("cache_enabled", True):
            return
        
        cache_key = get_cache_key(song, artist)
        lyrics_cache[cache_key] = {
            "result": result,
            "timestamp": time.time()
        }
        
        # Clean old cache entries (keep only last 100)
        if len(lyrics_cache) > 100:
            oldest_keys = sorted(lyrics_cache.keys(), 
                               key=lambda k: lyrics_cache[k]["timestamp"])[:20]
            for key in oldest_keys:
                del lyrics_cache[key]

    async def fetch_lyrics(bot) -> str:
        """Fetch lyrics for the currently playing song with enhanced features."""
        try:
            if not hasattr(bot, 'config'):
                return "# Bot configuration not available"
                
            song = bot.config.get("spotify_song")
            artist = bot.config.get("spotify_artist", "")
            
            if not song:
                return "# No song currently playing"

            song = song.strip()
            artist = artist.strip() if artist else ""

            display_info = f"**{song}**" + (f" by **{artist}**" if artist else "")

            # Check cache first
            cached_result = get_from_cache(song, artist)
            if cached_result:
                return cached_result

            genius_key = get_config_value("genius_key", "")
            
            if genius_key:
                try:
                    # Clean search query for better results
                    clean_title = clean_song_title(song)
                    search_query = clean_title
                    if artist:
                        search_query += f" {artist}"
                    
                    # URL encode properly
                    search_query = search_query.replace(' ', '%20').replace('&', '%26').replace('#', '%23')
                    search_url = f"https://api.genius.com/search?q={search_query}"
                    
                    timeout = get_config_value("timeout", 15)
                    max_retries = get_config_value("max_retries", 3)
                    
                    for attempt in range(max_retries):
                        try:
                            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=timeout)) as session:
                                headers = {"Authorization": f"Bearer {genius_key}"}
                                
                                async with session.get(search_url, headers=headers) as resp:
                                    if resp.status == 200:
                                        data = await resp.json()
                                        hits = data.get("response", {}).get("hits", [])
                                        
                                        if hits:
                                            best_match, best_score = find_best_match(song, artist, hits)
                                            
                                            if best_match:
                                                song_path = best_match.get("path", "")
                                                genius_title = best_match.get("title", "")
                                                genius_artist = best_match.get("primary_artist", {}).get("name", "")
                                                
                                                lyrics_url = f"https://genius.com{song_path}"
                                                match_info = f"'{genius_title}' by '{genius_artist}' (Match: {best_score:.1f}%)"
                                                result = f"# Lyrics for {display_info}\n**Found:** {match_info}\n{lyrics_url}"
                                                
                                                save_to_cache(song, artist, result)
                                                return result
                                            else:
                                                result = f"# No good matches found for {display_info}\nTry checking the song/artist spelling"
                                                save_to_cache(song, artist, result)
                                                return result
                                        else:
                                            result = f"# No search results for {display_info}"
                                            save_to_cache(song, artist, result)
                                            return result
                                    elif resp.status == 429:  # Rate limited
                                        if attempt < max_retries - 1:
                                            wait_time = 2 ** attempt
                                            print(f"Rate limited, waiting {wait_time}s...", type_="WARNING")
                                            await asyncio.sleep(wait_time)
                                            continue
                                        return f"# Rate limited - try again later"
                                    else:
                                        return f"# Genius API error: HTTP {resp.status}"
                            break  # Success, exit retry loop
                        except asyncio.TimeoutError:
                            if attempt < max_retries - 1:
                                continue
                            return "# Request timed out - try again"
                        except Exception as e:
                            if attempt < max_retries - 1:
                                continue
                            return f"# API error: {str(e)}"
                                
                except Exception as e:
                    return f"# Unexpected error: {str(e)}"

            # Fallback mode
            use_fallback = get_config_value("use_fallback", True)
            
            if use_fallback:
                search_query = song
                if artist:
                    search_query += f" {artist}"
                search_encoded = search_query.replace(' ', '+').replace('&', '%26')
                fallback_url = f"https://genius.com/search?q={search_encoded}"
                result = f"# Search lyrics for {display_info}\n{fallback_url}"
                
                save_to_cache(song, artist, result)
                return result
            
            return "# Lyrics not found - enable fallback mode to get search links"
            
        except Exception as e:
            print(f"Critical error in fetch_lyrics: {e}", type_="ERROR")
            return f"# Critical error: {str(e)}"

    @bot.command(
        name="lyrics",
        aliases=["ly", "lyric"],
        usage="[setkey <api_key>] [config] [toggle] [debug] [testkey] [clearcache] [threshold <value>]",
        description="Get lyrics for currently playing song or manage lyrics settings"
    )
    async def lyrics_command(ctx, *, args: str = ""):
        await ctx.message.delete()
        
        args = args.strip()
        parts = args.split(maxsplit=2) if args else []
        subcommand = parts[0].lower() if parts else ""
        
        if subcommand == "debug":
            config = load_config()
            genius_key = config.get("genius_key", "")
            fallback = config.get("use_fallback", True)
            cache_enabled = config.get("cache_enabled", True)
            match_threshold = config.get("match_threshold", 25)
            timeout = config.get("timeout", 15)
            max_retries = config.get("max_retries", 3)
            
            bot_has_config = hasattr(ctx.bot, 'config')
            bot_config_keys = list(ctx.bot.config.keys()) if bot_has_config else []
            song = ctx.bot.config.get("spotify_song", "Not found") if bot_has_config else "No config"
            artist = ctx.bot.config.get("spotify_artist", "Not found") if bot_has_config else "No config"
            
            cache_info = f"{len(lyrics_cache)} entries" if cache_enabled else "Disabled"
            
            debug_msg = f"""# **Lyrics Debug Information**

    **JSON Configuration:** `{CONFIG_PATH}`
    - File exists: {'✅ Yes' if CONFIG_PATH.exists() else '❌ No'}
    - Genius Key: {'✅ Set (' + str(len(genius_key)) + ' chars)' if genius_key else '❌ Not set'}
    - Fallback Mode: {'✅ Enabled' if fallback else '❌ Disabled'}
    - Cache: {cache_info}
    - Match Threshold: {match_threshold}%
    - Timeout: {timeout}s
    - Max Retries: {max_retries}

    **Bot Spotify Data:**
    - Config Available: {'✅ Yes' if bot_has_config else '❌ No'}
    - Available Keys: {', '.join(bot_config_keys[:10])}
    - Current Song: `{str(song)[:50]}{'...' if len(str(song)) > 50 else ''}`
    - Current Artist: `{str(artist)[:50]}{'...' if len(str(artist)) > 50 else ''}`

    **Commands:**
    - `lyrics testkey` - Test your API key
    - `lyrics setkey <key>` - Set new API key  
    - `lyrics toggle` - Toggle fallback mode
    - `lyrics clearcache` - Clear search cache
    - `lyrics threshold <value>` - Set match threshold (0-100)"""

            await ctx.send(debug_msg)
            return
        
        elif subcommand == "clearcache":
            lyrics_cache.clear()
            await ctx.send("# ✅ Cache cleared successfully")
            return
            
        elif subcommand == "threshold":
            if len(parts) < 2:
                current_threshold = get_config_value("match_threshold", 25)
                await ctx.send(f"# Current match threshold: {current_threshold}%\nUsage: `lyrics threshold <0-100>`")
                return
            
            try:
                threshold = float(parts[1])
                if not 0 <= threshold <= 100:
                    raise ValueError("Threshold must be between 0 and 100")
                
                if set_config_value("match_threshold", threshold):
                    await ctx.send(f"# ✅ Match threshold set to {threshold}%")
                else:
                    await ctx.send("# ❌ Failed to save threshold setting")
            except ValueError as e:
                await ctx.send(f"# ❌ Invalid threshold value: {e}")
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
                    # Clear cache when API key changes
                    lyrics_cache.clear()
                else:
                    await msg.edit(content="# ❌ Failed to save API key to config file")
            else:
                await msg.edit(content=f"# ❌ API key validation failed: {validation_msg}")
            return
            
        elif subcommand == "config":
            config = load_config()
            genius_key = config.get("genius_key", "")
            fallback = config.get("use_fallback", True)
            cache_enabled = config.get("cache_enabled", True)
            match_threshold = config.get("match_threshold", 25)
            timeout = config.get("timeout", 15)
            max_retries = config.get("max_retries", 3)
            
            cache_info = f"{len(lyrics_cache)} entries" if cache_enabled else "Disabled"
            
            config_msg = f"""# **Lyrics Configuration**
    **Config File:** `{CONFIG_PATH}`
    **Genius API Key:** {'✅ Set (' + str(len(genius_key)) + ' chars)' if genius_key else '❌ Not set'}
    **Fallback Mode:** {'✅ Enabled' if fallback else '❌ Disabled'}
    **Cache:** {cache_info}
    **Match Threshold:** {match_threshold}%
    **Timeout:** {timeout}s
    **Max Retries:** {max_retries}

    **Commands:**
    - `lyrics setkey <key>` - Set API key
    - `lyrics testkey` - Test current key  
    - `lyrics toggle` - Toggle fallback
    - `lyrics clearcache` - Clear cache
    - `lyrics threshold <value>` - Set match threshold
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

    print("Enhanced Lyrics script loaded successfully", type_="SUCCESS")
    
lyrics()