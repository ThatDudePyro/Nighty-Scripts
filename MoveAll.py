async def moveall_logic():
    @bot.command(
        name="moveall",
        description="Move all messages from the current channel into another channel by ID."
    )
    async def moveall_cmd(ctx, target_channel_id: int):
        await ctx.message.delete()

        target = ctx.guild.get_channel(target_channel_id)
        if not target:
            await ctx.send("❌ Invalid channel ID.")
            return

        moved = 0
        async for msg in ctx.channel.history(limit=None, oldest_first=True):
            content = msg.content or ""
            files = [await a.to_file() for a in msg.attachments]
            await target.send(content, files=files)
            moved += 1

        await ctx.send(f"✅ Moved {moved} messages to {target.mention}")

moveall_logic()
