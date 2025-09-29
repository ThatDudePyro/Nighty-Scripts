import json
import asyncio
from pathlib import Path

def AutoReplyScript():
    BASE_DIR = Path(getScriptsPath()) / "json"
    CONFIG_FILE = BASE_DIR / "auto_reply_config.json"

    def initialize_files():
        BASE_DIR.mkdir(parents=True, exist_ok=True)
        if not CONFIG_FILE.exists():
            default_config = {
                "enabled": True,
                "triggers": [],
                "notify_on_send": True,
                "reply_to_self": True,
                "default_delay": 10
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
                "triggers": [],
                "notify_on_send": True,
                "reply_to_self": True,
                "default_delay": 10
            }

    def save_config(config):
        try:
            with open(CONFIG_FILE, "w") as f:
                json.dump(config, f, indent=4)
            return True
        except Exception as e:
            print(f"Auto Reply | Error saving config: {e}", type_="ERROR")
            return False

    # --- UI SETUP ---
    tab = Tab(
        name="Auto Reply",
        title="Auto Reply Configuration", 
        icon="mail",
        gap=4
    )

    main_container = tab.create_container(type="rows", gap=4)
    top_container = main_container.create_container(type="columns", gap=4)

    settings_card = top_container.create_card(gap=3)
    settings_card.create_ui_element(UI.Text, content="Settings", size="xl", weight="bold")
    
    enable_toggle = settings_card.create_ui_element(UI.Toggle, label="Enable Auto Reply")
    notify_toggle = settings_card.create_ui_element(UI.Toggle, label="Show Notifications")
    reply_self_toggle = settings_card.create_ui_element(UI.Toggle, label="Reply to Self")
    delay_input = settings_card.create_ui_element(UI.Input, label="Default Delay", placeholder="10", value="10")
    save_btn = settings_card.create_ui_element(UI.Button, label="Save Settings", variant="cta")

    add_card = top_container.create_card(gap=3)
    add_card.create_ui_element(UI.Text, content="Add Trigger", size="xl", weight="bold")
    
    trigger_input = add_card.create_ui_element(UI.Input, label="Trigger Message", placeholder="Hello bot")
    reply_input = add_card.create_ui_element(UI.Input, label="Reply Message", placeholder="Hi there!")
    channel_input = add_card.create_ui_element(UI.Input, label="Channel ID", placeholder="123456789012345678")
    delay_trigger_input = add_card.create_ui_element(UI.Input, label="Delay (seconds)", placeholder="10")
    fuzzy_toggle = add_card.create_ui_element(UI.Toggle, label="Fuzzy Match (contains phrase)")
    blacklist_input = add_card.create_ui_element(UI.Input, label="Ignore if contains (optional)", placeholder="stop, ignore, no")
    add_btn = add_card.create_ui_element(UI.Button, label="Add Trigger", variant="cta")

    status_card = main_container.create_card(gap=3)
    status_card.create_ui_element(UI.Text, content="Status & Current Triggers", size="xl", weight="bold")
    
    status_row = status_card.create_group(type="columns", gap=4, full_width=True)
    status_text = status_row.create_ui_element(UI.Text, content="Auto Reply is enabled", size="base", color="#4ade80")
    count_text = status_row.create_ui_element(UI.Text, content="0 triggers", size="base", color="#6b7280")
    
    status_card.create_ui_element(UI.Text, content="Current Triggers:", size="lg", weight="bold")
    
    triggers_display = status_card.create_group(type="rows", gap=1)
    
    remove_select = status_card.create_ui_element(UI.Select,
        label="Select Trigger to Remove",
        items=[{"id": "", "title": "No triggers available"}],
        mode="single"
    )
    remove_btn = status_card.create_ui_element(UI.Button, label="Remove Selected Trigger", variant="flat")
    # --- END UI SETUP ---

    trigger_text_elements = []
    
    def fuzzy_match(message, trigger_phrase):
        return trigger_phrase.lower() in message.lower()
    
    def update_display():
        config = load_config()
        enabled = config["enabled"]
        trigger_count = len(config.get("triggers", []))
        
        status_text.content = f"Auto Reply is {'enabled' if enabled else 'disabled'}"
        status_text.color = "#4ade80" if enabled else "#f87171"
        count_text.content = f"{trigger_count} triggers configured"
        
        if config.get("triggers"):
            items = []
            for i, trigger in enumerate(config["triggers"]):
                match_type = "Fuzzy" if trigger.get("fuzzy_match", False) else "Exact"
                blacklist_info = f" | Ignores: {trigger['blacklist']}" if trigger.get("blacklist") else ""
                items.append({
                    "id": str(i),
                    "title": f"{i+1}. '{trigger['trigger_message']}' → '{trigger['reply_message']}' ({match_type}{blacklist_info})"
                })
            remove_select.items = items
        else:
            remove_select.items = [{"id": "", "title": "No triggers to remove"}]

    def refresh_triggers():
        config = load_config()
        
        for element in trigger_text_elements:
            element.visible = False
        trigger_text_elements.clear()
        
        if config.get("triggers"):
            for i, trigger in enumerate(config["triggers"]):
                match_type = "Fuzzy" if trigger.get("fuzzy_match", False) else "Exact"
                blacklist_info = f" | Ignores: {trigger['blacklist']}" if trigger.get("blacklist") else ""
                text = f"{i+1}. '{trigger['trigger_message']}' → '{trigger['reply_message']}' (Ch: {trigger['channel_id']}, {match_type}{blacklist_info})"
                text_element = triggers_display.create_ui_element(UI.Text, content=text, size="sm")
                trigger_text_elements.append(text_element)
        else:
            no_triggers_element = triggers_display.create_ui_element(UI.Text, content="No triggers configured", size="sm", color="#6b7280")
            trigger_text_elements.append(no_triggers_element)
        
        update_display()

    async def remove_selected_trigger():
        if not remove_select.selected_items or not remove_select.selected_items[0]:
            tab.toast(type="ERROR", title="No Selection", description="Please select a trigger to remove")
            return
            
        try:
            index = int(remove_select.selected_items[0])
            config = load_config()
            
            if 0 <= index < len(config["triggers"]):
                removed = config["triggers"].pop(index)
                if save_config(config):
                    refresh_triggers()
                    tab.toast(type="SUCCESS", title="Trigger Removed", description=f"Removed: '{removed['trigger_message']}'")
                else:
                    tab.toast(type="ERROR", title="Save Failed")
            else:
                tab.toast(type="ERROR", title="Error", description="Invalid trigger selection")
        except (ValueError, TypeError):
            tab.toast(type="ERROR", title="Error", description="Invalid trigger selection")

    async def save_settings():
        config = load_config()
        config["enabled"] = enable_toggle.checked
        config["notify_on_send"] = notify_toggle.checked
        config["reply_to_self"] = reply_self_toggle.checked
        
        try:
            config["default_delay"] = max(0, int(delay_input.value or "10"))
        except ValueError:
            config["default_delay"] = 10
            
        if save_config(config):
            update_display()
            tab.toast(type="SUCCESS", title="Settings Saved")
        else:
            tab.toast(type="ERROR", title="Save Failed")

    async def add_trigger():
        trigger_msg = trigger_input.value.strip()
        reply_msg = reply_input.value.strip()
        channel_id = channel_input.value.strip()
        delay = delay_trigger_input.value.strip()
        fuzzy = fuzzy_toggle.checked
        blacklist = blacklist_input.value.strip()

        if not trigger_msg or not reply_msg or not channel_id or not delay:
            tab.toast(type="ERROR", title="Missing Information", description="Fill trigger, reply, channel ID, and delay")
            return

        try:
            int(channel_id)
            delay_num = max(0, int(delay))
        except ValueError:
            tab.toast(type="ERROR", title="Invalid Input", description="Channel ID and delay must be numbers")
            return

        config = load_config()
        
        for existing_trigger in config["triggers"]:
            if (existing_trigger["trigger_message"].lower() == trigger_msg.lower() and 
                existing_trigger["channel_id"] == channel_id):
                tab.toast(type="ERROR", title="Duplicate Trigger", description="This trigger already exists for this channel")
                return
        
        new_trigger = {
            "trigger_message": trigger_msg,
            "reply_message": reply_msg, 
            "channel_id": channel_id,
            "delay": delay_num,
            "fuzzy_match": fuzzy
        }
        
        if blacklist:
            new_trigger["blacklist"] = blacklist
        
        config["triggers"].append(new_trigger)
        
        if save_config(config):
            trigger_input.value = ""
            reply_input.value = ""
            channel_input.value = ""
            delay_trigger_input.value = ""
            fuzzy_toggle.checked = False
            blacklist_input.value = ""
            
            refresh_triggers()
            match_type = "Fuzzy" if fuzzy else "Exact"
            blacklist_info = f" with blacklist: {blacklist}" if blacklist else ""
            tab.toast(type="SUCCESS", title="Trigger Added", description=f"Added: '{trigger_msg}' ({match_type}{blacklist_info})")
        else:
            tab.toast(type="ERROR", title="Save Failed", description="Failed to save trigger")

    save_btn.onClick = save_settings
    add_btn.onClick = add_trigger
    remove_btn.onClick = remove_selected_trigger

    @bot.listen('on_message')
    async def handle_auto_reply(message):
        config = load_config()
        if not config["enabled"] or not config.get("triggers"):
            return

        if not config.get("reply_to_self", True) and message.author == bot.user:
            return

        configured_channels = [trigger["channel_id"] for trigger in config["triggers"]]
        current_channel = str(message.channel.id)
        
        if current_channel not in configured_channels:
            return

        for trigger in config["triggers"]:
            trigger_msg = trigger["trigger_message"]
            incoming_msg = message.content.strip()
            channel_match = str(message.channel.id) == trigger["channel_id"]
            
            if trigger.get("blacklist"):
                blacklist_phrases = [phrase.strip().lower() for phrase in trigger["blacklist"].split(",")]
                message_lower = incoming_msg.lower()
                
                if any(phrase in message_lower for phrase in blacklist_phrases if phrase):
                    continue
            
            if trigger.get("fuzzy_match", False):
                match = fuzzy_match(incoming_msg, trigger_msg) and channel_match
            else:
                match = incoming_msg.lower() == trigger_msg.lower() and channel_match
            
            if match:
                delay = trigger.get("delay", config["default_delay"])
                
                if config.get("notify_on_send", True):
                    server_name = getattr(message.guild, 'name', 'DM') if message.guild else 'DM'
                    channel_name = getattr(message.channel, 'name', 'Unknown')
                    match_type = "Fuzzy" if trigger.get("fuzzy_match", False) else "Exact"
                    print(f"Auto Reply | {match_type} match in #{channel_name} ({server_name}) - responding in {delay}s", type_="INFO")
                
                if delay > 0:
                    await asyncio.sleep(delay)
                
                try:
                    await message.reply(trigger["reply_message"])
                    if config.get("notify_on_send", True):
                        print(f"Auto Reply | Sent: '{trigger['reply_message']}'", type_="INFO")
                except Exception as e:
                    print(f"Auto Reply | Error: {e}", type_="ERROR")
                break

    initialize_files()
    config = load_config()
    enable_toggle.checked = config["enabled"]
    notify_toggle.checked = config.get("notify_on_send", True)
    reply_self_toggle.checked = config.get("reply_to_self", True)
    delay_input.value = str(config.get("default_delay", 10))
    refresh_triggers()

    tab.render()

AutoReplyScript()