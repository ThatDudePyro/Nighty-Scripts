from pathlib import Path
import json
import re
import asyncio

@nightyScript(
    name="AliasSystem",
    author="0pyr",
    description="Create and manage command aliases for your selfbot",
    usage=
        """
    ALIAS SYSTEM
    -----------

    Create custom shortcuts for frequently used commands. Simple and effective.

    COMMANDS:
    <p>alias add <alias_name> <original_command> - Create a new alias
    <p>alias remove <alias_name> - Delete an existing alias
    <p>alias list [page] - Display your aliases (paginated, 20 per page)
    <p>aliases [page] - Quick shortcut to list aliases with page number
    <p>alias clear - Remove all aliases
    <p>setprefix <char> - Change your command prefix

    EXAMPLES:
    .alias add w weather New York - Creates 'w' alias for weather command
    .alias add gm say Good morning everyone! - Creates 'gm' alias
    .alias remove w - Removes the 'w' alias
    .aliases - Shows page 1 of your aliases
    .aliases 2 - Shows page 2 of your aliases
    .setprefix ! - Changes prefix from . to !
    """
)
def alias_script():
    """
    ALIAS SYSTEM
    -----------

    Create custom shortcuts for frequently used commands. Simple and effective.

    COMMANDS:
    <p>alias add <alias_name> <original_command> - Create a new alias
    <p>alias remove <alias_name> - Delete an existing alias
    <p>alias list [page] - Display your aliases (paginated, 20 per page)
    <p>aliases [page] - Quick shortcut to list aliases with page number
    <p>alias clear - Remove all aliases
    <p>setprefix <char> - Change your command prefix

    EXAMPLES:
    .alias add w weather New York - Creates 'w' alias for weather command
    .alias add gm say Good morning everyone! - Creates 'gm' alias
    .alias remove w - Removes the 'w' alias
    .aliases - Shows page 1 of your aliases
    .aliases 2 - Shows page 2 of your aliases
    .setprefix ! - Changes prefix from . to !
    """

    # Configuration key
    PREFIX_KEY = "alias_system_prefix"

    # Initialize default prefix if not set
    if getConfigData().get(PREFIX_KEY) is None:
        updateConfigData(PREFIX_KEY, ".")

    # JSON Storage Setup
    BASE_DIR = Path(getScriptsPath()) / "json"
    ALIASES_FILE = BASE_DIR / "aliases.json"
    BASE_DIR.mkdir(parents=True, exist_ok=True)

    # Initialize aliases file
    if not ALIASES_FILE.exists():
        with open(ALIASES_FILE, "w") as f:
            json.dump({}, f, indent=4)

    def get_prefix():
        """Get the current configured prefix."""
        return getConfigData().get(PREFIX_KEY, ".")

    def load_aliases():
        """Load aliases from JSON file."""
        try:
            with open(ALIASES_FILE, "r") as f:
                return json.load(f)
        except:
            return {}

    def save_aliases(aliases_data):
        """Save aliases to JSON file."""
        try:
            with open(ALIASES_FILE, "w") as f:
                json.dump(aliases_data, f, indent=4)
            return True
        except:
            return False

    async def handle_list_aliases_paginated(ctx, page_num=1):
        """Handle listing all aliases with pagination."""
        aliases = load_aliases()

        if not aliases:
            await ctx.send("No aliases configured")
            return

        prefix = get_prefix()

        aliases_per_page = 20
        sorted_aliases = sorted(aliases.keys())
        total_aliases = len(sorted_aliases)
        total_pages = (total_aliases + aliases_per_page - 1) // aliases_per_page

        if page_num > total_pages:
            await ctx.send(f"Page {page_num} doesn't exist. There are only {total_pages} page(s).")
            return

        start_idx = (page_num - 1) * aliases_per_page
        end_idx = min(start_idx + aliases_per_page, total_aliases)
        page_aliases = sorted_aliases[start_idx:end_idx]

        # Build message text with aliases and their commands
        lines = [f"**Alias commands `(Page {page_num}/{total_pages})`**",
                 f"Prefix: `{prefix}`",
                 f"Total aliases: `{total_aliases}`",
                 ""]

        for alias_name in page_aliases:
            command = aliases[alias_name]
            lines.append(f"`{prefix}{alias_name} » {prefix}{command}`")

        if total_pages > 1:
            lines.append("")
            lines.append("--- Navigation ---")
            if page_num > 1:
                lines.append(f"Previous page: {prefix}aliases {page_num - 1}")
            if page_num < total_pages:
                lines.append(f"Next page: {prefix}aliases {page_num + 1}")
            lines.append(f"Jump to page: {prefix}aliases <page_number>")

        message = "\n".join(lines)
        await ctx.send(message)

    @bot.command(name="setprefix", description="Set the prefix for commands")
    async def set_prefix_command(ctx, *, prefix_char: str = ""):
        await ctx.message.delete()

        if not prefix_char:
            current_prefix = get_prefix()
            await ctx.send(f"Current prefix: `{current_prefix}`")
            return

        new_prefix = prefix_char.strip()[0]
        updateConfigData(PREFIX_KEY, new_prefix)
        await ctx.send(f"✅ Prefix changed to `{new_prefix}`")

    @bot.command(name="alias", aliases=["al"], description="Manage aliases")
    async def alias_command(ctx, *, args: str = ""):
        await ctx.message.delete()

        if not args:
            prefix = get_prefix()
            await ctx.send(f"**Alias Commands:**\n`{prefix}alias add <alias> <command>`\n`{prefix}alias remove <alias>`\n`{prefix}alias list [page]`\n`{prefix}alias clear`\n`{prefix}aliases [page]` - Quick list with optional page number")
            return

        parts = args.split(None, 1)
        subcommand = parts[0].lower()
        subargs = parts[1] if len(parts) > 1 else ""

        if subcommand == "add":
            if not subargs:
                await ctx.send("Usage: `alias add <alias> <command>`")
                return

            alias_parts = subargs.split(None, 1)
            if len(alias_parts) < 2:
                await ctx.send("Usage: `alias add <alias> <command>`")
                return

            alias_name = alias_parts[0].lower()
            command = alias_parts[1]

            aliases = load_aliases()
            aliases[alias_name] = command
            save_aliases(aliases)

            prefix = get_prefix()
            await ctx.send(f"✅ Created alias: `{prefix}{alias_name}` → `{prefix}{command}`")

        elif subcommand == "remove":
            if not subargs:
                await ctx.send("Usage: `alias remove <alias>`")
                return

            alias_name = subargs.lower()
            aliases = load_aliases()

            if alias_name in aliases:
                removed = aliases.pop(alias_name)
                save_aliases(aliases)
                await ctx.send(f"✅ Removed alias: `{alias_name}`")
            else:
                await ctx.send(f"❌ Alias `{alias_name}` not found")

        elif subcommand == "list":
            page_num = 1
            if subargs.strip():
                try:
                    page_num = int(subargs.strip())
                    if page_num < 1:
                        page_num = 1
                except ValueError:
                    await ctx.send("Invalid page number. Using page 1.")
                    page_num = 1

            await handle_list_aliases_paginated(ctx, page_num)

        elif subcommand == "clear":
            aliases = load_aliases()
            if not aliases:
                await ctx.send("No aliases to clear")
                return

            count = len(aliases)
            msg = await ctx.send(f"⚠️ Delete all {count} aliases? Remove ✅ to confirm")
            await msg.add_reaction("✅")
            await msg.add_reaction("❌")

            def check(reaction, user):
                return (user.id == ctx.author.id and
                       str(reaction.emoji) in ["✅", "❌"] and
                       reaction.message.id == msg.id)

            try:
                reaction, user = await bot.wait_for('reaction_remove', timeout=30.0, check=check)
                if str(reaction.emoji) == "✅":
                    save_aliases({})
                    await msg.edit(content=f"✅ Cleared all {count} aliases")
                else:
                    await msg.edit(content="❌ Cancelled")
            except:
                await msg.edit(content="⏰ Timed out")

    @bot.listen("on_message")
    async def handle_aliases(message):
        if message.author.id != bot.user.id:
            return

        prefix = get_prefix()

        if not message.content.startswith(prefix):
            return

        match = re.match(f'^\\{prefix}(\\w+)(.*)', message.content)
        if not match:
            return

        command_name = match.group(1).lower()
        args = match.group(2)

        aliases = load_aliases()
        if command_name not in aliases:
            return

        target_command = aliases[command_name]

        try:
            await message.delete()
            await asyncio.sleep(0.01)
            sent_msg = await message.channel.send(f"{prefix}{target_command}{args}")
            await asyncio.sleep(0.5)
            await sent_msg.delete()

            print(f"Executed alias: {prefix}{command_name} -> {prefix}{target_command}", type_="INFO")
        except Exception as e:
            print(f"Error executing alias: {e}", type_="ERROR")

    print("Alias system loaded successfully", type_="SUCCESS")

alias_script()
