def SpotifyLyrics():
    import asyncio
    import aiohttp
    import json
    import os
    import re
    import time
    from pathlib import Path
    from typing import Dict, List, Tuple, Optional, Any
    from datetime import datetime

    CONFIG_PATH = Path(os.path.expandvars(r"%APPDATA%\Nighty Selfbot\data\scripts\json\LyricsConfig.json"))
    lyrics_cache: Dict[str, Dict[str, Any]] = {}
    CACHE_EXPIRY = 2592000
    CACHE_FILE = CONFIG_PATH.parent / "LyricsCache.json"
    SCRIPT_NAME = "SpotifyLyrics"

    async def run_in_thread(func, *args, **kwargs):
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, lambda: func(*args, **kwargs))

    def load_cache() -> Dict[str, Any]:
        nonlocal lyrics_cache
        try:
            if CACHE_FILE.exists():
                with open(CACHE_FILE, 'r', encoding='utf-8') as f:
                    lyrics_cache = json.load(f)
                    current_time = time.time()
                    lyrics_cache = {k: v for k, v in lyrics_cache.items() 
                                  if current_time - v.get("timestamp", 0) < CACHE_EXPIRY}
            return lyrics_cache
        except Exception as e:
            print(f"[{SCRIPT_NAME}] Cache load error: {e}", type_="ERROR")
            lyrics_cache = {}
            return lyrics_cache

    def save_cache() -> None:
        try:
            CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
            with open(CACHE_FILE, 'w', encoding='utf-8') as f:
                json.dump(lyrics_cache, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"[{SCRIPT_NAME}] Cache save error: {e}", type_="ERROR")

    def load_config() -> Dict[str, Any]:
        try:
            CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
            
            if CONFIG_PATH.exists():
                with open(CONFIG_PATH, "r", encoding='utf-8') as f:
                    config = json.load(f)
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
            print(f"[{SCRIPT_NAME}] Config load error: {e}", type_="ERROR")
            return {
                "genius_key": "", 
                "use_fallback": True, 
                "cache_enabled": True,
                "max_retries": 3,
                "timeout": 15,
                "match_threshold": 25
            }

    def save_config(config: Dict[str, Any]) -> bool:
        try:
            CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
            temp_path = CONFIG_PATH.with_suffix('.tmp')
            with open(temp_path, "w", encoding='utf-8') as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
            temp_path.replace(CONFIG_PATH)
            return True
        except Exception as e:
            print(f"[{SCRIPT_NAME}] Config save error: {e}", type_="ERROR")
            return False

    def get_config_value(key: str, default: Any = None) -> Any:
        config = load_config()
        return config.get(key, default)

    def set_config_value(key: str, value: Any) -> bool:
        config = load_config()
        
        if not isinstance(value, str):
            if key == "timeout" and (not isinstance(value, (int, float)) or value <= 0):
                return False
            if key == "max_retries" and (not isinstance(value, int) or value < 0):
                return False
            if key == "match_threshold" and (not isinstance(value, (int, float)) or not 0 <= value <= 100):
                return False
        
        config[key] = value
        return save_config(config)

    def clean_song_title(title: str) -> str:
        if not title:
            return ""
        
        title = re.sub(r'\s*\(.*?\)\s*', ' ', title)
        title = re.sub(r'\s*\[.*?\]\s*', ' ', title) 
        title = re.sub(r'\s*-\s*(feat|ft|featuring).*', '', title, flags=re.IGNORECASE)
        title = re.sub(r'\s*-\s*remaster.*', '', title, flags=re.IGNORECASE)
        title = re.sub(r'\s*-\s*radio edit.*', '', title, flags=re.IGNORECASE)
        title = re.sub(r'\s+', ' ', title).strip()
        return title

    async def test_genius_api_key(api_key: str) -> Tuple[bool, str]:
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
                                await asyncio.sleep(2 ** attempt)
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
        if not str1 or not str2:
            return 0.0
            
        str1 = str1.lower().strip()
        str2 = str2.lower().strip()
        
        if str1 == str2:
            return 100.0
        
        if str1 in str2 or str2 in str1:
            shorter = min(len(str1), len(str2))
            longer = max(len(str1), len(str2))
            return min(95.0, (shorter / longer) * 100)
        
        words1 = set(str1.split())
        words2 = set(str2.split())
        
        if not words1 or not words2:
            return 0.0
        
        intersection = len(words1.intersection(words2))
        union = len(words1.union(words2))
        jaccard = intersection / union
        
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
        if not hits:
            return None, 0.0
        
        clean_title = clean_song_title(song_title)
        clean_artist = artist_name.strip() if artist_name else ""
        best_match = None
        best_score = 0.0
        match_threshold = get_config_value("match_threshold", 25)
        
        for i, hit in enumerate(hits[:10]):
            result = hit.get("result", {})
            genius_title = result.get("title", "")
            genius_artist = result.get("primary_artist", {}).get("name", "")
            clean_genius_title = clean_song_title(genius_title)
            
            title_score = calculate_similarity(clean_title, clean_genius_title)
            artist_score = calculate_similarity(clean_artist, genius_artist) if clean_artist else 50.0
            combined_score = (title_score * 0.75) + (artist_score * 0.25)
            
            if combined_score > best_score and combined_score >= match_threshold:
                best_score = combined_score
                best_match = result
        
        return best_match, best_score

    def get_cache_key(song: str, artist: str) -> str:
        return f"{song.lower().strip()}|{artist.lower().strip() if artist else ''}"

    def is_cache_valid(cache_entry: Dict[str, Any]) -> bool:
        return time.time() - cache_entry.get("timestamp", 0) < CACHE_EXPIRY

    async def get_from_cache(song: str, artist: str) -> Optional[str]:
        if not get_config_value("cache_enabled", True):
            return None
        
        if not lyrics_cache:
            await run_in_thread(load_cache)
        
        cache_key = get_cache_key(song, artist)
        if cache_key in lyrics_cache and is_cache_valid(lyrics_cache[cache_key]):
            return lyrics_cache[cache_key]["result"]
        return None

    async def save_to_cache(song: str, artist: str, result: str) -> None:
        if not get_config_value("cache_enabled", True):
            return
        
        cache_key = get_cache_key(song, artist)
        lyrics_cache[cache_key] = {
            "result": result,
            "timestamp": time.time(),
            "song": song,
            "artist": artist
        }
        
        if len(lyrics_cache) > 500:
            oldest_keys = sorted(lyrics_cache.keys(), 
                               key=lambda k: lyrics_cache[k]["timestamp"])[:50]
            for key in oldest_keys:
                del lyrics_cache[key]
        
        await run_in_thread(save_cache)

    async def fetch_lyrics(bot) -> str:
        try:
            if not hasattr(bot, 'config'):
                return "# Bot configuration not available"
                
            song = bot.config.get("spotify_song")
            artist = bot.config.get("spotify_artist", "")
            
            if not song:
                return "# No song currently playing"

            song = song.strip()
            artist = artist.strip() if artist else ""
            display_info = f"**`{song}`**" + (f" by **`{artist}`**" if artist else "")

            cached_result = await get_from_cache(song, artist)
            if cached_result:
                return cached_result

            genius_key = get_config_value("genius_key", "")
            
            if genius_key:
                try:
                    clean_title = clean_song_title(song)
                    search_query = clean_title
                    if artist:
                        search_query += f" {artist}"
                    
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
                                                match_info = f"`{genius_title}` by `{genius_artist}`\n(Match: `{best_score:.1f}%`)"
                                                result = f"Lyrics for:\n{display_info}\n**Found:**\n{match_info}\n{lyrics_url}"
                                                
                                                await save_to_cache(song, artist, result)
                                                return result
                                            else:
                                                error_msg = f"No good matches found for {display_info}\nTry checking the song/artist spelling"
                                                result = f"# {error_msg}"
                                                await save_to_cache(song, artist, result)
                                                return result
                                        else:
                                            error_msg = f"No search results for:\n{display_info}"
                                            result = f"# {error_msg}"
                                            await save_to_cache(song, artist, result)
                                            return result
                                    elif resp.status == 429:
                                        if attempt < max_retries - 1:
                                            wait_time = 2 ** attempt
                                            await asyncio.sleep(wait_time)
                                            continue
                                        return "# Rate limited - try again later"
                                    else:
                                        return f"# Genius API error: HTTP {resp.status}"
                            break
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

            use_fallback = get_config_value("use_fallback", True)
            
            if use_fallback:
                search_query = song
                if artist:
                    search_query += f" {artist}"
                search_encoded = search_query.replace(' ', '+').replace('&', '%26')
                fallback_url = f"https://genius.com/search?q={search_encoded}"
                result = f"# Search lyrics for {display_info}\n{fallback_url}"
                await save_to_cache(song, artist, result)
                return result
            
            return "# Lyrics not found - enable fallback mode to get search links"
            
        except Exception as e:
            print(f"[{SCRIPT_NAME}] Critical error: {e}", type_="ERROR")
            return f"# Critical error: {str(e)}"

    @bot.command(
        name="lyrics",
        aliases=["ly", "lyric"],
        usage="[subcommand] [args]"
    )
    async def lyrics_command(ctx, *, args: str = ""):
        await ctx.message.delete()
        
        args = args.strip()
        parts = args.split(maxsplit=1) if args else []
        subcommand = parts[0].lower() if parts else ""
        subargs = parts[1] if len(parts) > 1 else ""
        
        if subcommand == "config":
            config = load_config()
            genius_key = config.get("genius_key", "")
            fallback = config.get("use_fallback", True)
            cache_enabled = config.get("cache_enabled", True)
            match_threshold = config.get("match_threshold", 25)
            timeout = config.get("timeout", 15)
            max_retries = config.get("max_retries", 3)
            
            if cache_enabled and not lyrics_cache:
                await run_in_thread(load_cache)
            
            cache_info = f"{len(lyrics_cache)} entries" if cache_enabled else "Disabled"
            
            config_msg = f"""# **Lyrics Configuration**

**Config File:** `{CONFIG_PATH}`
**Cache File:** `{CACHE_FILE}`

**Settings:**
- API Key: {'✅ Set (' + str(len(genius_key)) + ' chars)' if genius_key else '❌ Not set'}
- Fallback Mode: {'✅ Enabled' if fallback else '❌ Disabled'}
- Cache: {cache_info} (30-day expiry)
- Match Threshold: {match_threshold}%
- Timeout: {timeout}s
- Max Retries: {max_retries}

Use `lyrics help` for available commands."""
            
            await ctx.send(config_msg)
            return
        
        elif subcommand == "help":
            help_msg = f"""# **Lyrics Command Help**

**Basic Usage:**
`lyrics` - Fetch lyrics for currently playing song

**Configuration:**
`lyrics config` - Show current configuration
`lyrics setkey <api_key>` - Set Genius API key
`lyrics testkey` - Test your API key validity
`lyrics toggle` - Toggle fallback mode
`lyrics threshold <0-100>` - Set match threshold
`lyrics timeout <seconds>` - Set request timeout
`lyrics retries <count>` - Set max retry attempts

**Cache Management:**
`lyrics clearcache` - Clear all cached results

**Get API Key:** <https://genius.com/api-clients>"""

            await ctx.send(help_msg)
            return
        
        elif subcommand == "clearcache":
            entry_count = len(lyrics_cache)
            lyrics_cache.clear()
            try:
                if CACHE_FILE.exists():
                    await run_in_thread(CACHE_FILE.unlink)
                await ctx.send(f"# ✅ Cache cleared ({entry_count} entries)")
            except Exception as e:
                await ctx.send(f"# ⚠️ Cache cleared from memory (file error: {e})")
            return
            
        elif subcommand == "threshold":
            if not subargs:
                current_threshold = get_config_value("match_threshold", 25)
                await ctx.send(f"# Current match threshold: {current_threshold}%\nUsage: `lyrics threshold <0-100>`")
                return
            
            try:
                threshold = float(subargs)
                if not 0 <= threshold <= 100:
                    raise ValueError("Threshold must be between 0 and 100")
                
                if set_config_value("match_threshold", threshold):
                    await ctx.send(f"# ✅ Match threshold set to {threshold}%")
                else:
                    await ctx.send("# ❌ Failed to save threshold setting")
            except ValueError as e:
                await ctx.send(f"# ❌ Invalid threshold value: {e}")
            return
        
        elif subcommand == "timeout":
            if not subargs:
                current_timeout = get_config_value("timeout", 15)
                await ctx.send(f"# Current timeout: {current_timeout}s\nUsage: `lyrics timeout <seconds>`")
                return
            
            try:
                timeout_val = float(subargs)
                if timeout_val <= 0:
                    raise ValueError("Timeout must be positive")
                
                if set_config_value("timeout", timeout_val):
                    await ctx.send(f"# ✅ Timeout set to {timeout_val}s")
                else:
                    await ctx.send("# ❌ Failed to save timeout setting")
            except ValueError as e:
                await ctx.send(f"# ❌ Invalid timeout value: {e}")
            return
        
        elif subcommand == "retries":
            if not subargs:
                current_retries = get_config_value("max_retries", 3)
                await ctx.send(f"# Current max retries: {current_retries}\nUsage: `lyrics retries <count>`")
                return
            
            try:
                retries = int(subargs)
                if retries < 0:
                    raise ValueError("Retries must be non-negative")
                
                if set_config_value("max_retries", retries):
                    await ctx.send(f"# ✅ Max retries set to {retries}")
                else:
                    await ctx.send("# ❌ Failed to save retries setting")
            except ValueError as e:
                await ctx.send(f"# ❌ Invalid retries value: {e}")
            return
        
        elif subcommand == "testkey":
            genius_key = get_config_value("genius_key", "")
            if not genius_key:
                await ctx.send("# ❌ No API key configured. Use `lyrics setkey <your_key>`")
                return
            
            msg = await ctx.send("# 🔑 Testing Genius API key...")
            is_valid, validation_msg = await test_genius_api_key(genius_key)
            
            if is_valid:
                await msg.edit(content="# ✅ API key is valid and working!")
            else:
                await msg.edit(content=f"# ❌ API key test failed: {validation_msg}")
            return
        
        elif subcommand == "setkey":
            if not subargs:
                await ctx.send("# Usage: `lyrics setkey <your_genius_api_key>`\n*Get a key at: https://genius.com/api-clients*")
                return
                
            api_key = subargs.strip()
            if len(api_key) < 20:
                await ctx.send("# ❌ Invalid API key format - too short")
                return
            
            msg = await ctx.send("# 🔑 Testing new API key...")
            is_valid, validation_msg = await test_genius_api_key(api_key)
            
            if is_valid:
                if set_config_value("genius_key", api_key):
                    await msg.edit(content="# ✅ Genius API key saved and validated!")
                    lyrics_cache.clear()
                else:
                    await msg.edit(content="# ❌ Failed to save API key to config file")
            else:
                await msg.edit(content=f"# ❌ API key validation failed: {validation_msg}")
            return
            
        elif subcommand == "toggle":
            current_fallback = get_config_value("use_fallback", True)
            new_fallback = not current_fallback
            
            if set_config_value("use_fallback", new_fallback):
                status = "enabled" if new_fallback else "disabled"
                await ctx.send(f"# ✅ Fallback mode {status}")
            else:
                await ctx.send("# ❌ Failed to update fallback setting")
            return
            
        else:
            try:
                msg = await ctx.send("# 🎵 Fetching lyrics...")
                lyrics_result = await fetch_lyrics(ctx.bot)
                await msg.edit(content=lyrics_result)
            except Exception as e:
                print(f"[{SCRIPT_NAME}] Command error: {e}", type_="ERROR")
                await ctx.send(f"# ❌ Command error: {str(e)}")

    load_cache()

SpotifyLyrics()