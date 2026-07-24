@nightyScript(
    name="DM Logger",
    author="0pyr",
    description="Logs DMs using webhooks",
    usage="Configure via UI tab"
)
def DMLogger():
    import json
    import asyncio
    import requests
    from pathlib import Path
    from datetime import datetime
    import os
    import re
    import time
    import calendar

    BASE_DIR = Path(getScriptsPath()) / "json"
    CONFIG_FILE = BASE_DIR / "DMLoggerConf.json"

    _theme_cache = {"data": {}, "last_loaded": 0.0}
    THEME_TTL = 60.0

    def load_theme():
        now = time.monotonic()
        if now - _theme_cache["last_loaded"] < THEME_TTL and _theme_cache["data"]:
            return _theme_cache["data"]
        try:
            nighty_config_path = Path(os.getenv("APPDATA")) / "Nighty Selfbot" / "nighty.config"
            with open(nighty_config_path, "r", encoding="utf-8") as f:
                config_data = json.load(f)
            theme_name = config_data.get("theme")
            theme_file = Path(os.getenv("APPDATA")) / "Nighty Selfbot" / "data" / "themes" / f"{theme_name}.json"
            with open(theme_file, "r", encoding="utf-8") as tf:
                theme_data = json.load(tf)
            _theme_cache["data"] = theme_data
            _theme_cache["last_loaded"] = now
            return theme_data
        except Exception as e:
            print(f"DM Logger | Error loading theme: {e}", type_="ERROR")
            return _theme_cache["data"] if _theme_cache["data"] else {}

    def get_theme_values():
        theme = load_theme()
        color = int(theme.get("color", "5865F2").replace("#", ""), 16) if theme.get("color") else 0x5865F2
        return color, theme.get("small_image"), theme.get("large_image")

    def discord_ts(dt):
        unix = calendar.timegm(dt.timetuple())
        return f"<t:{unix}:f> · <t:{unix}:R>"

    def initialize_files():
        BASE_DIR.mkdir(parents=True, exist_ok=True)
        if not CONFIG_FILE.exists():
            with open(CONFIG_FILE, "w") as f:
                json.dump({
                    "enabled": True,
                    "log_self": False,
                    "notify_on_log": True,
                    "ping_on_log": False,
                    "log_deleted": True,
                    "log_edited": True,
                    "log_embeds": True,
                    "log_attachments": True,
                    "whitelist_enabled": False,
                    "whitelist": [],
                    "destination_channel_id": None,
                    "webhook_url": None,
                    "webhook_id": None,
                    "webhook_token": None
                }, f, indent=4)

    def load_config():
        try:
            with open(CONFIG_FILE, "r") as f:
                cfg = json.load(f)
            for key, default in [
                ("log_deleted", True),
                ("log_edited", True),
                ("log_embeds", True),
                ("log_attachments", True),
                ("whitelist_enabled", False),
                ("whitelist", []),
                ("webhook_url", None),
                ("webhook_id", None),
                ("webhook_token", None)
            ]:
                if key not in cfg:
                    cfg[key] = default
            return cfg
        except (FileNotFoundError, json.JSONDecodeError):
            return {
                "enabled": True,
                "log_self": False,
                "notify_on_log": True,
                "ping_on_log": False,
                "log_deleted": True,
                "log_edited": True,
                "log_embeds": True,
                "log_attachments": True,
                "whitelist_enabled": False,
                "whitelist": [],
                "destination_channel_id": None,
                "webhook_url": None,
                "webhook_id": None,
                "webhook_token": None
            }

    def save_config(config):
        try:
            with open(CONFIG_FILE, "w") as f:
                json.dump(config, f, indent=4)
            return True
        except Exception as e:
            print(f"DM Logger | Error saving config: {e}", type_="ERROR")
            return False

    async def run_in_thread(func, *args, **kwargs):
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, lambda: func(*args, **kwargs))

    def create_webhook(channel_id, webhook_name):
        try:
            url = f"https://discord.com/api/v9/channels/{channel_id}/webhooks"
            headers = {"Authorization": bot.http.token, "Content-Type": "application/json"}
            response = requests.post(url, headers=headers, json={"name": webhook_name}, timeout=10, verify=False)
            response.raise_for_status()
            webhook_data = response.json()
            webhook_url = f"https://discord.com/api/webhooks/{webhook_data['id']}/{webhook_data['token']}"
            return webhook_url, webhook_data["id"], webhook_data["token"]
        except Exception as e:
            print(f"DM Logger | Error creating webhook: {e}", type_="ERROR")
            return None, None, None

    def validate_webhook(webhook_url):
        if not webhook_url:
            return False
        try:
            return requests.get(webhook_url, timeout=10, verify=False).status_code == 200
        except Exception:
            return False

    def send_webhook_message(webhook_url, content=None, embed_data=None, embeds=None, username=None, avatar_url=None, files=None):
        if not webhook_url:
            return False
        payload = {}
        if content:
            payload["content"] = content
        all_embeds = []
        if embed_data:
            all_embeds.append(embed_data)
        if embeds:
            all_embeds.extend(embeds)
        if all_embeds:
            payload["embeds"] = all_embeds[:10]
        if username:
            payload["username"] = username
        if avatar_url:
            payload["avatar_url"] = avatar_url
        try:
            if files:
                multipart_files = []
                opened_files = []
                try:
                    for i, (file_path, file_name) in enumerate(files):
                        f = open(file_path, "rb")
                        opened_files.append(f)
                        multipart_files.append((f"files[{i}]", (file_name, f)))
                    multipart_files.append(("payload_json", (None, json.dumps(payload), "application/json")))
                    response = requests.post(webhook_url, files=multipart_files, timeout=20, verify=False)
                finally:
                    for f in opened_files:
                        try:
                            f.close()
                        except Exception:
                            pass
            else:
                response = requests.post(
                    webhook_url,
                    headers={"Content-Type": "application/json"},
                    data=json.dumps(payload),
                    timeout=10,
                    verify=False
                )
            response.raise_for_status()
            return response.status_code in (200, 204)
        except requests.exceptions.RequestException as e:
            print(f"DM Logger | Webhook error: {e}", type_="ERROR")
            return False

    async def download_attachment(att):
        try:
            loop = asyncio.get_event_loop()
            def _fetch():
                r = requests.get(att.url, timeout=20, verify=False)
                r.raise_for_status()
                return r.content
            data = await loop.run_in_executor(None, _fetch)
            temp_dir = Path(getScriptsPath()) / "tmp"
            temp_dir.mkdir(parents=True, exist_ok=True)
            safe_name = f"{att.id}_{att.filename}"
            file_path = temp_dir / safe_name
            with open(file_path, "wb") as f:
                f.write(data)
            return str(file_path), att.filename
        except Exception as e:
            print(f"DM Logger | Attachment download failed: {e}", type_="ERROR")
            return None, None

    def extract_all_urls(text):
        if not text:
            return []
        url_pattern = r'(https?://[^\s<>"{}|\\^`\[\]]+)'
        matches = re.findall(url_pattern, text)
        seen = set()
        out = []
        for m in matches:
            m = m.rstrip('.,;:!)?]\'"')
            if m not in seen:
                seen.add(m)
                out.append(m)
        return out

    async def get_or_create_webhook(config):
        webhook_url = config.get("webhook_url")
        dest_id = config.get("destination_channel_id")
        if not dest_id:
            return None
        if webhook_url and await run_in_thread(validate_webhook, webhook_url):
            return webhook_url
        new_url, new_id, new_token = await run_in_thread(create_webhook, dest_id, "DM Logger")
        if new_url:
            config["webhook_url"] = new_url
            config["webhook_id"] = new_id
            config["webhook_token"] = new_token
            save_config(config)
        return new_url

    def resolve_user_label(user_id: str) -> str:
        try:
            user = bot.get_user(int(user_id))
            if user:
                return f"{user.name} - {user_id}"
        except Exception:
            pass
        return f"Unknown - {user_id}"

    # ======================== UI START ========================

    tab = Tab(name="DM Logger", title="DM Logger Configuration", icon="message", gap=3)
    main_container = tab.create_container(type="rows", gap=3)

    top_row = main_container.create_container(type="columns", gap=3)

    # --- Settings card (top left) ---
    settings_card = top_row.create_card(gap=2)
    settings_card.create_ui_element(UI.Text, content="Settings", size="lg", weight="bold")

    toggle_row_1 = settings_card.create_group(type="columns", gap=4)
    enable_toggle = toggle_row_1.create_ui_element(UI.Toggle, label="Enable Logger")
    log_self_toggle = toggle_row_1.create_ui_element(UI.Toggle, label="Log Own DMs")

    toggle_row_2 = settings_card.create_group(type="columns", gap=4)
    notify_toggle = toggle_row_2.create_ui_element(UI.Toggle, label="Console Notifications")
    ping_toggle = toggle_row_2.create_ui_element(UI.Toggle, label="Ping on Log")

    toggle_row_3 = settings_card.create_group(type="columns", gap=4)
    log_deleted_toggle = toggle_row_3.create_ui_element(UI.Toggle, label="Log Deleted Messages")
    log_edited_toggle = toggle_row_3.create_ui_element(UI.Toggle, label="Log Edited Messages")

    toggle_row_4 = settings_card.create_group(type="columns", gap=4)
    log_embeds_toggle = toggle_row_4.create_ui_element(UI.Toggle, label="Log Embeds")
    log_attachments_toggle = toggle_row_4.create_ui_element(UI.Toggle, label="Log Attachments")

    toggle_row_5 = settings_card.create_group(type="columns", gap=4)
    whitelist_toggle = toggle_row_5.create_ui_element(UI.Toggle, label="Whitelist Only")

    save_settings_btn = settings_card.create_ui_element(UI.Button, label="Save", variant="cta", full_width=True)

    # --- Destination card (top right) ---
    dest_card = top_row.create_card(gap=2)
    dest_card.create_ui_element(UI.Text, content="Log Destination", size="lg", weight="bold")
    dest_card.create_ui_element(UI.Text, content="A single webhook is maintained for the destination channel.", size="sm", color="#6b7280")

    dest_servers_list = [{"id": "select_server", "title": "Select server"}]
    for server in bot.guilds:
        dest_servers_list.append({
            "id": str(server.id),
            "title": server.name,
            "iconUrl": server.icon.url if server.icon else "https://cdn.discordapp.com/embed/avatars/0.png"
        })

    dest_server_select = dest_card.create_ui_element(UI.Select, label="Server", items=dest_servers_list, disabled_items=["select_server"], mode="single", full_width=True)
    dest_channel_select = dest_card.create_ui_element(UI.Select, label="Channel", items=[{"id": "select_channel", "title": "Select server first"}], disabled_items=["select_channel"], mode="single", full_width=True)
    dest_status_text = dest_card.create_ui_element(UI.Text, content="No destination set", size="sm", color="#f87171")
    save_destination_btn = dest_card.create_ui_element(UI.Button, label="Save Destination", variant="cta", full_width=True)

    bottom_row = main_container.create_container(type="columns", gap=3)

    # --- Whitelist card (bottom right, spans under dest) ---
    whitelist_card = bottom_row.create_card(gap=2)
    whitelist_card.create_ui_element(UI.Text, content="Whitelist", size="lg", weight="bold")
    whitelist_card.create_ui_element(UI.Text, content="When Whitelist Only is enabled, only DMs from these users are logged.", size="sm", color="#6b7280")

    whitelist_count_text = whitelist_card.create_ui_element(UI.Text, content="0 users whitelisted", size="sm", color="#6b7280")

    wl_input_row = whitelist_card.create_group(type="columns", gap=2)
    whitelist_input = wl_input_row.create_ui_element(UI.Input, label="User ID", placeholder="Enter a User ID...")
    add_user_btn = wl_input_row.create_ui_element(UI.Button, label="Add", variant="cta")

    whitelist_select = whitelist_card.create_ui_element(
        UI.Select,
        label="Whitelisted Users",
        items=[{"id": "__none__", "title": "No users whitelisted"}],
        disabled_items=["__none__"],
        mode="single",
        full_width=True
    )
    remove_user_btn = whitelist_card.create_ui_element(UI.Button, label="Remove Selected", variant="flat", full_width=True)

    # ======================== UI END ========================

    def refresh_whitelist_ui():
        cfg = load_config()
        wl = cfg.get("whitelist", [])
        whitelist_count_text.content = f"{len(wl)} user{'s' if len(wl) != 1 else ''} whitelisted"
        if wl:
            whitelist_select.items = [{"id": uid, "title": resolve_user_label(uid)} for uid in wl]
            whitelist_select.disabled_items = []
        else:
            whitelist_select.items = [{"id": "__none__", "title": "No users whitelisted"}]
            whitelist_select.disabled_items = ["__none__"]

    def update_dest_channel_list(selected_server_ids):
        if not selected_server_ids or selected_server_ids[0] in ["", "select_server"]:
            dest_channel_select.items = [{"id": "select_channel", "title": "Select a server first"}]
            dest_channel_select.disabled_items = ["select_channel"]
            return
        try:
            server = bot.get_guild(int(selected_server_ids[0]))
            channels_list = [{"id": "select_channel", "title": "Select a channel"}]
            for channel in server.text_channels:
                channels_list.append({"id": str(channel.id), "title": f"#{channel.name}"})
            dest_channel_select.items = channels_list
            dest_channel_select.disabled_items = ["select_channel"]
        except Exception as e:
            print(f"DM Logger | Error updating destination channels: {e}", type_="ERROR")

    async def save_settings():
        config = load_config()
        config["enabled"] = enable_toggle.checked
        config["log_self"] = log_self_toggle.checked
        config["notify_on_log"] = notify_toggle.checked
        config["ping_on_log"] = ping_toggle.checked
        config["log_deleted"] = log_deleted_toggle.checked
        config["log_edited"] = log_edited_toggle.checked
        config["log_embeds"] = log_embeds_toggle.checked
        config["log_attachments"] = log_attachments_toggle.checked
        config["whitelist_enabled"] = whitelist_toggle.checked
        if save_config(config):
            tab.toast(type="SUCCESS", title="Settings Saved", description="Your settings have been saved.")
        else:
            tab.toast(type="ERROR", title="Save Failed", description="Could not write to config file.")

    async def save_destination():
        if not dest_channel_select.selected_items or dest_channel_select.selected_items[0] in ["", "select_channel"]:
            tab.toast(type="ERROR", title="No Channel Selected", description="Please select a destination channel.")
            return
        channel_id = dest_channel_select.selected_items[0]
        try:
            discord_channel = bot.get_channel(int(channel_id))
            if not discord_channel:
                tab.toast(type="ERROR", title="Invalid Channel", description="Bot cannot access this channel.")
                return
        except:
            tab.toast(type="ERROR", title="Invalid Channel", description="Channel ID is invalid.")
            return
        config = load_config()
        old_dest = config.get("destination_channel_id")
        old_webhook_id = config.get("webhook_id")
        old_webhook_token = config.get("webhook_token")
        if old_dest != channel_id and old_webhook_id and old_webhook_token:
            await run_in_thread(
                lambda: requests.delete(
                    f"https://discord.com/api/v9/webhooks/{old_webhook_id}/{old_webhook_token}",
                    timeout=10,
                    verify=False
                )
            )
            config["webhook_url"] = None
            config["webhook_id"] = None
            config["webhook_token"] = None
        config["destination_channel_id"] = channel_id
        save_destination_btn.loading = True
        try:
            new_url, new_id, new_token = await run_in_thread(create_webhook, channel_id, "DM Logger")
            if new_url:
                config["webhook_url"] = new_url
                config["webhook_id"] = new_id
                config["webhook_token"] = new_token
            if save_config(config):
                dest_status_text.content = f"Logging to: {discord_channel.guild.name} -> #{discord_channel.name}"
                dest_status_text.color = "#4ade80"
                tab.toast(type="SUCCESS", title="Destination Saved", description=f"Logs will be sent to #{discord_channel.name}.")
            else:
                tab.toast(type="ERROR", title="Save Failed", description="Could not write to config file.")
        except Exception as e:
            print(f"DM Logger | Error saving destination: {e}", type_="ERROR")
            tab.toast(type="ERROR", title="Error", description=str(e))
        finally:
            save_destination_btn.loading = False

    async def add_user():
        uid = whitelist_input.value.strip() if whitelist_input.value else ""
        if not uid:
            tab.toast(type="ERROR", title="No Input", description="Please enter a User ID.")
            return
        cfg = load_config()
        wl = cfg.get("whitelist", [])
        if uid in wl:
            tab.toast(type="ERROR", title="Already Added", description=f"{resolve_user_label(uid)} is already whitelisted.")
            return
        wl.append(uid)
        cfg["whitelist"] = wl
        save_config(cfg)
        whitelist_input.value = ""
        refresh_whitelist_ui()
        tab.toast(type="SUCCESS", title="Added", description=f"{resolve_user_label(uid)} added to whitelist.")

    async def remove_user():
        selected = whitelist_select.selected_items
        if not selected or selected[0] == "__none__":
            tab.toast(type="ERROR", title="No Selection", description="Select a user to remove.")
            return
        uid = selected[0]
        cfg = load_config()
        wl = cfg.get("whitelist", [])
        if uid in wl:
            wl.remove(uid)
            cfg["whitelist"] = wl
            save_config(cfg)
            refresh_whitelist_ui()
            tab.toast(type="SUCCESS", title="Removed", description=f"Removed {resolve_user_label(uid)} from whitelist.")

    save_settings_btn.onClick = save_settings
    save_destination_btn.onClick = save_destination
    add_user_btn.onClick = add_user
    remove_user_btn.onClick = remove_user
    dest_server_select.onChange = update_dest_channel_list

    @bot.listen('on_message')
    async def log_dm(message):
        config = load_config()
        if not config["enabled"]:
            return
        if message.guild:
            return
        if not config.get("log_self", False) and message.author.id == bot.user.id:
            return
        if not config.get("destination_channel_id"):
            return
        if config.get("whitelist_enabled", False):
            if str(message.author.id) not in config.get("whitelist", []):
                return

        webhook_url = await get_or_create_webhook(config)
        if not webhook_url:
            return

        theme_color, theme_small_image, theme_large_image = get_theme_values()
        content_text = message.content or ""
        inline_urls = extract_all_urls(content_text)
        attachment_urls = set(att.url for att in message.attachments) if message.attachments else set()

        author_display = message.author.name
        if hasattr(message.author, "discriminator") and message.author.discriminator and message.author.discriminator != "0":
            author_display = f"{message.author.name}#{message.author.discriminator}"

        embed_data = {
            "title": f"DM from {message.author.name}",
            "description": content_text[:2000] if content_text else "*No content*",
            "color": theme_color,
            "author": {
                "name": author_display,
                "icon_url": str(message.author.avatar.url) if message.author.avatar else None
            },
            "fields": [
                {"name": "User ID", "value": str(message.author.id), "inline": True},
                {"name": "Sent", "value": discord_ts(message.created_at), "inline": False}
            ]
        }

        if theme_small_image:
            embed_data["thumbnail"] = {"url": theme_small_image}
        if theme_large_image:
            embed_data["image"] = {"url": theme_large_image}

        try:
            content_to_send = f"<@{bot.user.id}>" if config.get("ping_on_log", False) else None
            avatar_url = str(message.author.avatar.url) if message.author.avatar else None

            extra_embeds = []
            if config.get("log_embeds", True) and message.embeds:
                for original_embed in message.embeds:
                    ed = original_embed.to_dict()
                    embed_type = ed.get("type", "")
                    if embed_type in ("link", "image", "video", "gifv"):
                        continue
                    embed_url = ed.get("url", "")
                    image_url = (ed.get("image") or {}).get("url", "")
                    video_url = (ed.get("video") or {}).get("url", "")
                    thumb_url = (ed.get("thumbnail") or {}).get("url", "")
                    if any(u in attachment_urls for u in [embed_url, image_url, video_url, thumb_url]):
                        continue
                    extra_embeds.append(ed)

            downloaded_files = []
            if config.get("log_attachments", True) and message.attachments:
                results = await asyncio.gather(*[download_attachment(att) for att in message.attachments], return_exceptions=True)
                for r in results:
                    if not isinstance(r, Exception) and r and r[0] and r[1]:
                        downloaded_files.append(r)

            await run_in_thread(
                send_webhook_message,
                webhook_url=webhook_url,
                content=content_to_send,
                embed_data=embed_data,
                embeds=extra_embeds if extra_embeds else None,
                username=message.author.name,
                avatar_url=avatar_url,
                files=downloaded_files[:10] if downloaded_files else None
            )

            for fp, _ in downloaded_files:
                try:
                    os.remove(fp)
                except Exception:
                    pass

            for i in range(10, len(downloaded_files), 10):
                await run_in_thread(
                    send_webhook_message,
                    webhook_url=webhook_url,
                    username=message.author.name,
                    avatar_url=avatar_url,
                    files=downloaded_files[i:i+10]
                )

            if inline_urls:
                for url in inline_urls:
                    await run_in_thread(send_webhook_message, webhook_url=webhook_url, content=url, username=message.author.name, avatar_url=avatar_url)

            if config.get("notify_on_log", True):
                print(f"DM Logger | Logged DM from {message.author.name}", type_="INFO")
        except Exception as e:
            print(f"DM Logger | Error logging DM: {e}", type_="ERROR")

    @bot.listen('on_message_edit')
    async def log_dm_edit(before, after):
        config = load_config()
        if not config["enabled"]:
            return
        if after.guild:
            return
        if not config.get("log_self", False) and after.author.id == bot.user.id:
            return
        if not config.get("destination_channel_id") or not config.get("log_edited", True):
            return
        if before.content == after.content:
            return
        if config.get("whitelist_enabled", False):
            if str(after.author.id) not in config.get("whitelist", []):
                return

        webhook_url = await get_or_create_webhook(config)
        if not webhook_url:
            return

        _, theme_small_image, theme_large_image = get_theme_values()
        edited_at = after.edited_at if after.edited_at else datetime.utcnow()

        author_display = after.author.name
        if hasattr(after.author, "discriminator") and after.author.discriminator and after.author.discriminator != "0":
            author_display = f"{after.author.name}#{after.author.discriminator}"

        embed_data = {
            "title": f"DM Edited by {after.author.name}",
            "color": 0xf59e0b,
            "author": {
                "name": author_display,
                "icon_url": str(after.author.avatar.url) if after.author.avatar else None
            },
            "fields": [
                {"name": "User ID", "value": str(after.author.id), "inline": True},
                {"name": "Before", "value": before.content[:1024] if before.content else "*Not cached*", "inline": False},
                {"name": "After", "value": after.content[:1024] if after.content else "*Empty*", "inline": False},
                {"name": "Edited", "value": discord_ts(edited_at), "inline": False}
            ]
        }

        if theme_small_image:
            embed_data["thumbnail"] = {"url": theme_small_image}
        if theme_large_image:
            embed_data["image"] = {"url": theme_large_image}

        try:
            content_to_send = f"<@{bot.user.id}>" if config.get("ping_on_log", False) else None
            avatar_url = str(after.author.avatar.url) if after.author.avatar else None
            await run_in_thread(send_webhook_message, webhook_url=webhook_url, content=content_to_send, embed_data=embed_data, username=after.author.name, avatar_url=avatar_url)
            if config.get("notify_on_log", True):
                print(f"DM Logger | Logged edited DM from {after.author.name}", type_="INFO")
        except Exception as e:
            print(f"DM Logger | Error logging edited DM: {e}", type_="ERROR")

    @bot.listen('on_message_delete')
    async def log_dm_delete(message):
        config = load_config()
        if not config["enabled"]:
            return
        if message.guild:
            return
        if not config.get("log_self", False) and message.author.id == bot.user.id:
            return
        if not config.get("destination_channel_id") or not config.get("log_deleted", True):
            return
        if config.get("whitelist_enabled", False):
            if str(message.author.id) not in config.get("whitelist", []):
                return

        webhook_url = await get_or_create_webhook(config)
        if not webhook_url:
            return

        _, theme_small_image, theme_large_image = get_theme_values()
        content_text = message.content or ""
        inline_urls = extract_all_urls(content_text)
        attachment_urls = set(att.url for att in message.attachments) if message.attachments else set()

        author_display = message.author.name
        if hasattr(message.author, "discriminator") and message.author.discriminator and message.author.discriminator != "0":
            author_display = f"{message.author.name}#{message.author.discriminator}"

        embed_data = {
            "title": f"DM Deleted from {message.author.name}",
            "description": content_text[:2000] if content_text else "*Content not cached*",
            "color": 0xef4444,
            "author": {
                "name": author_display,
                "icon_url": str(message.author.avatar.url) if message.author.avatar else None
            },
            "fields": [
                {"name": "User ID", "value": str(message.author.id), "inline": True},
                {"name": "Deleted At", "value": discord_ts(datetime.utcnow()), "inline": False}
            ]
        }

        if theme_small_image:
            embed_data["thumbnail"] = {"url": theme_small_image}
        if theme_large_image:
            embed_data["image"] = {"url": theme_large_image}

        try:
            content_to_send = f"<@{bot.user.id}>" if config.get("ping_on_log", False) else None
            avatar_url = str(message.author.avatar.url) if message.author.avatar else None

            extra_embeds = []
            if config.get("log_embeds", True) and message.embeds:
                for original_embed in message.embeds:
                    ed = original_embed.to_dict()
                    embed_type = ed.get("type", "")
                    if embed_type in ("link", "image", "video", "gifv"):
                        continue
                    embed_url = ed.get("url", "")
                    image_url = (ed.get("image") or {}).get("url", "")
                    video_url = (ed.get("video") or {}).get("url", "")
                    thumb_url = (ed.get("thumbnail") or {}).get("url", "")
                    if any(u in attachment_urls for u in [embed_url, image_url, video_url, thumb_url]):
                        continue
                    extra_embeds.append(ed)

            downloaded_files = []
            if config.get("log_attachments", True) and message.attachments:
                results = await asyncio.gather(*[download_attachment(att) for att in message.attachments], return_exceptions=True)
                for r in results:
                    if not isinstance(r, Exception) and r and r[0] and r[1]:
                        downloaded_files.append(r)

            await run_in_thread(
                send_webhook_message,
                webhook_url=webhook_url,
                content=content_to_send,
                embed_data=embed_data,
                embeds=extra_embeds if extra_embeds else None,
                username=message.author.name,
                avatar_url=avatar_url,
                files=downloaded_files[:10] if downloaded_files else None
            )

            for fp, _ in downloaded_files:
                try:
                    os.remove(fp)
                except Exception:
                    pass

            for i in range(10, len(downloaded_files), 10):
                await run_in_thread(
                    send_webhook_message,
                    webhook_url=webhook_url,
                    username=message.author.name,
                    avatar_url=avatar_url,
                    files=downloaded_files[i:i+10]
                )

            if inline_urls:
                for url in inline_urls:
                    await run_in_thread(send_webhook_message, webhook_url=webhook_url, content=url, username=message.author.name, avatar_url=avatar_url)

            if config.get("notify_on_log", True):
                print(f"DM Logger | Logged deleted DM from {message.author.name}", type_="INFO")
        except Exception as e:
            print(f"DM Logger | Error logging deleted DM: {e}", type_="ERROR")

    async def validate_webhook_on_start():
        try:
            config = load_config()
            webhook_url = config.get("webhook_url")
            dest_id = config.get("destination_channel_id")
            if not dest_id or not webhook_url:
                return
            valid = await run_in_thread(validate_webhook, webhook_url)
            if not valid:
                print("DM Logger | Webhook invalid, recreating...", type_="INFO")
                new_url, new_id, new_token = await run_in_thread(create_webhook, dest_id, "DM Logger")
                if new_url:
                    config["webhook_url"] = new_url
                    config["webhook_id"] = new_id
                    config["webhook_token"] = new_token
                    save_config(config)
                    print("DM Logger | Webhook recreated.", type_="INFO")
        except Exception as e:
            print(f"DM Logger | Webhook validation error: {e}", type_="ERROR")

    initialize_files()
    config = load_config()

    enable_toggle.checked = config["enabled"]
    log_self_toggle.checked = config.get("log_self", False)
    notify_toggle.checked = config.get("notify_on_log", True)
    ping_toggle.checked = config.get("ping_on_log", False)
    log_deleted_toggle.checked = config.get("log_deleted", True)
    log_edited_toggle.checked = config.get("log_edited", True)
    log_embeds_toggle.checked = config.get("log_embeds", True)
    log_attachments_toggle.checked = config.get("log_attachments", True)
    whitelist_toggle.checked = config.get("whitelist_enabled", False)

    refresh_whitelist_ui()

    dest_id = config.get("destination_channel_id")
    if dest_id:
        try:
            ch = bot.get_channel(int(dest_id))
            if ch and ch.guild:
                dest_server_select.selected_items = [str(ch.guild.id)]
                update_dest_channel_list([str(ch.guild.id)])
                dest_channel_select.selected_items = [dest_id]
                dest_status_text.content = f"Logging to: {ch.guild.name} -> #{ch.name}"
                dest_status_text.color = "#4ade80"
        except:
            pass

    tab.render()
    bot.loop.create_task(validate_webhook_on_start())


DMLogger()
