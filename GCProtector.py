def GC_Protector():
    from pathlib import Path
    import json

    BASE_DIR = Path(getScriptsPath()) / "json"
    DATA_FILE = BASE_DIR / "gcprotect_data.json"

    BASE_DIR.mkdir(parents=True, exist_ok=True)

    if not DATA_FILE.exists():
        with open(DATA_FILE, "w") as f:
            json.dump([], f, indent=4)

    def load_data():
        try:
            with open(DATA_FILE, "r") as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return []

    def save_data(data):
        try:
            with open(DATA_FILE, "w") as f:
                json.dump(data, f, indent=4)
        except IOError as e:
            print(f"Error saving gcprotect data: {e}", type_="ERROR")

    def get_protected_name(channel_id):
        for entry in load_data():
            if entry["group_id"] == channel_id:
                return entry["group_name"]
        return None

    def set_protected(channel_id, name):
        data = load_data()
        for entry in data:
            if entry["group_id"] == channel_id:
                entry["group_name"] = name
                save_data(data)
                return
        data.append({"group_id": channel_id, "group_name": name})
        save_data(data)

    def remove_protected(channel_id):
        data = load_data()
        new_data = [e for e in data if e["group_id"] != channel_id]
        if len(new_data) == len(data):
            return False
        save_data(new_data)
        return True

    @bot.command(
        name="gcprotect",
        description="Set and protect a Group DM's name. Run with no args for help."
    )
    async def gcprotect(ctx, *, args: str = ""):
        await ctx.message.delete()

        args = args.strip()

        if not args:
            await ctx.send(
                "**GC Name Protector**\n\n"
                "**Usage:**\n"
                "- `<p>gcprotect <name>` — Protect the current GC's name (run inside the GC)\n"
                "- `<p>gcprotect <Group ID> <name>` — Protect a GC's name by ID\n"
                "- `<p>gcprotect off` — Disable protection for the current GC\n"
                "- `<p>gcprotect off <Group ID>` — Disable protection for a GC by ID\n\n"
                "**Examples:**\n"
                "`<p>gcprotect the boys`\n"
                "`<p>gcprotect 123456789012345678 the boys`"
            )
            return

        parts = args.split(maxsplit=1)

        if parts[0].lower() == "off":
            if len(parts) > 1 and parts[1].strip().isdigit():
                channel_id = parts[1].strip()
            elif hasattr(ctx.channel, "recipients"):
                channel_id = str(ctx.channel.id)
            else:
                await ctx.send("Run this inside a GC or provide a Group ID.")
                return

            if remove_protected(channel_id):
                await ctx.send(f"Protection disabled for GC `{channel_id}`.")
            else:
                await ctx.send(f"No protection was set for GC `{channel_id}`.")
            return

        if parts[0].isdigit():
            channel_id = parts[0]
            if len(parts) < 2 or not parts[1].strip():
                await ctx.send("Please provide a name after the Group ID.")
                return
            protected_name = parts[1].strip()
        else:
            if not hasattr(ctx.channel, "recipients"):
                await ctx.send("You're not in a Group DM. Use `<p>gcprotect <Group ID> <name>`.")
                return
            channel_id = str(ctx.channel.id)
            protected_name = args

        set_protected(channel_id, protected_name)
        await ctx.send(f"Protection set! GC `{channel_id}` will be renamed back to **{protected_name}** if changed.")

    @bot.listen("on_private_channel_update")
    async def on_gc_name_change(before, after):
        if not hasattr(after, "recipients"):
            return

        if before.name == after.name:
            return

        protected_name = get_protected_name(str(after.id))

        if protected_name is None:
            return

        if after.name != protected_name:
            try:
                await after.edit(name=protected_name)
                print(f"GC name restored to '{protected_name}' (was changed to '{after.name}')", type_="INFO")
            except Exception as e:
                print(f"Failed to restore GC name: {e}", type_="ERROR")

GC_Protector()