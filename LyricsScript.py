import asyncio
import json
import aiohttp

CONFIG_PATH = r"%APPDATA%\Nighty Selfbot\data\scripts\json\LyricsConfig.json"

# Load/save config
def load_config():
    try:
        with open(CONFIG_PATH, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return {"genius_key": "", "use_fallback": True}

def save_config(config):
    with open(CONFIG_PATH, "w") as f:
        json.dump(config, f, indent=2)

config = load_config()

# Core lyric-fetching logic
async def fetch_lyrics(bot):
    song = bot.config.get("spotify_song")
    if not song:
        return "# No song currently playing"

    # Try Genius first
    if config.get("genius_key"):
        async with aiohttp.ClientSession() as session:
            headers = {"Authorization": f"Bearer {config['genius_key']}"}
            search_url = f"https://api.genius.com/search?q={song.replace(' ', '%20')}"
            async with session.get(search_url, headers=headers) as resp:
                data = await resp.json()
                try:
                    song_path = data["response"]["hits"][0]["result"]["path"]
                    lyrics_url = f"https://genius.com{song_path}"
                    return f"# Lyrics for {song}: {lyrics_url}"
                except Exception:
                    if not config.get("use_fallback"):
                        return "# Lyrics not found"
    return "# Lyrics not found"

# Commands
async def lyrics_command(ctx):
    lyrics = await fetch_lyrics(ctx.bot)
    await ctx.send(lyrics)
    await ctx.message.delete()

async def lyrics_setkey(ctx, key: str):
    config["genius_key"] = key
    save_config(config)
    await ctx.send(f"# Genius API key saved")
    await ctx.message.delete()

async def lyrics_toggleapi(ctx):
    config["use_fallback"] = not config.get("use_fallback", True)
    save_config(config)
    await ctx.send(f"# Fallback Genius API: {'enabled' if config['use_fallback'] else 'disabled'}")
    await ctx.message.delete()

async def lyrics_config(ctx):
    await ctx.send(f"# Current config:\nGenius Key: {'set' if config.get('genius_key') else 'not set'}\nFallback: {config.get('use_fallback', True)}")
    await ctx.message.delete()
