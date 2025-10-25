import json
import asyncio
import requests
from pathlib import Path
from datetime import datetime
import os
import re

def ChannelLogger():
    BASE_DIR = Path(getScriptsPath()) / "json"
    CONFIG_FILE = BASE_DIR / "ChannelLoggerConf.json"

    def load_theme():
        try:
            nighty_config_path = Path(os.getenv("APPDATA")) / "Nighty Selfbot" / "nighty.config"
            with open(nighty_config_path, "r", encoding="utf-8") as f:
                config_data = json.load(f)
            theme_name = config_data.get("theme")
            theme_file = Path(os.getenv("APPDATA")) / "Nighty Selfbot" / "data" / "themes" / f"{theme_name}.json"
            with open(theme_file, "r", encoding="utf-8") as tf:
                theme_data = json.load(tf)
            return theme_data
        except Exception as e:
            print(f"Channel Logger | Error loading theme: {e}", type_="ERROR")
            return {}

    theme = load_theme()
    theme_color = int(theme.get("color", "5865F2").replace("#", ""), 16) if theme.get("color") else 0x5865F2
    theme_small_image = theme.get("small_image")
    theme_large_image = theme.get("large_image")

    def initialize_files():
        BASE_DIR.mkdir(parents=True, exist_ok=True)
        if not CONFIG_FILE.exists():
            default_config = {
                "enabled": True,
                "log_channels": [],
                "log_self": False,
                "notify_on_log": True,
                "destination_channel_id": None,
                "ping_on_log": False
            }
            with open(CONFIG_FILE, "w") as f:
                json.dump(default_config, f, indent=4)

    def load_config():
        try:
            with open(CONFIG_FILE, "r") as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {
                "enabled": True,
                "log_channels": [],
                "log_self": False,
                "notify_on_log": True,
                "destination_channel_id": None,
                "ping_on_log": False
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
            payload = {"name": webhook_name}
            response = requests.post(url, headers=headers, json=payload, timeout=10)
            response.raise_for_status()
            webhook_data = response.json()
            webhook_url = f"https://discord.com/api/webhooks/{webhook_data['id']}/{webhook_data['token']}"
            return webhook_url, webhook_data['id']
        except Exception as e:
            print(f"Channel Logger | Error creating webhook: {e}", type_="ERROR")
            return None, None

    def delete_webhook(webhook_id, webhook_token):
        try:
            url = f"https://discord.com/api/v9/webhooks/{webhook_id}/{webhook_token}"
            response = requests.delete(url, timeout=10)
            response.raise_for_status()
            return True
        except Exception as e:
            print(f"Channel Logger | Error deleting webhook: {e}", type_="ERROR")
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
        headers = {"Content-Type": "application/json"}
        try:
            response = requests.post(webhook_url, headers=headers, data=json.dumps(payload), timeout=10)
            response.raise_for_status()
            return response.status_code in (200, 204)
        except requests.exceptions.RequestException as e:
            print(f"Channel Logger | Webhook error: {e}", type_="ERROR")
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

    tab = Tab(name="Channel Logger", title="Channel Logger Configuration", icon="message", gap=3)
    main_container = tab.create_container(type="rows", gap=3)
    top_row = main_container.create_container(type="columns", gap=3)

    settings_card = top_row.create_card(gap=2)
    settings_card.create_ui_element(UI.Text, content="Settings", size="lg", weight="bold")
    enable_toggle = settings_card.create_ui_element(UI.Toggle, label="Enable Logger")
    log_self_toggle = settings_card.create_ui_element(UI.Toggle, label="Log Own Messages")
    notify_toggle = settings_card.create_ui_element(UI.Toggle, label="Console Notifications")
    ping_toggle = settings_card.create_ui_element(UI.Toggle, label="Ping on Log")
    save_settings_btn = settings_card.create_ui_element(UI.Button, label="Save", variant="cta", full_width=True)

    dest_card = top_row.create_card(gap=2)
    dest_card.create_ui_element(UI.Text, content="Log Destination", size="lg", weight="bold")
    
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
    add_card = bottom_row.create_card(gap=2)
    add_card.create_ui_element(UI.Text, content="Add Source Channel", size="lg", weight="bold")
    
    source_servers_list = [{"id": "select_server", "title": "Select server"}]
    for server in bot.guilds:
        source_servers_list.append({
            "id": str(server.id), 
            "title": server.name, 
            "iconUrl": server.icon.url if server.icon else "https://cdn.discordapp.com/embed/avatars/0.png"
        })
    
    source_server_select = add_card.create_ui_element(UI.Select, label="Server", items=source_servers_list, disabled_items=["select_server"], mode="single", full_width=True)
    source_channel_select = add_card.create_ui_element(UI.Select, label="Channel", items=[{"id": "select_channel", "title": "Select server first"}], disabled_items=["select_channel"], mode="single", full_width=True)
    add_channel_btn = add_card.create_ui_element(UI.Button, label="Add Channel", variant="cta", full_width=True)

    manage_card = bottom_row.create_card(gap=2)
    manage_card.create_ui_element(UI.Text, content="Manage Sources", size="lg", weight="bold")
    status_text = manage_card.create_ui_element(UI.Text, content="Logger is enabled", size="sm", color="#4ade80")
    count_text = manage_card.create_ui_element(UI.Text, content="0 source channels", size="sm", color="#6b7280")
    channels_display = manage_card.create_group(type="rows", gap=1)
    remove_select = manage_card.create_ui_element(UI.Select, label="Remove Channel", items=[{"id": "", "title": "No channels"}], mode="single", full_width=True)
    remove_btn = manage_card.create_ui_element(UI.Button, label="Remove", variant="flat", full_width=True)

    channel_text_elements = []

    def update_dest_channel_list(selected_server_ids):
        if not selected_server_ids or selected_server_ids[0] in ["", "select_server"]:
            dest_channel_select.items = [{"id": "select_channel", "title": "Select a server first"}]
            return
        try:
            server_id = int(selected_server_ids[0])
            server = bot.get_guild(server_id)
            channels_list = [{"id": "select_channel", "title": "Select a channel"}]
            for channel in server.text_channels:
                channels_list.append({"id": str(channel.id), "title": f"#{channel.name}"})
            dest_channel_select.items = channels_list
        except Exception as e:
            print(f"Channel Logger | Error updating destination channels: {e}", type_="ERROR")
            dest_channel_select.items = [{"id": "select_channel", "title": "Error loading channels"}]

    def update_source_channel_list(selected_server_ids):
        if not selected_server_ids or selected_server_ids[0] in ["", "select_server"]:
            source_channel_select.items = [{"id": "select_channel", "title": "Select a server first"}]
            return
        try:
            server_id = int(selected_server_ids[0])
            server = bot.get_guild(server_id)
            channels_list = [{"id": "select_channel", "title": "Select a channel"}]
            for channel in server.text_channels:
                channels_list.append({"id": str(channel.id), "title": f"#{channel.name}"})
            source_channel_select.items = channels_list
        except Exception as e:
            print(f"Channel Logger | Error updating source channels: {e}", type_="ERROR")
            source_channel_select.items = [{"id": "select_channel", "title": "Error loading channels"}]

    def update_display():
        config = load_config()
        enabled = config["enabled"]
        channel_count = len(config.get("log_channels", []))
        status_text.content = f"Status: {'Enabled' if enabled else 'Disabled'}"
        status_text.color = "#4ade80" if enabled else "#f87171"
        count_text.content = f"{channel_count} channel{'s' if channel_count != 1 else ''} configured"
        dest_id = config.get("destination_channel_id")
        if dest_id:
            try:
                dest_channel = bot.get_channel(int(dest_id))
                server_name = dest_channel.guild.name if dest_channel.guild else "DM"
                dest_status_text.content = f"Logging to {server_name} -> #{dest_channel.name}"
                dest_status_text.color = "#4ade80"
            except:
                dest_status_text.content = "Invalid channel"
                dest_status_text.color = "#f87171"
        else:
            dest_status_text.content = "No destination set"
            dest_status_text.color = "#f87171"
        if config.get("log_channels"):
            items = []
            for i, channel in enumerate(config["log_channels"]):
                try:
                    discord_channel = bot.get_channel(int(channel))
                    server_name = discord_channel.guild.name if discord_channel.guild else "DM"
                    channel_name = f"{server_name} -> #{discord_channel.name}"
                except:
                    channel_name = f"Channel {channel}"
                items.append({"id": str(i), "title": channel_name})
            remove_select.items = items
        else:
            remove_select.items = [{"id": "", "title": "No channels"}]

    def refresh_channels():
        config = load_config()
        for element in channel_text_elements:
            element.visible = False
        channel_text_elements.clear()
        if config.get("log_channels"):
            channels_to_show = config["log_channels"][:5]
            for channel_id in channels_to_show:
                try:
                    discord_channel = bot.get_channel(int(channel_id))
                    server_name = discord_channel.guild.name if discord_channel.guild else "DM"
                    channel_display = f"• {server_name} -> #{discord_channel.name}"
                except:
                    channel_display = f"• {channel_id}"
                text_element = channels_display.create_ui_element(UI.Text, content=channel_display, size="sm")
                channel_text_elements.append(text_element)
            if len(config["log_channels"]) > 5:
                more_text = channels_display.create_ui_element(UI.Text, content=f"+ {len(config['log_channels']) - 5} more...", size="sm", color="#6b7280")
                channel_text_elements.append(more_text)
        else:
            no_channels_element = channels_display.create_ui_element(UI.Text, content="No channels yet", size="sm", color="#6b7280")
            channel_text_elements.append(no_channels_element)
        update_display()

    async def save_settings():
        config = load_config()
        config["enabled"] = enable_toggle.checked
        config["log_self"] = log_self_toggle.checked
        config["notify_on_log"] = notify_toggle.checked
        config["ping_on_log"] = ping_toggle.checked
        if save_config(config):
            update_display()
            tab.toast(type="SUCCESS", title="Settings Saved")
        else:
            tab.toast(type="ERROR", title="Save Failed")

    async def save_destination():
        if not dest_channel_select.selected_items or dest_channel_select.selected_items[0] in ["", "select_channel"]:
            tab.toast(type="ERROR", title="No Channel Selected", description="Please select a destination channel")
            return
        channel_id = dest_channel_select.selected_items[0]
        try:
            discord_channel = bot.get_channel(int(channel_id))
            if not discord_channel:
                tab.toast(type="ERROR", title="Invalid Channel", description="Bot cannot access this channel")
                return
        except:
            tab.toast(type="ERROR", title="Invalid Channel", description="Channel ID is invalid")
            return
        config = load_config()
        config["destination_channel_id"] = channel_id
        if save_config(config):
            refresh_channels()
            channel_name = f"#{discord_channel.name}" if discord_channel else channel_id
            tab.toast(type="SUCCESS", title="Destination Set", description=f"Logs will be sent to {channel_name}")
        else:
            tab.toast(type="ERROR", title="Save Failed")

    async def add_channel():
        if not source_channel_select.selected_items or source_channel_select.selected_items[0] in ["", "select_channel"]:
            tab.toast(type="ERROR", title="No Channel Selected", description="Please select a source channel")
            return
        channel_id = source_channel_select.selected_items[0]
        config = load_config()
        if channel_id in config.get("log_channels", []):
            tab.toast(type="ERROR", title="Duplicate Channel", description="This channel is already being logged")
            return
        if "log_channels" not in config:
            config["log_channels"] = []
        config["log_channels"].append(channel_id)
        if save_config(config):
            refresh_channels()
            discord_channel = bot.get_channel(int(channel_id))
            channel_name = f"#{discord_channel.name}" if discord_channel else channel_id
            tab.toast(type="SUCCESS", title="Channel Added", description=f"Now logging {channel_name}")
        else:
            tab.toast(type="ERROR", title="Save Failed")

    async def remove_channel():
        if not remove_select.selected_items or not remove_select.selected_items[0]:
            tab.toast(type="ERROR", title="No Selection", description="Select a channel to remove")
            return
        try:
            index = int(remove_select.selected_items[0])
            config = load_config()
            if 0 <= index < len(config["log_channels"]):
                removed = config["log_channels"].pop(index)
                if save_config(config):
                    refresh_channels()
                    discord_channel = bot.get_channel(int(removed))
                    channel_name = f"#{discord_channel.name}" if discord_channel else removed
                    tab.toast(type="SUCCESS", title="Channel Removed", description=f"Stopped logging {channel_name}")
                else:
                    tab.toast(type="ERROR", title="Save Failed")
            else:
                tab.toast(type="ERROR", title="Invalid Selection")
        except (ValueError, TypeError):
            tab.toast(type="ERROR", title="Invalid Selection")

    save_settings_btn.onClick = save_settings
    save_destination_btn.onClick = save_destination
    add_channel_btn.onClick = add_channel
    remove_btn.onClick = remove_channel
    dest_server_select.onChange = update_dest_channel_list
    source_server_select.onChange = update_source_channel_list

    @bot.listen('on_message')
    async def log_message(message):
        config = load_config()
        if not config["enabled"] or not config.get("log_channels") or not config.get("destination_channel_id"):
            return
        if not config.get("log_self", False) and message.author.id == bot.user.id:
            return
        current_channel_id = str(message.channel.id)
        if current_channel_id not in config["log_channels"]:
            return
        server_name = message.guild.name if message.guild else "Direct Message"
        channel_name = message.channel.name if hasattr(message.channel, 'name') else "DM"
        message_link = f"https://discord.com/channels/{message.guild.id if message.guild else '@me'}/{message.channel.id}/{message.id}"

        content_text = message.content or ""
        inline_urls = extract_all_urls(content_text)
        attachments = [att.url for att in message.attachments] if message.attachments else []
        links_to_send = []
        for u in inline_urls: 
            if u not in links_to_send:
                links_to_send.append(u)
        for a in attachments: 
            if a not in links_to_send:
                links_to_send.append(a)

        media_urls = [u for u in links_to_send if re.search(r'\.(?:jpg|jpeg|png|gif|webp|bmp)$', u, re.IGNORECASE)]
        other_links = [u for u in links_to_send if u not in media_urls]

        cleaned_content = content_text
        if links_to_send and cleaned_content:
            for l in links_to_send:
                cleaned_content = cleaned_content.replace(l, "")
            cleaned_content = re.sub(r'\s+\n', '\n', cleaned_content)
            cleaned_content = re.sub(r'\n{3,}', '\n\n', cleaned_content)
            cleaned_content = cleaned_content.strip()
            if not cleaned_content:
                cleaned_content = None
        else:
            cleaned_content = cleaned_content if cleaned_content else None

        embed_data = {
            "title": f"#{channel_name}",
            "description": cleaned_content[:2000] if cleaned_content else "*No content*",
            "color": theme_color,
            "author": {"name": f"{message.author.name}#{message.author.discriminator}", "icon_url": str(message.author.avatar.url) if message.author.avatar else None},
            "fields": [
                {"name": "Author", "value": f"<@{message.author.id}>", "inline": True},
                {"name": "Channel", "value": f"<#{current_channel_id}>", "inline": True},
                {"name": "Message Link", "value": f"[Jump to Message]({message_link})", "inline": False}
            ],
            "timestamp": datetime.utcnow().isoformat()
        }

        if theme_small_image and not links_to_send:
            embed_data["thumbnail"] = {"url": theme_small_image}
        if theme_large_image and not links_to_send:
            embed_data["image"] = {"url": theme_large_image}

        try:
            webhook_url, webhook_id = await run_in_thread(create_webhook, config["destination_channel_id"], server_name)
            if not webhook_url:
                print("Channel Logger | Failed to create webhook", type_="ERROR")
                return
            webhook_token = webhook_url.split('/')[-1]
            avatar_url = message.guild.icon.url if message.guild and message.guild.icon else None

            content_to_send = f"<@{bot.user.id}>" if config.get("ping_on_log", False) else None
            await run_in_thread(send_webhook_message, webhook_url=webhook_url, content=content_to_send, embed_data=embed_data, username=server_name, avatar_url=avatar_url)

            if other_links:
                for link in other_links:
                    await run_in_thread(send_webhook_message, webhook_url=webhook_url, content=link, embed_data=None, username=server_name, avatar_url=avatar_url)
            if media_urls:
                for media in media_urls:
                    await run_in_thread(send_webhook_message, webhook_url=webhook_url, content=media, embed_data=None, username=server_name, avatar_url=avatar_url)
            
            if message.embeds:
                for original_embed in message.embeds:
                    embed_dict = original_embed.to_dict()
                    logged_embed = {"color": embed_dict.get("color", theme_color), "timestamp": datetime.utcnow().isoformat()}
                    if embed_dict.get("title"):
                        logged_embed["title"] = "Embed: " + embed_dict["title"]
                    else:
                        logged_embed["title"] = "Embedded Content"
                    if embed_dict.get("description"):
                        logged_embed["description"] = embed_dict["description"][:2000]
                    if embed_dict.get("author"):
                        logged_embed["author"] = embed_dict["author"]
                    if embed_dict.get("fields"):
                        logged_embed["fields"] = embed_dict["fields"]
                    if embed_dict.get("footer"):
                        logged_embed["footer"] = embed_dict["footer"]
                    if embed_dict.get("thumbnail"):
                        logged_embed["thumbnail"] = embed_dict["thumbnail"]
                    if embed_dict.get("image"):
                        logged_embed["image"] = embed_dict["image"]
                    await run_in_thread(send_webhook_message, webhook_url=webhook_url, content=None, embed_data=logged_embed, username=server_name, avatar_url=avatar_url)
            
            await run_in_thread(delete_webhook, webhook_id, webhook_token)
            if config.get("notify_on_log", True):
                print(f"Channel Logger | Logged message from {message.author.name} in #{channel_name} ({server_name})", type_="INFO")
        except Exception as e:
            print(f"Channel Logger | Error logging message: {e}", type_="ERROR")

    initialize_files()
    config = load_config()
    enable_toggle.checked = config["enabled"]
    log_self_toggle.checked = config.get("log_self", False)
    notify_toggle.checked = config.get("notify_on_log", True)
    ping_toggle.checked = config.get("ping_on_log", False)
    refresh_channels()
    tab.render()

ChannelLogger()