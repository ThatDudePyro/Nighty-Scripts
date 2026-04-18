def ChannelLogger():
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
    CONFIG_FILE = BASE_DIR / "ChannelLoggerConf.json"

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
            print(f"Channel Logger | Error loading theme: {e}", type_="ERROR")
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
                    "enabled": True, "log_self": False, "notify_on_log": True, "ping_on_log": False,
                    "log_deleted": True, "log_edited": True, "log_embeds": True,
                    "log_attachments": True, "log_bulk_deleted": True, "sources": []
                }, f, indent=4)

    def load_config():
        try:
            with open(CONFIG_FILE, "r") as f:
                cfg = json.load(f)
            if "sources" not in cfg:
                sources = []
                def _make_source(type_, id_, server_id=None):
                    return {
                        "type": type_, "id": id_, "server_id": server_id,
                        "destination_channel_id": cfg.get("destination_channel_id"),
                        "webhook_url": cfg.get("webhook_url"),
                        "webhook_id": cfg.get("webhook_id"),
                        "webhook_token": cfg.get("webhook_token")
                    }
                for ch in cfg.get("log_channels", []):
                    sources.append(_make_source("channel", ch))
                for entry in cfg.get("log_categories", []):
                    sources.append(_make_source("category", entry["category_id"], entry["server_id"]))
                for sv in cfg.get("log_servers", []):
                    sources.append(_make_source("server", sv))
                cfg["sources"] = sources
                for k in ["log_channels", "log_categories", "log_servers", "destination_channel_id", "webhook_url", "webhook_id", "webhook_token"]:
                    cfg.pop(k, None)
            for key, default in [("log_deleted", True), ("log_edited", True), ("log_embeds", True), ("log_attachments", True), ("log_bulk_deleted", True)]:
                if key not in cfg:
                    cfg[key] = default
            return cfg
        except (FileNotFoundError, json.JSONDecodeError):
            return {
                "enabled": True, "log_self": False, "notify_on_log": True, "ping_on_log": False,
                "log_deleted": True, "log_edited": True, "log_embeds": True,
                "log_attachments": True, "log_bulk_deleted": True, "sources": []
            }

    def save_config(config):
        try:
            with open(CONFIG_FILE, "w") as f:
                json.dump(config, f, indent=4)
            return True
        except Exception as e:
            print(f"Channel Logger | Error saving config: {e}", type_="ERROR")
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
            data = response.json()
            return f"https://discord.com/api/webhooks/{data['id']}/{data['token']}", data['id'], data['token']
        except Exception as e:
            print(f"Channel Logger | Error creating webhook: {e}", type_="ERROR")
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
            response = requests.post(webhook_url, headers={"Content-Type": "application/json"}, data=json.dumps(payload), timeout=10)
            response.raise_for_status()
            return response.status_code in (200, 204)
        except requests.exceptions.RequestException as e:
            print(f"Channel Logger | Webhook error: {e}", type_="ERROR")
            return False

    def extract_all_urls(text):
        if not text:
            return []
        seen = set()
        out = []
        for m in re.findall(r'(https?://[^\s<>"{}|\\^`\[\]]+)', text):
            m = m.rstrip('.,;:!)?]\'"')
            if m not in seen:
                seen.add(m)
                out.append(m)
        return out

    def get_last_dest_channel_id(config):
        for source in reversed(config.get("sources", [])):
            if source.get("destination_channel_id"):
                return source["destination_channel_id"]
        return None

    def find_matched_source(config, channel_id, server_id, category_id=None):
        for source in config.get("sources", []):
            if source["type"] == "channel" and source["id"] == channel_id:
                return source
            if source["type"] == "category" and category_id and source["id"] == category_id and source.get("server_id") == server_id:
                return source
            if source["type"] == "server" and source["id"] == server_id:
                return source
        return None

    def source_label(source):
        stype = source.get("type")
        sid = source.get("id")
        server_id = source.get("server_id")
        dest_id = source.get("destination_channel_id")
        try:
            dest_str = f"#{bot.get_channel(int(dest_id)).name}"
        except:
            dest_str = "unknown dest"
        try:
            if stype == "server":
                src_str = f"Server: {bot.get_guild(int(sid)).name}"
            elif stype == "category":
                sv = bot.get_guild(int(server_id))
                src_str = f"Category: {sv.name} > {sv.get_channel(int(sid)).name}"
            else:
                ch = bot.get_channel(int(sid))
                src_str = f"{ch.guild.name} > #{ch.name}"
        except:
            src_str = f"{stype} {sid}"
        return f"{src_str}  ->  {dest_str}"

    # === UI START ===

    tab = Tab(name="Channel Logger", title="Channel Logger Configuration", icon="message", gap=3)
    main_container = tab.create_container(type="rows", gap=3)
    top_row = main_container.create_container(type="columns", gap=3)

    settings_card = top_row.create_card(gap=2)
    settings_card.create_ui_element(UI.Text, content="Settings", size="lg", weight="bold")

    toggle_row_1 = settings_card.create_group(type="columns", gap=4)
    enable_toggle = toggle_row_1.create_ui_element(UI.Toggle, label="Enable Logger")
    log_self_toggle = toggle_row_1.create_ui_element(UI.Toggle, label="Log Own Messages")

    toggle_row_2 = settings_card.create_group(type="columns", gap=4)
    notify_toggle = toggle_row_2.create_ui_element(UI.Toggle, label="Console Notifications")
    ping_toggle = toggle_row_2.create_ui_element(UI.Toggle, label="Ping on Log")

    toggle_row_3 = settings_card.create_group(type="columns", gap=4)
    log_deleted_toggle = toggle_row_3.create_ui_element(UI.Toggle, label="Log Deleted Messages")
    log_edited_toggle = toggle_row_3.create_ui_element(UI.Toggle, label="Log Edited Messages")

    toggle_row_4 = settings_card.create_group(type="columns", gap=4)
    log_bulk_toggle = toggle_row_4.create_ui_element(UI.Toggle, label="Log Bulk Deleted")
    log_embeds_toggle = toggle_row_4.create_ui_element(UI.Toggle, label="Log Embeds")

    log_attachments_toggle = settings_card.create_ui_element(UI.Toggle, label="Log Attachments")
    save_settings_btn = settings_card.create_ui_element(UI.Button, label="Save", variant="cta", full_width=True)

    dest_card = top_row.create_card(gap=2)
    dest_card.create_ui_element(UI.Text, content="Log Destination", size="lg", weight="bold")
    dest_card.create_ui_element(UI.Text, content="Selected destination will be used when adding a source.", size="sm", color="#6b7280")

    dest_servers_list = [{"id": "select_server", "title": "Select server"}]
    for server in bot.guilds:
        dest_servers_list.append({
            "id": str(server.id), "title": server.name,
            "iconUrl": server.icon.url if server.icon else "https://cdn.discordapp.com/embed/avatars/0.png"
        })

    dest_server_select = dest_card.create_ui_element(UI.Select, label="Server", items=dest_servers_list, disabled_items=["select_server"], mode="single", full_width=True)
    dest_channel_select = dest_card.create_ui_element(UI.Select, label="Channel", items=[{"id": "select_channel", "title": "Select server first"}], disabled_items=["select_channel"], mode="single", full_width=True)
    dest_current_text = dest_card.create_ui_element(UI.Text, content="No destination selected", size="sm", color="#f87171")

    bottom_row = main_container.create_container(type="columns", gap=3)

    add_card = bottom_row.create_card(gap=2)
    add_card.create_ui_element(UI.Text, content="Add Source", size="lg", weight="bold")
    add_card.create_ui_element(UI.Text, content="Select server only -> log full server\nSelect server + category -> log full category\nSelect server + category + channel -> log single channel", size="sm", color="#6b7280")

    source_servers_list = [{"id": "select_server", "title": "Select server"}]
    for server in bot.guilds:
        source_servers_list.append({
            "id": str(server.id), "title": server.name,
            "iconUrl": server.icon.url if server.icon else "https://cdn.discordapp.com/embed/avatars/0.png"
        })

    source_server_select = add_card.create_ui_element(UI.Select, label="Server", items=source_servers_list, disabled_items=["select_server"], mode="single", full_width=True)
    source_category_select = add_card.create_ui_element(UI.Select, label="Category (optional)", items=[{"id": "none", "title": "No category — full server"}], mode="single", full_width=True)
    source_channel_select = add_card.create_ui_element(UI.Select, label="Channel (optional)", items=[{"id": "none", "title": "No channel — full category/server"}], mode="single", full_width=True)
    add_source_btn = add_card.create_ui_element(UI.Button, label="Add Source", variant="cta", full_width=True)

    manage_card = bottom_row.create_card(gap=2)
    manage_card.create_ui_element(UI.Text, content="Manage Sources", size="lg", weight="bold")
    status_text = manage_card.create_ui_element(UI.Text, content="Logger is enabled", size="sm", color="#4ade80")
    count_text = manage_card.create_ui_element(UI.Text, content="0 sources configured", size="sm", color="#6b7280")
    channels_display = manage_card.create_group(type="rows", gap=1)
    remove_select = manage_card.create_ui_element(UI.Select, label="Remove Source", items=[{"id": "__none__", "title": "No sources"}], disabled_items=["__none__"], mode="single", full_width=True)
    remove_btn = manage_card.create_ui_element(UI.Button, label="Remove", variant="flat", full_width=True)

    # === UI END ===

    channel_text_elements = []

    def update_dest_channel_list(selected_server_ids):
        if not selected_server_ids or selected_server_ids[0] in ["", "select_server"]:
            dest_channel_select.items = [{"id": "select_channel", "title": "Select a server first"}]
            dest_channel_select.disabled_items = ["select_channel"]
            dest_current_text.content = "No destination selected"
            dest_current_text.color = "#f87171"
            return
        try:
            server = bot.get_guild(int(selected_server_ids[0]))
            channels_list = [{"id": "select_channel", "title": "Select a channel"}]
            for channel in server.text_channels:
                channels_list.append({"id": str(channel.id), "title": f"#{channel.name}"})
            dest_channel_select.items = channels_list
            dest_channel_select.disabled_items = ["select_channel"]
        except Exception as e:
            print(f"Channel Logger | Error updating destination channels: {e}", type_="ERROR")

    def update_dest_status(selected_channel_ids):
        if not selected_channel_ids or selected_channel_ids[0] in ["", "select_channel"]:
            dest_current_text.content = "No destination selected"
            dest_current_text.color = "#f87171"
            return
        try:
            ch = bot.get_channel(int(selected_channel_ids[0]))
            dest_current_text.content = f"Will log to: {ch.guild.name} -> #{ch.name}"
            dest_current_text.color = "#4ade80"
        except:
            dest_current_text.content = "Selected channel not found"
            dest_current_text.color = "#f59e0b"

    def update_source_category_list(selected_server_ids):
        source_channel_select.items = [{"id": "none", "title": "No channel — full category/server"}]
        if not selected_server_ids or selected_server_ids[0] in ["", "select_server"]:
            source_category_select.items = [{"id": "none", "title": "No category — full server"}]
            return
        try:
            server = bot.get_guild(int(selected_server_ids[0]))
            cat_list = [{"id": "none", "title": "No category — full server"}]
            for cat in server.categories:
                cat_list.append({"id": str(cat.id), "title": cat.name})
            source_category_select.items = cat_list
        except Exception as e:
            print(f"Channel Logger | Error updating categories: {e}", type_="ERROR")

    def update_source_channel_list(selected_category_ids):
        server_sel = source_server_select.selected_items
        if not selected_category_ids or selected_category_ids[0] in ["", "none"]:
            if not server_sel or server_sel[0] in ["", "select_server"]:
                source_channel_select.items = [{"id": "none", "title": "No channel — full category/server"}]
                return
            try:
                server = bot.get_guild(int(server_sel[0]))
                ch_list = [{"id": "none", "title": "No channel — full server"}]
                for ch in server.text_channels:
                    ch_list.append({"id": str(ch.id), "title": f"#{ch.name}"})
                source_channel_select.items = ch_list
            except Exception as e:
                print(f"Channel Logger | Error loading channels: {e}", type_="ERROR")
            return
        try:
            server = bot.get_guild(int(server_sel[0]))
            category = server.get_channel(int(selected_category_ids[0]))
            if not category:
                source_channel_select.items = [{"id": "none", "title": "Category not found"}]
                return
            ch_list = [{"id": "none", "title": "No channel — full category"}]
            for ch in category.text_channels:
                ch_list.append({"id": str(ch.id), "title": f"#{ch.name}"})
            source_channel_select.items = ch_list
        except Exception as e:
            print(f"Channel Logger | Error updating channels for category: {e}", type_="ERROR")

    def update_display():
        config = load_config()
        sources = config.get("sources", [])
        status_text.content = f"Status: {'Enabled' if config['enabled'] else 'Disabled'}"
        status_text.color = "#4ade80" if config["enabled"] else "#f87171"
        count_text.content = f"{len(sources)} source{'s' if len(sources) != 1 else ''} configured"
        items = [{"id": str(i), "title": source_label(s)} for i, s in enumerate(sources)]
        if items:
            remove_select.items = items
            remove_select.disabled_items = []
        else:
            remove_select.items = [{"id": "__none__", "title": "No sources"}]
            remove_select.disabled_items = ["__none__"]

    def refresh_channels():
        for element in channel_text_elements:
            element.visible = False
        channel_text_elements.clear()
        config = load_config()
        sources = config.get("sources", [])
        if sources:
            for source in sources[:6]:
                el = channels_display.create_ui_element(UI.Text, content=f"• {source_label(source)}", size="sm")
                channel_text_elements.append(el)
            if len(sources) > 6:
                more = channels_display.create_ui_element(UI.Text, content=f"+ {len(sources) - 6} more...", size="sm", color="#6b7280")
                channel_text_elements.append(more)
        else:
            el = channels_display.create_ui_element(UI.Text, content="No sources yet", size="sm", color="#6b7280")
            channel_text_elements.append(el)
        update_display()

    async def save_settings():
        config = load_config()
        config["enabled"] = enable_toggle.checked
        config["log_self"] = log_self_toggle.checked
        config["notify_on_log"] = notify_toggle.checked
        config["ping_on_log"] = ping_toggle.checked
        config["log_deleted"] = log_deleted_toggle.checked
        config["log_edited"] = log_edited_toggle.checked
        config["log_bulk_deleted"] = log_bulk_toggle.checked
        config["log_embeds"] = log_embeds_toggle.checked
        config["log_attachments"] = log_attachments_toggle.checked
        if save_config(config):
            update_display()
            tab.toast(type="SUCCESS", title="Settings Saved", description="Your settings have been saved.")
        else:
            tab.toast(type="ERROR", title="Save Failed", description="Could not write to config file.")

    async def add_source():
        dest_sel = dest_channel_select.selected_items
        dest_channel_id = dest_sel[0] if dest_sel and dest_sel[0] not in ["", "select_channel"] else None
        if not dest_channel_id:
            dest_channel_id = get_last_dest_channel_id(load_config())
        if not dest_channel_id:
            tab.toast(type="ERROR", title="No Destination", description="Please select a log destination channel first.")
            return

        server_sel = source_server_select.selected_items
        if not server_sel or server_sel[0] in ["", "select_server"]:
            tab.toast(type="ERROR", title="No Server Selected", description="Please select a source server.")
            return

        server_id = server_sel[0]
        category_sel = source_category_select.selected_items
        channel_sel = source_channel_select.selected_items
        category_id = category_sel[0] if category_sel and category_sel[0] not in ["", "none"] else None
        channel_id = channel_sel[0] if channel_sel and channel_sel[0] not in ["", "none"] else None

        config = load_config()
        for s in config.get("sources", []):
            if channel_id and s["type"] == "channel" and s["id"] == channel_id:
                tab.toast(type="ERROR", title="Already Added", description="This channel is already being logged.")
                return
            if category_id and not channel_id and s["type"] == "category" and s["id"] == category_id:
                tab.toast(type="ERROR", title="Already Added", description="This category is already being logged.")
                return
            if not category_id and not channel_id and s["type"] == "server" and s["id"] == server_id:
                tab.toast(type="ERROR", title="Already Added", description="This server is already being fully logged.")
                return

        add_source_btn.loading = True
        try:
            existing = next((s for s in config.get("sources", []) if s.get("destination_channel_id") == dest_channel_id and s.get("webhook_url")), None)
            if existing and await run_in_thread(validate_webhook, existing["webhook_url"]):
                webhook_url, webhook_id, webhook_token = existing["webhook_url"], existing["webhook_id"], existing["webhook_token"]
            else:
                webhook_url, webhook_id, webhook_token = await run_in_thread(create_webhook, dest_channel_id, "Channel Logger")
                if not webhook_url:
                    tab.toast(type="ERROR", title="Webhook Failed", description="Could not create webhook in destination channel.")
                    return

            if channel_id:
                stype, sid, sv_id = "channel", channel_id, None
            elif category_id:
                stype, sid, sv_id = "category", category_id, server_id
            else:
                stype, sid, sv_id = "server", server_id, None

            config["sources"].append({
                "type": stype, "id": sid, "server_id": sv_id,
                "destination_channel_id": dest_channel_id,
                "webhook_url": webhook_url, "webhook_id": webhook_id, "webhook_token": webhook_token
            })

            if save_config(config):
                refresh_channels()
                try:
                    dest_name = f"#{bot.get_channel(int(dest_channel_id)).name}"
                except:
                    dest_name = dest_channel_id
                tab.toast(type="SUCCESS", title="Source Added", description=f"Logging to {dest_name}.")
            else:
                tab.toast(type="ERROR", title="Save Failed", description="Config could not be saved.")
        except Exception as e:
            print(f"Channel Logger | Error adding source: {e}", type_="ERROR")
            tab.toast(type="ERROR", title="Error", description=str(e))
        finally:
            add_source_btn.loading = False

    async def remove_source():
        if not remove_select.selected_items or remove_select.selected_items[0] == "__none__":
            tab.toast(type="ERROR", title="No Selection", description="Select a source to remove.")
            return
        try:
            index = int(remove_select.selected_items[0])
        except ValueError:
            return
        config = load_config()
        sources = config.get("sources", [])
        if index < 0 or index >= len(sources):
            return
        removed = sources.pop(index)
        config["sources"] = sources
        wh_url = removed.get("webhook_url")
        wh_id = removed.get("webhook_id")
        wh_token = removed.get("webhook_token")
        if wh_id and wh_token and not any(s.get("webhook_url") == wh_url for s in sources):
            await run_in_thread(lambda: requests.delete(f"https://discord.com/api/v9/webhooks/{wh_id}/{wh_token}", timeout=10))
        if save_config(config):
            refresh_channels()
            tab.toast(type="SUCCESS", title="Source Removed", description="Source has been removed.")
        else:
            tab.toast(type="ERROR", title="Save Failed", description="Config could not be saved.")

    save_settings_btn.onClick = save_settings
    add_source_btn.onClick = add_source
    remove_btn.onClick = remove_source
    dest_server_select.onChange = update_dest_channel_list
    dest_channel_select.onChange = update_dest_status
    source_server_select.onChange = update_source_category_list
    source_category_select.onChange = update_source_channel_list

    @bot.listen('on_message')
    async def log_message(message):
        config = load_config()
        if not config["enabled"]:
            return
        if not config.get("log_self", False) and message.author.id == bot.user.id:
            return

        current_channel_id = str(message.channel.id)
        current_server_id = str(message.guild.id) if message.guild else None
        category_id = str(message.channel.category_id) if hasattr(message.channel, 'category_id') and message.channel.category_id else None
        matched = find_matched_source(config, current_channel_id, current_server_id, category_id)
        if not matched:
            return

        webhook_url = matched.get("webhook_url")
        if not webhook_url:
            return

        theme_color, theme_small_image, theme_large_image = get_theme_values()
        server_name = message.guild.name if message.guild else "Direct Message"
        channel_name = message.channel.name if hasattr(message.channel, 'name') else "DM"
        message_link = f"https://discord.com/channels/{message.guild.id if message.guild else '@me'}/{message.channel.id}/{message.id}"

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
            cleaned_content = re.sub(r'\n{3,}', '\n\n', cleaned_content)
            cleaned_content = cleaned_content.strip() or None
        else:
            cleaned_content = cleaned_content or None

        author_display = message.author.name
        if hasattr(message.author, 'discriminator') and message.author.discriminator and message.author.discriminator != '0':
            author_display = f"{message.author.name}#{message.author.discriminator}"

        embed_data = {
            "title": f"#{channel_name}",
            "description": cleaned_content[:2000] if cleaned_content else "*No content*",
            "color": theme_color,
            "author": {
                "name": author_display,
                "icon_url": str(message.author.avatar.url) if message.author.avatar else None
            },
            "fields": [
                {"name": "Author", "value": f"<@{message.author.id}>", "inline": True},
                {"name": "User ID", "value": str(message.author.id), "inline": True},
                {"name": "Channel", "value": f"<#{current_channel_id}>", "inline": True},
                {"name": "Message Link", "value": f"[Jump to Message]({message_link})", "inline": True},
                {"name": "Sent", "value": discord_ts(message.created_at), "inline": False}
            ]
        }

        if theme_small_image and not links_to_send:
            embed_data["thumbnail"] = {"url": theme_small_image}
        if theme_large_image and not links_to_send:
            embed_data["image"] = {"url": theme_large_image}

        try:
            avatar_url = message.guild.icon.url if message.guild and message.guild.icon else None
            content_to_send = f"<@{bot.user.id}>" if config.get("ping_on_log", False) else None

            success = await run_in_thread(send_webhook_message, webhook_url=webhook_url, content=content_to_send, embed_data=embed_data, username=server_name, avatar_url=avatar_url)
            if not success:
                print("Channel Logger | Webhook send failed, attempting to recreate...", type_="ERROR")
                dest_id = matched.get("destination_channel_id")
                new_url, new_id, new_token = await run_in_thread(create_webhook, dest_id, "Channel Logger")
                if new_url:
                    cfg = load_config()
                    for s in cfg.get("sources", []):
                        if s.get("webhook_url") == webhook_url:
                            s["webhook_url"] = new_url
                            s["webhook_id"] = new_id
                            s["webhook_token"] = new_token
                    save_config(cfg)
                    webhook_url = new_url
                    await run_in_thread(send_webhook_message, webhook_url=webhook_url, content=content_to_send, embed_data=embed_data, username=server_name, avatar_url=avatar_url)
                else:
                    print("Channel Logger | Could not recreate webhook.", type_="ERROR")
                    return

            for link in other_links:
                await run_in_thread(send_webhook_message, webhook_url=webhook_url, content=link, username=server_name, avatar_url=avatar_url)
            for media in media_urls:
                await run_in_thread(send_webhook_message, webhook_url=webhook_url, content=media, username=server_name, avatar_url=avatar_url)

            if config.get("log_embeds", True) and message.embeds:
                for original_embed in message.embeds:
                    await run_in_thread(send_webhook_message, webhook_url=webhook_url, embed_data=original_embed.to_dict(), username=server_name, avatar_url=avatar_url)

            if config.get("notify_on_log", True):
                print(f"Channel Logger | Logged message from {message.author.name} in #{channel_name} ({server_name})", type_="INFO")
        except Exception as e:
            print(f"Channel Logger | Error logging message: {e}", type_="ERROR")

    @bot.listen('on_message_delete')
    async def log_deleted(message):
        config = load_config()
        if not config["enabled"] or not config.get("log_deleted", True):
            return

        current_channel_id = str(message.channel.id)
        current_server_id = str(message.guild.id) if message.guild else None
        category_id = str(message.channel.category_id) if hasattr(message.channel, 'category_id') and message.channel.category_id else None
        matched = find_matched_source(config, current_channel_id, current_server_id, category_id)
        if not matched:
            return

        webhook_url = matched.get("webhook_url")
        if not webhook_url:
            return

        server_name = message.guild.name if message.guild else "Direct Message"
        channel_name = message.channel.name if hasattr(message.channel, 'name') else "DM"
        author_display = message.author.name if message.author else "Unknown"
        if message.author and hasattr(message.author, 'discriminator') and message.author.discriminator and message.author.discriminator != '0':
            author_display = f"{message.author.name}#{message.author.discriminator}"

        fields = [
            {"name": "Channel", "value": f"<#{current_channel_id}>", "inline": True},
            {"name": "Deleted At", "value": discord_ts(datetime.utcnow()), "inline": False}
        ]
        if message.author:
            fields.insert(0, {"name": "User ID", "value": str(message.author.id), "inline": True})
            fields.insert(0, {"name": "Author", "value": f"<@{message.author.id}>", "inline": True})

        embed_data = {
            "title": f"Message Deleted in #{channel_name}",
            "description": message.content[:2000] if message.content else "*Content not cached*",
            "color": 0xef4444,
            "author": {
                "name": author_display,
                "icon_url": str(message.author.avatar.url) if message.author and message.author.avatar else None
            },
            "fields": fields
        }

        try:
            avatar_url = message.guild.icon.url if message.guild and message.guild.icon else None
            success = await run_in_thread(send_webhook_message, webhook_url=webhook_url, embed_data=embed_data, username=server_name, avatar_url=avatar_url)
            if not success:
                dest_id = matched.get("destination_channel_id")
                new_url, new_id, new_token = await run_in_thread(create_webhook, dest_id, "Channel Logger")
                if new_url:
                    cfg = load_config()
                    for s in cfg.get("sources", []):
                        if s.get("webhook_url") == webhook_url:
                            s["webhook_url"] = new_url
                            s["webhook_id"] = new_id
                            s["webhook_token"] = new_token
                    save_config(cfg)
                    await run_in_thread(send_webhook_message, webhook_url=new_url, embed_data=embed_data, username=server_name, avatar_url=avatar_url)
        except Exception as e:
            print(f"Channel Logger | Error logging deleted message: {e}", type_="ERROR")

    @bot.listen('on_message_edit')
    async def log_edited(message_before, message_after):
        config = load_config()
        if not config["enabled"] or not config.get("log_edited", True):
            return
        if message_before.content == message_after.content:
            return

        current_channel_id = str(message_after.channel.id)
        current_server_id = str(message_after.guild.id) if message_after.guild else None
        category_id = str(message_after.channel.category_id) if hasattr(message_after.channel, 'category_id') and message_after.channel.category_id else None
        matched = find_matched_source(config, current_channel_id, current_server_id, category_id)
        if not matched:
            return

        webhook_url = matched.get("webhook_url")
        if not webhook_url:
            return

        server_name = message_after.guild.name if message_after.guild else "Direct Message"
        channel_name = message_after.channel.name if hasattr(message_after.channel, 'name') else "DM"
        message_link = f"https://discord.com/channels/{message_after.guild.id if message_after.guild else '@me'}/{message_after.channel.id}/{message_after.id}"
        edited_at = message_after.edited_at if message_after.edited_at else datetime.utcnow()
        author_display = message_after.author.name
        if hasattr(message_after.author, 'discriminator') and message_after.author.discriminator and message_after.author.discriminator != '0':
            author_display = f"{message_after.author.name}#{message_after.author.discriminator}"

        embed_data = {
            "title": f"Message Edited in #{channel_name}",
            "color": 0xf59e0b,
            "author": {
                "name": author_display,
                "icon_url": str(message_after.author.avatar.url) if message_after.author.avatar else None
            },
            "fields": [
                {"name": "Author", "value": f"<@{message_after.author.id}>", "inline": True},
                {"name": "User ID", "value": str(message_after.author.id), "inline": True},
                {"name": "Channel", "value": f"<#{current_channel_id}>", "inline": True},
                {"name": "Before", "value": message_before.content[:1024] if message_before.content else "*Not cached*", "inline": False},
                {"name": "After", "value": message_after.content[:1024] if message_after.content else "*Empty*", "inline": False},
                {"name": "Message Link", "value": f"[Jump to Message]({message_link})", "inline": True},
                {"name": "Edited", "value": discord_ts(edited_at), "inline": True}
            ]
        }

        try:
            avatar_url = message_after.guild.icon.url if message_after.guild and message_after.guild.icon else None
            success = await run_in_thread(send_webhook_message, webhook_url=webhook_url, embed_data=embed_data, username=server_name, avatar_url=avatar_url)
            if not success:
                dest_id = matched.get("destination_channel_id")
                new_url, new_id, new_token = await run_in_thread(create_webhook, dest_id, "Channel Logger")
                if new_url:
                    cfg = load_config()
                    for s in cfg.get("sources", []):
                        if s.get("webhook_url") == webhook_url:
                            s["webhook_url"] = new_url
                            s["webhook_id"] = new_id
                            s["webhook_token"] = new_token
                    save_config(cfg)
                    await run_in_thread(send_webhook_message, webhook_url=new_url, embed_data=embed_data, username=server_name, avatar_url=avatar_url)
        except Exception as e:
            print(f"Channel Logger | Error logging edited message: {e}", type_="ERROR")

    @bot.listen('on_bulk_message_delete')
    async def log_bulk_deleted(messages):
        config = load_config()
        if not config["enabled"] or not config.get("log_bulk_deleted", True):
            return
        if not messages:
            return

        first = messages[0]
        current_channel_id = str(first.channel.id)
        current_server_id = str(first.guild.id) if first.guild else None
        category_id = str(first.channel.category_id) if hasattr(first.channel, 'category_id') and first.channel.category_id else None
        matched = find_matched_source(config, current_channel_id, current_server_id, category_id)
        if not matched:
            return

        webhook_url = matched.get("webhook_url")
        if not webhook_url:
            return

        server_name = first.guild.name if first.guild else "Direct Message"
        channel_name = first.channel.name if hasattr(first.channel, 'name') else "DM"
        cached = [m for m in messages if m.content or m.author]
        summary_lines = []
        for m in cached[:20]:
            author_name = m.author.name if m.author else "Unknown"
            preview = (m.content[:80] + "...") if m.content and len(m.content) > 80 else (m.content or "*No content*")
            summary_lines.append(f"**{author_name}**: {preview}")
        if len(cached) > 20:
            summary_lines.append(f"*... and {len(cached) - 20} more cached messages*")

        embed_data = {
            "title": f"Bulk Delete in #{channel_name}",
            "description": ("\n".join(summary_lines) if summary_lines else "*No cached content available*")[:2000],
            "color": 0xdc2626,
            "fields": [
                {"name": "Total Deleted", "value": str(len(messages)), "inline": True},
                {"name": "Cached", "value": str(len(cached)), "inline": True},
                {"name": "Not Cached", "value": str(len(messages) - len(cached)), "inline": True},
                {"name": "Channel", "value": f"<#{current_channel_id}>", "inline": True},
                {"name": "Deleted At", "value": discord_ts(datetime.utcnow()), "inline": True}
            ]
        }

        try:
            avatar_url = first.guild.icon.url if first.guild and first.guild.icon else None
            success = await run_in_thread(send_webhook_message, webhook_url=webhook_url, embed_data=embed_data, username=server_name, avatar_url=avatar_url)
            if not success:
                dest_id = matched.get("destination_channel_id")
                new_url, new_id, new_token = await run_in_thread(create_webhook, dest_id, "Channel Logger")
                if new_url:
                    cfg = load_config()
                    for s in cfg.get("sources", []):
                        if s.get("webhook_url") == webhook_url:
                            s["webhook_url"] = new_url
                            s["webhook_id"] = new_id
                            s["webhook_token"] = new_token
                    save_config(cfg)
                    await run_in_thread(send_webhook_message, webhook_url=new_url, embed_data=embed_data, username=server_name, avatar_url=avatar_url)
        except Exception as e:
            print(f"Channel Logger | Error logging bulk delete: {e}", type_="ERROR")

    async def validate_all_webhooks():
        try:
            config = load_config()
            seen = {}
            changed = False
            for source in config.get("sources", []):
                wh_url = source.get("webhook_url")
                dest_id = source.get("destination_channel_id")
                if not wh_url or not dest_id:
                    continue
                if wh_url in seen:
                    if seen[wh_url]:
                        source["webhook_url"] = seen[wh_url]["url"]
                        source["webhook_id"] = seen[wh_url]["id"]
                        source["webhook_token"] = seen[wh_url]["token"]
                    continue
                valid = await run_in_thread(validate_webhook, wh_url)
                if not valid:
                    print(f"Channel Logger | Invalid webhook for dest {dest_id}, recreating...", type_="INFO")
                    new_url, new_id, new_token = await run_in_thread(create_webhook, dest_id, "Channel Logger")
                    if new_url:
                        seen[wh_url] = {"url": new_url, "id": new_id, "token": new_token}
                        source["webhook_url"] = new_url
                        source["webhook_id"] = new_id
                        source["webhook_token"] = new_token
                        changed = True
                    else:
                        seen[wh_url] = None
                else:
                    seen[wh_url] = None
            if changed:
                save_config(config)
                print("Channel Logger | Webhooks validated and updated.", type_="INFO")
        except Exception as e:
            print(f"Channel Logger | Webhook validation error: {e}", type_="ERROR")

    initialize_files()
    config = load_config()
    enable_toggle.checked = config["enabled"]
    log_self_toggle.checked = config.get("log_self", False)
    notify_toggle.checked = config.get("notify_on_log", True)
    ping_toggle.checked = config.get("ping_on_log", False)
    log_deleted_toggle.checked = config.get("log_deleted", True)
    log_edited_toggle.checked = config.get("log_edited", True)
    log_bulk_toggle.checked = config.get("log_bulk_deleted", True)
    log_embeds_toggle.checked = config.get("log_embeds", True)
    log_attachments_toggle.checked = config.get("log_attachments", True)

    last_dest = get_last_dest_channel_id(config)
    if last_dest:
        try:
            ch = bot.get_channel(int(last_dest))
            if ch and ch.guild:
                dest_server_select.selected_items = [str(ch.guild.id)]
                update_dest_channel_list([str(ch.guild.id)])
                dest_channel_select.selected_items = [last_dest]
                dest_current_text.content = f"Will log to: {ch.guild.name} -> #{ch.name}"
                dest_current_text.color = "#4ade80"
        except:
            pass

    refresh_channels()
    tab.render()
    bot.loop.create_task(validate_all_webhooks())


ChannelLogger()