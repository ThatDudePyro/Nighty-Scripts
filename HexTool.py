import random
import json
import re
from pathlib import Path

def HexTool():
    BASE_DIR = Path(getScriptsPath()) / "json"
    HEX_FILE = BASE_DIR / "hex_settings.json"

    def initialize_files():
        BASE_DIR.mkdir(parents=True, exist_ok=True)
        if not HEX_FILE.exists():
            with open(HEX_FILE, "w") as f:
                json.dump({
                    "enabled": True,
                    "show_rgb": True,
                    "use_embed": True,
                    "delete_command": True,
                    "show_color_preview": True
                }, f, indent=4)

    def load_hex_settings():
        try:
            with open(HEX_FILE, "r") as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {
                "enabled": True,
                "show_rgb": True,
                "use_embed": True,
                "delete_command": True,
                "show_color_preview": True
            }

    def save_hex_settings(settings):
        with open(HEX_FILE, "w") as f:
            json.dump(settings, f, indent=4)

    def validate_hex_code(hex_input):
        hex_input = hex_input.strip()
        if not hex_input.startswith('#'):
            hex_input = '#' + hex_input
        if re.match(r'^#[0-9A-Fa-f]{6}$', hex_input):
            return hex_input.upper()
        elif re.match(r'^#[0-9A-Fa-f]{3}$', hex_input):
            expanded = '#' + ''.join([c*2 for c in hex_input[1:]])
            return expanded.upper()
        else:
            return None

    tab = Tab(
        name="Hex Tool",
        title="Hex Tool Settings",
        icon="palette",
        gap=4
    )

    main_container = tab.create_container(type="rows", gap=4)
    settings_card = main_container.create_card(gap=4)

    toggle_group = settings_card.create_group(type="columns", gap=2, full_width=True)
    enabled_toggle = toggle_group.create_ui_element(UI.Toggle, label="Enable Hex Tool")

    options_group = settings_card.create_group(type="rows", gap=4, full_width=True)
    rgb_toggle = options_group.create_ui_element(UI.Toggle, label="Show RGB Values")
    embed_toggle = options_group.create_ui_element(UI.Toggle, label="Use Embed Format")
    delete_toggle = options_group.create_ui_element(UI.Toggle, label="Delete Command Message")
    color_preview_toggle = options_group.create_ui_element(UI.Toggle, label="Show Color Preview")

    status_group = settings_card.create_group(type="rows", gap=2, full_width=True)
    status_group.create_ui_element(UI.Text, content="Status:", size="lg", weight="bold")

    status_text = status_group.create_ui_element(
        UI.Text,
        content="Hex Tool is enabled",
        size="base",
        color="#4ade80"
    )

    save_button_group = settings_card.create_group(type="rows", gap=2, full_width=True)
    save_button = save_button_group.create_ui_element(
        UI.Button,
        label="Save Settings",
        variant="cta",
        full_width=True
    )

    def update_status_display(enabled):
        status_text.content = f"Hex Tool is {'enabled' if enabled else 'disabled'}"
        status_text.color = "#4ade80" if enabled else "#f87171"

    initialize_files()
    hex_settings = load_hex_settings()

    enabled_toggle.checked = hex_settings["enabled"]
    rgb_toggle.checked = hex_settings["show_rgb"]
    embed_toggle.checked = hex_settings["use_embed"]
    delete_toggle.checked = hex_settings["delete_command"]
    color_preview_toggle.checked = hex_settings.get("show_color_preview", True)

    update_status_display(hex_settings["enabled"])

    async def on_save_click():
        hex_settings["enabled"] = enabled_toggle.checked
        hex_settings["show_rgb"] = rgb_toggle.checked
        hex_settings["use_embed"] = embed_toggle.checked
        hex_settings["delete_command"] = delete_toggle.checked
        hex_settings["show_color_preview"] = color_preview_toggle.checked

        save_hex_settings(hex_settings)
        update_status_display(hex_settings["enabled"])

        tab.toast(
            type="SUCCESS",
            title="Settings Saved",
            description=f"Hex Tool {'enabled' if hex_settings['enabled'] else 'disabled'}"
        )

    save_button.onClick = on_save_click

    def disable_private():
        current_private = getConfigData().get("private", False)
        updateConfigData("private", False)
        return current_private

    def restore_private(previous_state):
        updateConfigData("private", previous_state)

    async def send_embed(ctx, content, title=None, image=None):
        previous_private = disable_private()
        try:
            await forwardEmbedMethod(
                channel_id=ctx.channel.id,
                content=content,
                title=title,
                image=image
            )
        finally:
            restore_private(previous_state)

    async def process_hex_command(message, hex_code, is_custom=False):
        hex_settings = load_hex_settings()
        
        try:
            if hex_settings["use_embed"]:
                hex_without_hash = hex_code[1:]
                description = f"```css\n{hex_code}\n```"

                if hex_settings["show_rgb"]:
                    r = int(hex_code[1:3], 16)
                    g = int(hex_code[3:5], 16)
                    b = int(hex_code[5:7], 16)
                    description += f"\n**RGB Values:** R: {r} | G: {g} | B: {b}"

                direct_image_url = f"https://dummyimage.com/300x300/{hex_without_hash}/{hex_without_hash}.png" if hex_settings.get("show_color_preview", True) else None

                title = "🎨 Custom Hex Color" if is_custom else "🎨 Random Hex Code"
                
                await send_embed(
                    ctx=message,
                    content=description,
                    title=title,
                    image=direct_image_url
                )
            else:
                color_type = "Custom" if is_custom else "Random"
                response = f"🎨 **{color_type} Hex Code:** `{hex_code}`"
                if hex_settings["show_rgb"]:
                    r = int(hex_code[1:3], 16)
                    g = int(hex_code[3:5], 16)
                    b = int(hex_code[5:7], 16)
                    response += f"\n**RGB:** R: {r} | G: {g} | B: {b}"
                await message.channel.send(response)
        except Exception as e:
            print(f"Hex Tool | Error sending hex code: {e}", type_="ERROR")

    @bot.listen('on_message')
    async def handle_hex_command(message):
        if message.author != bot.user:
            return

        user_prefix = getConfigData().get('prefix')
        hex_command = f"{user_prefix}hex"

        if not message.content.startswith(hex_command):
            return

        hex_settings = load_hex_settings()
        if not hex_settings["enabled"]:
            return

        if hex_settings["delete_command"]:
            try:
                await message.delete()
            except Exception as e:
                print(f"Error deleting command message: {e}", type_="ERROR")

        command_parts = message.content.strip().split()
        
        if len(command_parts) > 1:
            provided_hex = ' '.join(command_parts[1:])
            validated_hex = validate_hex_code(provided_hex)
            
            if validated_hex:
                await process_hex_command(message, validated_hex, is_custom=True)
            else:
                try:
                    error_msg = f"❌ Invalid hex code: `{provided_hex}`\nPlease use a valid 6-digit hex code (e.g., #FF5733 or FF5733) or 3-digit hex code (e.g., #F73 or F73)"
                    await message.channel.send(error_msg)
                except Exception as e:
                    print(f"Hex Tool | Error sending error message: {e}", type_="ERROR")
        else:
            hex_code = "#{:06x}".format(random.randint(0, 0xFFFFFF))
            await process_hex_command(message, hex_code, is_custom=False)

    initialize_files()
    hex_settings = load_hex_settings()
    print(f"Hex Tool initialized - Status: {'Enabled' if hex_settings['enabled'] else 'Disabled'}", type_="INFO")

    tab.render()

HexTool()