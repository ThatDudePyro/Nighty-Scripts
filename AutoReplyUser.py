def AutoReplyUser():
    from pathlib import Path
    import json
    import re
    import asyncio
    
    BASE_DIR = Path(getScriptsPath()) / "json"
    CONFIG_FILE = BASE_DIR / "UserAutoReplyConf.json"
    BASE_DIR.mkdir(parents=True, exist_ok=True)
    
    if not CONFIG_FILE.exists():
        with open(CONFIG_FILE, "w") as f:
            json.dump({"enabled": True, "delay": 0, "contexts": {}}, f, indent=4)
    
    def load_autoreplies():
        try:
            with open(CONFIG_FILE, "r") as f:
                data = json.load(f)
                if "enabled" not in data:
                    old_data = data.copy()
                    data = {"enabled": True, "delay": 0, "contexts": old_data}
                if "contexts" not in data:
                    data["contexts"] = data.get("servers", {})
                    if "servers" in data:
                        del data["servers"]
                return data
        except (FileNotFoundError, json.JSONDecodeError):
            print("Warning: UserAutoReply config file not found or invalid. Returning default.", type_="ERROR")
            return {"enabled": True, "delay": 0, "contexts": {}}
    
    def save_autoreplies(data):
        try:
            with open(CONFIG_FILE, "w") as f:
                json.dump(data, f, indent=4)
            print(f"Auto-reply config saved to {CONFIG_FILE.name}", type_="INFO")
        except IOError as e:
            print(f"Error saving autoreply data to {CONFIG_FILE}: {e}", type_="ERROR")
    
    def extract_user_id(user_input):
        match = re.search(r'(\d{17,20})', user_input)
        return match.group(1) if match else None
    
    def get_context_id(ctx):
        if ctx.guild:
            return f"server_{ctx.guild.id}"
        else:
            return f"dm_{ctx.channel.id}"
    
    @bot.command(
        name="autoreply",
        aliases=["ar"],
        usage="<@user/UserID> <reply text> | list | remove <@user/UserID> | clear | toggle | delay <seconds>",
        description="Set automatic replies for specific users"
    )
    async def autoreply_command(ctx, *, args: str = ""):
        await ctx.message.delete()
        
        if not args:
            data = load_autoreplies()
            status = "🟢 **Enabled**" if data.get("enabled", True) else "🔴 **Disabled**"
            delay = data.get("delay", 0)
            prefix = getConfigData().get("prefix", "<p>")
            
            help_text = f"""**UserAutoReply Status:** {status}
**Reply Delay:** {delay} seconds

**Commands:** (use `{prefix}autoreply` or `{prefix}ar`)
`{prefix}autoreply @user <text>` - Set auto-reply for a user
`{prefix}autoreply list` - Show all auto-replies
`{prefix}autoreply remove @user` - Remove auto-reply
`{prefix}autoreply clear` - Clear all auto-replies
`{prefix}autoreply toggle` - Enable/disable auto-replies
`{prefix}autoreply delay <seconds>` - Set reply delay (0-60)

**Examples:**
`{prefix}autoreply @John Hey buddy!`
`{prefix}ar @John Hey buddy!` (using alias)
`{prefix}autoreply delay 2`
`{prefix}ar toggle`"""
            await ctx.send(help_text, delete_after=30)
            return
        
        parts = args.strip().split(maxsplit=1)
        subcommand = parts[0].lower()
        
        if subcommand == "toggle":
            data = load_autoreplies()
            current_state = data.get("enabled", True)
            data["enabled"] = not current_state
            save_autoreplies(data)
            
            new_status = "🟢 **Enabled**" if data["enabled"] else "🔴 **Disabled**"
            await ctx.send(f"Auto-replies {new_status}", delete_after=10)
            print(f"Auto-replies toggled: {data['enabled']}", type_="SUCCESS")
            return
        
        if subcommand == "delay":
            if len(parts) < 2:
                data = load_autoreplies()
                current_delay = data.get("delay", 0)
                prefix = getConfigData().get("prefix", "<p>")
                await ctx.send(f"Current delay: **{current_delay} seconds**\nUsage: `{prefix}autoreply delay <seconds>`", delete_after=15)
                return
            
            try:
                delay_value = float(parts[1])
                if delay_value < 0 or delay_value > 60:
                    await ctx.send("Delay must be between 0 and 60 seconds.", delete_after=10)
                    return
                
                data = load_autoreplies()
                data["delay"] = delay_value
                save_autoreplies(data)
                await ctx.send(f"Reply delay set to **{delay_value} seconds**", delete_after=10)
                print(f"Auto-reply delay set to {delay_value}s", type_="SUCCESS")
            except ValueError:
                await ctx.send("Invalid delay value. Use a number between 0 and 60.", delete_after=10)
            return
        
        if subcommand == "list":
            data = load_autoreplies()
            contexts = data.get("contexts", {})
            context_id = get_context_id(ctx)
            
            if context_id not in contexts or not contexts[context_id]:
                await ctx.send("No auto-replies set for this context.", delete_after=15)
                return
            
            reply_list = ["**Auto-replies in this context:**\n"]
            for user_id, reply_text in contexts[context_id].items():
                display_text = reply_text if len(reply_text) <= 50 else reply_text[:47] + "..."
                reply_list.append(f"• <@{user_id}>: `{display_text}`")
            
            list_message = "\n".join(reply_list)
            await ctx.send(list_message, delete_after=45)
            return
        
        if subcommand == "clear":
            data = load_autoreplies()
            contexts = data.get("contexts", {})
            context_id = get_context_id(ctx)
            
            if context_id in contexts and contexts[context_id]:
                count = len(contexts[context_id])
                del contexts[context_id]
                data["contexts"] = contexts
                save_autoreplies(data)
                await ctx.send(f"Cleared **{count}** auto-reply(s) for this context.", delete_after=10)
                print(f"Cleared {count} auto-replies in context {context_id}", type_="SUCCESS")
            else:
                await ctx.send("No auto-replies to clear.", delete_after=10)
            return
        
        if subcommand == "remove":
            if len(parts) < 2:
                prefix = getConfigData().get("prefix", "<p>")
                await ctx.send(f"Usage: `{prefix}autoreply remove <@user/UserID>`", delete_after=15)
                return
            
            user_id = extract_user_id(parts[1])
            if not user_id:
                await ctx.send("Invalid user mention or ID.", delete_after=10)
                return
            
            data = load_autoreplies()
            contexts = data.get("contexts", {})
            context_id = get_context_id(ctx)
            
            if context_id in contexts and user_id in contexts[context_id]:
                old_reply = contexts[context_id][user_id]
                del contexts[context_id][user_id]
                if not contexts[context_id]:
                    del contexts[context_id]
                data["contexts"] = contexts
                save_autoreplies(data)
                
                display_reply = old_reply if len(old_reply) <= 50 else old_reply[:47] + "..."
                await ctx.send(f"Removed auto-reply for <@{user_id}>\nOld reply: `{display_reply}`", delete_after=15)
                print(f"Removed auto-reply for user {user_id}", type_="SUCCESS")
            else:
                await ctx.send("No auto-reply found for that user.", delete_after=10)
            return
        
        user_input = parts[0]
        
        if len(parts) < 2:
            prefix = getConfigData().get("prefix", "<p>")
            await ctx.send(f"Usage: `{prefix}autoreply <@user/UserID> <reply text>`", delete_after=15)
            return
        
        reply_text = parts[1]
        
        user_id = extract_user_id(user_input)
        
        if not user_id:
            await ctx.send("Invalid user mention or ID. Use @mention or paste the user ID.", delete_after=10)
            return
        
        context_id = get_context_id(ctx)
        
        data = load_autoreplies()
        contexts = data.get("contexts", {})
        
        if context_id not in contexts:
            contexts[context_id] = {}
        
        is_update = user_id in contexts[context_id]
        
        contexts[context_id][user_id] = reply_text
        data["contexts"] = contexts
        save_autoreplies(data)
        
        display_reply = reply_text if len(reply_text) <= 50 else reply_text[:47] + "..."
        
        action = "updated" if is_update else "set"
        await ctx.send(f"Auto-reply {action} for <@{user_id}>:\n`{display_reply}`", delete_after=15)
        print(f"Auto-reply {action}: User {user_id} in context {context_id}", type_="SUCCESS")
    
    @bot.listen("on_message")
    async def autoreply_listener(message):
        if message.author.id == bot.user.id:
            return
        
        if message.author.bot:
            return
        
        data = load_autoreplies()
        
        if not data.get("enabled", True):
            return
        
        contexts = data.get("contexts", {})
        
        if message.guild:
            context_id = f"server_{message.guild.id}"
        else:
            context_id = f"dm_{message.channel.id}"
        
        user_id = str(message.author.id)
        
        if context_id in contexts and user_id in contexts[context_id]:
            reply_text = contexts[context_id][user_id]
            delay = data.get("delay", 0)
            
            try:
                if delay > 0:
                    await asyncio.sleep(delay)
                
                await message.reply(reply_text, mention_author=False)
                print(f"Auto-replied to {message.author.name} in context {context_id}", type_="INFO")
            except Exception as e:
                print(f"Error sending auto-reply: {e}", type_="ERROR")

AutoReplyUser()