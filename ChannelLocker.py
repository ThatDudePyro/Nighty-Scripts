import asyncio
import os
import json

def channel_locker_logic():
    # File path
    perm_file_path = os.path.expandvars(
        "%APPDATA%\\Nighty Selfbot\\data\\scripts\\json\\lockperms.json"
    )
    os.makedirs(os.path.dirname(perm_file_path), exist_ok=True)

    def load_permissions():
        if os.path.isfile(perm_file_path):
            with open(perm_file_path, "r") as f:
                return json.load(f)
        return {}

    def save_permissions(data):
        with open(perm_file_path, "w") as f:
            json.dump(data, f, indent=2)

    async def lock_channel(ctx):
        perms = load_permissions()
        channel_id = str(ctx.channel.id)
        perms[channel_id] = perms.get(channel_id, {})
        perms[channel_id]["send_messages"] = {}

        for role in ctx.guild.roles:
            overwrites = ctx.channel.overwrites_for(role)
            if overwrites.is_empty():
                continue
            perms[channel_id]["send_messages"][str(role.id)] = overwrites.send_messages
            overwrites.send_messages = False
            await ctx.channel.set_permissions(role, overwrite=overwrites)

        save_permissions(perms)
        await ctx.send("# 🔒 Channel is locked")
        await ctx.message.add_reaction("✅")

    async def unlock_channel(ctx):
        perms = load_permissions()
        channel_id = str(ctx.channel.id)

        if channel_id not in perms or "send_messages" not in perms[channel_id]:
            await ctx.message.add_reaction("❌")
            return

        for role_id, original_value in perms[channel_id]["send_messages"].items():
            role = ctx.guild.get_role(int(role_id))
            if role is None:
                continue
            overwrites = ctx.channel.overwrites_for(role)
            overwrites.send_messages = original_value
            await ctx.channel.set_permissions(role, overwrite=overwrites)

        await ctx.send("# 🔓 Channel is unlocked")
        await ctx.message.add_reaction("✅")

    async def lockdown_channel(ctx):
        perms = load_permissions()
        channel_id = str(ctx.channel.id)
        perms[channel_id] = perms.get(channel_id, {})
        perms[channel_id]["read_messages"] = {}
        perms[channel_id]["send_messages"] = {}

        for role in ctx.guild.roles:
            overwrites = ctx.channel.overwrites_for(role)
            if overwrites.is_empty():
                continue
            perms[channel_id]["read_messages"][str(role.id)] = overwrites.read_messages
            perms[channel_id]["send_messages"][str(role.id)] = overwrites.send_messages
            overwrites.read_messages = False
            overwrites.send_messages = False
            await ctx.channel.set_permissions(role, overwrite=overwrites)

        save_permissions(perms)
        await ctx.message.add_reaction("✅")

    async def unlockdown_channel(ctx):
        perms = load_permissions()
        channel_id = str(ctx.channel.id)

        if channel_id not in perms or "read_messages" not in perms[channel_id] or "send_messages" not in perms[channel_id]:
            await ctx.message.add_reaction("❌")
            return

        for role_id in set(list(perms[channel_id]["read_messages"].keys()) + list(perms[channel_id]["send_messages"].keys())):
            role = ctx.guild.get_role(int(role_id))
            if role is None:
                continue
            overwrites = ctx.channel.overwrites_for(role)
            if role_id in perms[channel_id]["read_messages"]:
                overwrites.read_messages = perms[channel_id]["read_messages"][role_id]
            if role_id in perms[channel_id]["send_messages"]:
                overwrites.send_messages = perms[channel_id]["send_messages"][role_id]
            await ctx.channel.set_permissions(role, overwrite=overwrites)

        await ctx.message.add_reaction("✅")

    @bot.command(name="lock")
    async def lock(ctx):
        await lock_channel(ctx)

    @bot.command(name="unlock")
    async def unlock(ctx):
        await unlock_channel(ctx)

    @bot.command(name="lockdown")
    async def lockdown(ctx):
        await lockdown_channel(ctx)

    @bot.command(name="unlockdown")
    async def unlockdown(ctx):
        await unlockdown_channel(ctx)
