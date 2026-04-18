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
            response = requests.post(url, headers=headers, json={"name": webhook_name}, timeout=10)
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
            return requests.get(webhook_url, timeout=10).status_code == 200
        except Exception:
            return False

    def send_webhook_message(webhook_url, content=None, embed_data=None, username=None, avatar_url=None):
        if not webhook_url:
            return False
        payload = {}
        if content:
            payload["content"] = content
        if embed_data:
            payload["embeds"] = [embed_data]
        if username:
            payload["username"] = username
        if avatar_url:
            payload["avatar_url"] = avatar_url
        try:
            response = requests.post(
                webhook_url,
                headers={"Content-Type": "application/json"},
                data=json.dumps(payload),
                timeout=10
            )
            response.raise_for_status()
            return response.status_code in (200, 204)
        except requests.exceptions.RequestException as e:
            print(f"DM Logger | Webhook error: {e}", type_="ERROR")
            return False

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

    # ======================== UI START ========================

    tab = Tab(name="DM Logger", title="DM Logger Configuration", icon="message", gap=3)
    main_container = tab.create_container(type="rows", gap=3)
    top_row = main_container.create_container(type="columns", gap=3)

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

    save_settings_btn = settings_card.create_ui_element(UI.Button, label="Save", variant="cta", full_width=True)

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

    # ======================== UI END ========================

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
                    timeout=10
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

    save_settings_btn.onClick = save_settings
    save_destination_btn.onClick = save_destination
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

        webhook_url = await get_or_create_webhook(config)
        if not webhook_url:
            return

        theme_color, theme_small_image, theme_large_image = get_theme_values()

        content_text = message.content or ""
        inline_urls = extract_all_urls(content_text)
        attachments = [att.url for att in message.attachments] if message.attachments else []

        links_to_send = []
        if config.get("log_attachments", True):
            for u in inline_urls:
                if u not in links_to_send:
                    links_to_send.append(u)
            for a in attachments:
                if a not in links_to_send:
                    links_to_send.append(a)

        media_urls = [u for u in links_to_send if re.search(r'\.(?:jpg|jpeg|png|gif|webp|bmp)(\?|$)', u, re.IGNORECASE)]
        other_links = [u for u in links_to_send if u not in media_urls]

        cleaned_content = content_text
        if links_to_send and cleaned_content:
            for l in links_to_send:
                cleaned_content = cleaned_content.replace(l, "")
            cleaned_content = re.sub(r'\s+\n', '\n', cleaned_content)
            cleaned_content = re.sub(r'\n{3,}', '\n\n', cleaned_content).strip() or None
        else:
            cleaned_content = cleaned_content or None

        author_display = message.author.name
        if hasattr(message.author, "discriminator") and message.author.discriminator and message.author.discriminator != "0":
            author_display = f"{message.author.name}#{message.author.discriminator}"

        embed_data = {
            "title": f"DM from {message.author.name}",
            "description": cleaned_content[:2000] if cleaned_content else "*No content*",
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

        if theme_small_image and not links_to_send:
            embed_data["thumbnail"] = {"url": theme_small_image}
        if theme_large_image and not links_to_send:
            embed_data["image"] = {"url": theme_large_image}

        try:
            content_to_send = f"<@{bot.user.id}>" if config.get("ping_on_log", False) else None
            avatar_url = str(message.author.avatar.url) if message.author.avatar else None

            await run_in_thread(
                send_webhook_message,
                webhook_url=webhook_url,
                content=content_to_send,
                embed_data=embed_data,
                username=message.author.name,
                avatar_url=avatar_url
            )

            for link in other_links:
                await run_in_thread(
                    send_webhook_message,
                    webhook_url=webhook_url,
                    content=link,
                    username=message.author.name,
                    avatar_url=avatar_url
                )

            for media in media_urls:
                await run_in_thread(
                    send_webhook_message,
                    webhook_url=webhook_url,
                    content=media,
                    username=message.author.name,
                    avatar_url=avatar_url
                )

            if config.get("log_embeds", True) and message.embeds:
                for original_embed in message.embeds:
                    await run_in_thread(
                        send_webhook_message,
                        webhook_url=webhook_url,
                        embed_data=original_embed.to_dict(),
                        username=message.author.name,
                        avatar_url=avatar_url
                    )

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

            await run_in_thread(
                send_webhook_message,
                webhook_url=webhook_url,
                content=content_to_send,
                embed_data=embed_data,
                username=after.author.name,
                avatar_url=avatar_url
            )

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

        webhook_url = await get_or_create_webhook(config)
        if not webhook_url:
            return

        _, theme_small_image, theme_large_image = get_theme_values()

        author_display = message.author.name
        if hasattr(message.author, "discriminator") and message.author.discriminator and message.author.discriminator != "0":
            author_display = f"{message.author.name}#{message.author.discriminator}"

        embed_data = {
            "title": f"DM Deleted from {message.author.name}",
            "description": message.content[:2000] if message.content else "*Content not cached*",
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

            await run_in_thread(
                send_webhook_message,
                webhook_url=webhook_url,
                content=content_to_send,
                embed_data=embed_data,
                username=message.author.name,
                avatar_url=avatar_url
            )

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