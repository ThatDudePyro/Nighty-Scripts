import json
import asyncio
import requests
from pathlib import Path
from datetime import datetime
    
    BASE_DIR = Path(getScriptsPath()) / "json"
    CONFIG_FILE = BASE_DIR / "ChannelLogger.json"

    def initialize_files():
        BASE_DIR.mkdir(parents=True, exist_ok=True)
        if not CONFIG_FILE.exists():
            default_config = {
                "enabled": True,
                "log_channels": [],
                "log_self": False,
                "notify_on_log": True,
                "destination_channel_id": None
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
                "destination_channel_id": None
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
            headers = {
                "Authorization": bot.http.token,
                "Content-Type": "application/json"
            }
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

    def send_webhook_embed(webhook_url, embed_data, username=None, avatar_url=None):
        if not webhook_url:
            return False
            
        payload = {"embeds": [embed_data]}
        if username:
            payload["username"] = username
        if avatar_url:
            payload["avatar_url"] = avatar_url
            
        headers = {"Content-Type": "application/json"}
        
        try:
            response = requests.post(
                webhook_url, 
                headers=headers, 
                data=json.dumps(payload), 
                timeout=10
            )
            response.raise_for_status()
            return response.status_code == 204
        except requests.exceptions.RequestException as e:
            print(f"Channel Logger | Webhook error: {e}", type_="ERROR")
            return False

    # ======================== UI START ========================
    tab = Tab(
        name="Channel Logger",
        title="Channel Logger Configuration",
        icon="message",
        gap=3
    )

    main_container = tab.create_container(type="rows", gap=3)
    
    top_row = main_container.create_container(type="columns", gap=3)

    settings_card = top_row.create_card(gap=2)
    settings_card.create_ui_element(UI.Text, content="Settings", size="lg", weight="bold")
    enable_toggle = settings_card.create_ui_element(UI.Toggle, label="Enable Logger")
    log_self_toggle = settings_card.create_ui_element(UI.Toggle, label="Log Own Messages")
    notify_toggle = settings_card.create_ui_element(UI.Toggle, label="Notifications")
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
    
    dest_server_select = dest_card.create_ui_element(
        UI.Select,
        label="Server",
        items=dest_servers_list,
        disabled_items=["select_server"],
        mode="single",
        full_width=True
    )
    
    dest_channel_select = dest_card.create_ui_element(
        UI.Select,
        label="Channel",
        items=[{"id": "select_channel", "title": "Select server first"}],
        disabled_items=["select_channel"],
        mode="single",
        full_width=True
    )
    
    dest_status_text = dest_card.create_ui_element(
        UI.Text,
        content="No destination set",
        size="sm",
        color="#f87171"
    )
    
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
    
    source_server_select = add_card.create_ui_element(
        UI.Select,
        label="Server",
        items=source_servers_list,
        disabled_items=["select_server"],
        mode="single",
        full_width=True
    )
    
    source_channel_select = add_card.create_ui_element(
        UI.Select,
        label="Channel",
        items=[{"id": "select_channel", "title": "Select server first"}],
        disabled_items=["select_channel"],
        mode="single",
        full_width=True
    )
    
    add_channel_btn = add_card.create_ui_element(UI.Button, label="Add Channel", variant="cta", full_width=True)

    manage_card = bottom_row.create_card(gap=2)
    manage_card.create_ui_element(UI.Text, content="Manage Sources", size="lg", weight="bold")
    
    status_text = manage_card.create_ui_element(
        UI.Text, 
        content="Logger is enabled", 
        size="sm", 
        color="#4ade80"
    )
    
    count_text = manage_card.create_ui_element(
        UI.Text, 
        content="0 source channels", 
        size="sm", 
        color="#6b7280"
    )
    
    channels_display = manage_card.create_group(type="rows", gap=1)
    
    remove_select = manage_card.create_ui_element(
        UI.Select,
        label="Remove Channel",
        items=[{"id": "", "title": "No channels"}],
        mode="single",
        full_width=True
    )
    remove_btn = manage_card.create_ui_element(UI.Button, label="Remove", variant="flat", full_width=True)
    # ======================== UI END ========================

    channel_text_elements = []

    def update_dest_channel_list(selected_server_ids):
        if not selected_server_ids or not selected_server_ids[0] or selected_server_ids[0] == "select_server":
            dest_channel_select.items = [{"id": "select_channel", "title": "Select a server first"}]
            return
        
        try:
            server_id = int(selected_server_ids[0])
            server = bot.get_guild(server_id)
            
            if not server:
                dest_channel_select.items = [{"id": "select_channel", "title": "Server not found"}]
                return
            
            channels_list = [{"id": "select_channel", "title": "Select a channel"}]
            
            for channel in server.text_channels:
                channels_list.append({
                    "id": str(channel.id),
                    "title": f"#{channel.name}"
                })
            
            dest_channel_select.items = channels_list
            
        except Exception as e:
            print(f"Message Logger | Error updating destination channels: {e}", type_="ERROR")
            dest_channel_select.items = [{"id": "select_channel", "title": "Error loading channels"}]

    def update_source_channel_list(selected_server_ids):
        if not selected_server_ids or not selected_server_ids[0] or selected_server_ids[0] == "select_server":
            source_channel_select.items = [{"id": "select_channel", "title": "Select a server first"}]
            return
        
        try:
            server_id = int(selected_server_ids[0])
            server = bot.get_guild(server_id)
            
            if not server:
                source_channel_select.items = [{"id": "select_channel", "title": "Server not found"}]
                return
            
            channels_list = [{"id": "select_channel", "title": "Select a channel"}]
            
            for channel in server.text_channels:
                channels_list.append({
                    "id": str(channel.id),
                    "title": f"#{channel.name}"
                })
            
            source_channel_select.items = channels_list
            
        except Exception as e:
            print(f"Message Logger | Error updating source channels: {e}", type_="ERROR")
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
                if dest_channel:
                    server_name = dest_channel.guild.name if dest_channel.guild else "DM"
                    dest_status_text.content = f"✓ {server_name} → #{dest_channel.name}"
                    dest_status_text.color = "#4ade80"
                else:
                    dest_status_text.content = "Channel not found"
                    dest_status_text.color = "#f87171"
            except:
                dest_status_text.content = "Invalid channel"
                dest_status_text.color = "#f87171"
        else:
            dest_status_text.content = "No destination set"
            dest_status_text.color = "#f87171"
        
        if config.get("log_channels"):
            items = []
            for i, channel in enumerate(config["log_channels"]):
                channel_name = f"Channel {channel}"
                try:
                    discord_channel = bot.get_channel(int(channel))
                    if discord_channel:
                        server_name = discord_channel.guild.name if discord_channel.guild else "DM"
                        channel_name = f"{server_name} → #{discord_channel.name}"
                except:
                    pass
                
                items.append({
                    "id": str(i),
                    "title": f"{channel_name}"
                })
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
            for i, channel_id in enumerate(channels_to_show):
                channel_display = f"• {channel_id}"
                try:
                    discord_channel = bot.get_channel(int(channel_id))
                    if discord_channel:
                        server_name = discord_channel.guild.name if discord_channel.guild else "DM"
                        channel_display = f"• {server_name} → #{discord_channel.name}"
                except:
                    pass
                
                text_element = channels_display.create_ui_element(
                    UI.Text, 
                    content=channel_display, 
                    size="sm"
                )
                channel_text_elements.append(text_element)
            
            if len(config["log_channels"]) > 5:
                more_text = channels_display.create_ui_element(
                    UI.Text,
                    content=f"+ {len(config['log_channels']) - 5} more...",
                    size="sm",
                    color="#6b7280"
                )
                channel_text_elements.append(more_text)
        else:
            no_channels_element = channels_display.create_ui_element(
                UI.Text, 
                content="No channels yet", 
                size="sm", 
                color="#6b7280"
            )
            channel_text_elements.append(no_channels_element)
        
        update_display()

    async def save_settings():
        config = load_config()
        config["enabled"] = enable_toggle.checked
        config["log_self"] = log_self_toggle.checked
        config["notify_on_log"] = notify_toggle.checked
        
        if save_config(config):
            update_display()
            tab.toast(type="SUCCESS", title="Settings Saved")
        else:
            tab.toast(type="ERROR", title="Save Failed")

    async def save_destination():
        if not dest_channel_select.selected_items or not dest_channel_select.selected_items[0] or dest_channel_select.selected_items[0] == "select_channel":
            tab.toast(
                type="ERROR", 
                title="No Channel Selected", 
                description="Please select a destination channel"
            )
            return
        
        channel_id = dest_channel_select.selected_items[0]
        
        try:
            discord_channel = bot.get_channel(int(channel_id))
            if not discord_channel:
                tab.toast(
                    type="ERROR",
                    title="Invalid Channel",
                    description="Bot cannot access this channel"
                )
                return
        except:
            tab.toast(
                type="ERROR",
                title="Invalid Channel",
                description="Channel ID is invalid"
            )
            return
        
        config = load_config()
        config["destination_channel_id"] = channel_id
        
        if save_config(config):
            refresh_channels()
            
            try:
                channel_name = f"#{discord_channel.name}" if discord_channel else channel_id
            except:
                channel_name = channel_id
            
            tab.toast(
                type="SUCCESS", 
                title="Destination Set", 
                description=f"Logs will be sent to {channel_name}"
            )
        else:
            tab.toast(type="ERROR", title="Save Failed")

    async def add_channel():
        if not source_channel_select.selected_items or not source_channel_select.selected_items[0] or source_channel_select.selected_items[0] == "select_channel":
            tab.toast(
                type="ERROR", 
                title="No Channel Selected", 
                description="Please select a source channel"
            )
            return
        
        channel_id = source_channel_select.selected_items[0]
        
        config = load_config()
        
        if channel_id in config.get("log_channels", []):
            tab.toast(
                type="ERROR", 
                title="Duplicate Channel", 
                description="This channel is already being logged"
            )
            return
        
        if "log_channels" not in config:
            config["log_channels"] = []
        
        config["log_channels"].append(channel_id)
        
        if save_config(config):
            refresh_channels()
            
            try:
                discord_channel = bot.get_channel(int(channel_id))
                channel_name = f"#{discord_channel.name}" if discord_channel else channel_id
            except:
                channel_name = channel_id
            
            tab.toast(
                type="SUCCESS", 
                title="Channel Added", 
                description=f"Now logging {channel_name}"
            )
        else:
            tab.toast(type="ERROR", title="Save Failed")

    async def remove_channel():
        if not remove_select.selected_items or not remove_select.selected_items[0]:
            tab.toast(
                type="ERROR", 
                title="No Selection", 
                description="Select a channel to remove"
            )
            return
        
        try:
            index = int(remove_select.selected_items[0])
            config = load_config()
            
            if 0 <= index < len(config["log_channels"]):
                removed = config["log_channels"].pop(index)
                if save_config(config):
                    refresh_channels()
                    
                    try:
                        discord_channel = bot.get_channel(int(removed))
                        channel_name = f"#{discord_channel.name}" if discord_channel else removed
                    except:
                        channel_name = removed
                    
                    tab.toast(
                        type="SUCCESS", 
                        title="Channel Removed", 
                        description=f"Stopped logging {channel_name}"
                    )
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
        
        if not config["enabled"] or not config.get("log_channels"):
            return
        
        if not config.get("destination_channel_id"):
            return
        
        if not config.get("log_self", False) and message.author.id == bot.user.id:
            return
        
        current_channel_id = str(message.channel.id)
        
        if current_channel_id not in config["log_channels"]:
            return
        
        server_name = message.guild.name if message.guild else "Direct Message"
        channel_name = message.channel.name if hasattr(message.channel, 'name') else "DM"
        
        if message.guild:
            message_link = f"https://discord.com/channels/{message.guild.id}/{message.channel.id}/{message.id}"
        else:
            message_link = f"https://discord.com/channels/@me/{message.channel.id}/{message.id}"
        
        embed_data = {
            "title": f"#{channel_name}",
            "description": message.content[:2000] if message.content else "*No content*",
            "color": 0x5865F2,
            "author": {
                "name": f"{message.author.name}#{message.author.discriminator}",
                "icon_url": str(message.author.avatar.url) if message.author.avatar else None
            },
            "fields": [
                {
                    "name": "Author",
                    "value": f"<@{message.author.id}>",
                    "inline": True
                },
                {
                    "name": "Channel",
                    "value": f"<#{current_channel_id}>",
                    "inline": True
                },
                {
                    "name": "Message Link",
                    "value": f"[Jump to Message]({message_link})",
                    "inline": False
                }
            ],
            "timestamp": datetime.utcnow().isoformat()
        }
        
        if message.attachments:
            attachment_urls = "\n".join([att.url for att in message.attachments[:5]])
            embed_data["fields"].append({
                "name": "Attachments",
                "value": attachment_urls,
                "inline": False
            })
        
        try:
            webhook_url, webhook_id = await run_in_thread(
                create_webhook,
                config["destination_channel_id"],
                server_name
            )
            
            if not webhook_url:
                print("Message Logger | Failed to create webhook", type_="ERROR")
                return
            
            webhook_token = webhook_url.split('/')[-1]
            
            avatar_url = message.guild.icon.url if message.guild and message.guild.icon else None
            
            success = await run_in_thread(
                send_webhook_embed,
                webhook_url=webhook_url,
                embed_data=embed_data,
                username=server_name,
                avatar_url=avatar_url
            )
            
            await run_in_thread(delete_webhook, webhook_id, webhook_token)
            
            if success and config.get("notify_on_log", True):
                print(
                    f"Message Logger | Logged message from {message.author.name} in #{channel_name} ({server_name})",
                    type_="INFO"
                )
        except Exception as e:
            print(f"Message Logger | Error logging message: {e}", type_="ERROR")

    initialize_files()
    config = load_config()
    enable_toggle.checked = config["enabled"]
    log_self_toggle.checked = config.get("log_self", False)
    notify_toggle.checked = config.get("notify_on_log", True)
    refresh_channels()

    tab.render()