def channel_mover_logic():
    @bot.command(name="moveall")
    async def moveall(ctx, target_channel_id: int):
        source_channel = ctx.channel
        target_channel = ctx.guild.get_channel(target_channel_id)

        if target_channel is None:
            await ctx.send("❌ Invalid channel ID.")
            return

        await ctx.send(f"📦 Moving all messages from {source_channel.mention} to {target_channel.mention}...")

        messages = [message async for message in source_channel.history(limit=None, oldest_first=True)]

        for msg in messages:
            content = msg.content if msg.content else ""
            files = []
            for attachment in msg.attachments:
                file = await attachment.to_file()
                files.append(file)

            await target_channel.send(content, files=files)

        await ctx.send("✅ All messages have been moved.")
