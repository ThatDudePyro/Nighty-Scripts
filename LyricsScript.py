import os
import re
import json
import asyncio
from pathlib import Path

import aiohttp

# ------------------------------
# Config persistence
# ------------------------------
CONFIG_PATH = os.path.expandvars(
    r"%APPDATA%\Nighty Selfbot\data\scripts\json\LyricsConfig.json"
)

def _ensure_config_dir():
    Path(os.path.dirname(CONFIG_PATH)).mkdir(parents=True, exist_ok=True)

def load_config():
    _ensure_config_dir()
    if os.path.isfile(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                if not isinstance(data, dict):
                    data = {}
        except Exception:
            data = {}
    else:
        data = {}

    # defaults
    data.setdefault("genius_api_key", "")
    data.setdefault("use_genius", True)
    return data

def save_config(cfg):
    _ensure_config_dir()
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2)


# ------------------------------
# Helpers
# ------------------------------
def _chunk(text, size=1900):
    # 1900 to leave room for code fences / headers
    buf = []
    cur = []
    total = 0
    for line in text.splitlines():
        # keep line endings consistent
        candidate = (line + "\n")
        if total + len(candidate) > size and cur:
            buf.append("".join(cur))
            cur = [candidate]
            total = len(candidate)
        else:
            cur.append(candidate)
            total += len(candidate)
    if cur:
        buf.append("".join(cur))
    return buf or ["(no lyrics found)"]

def _clean_title(s):
    # remove things like " - Remastered", "(feat. X)", etc. (light touch)
    s = re.sub(r"\s*-\s*(Remaster(?:ed)?\s*\d{2,4}?|Live.*|Single|Radio Edit).*", "", s, flags=re.I)
    s = re.sub(r"\s*\(feat\..*\)", "", s, flags=re.I)
    s = re.sub(r"\s*\[feat\..*\]", "", s, flags=re.I)
    return s.strip()

def _parse_song_arg(arg: str):
    # supports "Title | Artist" OR "Title by Artist"
    if "|" in arg:
        t, a = arg.split("|", 1)
        return t.strip(), a.strip()
    m = re.match(r"(.+?)\s+by\s+(.+)$", arg, flags=re.I)
    if m:
        return m.group(1).strip(), m.group(2).strip()
    return arg.strip(), ""


# ------------------------------
# Spotify Now Playing (multiple fallbacks)
# ------------------------------
def _try_nighty_spotify():
    """
    Try a few common Nighty helpers if present in the environment.
    We don't know the exact API, so we defensively probe a few names.
    Expect a dict like: {"title": "...", "artist": "..."} or similar.
    """
    candidate_funcs = [
        "getSpotifyInfo", "get_spotify_info",
        "nightySpotifyNowPlaying", "nighty_spotify_nowplaying",
        "spotify_now_playing", "spotifyNowPlaying"
    ]
    for name in candidate_funcs:
        fn = globals().get(name)
        if callable(fn):
            try:
                data = fn()
                if isinstance(data, dict):
                    # normalize common keys
                    title = data.get("title") or data.get("track") or data.get("song")
                    artist = data.get("artist") or data.get("artists") or data.get("author")
                    if isinstance(artist, list):
                        artist = ", ".join(artist)
                    if title and artist:
                        return _clean_title(str(title)), str(artist)
            except Exception:
                continue
    return None

async def _try_discord_presence(ctx):
    """
    Fallback: scan user's activities for a Spotify presence.
    Works in many selfbot contexts.
    """
    try:
        me = ctx.author
        for act in getattr(me, "activities", []) or []:
            # Discord.py represents Spotify as an activity with attributes .title and .artists
            t = getattr(act, "title", None)
            arts = getattr(act, "artists", None)
            if t and arts:
                if isinstance(arts, (list, tuple)):
                    artist = ", ".join(arts)
                else:
                    artist = str(arts)
                return _clean_title(str(t)), str(artist)
    except Exception:
        pass
    return None

async def get_current_track(ctx):
    """
    Returns (title, artist) or (None, None)
    Order:
      1) Nighty helper if available
      2) Discord presence fallback
    """
    tup = _try_nighty_spotify()
    if tup:
        return tup
    tup = await _try_discord_presence(ctx)
    if tup:
        return tup
    return (None, None)


# ------------------------------
# Lyrics providers
# ------------------------------
async def fetch_lyrics_some_random_api(session, title, artist):
    # Free endpoint: https://some-random-api.com/lyrics?title={query}
    # We'll query "title artist" together.
    q = f"{title} {artist}".strip()
    url = f"https://some-random-api.com/lyrics?title={aiohttp.helpers.quote(q)}"
    try:
        async with session.get(url, timeout=15) as r:
            if r.status != 200:
                return None
            data = await r.json()
            lyrics = data.get("lyrics")
            if lyrics and isinstance(lyrics, str):
                return lyrics.strip()
    except Exception:
        pass
    return None

async def fetch_lyrics_ovh(session, title, artist):
    # https://api.lyrics.ovh/v1/{artist}/{title}
    if not artist:
        return None
    url = f"https://api.lyrics.ovh/v1/{aiohttp.helpers.quote(artist)}/{aiohttp.helpers.quote(title)}"
    try:
        async with session.get(url, timeout=15) as r:
            if r.status != 200:
                return None
            data = await r.json()
            lyrics = data.get("lyrics")
            if lyrics and isinstance(lyrics, str):
                return lyrics.strip()
    except Exception:
        pass
    return None

async def fetch_lyrics_genius(session, title, artist, token):
    """
    Genius API search -> scrape lyrics from the song URL.
    Requires token (Bearer).
    Note: we keep parsing light to reduce deps (no bs4).
    """
    if not token:
        return None

    # 1) Search
    q = f"{title} {artist}".strip()
    search_url = "https://api.genius.com/search"
    headers = {"Authorization": f"Bearer {token}"}
    try:
        async with session.get(search_url, params={"q": q}, headers=headers, timeout=15) as r:
            if r.status != 200:
                return None
            data = await r.json()
            hits = (data.get("response") or {}).get("hits") or []
            if not hits:
                return None
            # pick the top hit
            url = ((hits[0] or {}).get("result") or {}).get("url")
            if not url:
                return None
    except Exception:
        return None

    # 2) Fetch page & naive-parse lyrics
    try:
        async with session.get(url, timeout=15) as r:
            if r.status != 200:
                return None
            html = await r.text()
    except Exception:
        return None

    # Genius has multiple render variants. Try a couple of simple patterns:
    # (a) data-lyrics-container="true" blocks
    blocks = re.findall(r'<div[^>]+data-lyrics-container="true"[^>]*>(.*?)</div>', html, flags=re.S|re.I)
    if blocks:
        # strip tags
        joined = []
        for b in blocks:
            # replace <br/> with newlines, remove other tags
            b = re.sub(r"<br\s*/?>", "\n", b, flags=re.I)
            b = re.sub(r"<[^>]+>", "", b)
            joined.append(b)
        text = "\n".join(joined).strip()
        if text:
            return text

    # (b) fallback: try to pull from plain text between <lyrics> noise (very rough)
    text = re.sub(r"<script.*?</script>|<style.*?</style>", "", html, flags=re.S|re.I)
    m = re.search(r"(?i)Lyrics\s*\n(.*?)\n\s*Embed", text, flags=re.S)
    if m:
        rough = re.sub(r"<[^>]+>", "", m.group(1))
        rough = re.sub(r"\r", "", rough)
        rough = re.sub(r"\n{3,}", "\n\n", rough)
        return rough.strip() or None

    return None


# ------------------------------
# Command registration
# ------------------------------
async def lyrics_logic():
    cfg = load_config()

    async def do_fetch_and_send(ctx, title, artist):
        title = _clean_title(title or "")
        artist = (artist or "").strip()
        if not title:
            await ctx.send("❌ I need a song title to search for lyrics.")
            return

        # Small "searching" notice
        status_msg = await ctx.send(f"🔎 Searching lyrics for **{title}** by **{artist or 'Unknown'}** ...")

        async with aiohttp.ClientSession() as session:
            text = await fetch_lyrics_some_random_api(session, title, artist)
            if not text:
                text = await fetch_lyrics_ovh(session, title, artist)
            if not text and cfg.get("use_genius", True):
                text = await fetch_lyrics_genius(session, title, artist, cfg.get("genius_api_key", ""))

        if not text:
            await status_msg.edit(content=f"❌ No lyrics found for **{title}**{(' by **' + artist + '**') if artist else ''}.")
            return

        header = f"🎵 **{title}**" + (f" — **{artist}**" if artist else "")
        chunks = _chunk(text, size=1850)  # leave headroom for header/formatting

        # edit first message with header + first chunk
        first = f"{header}\n\n{chunks[0]}"
        await status_msg.edit(content=first if len(first) <= 2000 else chunks[0])

        # send remaining chunks
        for c in chunks[1:]:
            await ctx.send(c)

    @bot.command(
        name="lyrics",
        description="Fetch lyrics for the current Spotify song, or a specific song via 'lyrics song <title> | <artist>'."
    )
    async def lyrics_cmd(ctx, *args):
        # auto-delete trigger
        try:
            await ctx.message.delete()
        except Exception:
            pass

        # subcommands
        if args:
            sub = args[0].lower()
            rest = " ".join(args[1:]).strip()

            if sub == "song":
                if not rest:
                    await ctx.send("Usage: `<p>lyrics song <title> | <artist>` or `<p>lyrics song <title> by <artist>`")
                    return
                t, a = _parse_song_arg(rest)
                await do_fetch_and_send(ctx, t, a)
                return

            if sub == "setkey":
                token = rest
                if not token:
                    await ctx.send("Usage: `<p>lyrics setkey <GENIUS_TOKEN>`")
                    return
                cfg["genius_api_key"] = token.strip()
                save_config(cfg)
                await ctx.send("✅ Genius API key saved.")
                return

            if sub in ("togglegenius", "togglegen"):
                cfg["use_genius"] = not cfg.get("use_genius", True)
                save_config(cfg)
                await ctx.send(f"✅ Genius fallback is now **{'ENABLED' if cfg['use_genius'] else 'DISABLED'}**.")
                return

            if sub == "config":
                masked = "••••••••" if cfg.get("genius_api_key") else "(none)"
                await ctx.send(
                    "🛠 **Lyrics Config**\n"
                    f"- Genius fallback: **{'ON' if cfg.get('use_genius', True) else 'OFF'}**\n"
                    f"- Genius API key: **{masked}**\n"
                    f"- Config path: `{CONFIG_PATH}`"
                )
                return

        # default: use Spotify current song
        title, artist = await get_current_track(ctx)
        if not title:
            await ctx.send("❌ I couldn't detect a Spotify song. Start playing on Spotify, or use: `<p>lyrics song <title> | <artist>`")
            return

        await do_fetch_and_send(ctx, title, artist)

# Register
asyncio.create_task(lyrics_logic())
