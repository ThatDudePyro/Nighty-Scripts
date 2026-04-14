def WeatherDynamicValues():
    import requests
    import time

    CACHE_TTL = 300
    DEFAULT_CITY = "Dallas,US"
    DEFAULT_UNITS = "imperial"
    OWM_URL = "https://api.openweathermap.org/data/2.5/weather"

    HELP_TEXT = (
        "```\n"
        "+------------------------------------------+\n"
        "|      Weather Dynamic Values -- Help      |\n"
        "+------------------------------------------+\n"
        "\n"
        "SETUP\n"
        "------------------------------------------\n"
        "1. Get a free API key:\n"
        "   https://openweathermap.org/api\n"
        "   Sign up -> API Keys tab -> copy key\n"
        "   NOTE: New keys take up to 2 hours to activate\n"
        "\n"
        "2. Configure this script:\n"
        "   <p>weatherset YOUR_KEY Dallas,US\n"
        "\n"
        "3. Verify it works:\n"
        "   <p>weathertest\n"
        "\n"
        "COMMANDS\n"
        "------------------------------------------\n"
        "<p>weatherhelp                  This help message\n"
        "<p>weatherset <key> <city>      Set API key + city\n"
        "<p>weathercity <city>           Change city only\n"
        "<p>weatherunits metric          Switch to Celsius\n"
        "<p>weatherunits imperial        Switch to Fahrenheit\n"
        "<p>weathertest                  Test & print current weather\n"
        "\n"
        "CITY FORMAT\n"
        "------------------------------------------\n"
        "Use City,CountryCode format:\n"
        "  Dallas,US  |  London,GB  |  Tokyo,JP\n"
        "  Paris,FR     |  Sydney,AU  |  Berlin,DE\n"
        "\n"
        "DYNAMIC VALUES (for rich presence)\n"
        "------------------------------------------\n"
        "{weather_temp}         ->  72 F\n"
        "{weather_feels_like}   ->  69 F\n"
        "{weather_desc}         ->  clear sky\n"
        "{weather_humidity}     ->  54%\n"
        "{weather_city}         ->  Dallas\n"
        "{weather_full}         ->  Dallas: 72 F, clear sky\n"
        "```"
    )

    _cache = {"data": None, "ts": 0}

    def _cfg(key, fallback=""):
        return getConfigData().get(key, fallback)

    def _unit_symbol():
        return "F" if _cfg("weather_units", DEFAULT_UNITS) == "imperial" else "C"

    def _fetch():
        now = time.time()
        if _cache["data"] and (now - _cache["ts"]) < CACHE_TTL:
            return _cache["data"]

        api_key = _cfg("weather_api_key")
        if not api_key:
            return None

        city = _cfg("weather_city", DEFAULT_CITY)
        units = _cfg("weather_units", DEFAULT_UNITS)

        try:
            resp = requests.get(
                OWM_URL,
                params={"q": city, "appid": api_key, "units": units},
                timeout=10
            )

            if resp.status_code == 401:
                print("[Weather] Invalid API key. Run <p>weatherset to update it.", type_="ERROR")
                return None
            if resp.status_code == 404:
                print(f"[Weather] City '{city}' not found. Run <p>weathercity to change it.", type_="ERROR")
                return None
            if resp.status_code != 200:
                print(f"[Weather] API error {resp.status_code}: {resp.text}", type_="ERROR")
                return None

            data = resp.json()
            _cache["data"] = data
            _cache["ts"] = now
            return data

        except Exception as e:
            print(f"[Weather] Fetch error: {e}", type_="ERROR")
            return None

    if not _cfg("weather_city"):
        updateConfigData("weather_city", DEFAULT_CITY)
    if not _cfg("weather_units"):
        updateConfigData("weather_units", DEFAULT_UNITS)

    def weather_temp():
        data = _fetch()
        if not data:
            return ""
        temp = data.get("main", {}).get("temp", "")
        if temp == "":
            return ""
        return f"{round(temp)} {_unit_symbol()}"

    def weather_feels_like():
        data = _fetch()
        if not data:
            return ""
        feels = data.get("main", {}).get("feels_like", "")
        if feels == "":
            return ""
        return f"{round(feels)} {_unit_symbol()}"

    def weather_desc():
        data = _fetch()
        if not data:
            return ""
        weather_list = data.get("weather", [])
        if not weather_list:
            return ""
        return weather_list[0].get("description", "")

    def weather_humidity():
        data = _fetch()
        if not data:
            return ""
        humidity = data.get("main", {}).get("humidity", "")
        if humidity == "":
            return ""
        return f"{humidity}%"

    def weather_city():
        data = _fetch()
        if not data:
            return ""
        return data.get("name", "")

    def weather_full():
        data = _fetch()
        if not data:
            return ""
        name = data.get("name", "")
        temp = data.get("main", {}).get("temp", "")
        desc_list = data.get("weather", [])
        desc = desc_list[0].get("description", "") if desc_list else ""
        if not name or temp == "":
            return ""
        return f"{name}: {round(temp)} {_unit_symbol()}, {desc}"

    @bot.command(
        name="weatherhelp",
        description="Show the Weather Dynamic Values setup guide and command reference."
    )
    async def cmd_weatherhelp(ctx):
        await ctx.message.delete()
        await ctx.send(HELP_TEXT)

    @bot.command(
        name="weatherset",
        description="Set weather API key and city. Usage: <p>weatherset <api_key> <city>"
    )
    async def cmd_weatherset(ctx, *, args: str):
        await ctx.message.delete()
        parts = args.strip().split(maxsplit=1)
        if len(parts) < 2:
            await ctx.send("Usage: `<p>weatherset <api_key> <city>`\nExample: `<p>weatherset abc123 London,GB`\n\nRun `<p>weatherhelp` for the full setup guide.")
            return
        api_key, city = parts[0], parts[1]
        updateConfigData("weather_api_key", api_key)
        updateConfigData("weather_city", city)
        _cache["data"] = None
        print(f"[Weather] API key and city set. City: {city}", type_="SUCCESS")
        await ctx.send(f"Weather configured. City set to **{city}**.\nRun `<p>weathertest` to verify your API key is working.")

    @bot.command(
        name="weathercity",
        description="Change the weather city. Usage: <p>weathercity <city>"
    )
    async def cmd_weathercity(ctx, *, args: str):
        await ctx.message.delete()
        city = args.strip()
        if not city:
            await ctx.send("Usage: `<p>weathercity <city>`\nExample: `<p>weathercity Tokyo,JP`")
            return
        updateConfigData("weather_city", city)
        _cache["data"] = None
        print(f"[Weather] City updated to: {city}", type_="SUCCESS")
        await ctx.send(f"City updated to **{city}**. Run `<p>weathertest` to verify.")

    @bot.command(
        name="weatherunits",
        description="Set units to metric (Celsius) or imperial (Fahrenheit). Usage: <p>weatherunits <metric|imperial>"
    )
    async def cmd_weatherunits(ctx, *, args: str):
        await ctx.message.delete()
        units = args.strip().lower()
        if units not in ("metric", "imperial"):
            await ctx.send("Usage: `<p>weatherunits metric` or `<p>weatherunits imperial`")
            return
        updateConfigData("weather_units", units)
        _cache["data"] = None
        symbol = "Celsius" if units == "metric" else "Fahrenheit"
        print(f"[Weather] Units set to: {units} ({symbol})", type_="SUCCESS")
        await ctx.send(f"Units set to **{units}** ({symbol}).")

    @bot.command(
        name="weathertest",
        description="Force-fetch weather now and print the result to the Nighty log."
    )
    async def cmd_weathertest(ctx):
        await ctx.message.delete()
        api_key = _cfg("weather_api_key")
        if not api_key:
            await ctx.send("No API key set. Run `<p>weatherset <api_key> <city>` to get started.\n\nDon't have a key? Get one free at: **https://openweathermap.org/api**")
            return
        _cache["data"] = None
        result = weather_full()
        if result:
            print(f"[Weather] Test OK -> {result}", type_="SUCCESS")
            await ctx.send(f"**{result}**\n\nAll dynamic values are working.")
        else:
            city = _cfg("weather_city", DEFAULT_CITY)
            print("[Weather] Test FAILED. Check API key and city.", type_="ERROR")
            await ctx.send(
                f"Weather fetch failed for **{city}**.\n\n"
                "Possible causes:\n"
                "- API key is invalid or not yet activated (can take up to 2 hours after signup)\n"
                "- City not found -- try format `City,CountryCode` e.g. `London,GB`\n\n"
                "Run `<p>weatherhelp` for the full setup guide."
            )

    addDRPCValue("weather_temp",       weather_temp)
    addDRPCValue("weather_feels_like", weather_feels_like)
    addDRPCValue("weather_desc",       weather_desc)
    addDRPCValue("weather_humidity",   weather_humidity)
    addDRPCValue("weather_city",       weather_city)
    addDRPCValue("weather_full",       weather_full)


WeatherDynamicValues()