import json
import asyncio
import requests
from pathlib import Path
from datetime import datetime
import os
import re

def DMLogger():
    BASE_DIR = Path(getScriptsPath()) / "json"
    CONFIG_FILE = BASE_DIR / "DMLoggerConf.json"

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
            print(f"DM Logger | Error loading theme: {e}", type_="ERROR")
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
            print(f"DM Logger | Error saving config: {e}", type_="ERROR")
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
            print(f"DM Logger | Error creating webhook: {e}", type_="ERROR")
            return None, None

    def delete_webhook(webhook_id, webhook_token):
        try:
            url = f"https://discord.com/api/v9/webhooks/{webhook_id}/{webhook_token}"
            response = requests.delete(url, timeout=10)
            response.raise_for_status()
            return True
        except Exception as e:
            print(f"DM Logger | Error deleting webhook: {e}", type_="ERROR")
            return False

    def send_webhook_message(webhook_url, content=None, embed_data=None, username=None, avatar_url=None):
        if not webhook_url: return False
        payload = {}
        if content: payload["content"] = content
        if embed_data: payload["embeds"] = [embed_data]
        if username: payload["username"] = username
        if avatar_url: payload["avatar_url"] = avatar_url
        headers = {"Content-Type": "application/json"}
        try:
            response = requests.post(webhook_url, headers=headers, data=json.dumps(payload), timeout=10)
            response.raise_for_status()
            return response.status_code in (200, 204)
        except requests.exceptions.RequestException as e:
            print(f"DM Logger | Webhook error: {e}", type_="ERROR")
            return False

    def extract_all_urls(text):
        if not text: return []
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

    # ======================== UI START ========================
    tab = Tab(name="DM Logger", title="DM Logger Configuration", icon="message", gap=3)
    main_container = tab.create_container(type="rows", gap=3)
    top_row = main_container.create_container(type="columns", gap=3)

    settings_card = top_row.create_card(gap=2)
    settings_card.create_ui_element(UI.Text, content="Settings", size="lg", weight="bold")
    enable_toggle = settings_card.create_ui_element(UI.Toggle, label="Enable Logger")
    log_self_toggle = settings_card.create_ui_element(UI.Toggle, label="Log Own DMs")
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
    # ======================== UI END ========================

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
            print(f"DM Logger | Error updating destination channels: {e}", type_="ERROR")
            dest_channel_select.items = [{"id": "select_channel", "title": "Error loading channels"}]

    async def save_settings():
        config = load_config()
        config["enabled"] = enable_toggle.checked
        config["log_self"] = log_self_toggle.checked
        config["notify_on_log"] = notify_toggle.checked
        config["ping_on_log"] = ping_toggle.checked
        if save_config(config):
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
            dest_status_text.content = f"✓ #{discord_channel.name}"
            dest_status_text.color = "#4ade80"
            tab.toast(type="SUCCESS", title="Destination Set", description=f"Logs will be sent to #{discord_channel.name}")
        else:
            tab.toast(type="ERROR", title="Save Failed")

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

        content_text = message.content or ""
        inline_urls = extract_all_urls(content_text)
        attachments = [att.url for att in getattr(message, "attachments", [])] if getattr(message, "attachments", None) else []

        links_to_send = []
        for u in inline_urls: 
            if u not in links_to_send: links_to_send.append(u)
        for a in attachments: 
            if a not in links_to_send: links_to_send.append(a)

        media_urls = [u for u in links_to_send if re.search(r'\.(?:jpg|jpeg|png|gif|webp|bmp)$', u, re.IGNORECASE)]
        other_links = [u for u in links_to_send if u not in media_urls]

        cleaned_content = content_text
        if links_to_send and cleaned_content:
            for l in links_to_send: cleaned_content = cleaned_content.replace(l, "")
            cleaned_content = re.sub(r'\s+\n', '\n', cleaned_content)
            cleaned_content = re.sub(r'\n{3,}', '\n\n', cleaned_content).strip()
            if not cleaned_content: cleaned_content = None
        else:
            cleaned_content = cleaned_content if cleaned_content else None

        embed_data = {
            "title": f"DM from {message.author.name}",
            "description": cleaned_content[:2000] if cleaned_content else "*No content*",
            "color": theme_color,
            "author": {"name": f"{message.author.name}#{message.author.discriminator}", "icon_url": str(message.author.avatar.url) if message.author.avatar else None},
            "timestamp": datetime.utcnow().isoformat()
        }

        if theme_small_image and not links_to_send:
            embed_data["thumbnail"] = {"url": theme_small_image}
        if theme_large_image and not links_to_send:
            embed_data["image"] = {"url": theme_large_image}

        try:
            webhook_url, webhook_id = await run_in_thread(create_webhook, config["destination_channel_id"], f"DM {message.author.name}")
            if not webhook_url: return
            webhook_token = webhook_url.split('/')[-1]
            content_to_send = f"<@{bot.user.id}>" if config.get("ping_on_log", False) else None

            await run_in_thread(send_webhook_message, webhook_url=webhook_url, content=content_to_send, embed_data=embed_data, username=message.author.name, avatar_url=str(message.author.avatar.url) if message.author.avatar else None)
            
            for link in other_links + media_urls:
                await run_in_thread(send_webhook_message, webhook_url=webhook_url, content=link, embed_data=None, username=message.author.name, avatar_url=str(message.author.avatar.url) if message.author.avatar else None)

            await run_in_thread(delete_webhook, webhook_id, webhook_token)
            if config.get("notify_on_log", True):
                print(f"DM Logger | Logged DM from {message.author.name}", type_="INFO")
        except Exception as e:
            print(f"DM Logger | Error logging DM: {e}", type_="ERROR")

    initialize_files()
    config = load_config()
    enable_toggle.checked = config["enabled"]
    log_self_toggle.checked = config.get("log_self", False)
    notify_toggle.checked = config.get("notify_on_log", True)
    ping_toggle.checked = config.get("ping_on_log", False)
    tab.render()

DMLogger()