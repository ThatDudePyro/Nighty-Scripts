@nightyScript(
    name="ScriptUtils",
    author="0pyr",
    description="Send and download scripts. Original authors: Luxed, bnly",
    usage="<p>scriptutils | <p>sendscript <name> | <p>downloadscript (off)"
)
def ScriptUtils():
    import asyncio
    import difflib
    from pathlib import Path
    import aiohttp
    import traceback
    import io
    import os
    import json
    import re

    SCRIPTS_DIR = Path(getScriptsPath())
    try:
        appdata_path = os.getenv('APPDATA') or os.path.join(os.path.expanduser('~'), '.config')
        if 'local' in appdata_path.lower():
            appdata_path = Path(appdata_path).parent / 'Roaming'
        MISC_DATA_DIR = Path(appdata_path) / 'Nighty Selfbot' / 'data' / 'misc'
        SCRIPTS_JSON_PATH = MISC_DATA_DIR / 'scripts.json'
        os.makedirs(MISC_DATA_DIR, exist_ok=True)
    except Exception as e:
        print(f"[ScriptUtils] Could not define path to scripts.json: {e}", type_="ERROR")
        SCRIPTS_JSON_PATH = None

    # --- ANSI color palette
    RESET = "\u001b[0m"
    HEADER = "\u001b[38;5;51m"    # bright cyan
    CMD = "\u001b[38;5;213m"      # bright pink/magenta
    SUCCESS = "\u001b[38;5;46m"   # bright green
    ERROR = "\u001b[38;5;196m"    # bright red
    WARN = "\u001b[38;5;226m"     # bright yellow

    def _c(text, color):
        return f"{color}{text}{RESET}"

    def _block(text):
        return f"```ansi\n{text}\n```"

    async def _handle_error(ctx, status_msg=None):
        tb = traceback.format_exc()
        print(f"[ScriptUtils] Error:\n{tb}", type_="ERROR")
        header = _c("An unexpected error occurred. Full traceback below:", ERROR)
        if len(tb) > 1900:
            f = discord.File(fp=io.BytesIO(tb.encode('utf-8')), filename="error.txt")
            content = f"{header}\n{_c('The error was too long and has been sent as a file.', WARN)}"
            if status_msg:
                await status_msg.edit(content=content, attachments=[f], delete_after=60)
            else:
                await ctx.send(content=content, file=f, delete_after=60)
        else:
            content = f"{header}\n```python\n{tb}\n```"
            if status_msg:
                await status_msg.edit(content=content, delete_after=60)
            else:
                await ctx.send(content=content, delete_after=60)

    def _get_enabled_scripts():
        if not SCRIPTS_JSON_PATH or not os.path.exists(SCRIPTS_JSON_PATH):
            return None
        try:
            with open(SCRIPTS_JSON_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data.get("enabled", [])
        except (IOError, json.JSONDecodeError):
            return None

    async def _update_scripts_json(script_name: str, status_msg):
        if not SCRIPTS_JSON_PATH or not os.path.exists(SCRIPTS_JSON_PATH):
            await status_msg.edit(content=_block(_c("Warning: scripts.json not found. Skipping auto-enable.", WARN)), delete_after=15)
            return False
        try:
            with open(SCRIPTS_JSON_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            if script_name not in data.get("enabled", []):
                await status_msg.edit(content=_block(_c(f"Enabling {script_name} in configuration...", WARN)))
                data.setdefault("enabled", []).append(script_name)
                with open(SCRIPTS_JSON_PATH, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=4)
            return True
        except (IOError, json.JSONDecodeError) as e:
            await status_msg.edit(content=_block(_c(f"Error processing scripts.json: {e}", ERROR)), delete_after=15)
            print(f"[ScriptUtils] Failed to read or write scripts.json: {e}", type_="ERROR")
            return False

    async def _resolve_conflict(ctx, status_msg, filename):
        file_path = SCRIPTS_DIR / filename
        if not file_path.exists():
            return filename, file_path
        prompt = (
            f"{_c(filename, WARN)} already exists.\n"
            f"Reply {_c('replace', CMD)} to overwrite it, send a new filename to save it as instead, "
            f"or {_c('cancel', CMD)} to abort. (30s to respond)"
        )
        if status_msg:
            await status_msg.edit(content=_block(prompt))
        else:
            status_msg = await ctx.send(_block(prompt))

        def check(m):
            return m.author.id == ctx.author.id and m.channel.id == ctx.channel.id

        try:
            reply = await bot.wait_for("message", check=check, timeout=30)
        except asyncio.TimeoutError:
            await status_msg.edit(content=_block(_c("Timed out waiting for a response. Download cancelled.", ERROR)), delete_after=15)
            return None, None
        try:
            await reply.delete()
        except Exception:
            pass
        answer = reply.content.strip()
        if answer.lower() == "cancel":
            await status_msg.edit(content=_block(_c("Download cancelled.", WARN)), delete_after=15)
            return None, None
        if answer.lower() == "replace":
            return filename, file_path
        new_name = answer[:-3] if answer.endswith(".py") else answer
        new_filename = new_name + ".py"
        return new_filename, SCRIPTS_DIR / new_filename

    @bot.command(
        name="scriptutils",
        aliases=["su"],
        description="Shows all ScriptUtils commands."
    )
    async def _scriptutils(ctx):
        try:
            await ctx.message.delete()
        except Exception:
            pass
        p = getConfigData().get("prefix", "<p>")
        lines = [
            _c("ScriptUtils", HEADER),
            f"{_c(p + 'sendscript <name>', CMD)} — send a script to this channel (reply to send to DMs)",
            f"{_c(p + 'sendscript list', CMD)} — list enabled scripts",
            f"{_c(p + 'sendscript listall', CMD)} — list all installed scripts",
            f"{_c(p + 'sendscript', CMD)} — sendscript help",
            f"{_c(p + 'downloadscript', CMD)} — downloadscript help",
            f"{_c(p + 'scriptutils', CMD)} — show this message",
        ]
        await ctx.send(_block("\n".join(lines)))

    @bot.command(
        name="sendscript",
        aliases=["ss"],
        description="Sends a script file to the current channel."
    )
    async def _sendscript(ctx, script_name: str = None):
        try:
            await ctx.message.delete()
        except Exception:
            pass
        available = sorted([f[:-3] for f in os.listdir(SCRIPTS_DIR) if f.endswith(".py")])
        if not script_name:
            p = getConfigData().get("prefix", "<p>")
            lines = [
                _c("sendscript", HEADER),
                f"{_c(p + 'sendscript <name>', CMD)} — send a script to this channel (reply to send to DMs)",
                f"{_c(p + 'sendscript list', CMD)} — list enabled scripts",
                f"{_c(p + 'sendscript listall', CMD)} — list all installed scripts",
                f"alias: {_c(p + 'ss', CMD)}",
            ]
            await ctx.send(_block("\n".join(lines)))
            return
        if script_name.lower() in ("list", "listall"):
            show_all = script_name.lower() == "listall"
            enabled = _get_enabled_scripts()
            if show_all:
                listing = available
            else:
                if enabled is None:
                    await ctx.send(_block(_c("Could not read scripts.json to determine enabled scripts.", ERROR)))
                    return
                enabled_lower = set(e.lower() for e in enabled)
                listing = [s for s in available if s.lower() in enabled_lower]
            if not listing:
                await ctx.send(_block(_c("No scripts found." if show_all else "No enabled scripts found.", WARN)))
                return
            enabled_lower = set(e.lower() for e in enabled) if enabled else set()
            col_width = max(len(s) for s in listing) + 2
            cols = 4 if col_width <= 20 else 3
            rows = []
            for i in range(0, len(listing), cols):
                row = listing[i:i + cols]
                line = ""
                for s in row:
                    padded = s.ljust(col_width)
                    if show_all and s.lower() in enabled_lower:
                        line += _c(padded, SUCCESS)
                    elif show_all:
                        line += padded
                    else:
                        line += _c(padded, SUCCESS)
                rows.append(line)
            grid = "\n".join(rows)
            label = "All Scripts" if show_all else "Enabled Scripts"
            header = _c(f"{label} ({len(listing)})", HEADER)
            await ctx.send(_block(header + "\n" + grid))
            return
        if script_name.endswith(".py"):
            script_name = script_name[:-3]
        script_path = os.path.join(SCRIPTS_DIR, f"{script_name}.py")
        if not os.path.exists(script_path):
            matches = difflib.get_close_matches(script_name.lower(), [s.lower() for s in available], n=5, cutoff=0.4)
            similar = [s for s in available if s.lower() in matches]
            if not similar:
                similar = [s for s in available if script_name.lower() in s.lower()]
            if similar:
                suggestion_list = ", ".join([_c(s, WARN) for s in similar])
                msg = _block(f"Script {_c(script_name, WARN)} not found. Did you mean: {suggestion_list}?")
            else:
                msg = _block(f"Script {_c(script_name, WARN)} not found.")
            await ctx.send(msg)
            showToast(text=f"Script {script_name} not found.", type_="ERROR", title="ScriptUtils")
            return
        try:
            if ctx.message.reference and ctx.message.reference.message_id:
                replied = await ctx.channel.fetch_message(ctx.message.reference.message_id)
                target = replied.author
                dm = await target.create_dm()
                with open(script_path, "rb") as f:
                    await dm.send(
                        content=f"> **Script:** `{script_name}.py`",
                        file=discord.File(f, f"{script_name}.py")
                    )
                showToast(text=f"Script {script_name} sent to {target.name}'s DMs.", type_="SUCCESS", title="ScriptUtils")
            else:
                with open(script_path, "rb") as f:
                    await ctx.channel.send(
                        content=f"> **Script:** `{script_name}.py`",
                        file=discord.File(f, f"{script_name}.py")
                    )
                showToast(text=f"Script {script_name} posted in #{ctx.channel.name}.", type_="SUCCESS", title="ScriptUtils")
        except Exception as e:
            showToast(text=f"Failed to send script: {e}", type_="ERROR", title="ScriptUtils")

    @bot.command(
        name="downloadscript",
        aliases=["dls"],
        description="Downloads a .py or .txt attachment from a replied message into the scripts folder as a .py file."
    )
    async def _dls(ctx, *, args: str = None):
        await ctx.message.delete()
        status_msg = None
        if not (ctx.message.reference and ctx.message.reference.message_id):
            p = getConfigData().get("prefix", "<p>")
            lines = [
                _c("downloadscript", HEADER),
                f"{_c(p + 'downloadscript', CMD)} — download a script (reply to a message with a .py or .txt attachment or code block)",
                f"{_c(p + 'downloadscript off', CMD)} — download without auto-reloading scripts",
                f"{_c(p + 'downloadscript <name>', CMD)} — provide a filename if one cannot be detected",
                f"alias: {_c(p + 'dls', CMD)}",
            ]
            await ctx.send(_block("\n".join(lines)))
            return
        args_parts = args.strip().split() if args else []
        do_reload = True
        custom_name = None
        for part in args_parts:
            if part.lower() == "off":
                do_reload = False
            else:
                custom_name = part[:-3] if part.endswith(".py") else part
        try:
            replied = await ctx.channel.fetch_message(ctx.message.reference.message_id)
            attachment = next((a for a in replied.attachments if a.filename.endswith(('.py', '.txt'))), None)
            if attachment is not None:
                filename = Path(attachment.filename).stem + ".py"
                if custom_name:
                    filename = custom_name + ".py"
                filename, file_path = await _resolve_conflict(ctx, status_msg, filename)
                if filename is None:
                    return
                status_msg = await ctx.send(_block(_c(f"Downloading {filename}...", WARN))) if not status_msg else status_msg
                headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
                async with aiohttp.ClientSession(headers=headers) as session:
                    async with session.get(attachment.url) as response:
                        if response.status == 200:
                            code = await response.read()
                        else:
                            await status_msg.edit(content=_block(_c(f"Failed to download. HTTP Status: {response.status}", ERROR)), delete_after=15)
                            return
            else:
                code_match = re.search(r"```(?:py|python)?\n?([\s\S]+?)```", replied.content)
                if not code_match:
                    await ctx.send(_block(_c("No attachment or code block found in the replied message.", ERROR)), delete_after=15)
                    return
                code = code_match.group(1).encode("utf-8")
                if not custom_name:
                    name_match = re.search(r'name\s*=\s*["\'](.*?)["\'"]', code.decode("utf-8"))
                    if name_match:
                        raw = name_match.group(1)
                        custom_name = re.sub(r'[^\w\-]', '_', raw).strip('_').lower()
                    else:
                        p = getConfigData().get("prefix", "<p>")
                        await ctx.send(
                            _block(_c(f"Could not find a script name in the code block. Please re-run with a name: {p}dls <name>", ERROR)),
                            delete_after=20
                        )
                        return
                filename = custom_name + ".py"
                filename, file_path = await _resolve_conflict(ctx, status_msg, filename)
                if filename is None:
                    return
                status_msg = await ctx.send(_block(_c(f"Saving code block as {filename}...", WARN))) if not status_msg else status_msg
            with open(file_path, "wb") as f:
                f.write(code)
            final = _c(f"Successfully saved {filename}.", SUCCESS)
            script_name = Path(filename).stem
            json_updated = await _update_scripts_json(script_name, status_msg)
            if json_updated:
                if do_reload:
                    await status_msg.edit(content=_block(_c("Reloading all scripts...", WARN)))
                    reloadAllScripts()
                    final += "\n" + _c("Scripts reloaded automatically.", SUCCESS)
                else:
                    final += "\n" + _c("Skipped auto-reload. Please reload manually.", WARN)
            await status_msg.edit(content=_block(final), delete_after=20)
        except Exception:
            await _handle_error(ctx, status_msg)
ScriptUtils()
