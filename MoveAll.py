def channel_mover_logic():
    import discord
    from discord.ext import commands

    @bot.command(name="moveall")
    async def moveall(ctx, target_channel_id: int):
        source_channel = ctx.channel
        target_channel = ctx.guild.get_channel(target_channel_id)

        if target_channel is None:
            await ctx.send("❌ Invalid channel ID.")
            return

        await ctx.send(f"📦 Moving all messages from {source_channel.mention} to {target_channel.mention}...")

        async for msg in source_channel.history(limit=None, oldest_first=True):
            content = msg.content if msg.content else None
            files = [await a.to_file() for a in msg.attachments]
            if content or files:
                await target_channel.send(content or "", files=files)

        await ctx.send("✅ All messages have been moved.")
