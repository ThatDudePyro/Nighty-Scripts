async def moveall_logic():
    @bot.command(
        name="moveall",
        description="Move all messages from the current channel into another channel by ID."
    )
    async def moveall_cmd(ctx, target_channel_id: int):
        # auto-clean: delete the trigger message
        try:
            await ctx.message.delete()
        except:
            pass

        # works across all servers since you're user-connected
        target = bot.get_channel(target_channel_id)
        if not target:
            await ctx.send("❌ Invalid channel ID (or you don’t have access).")
            return

        moved = 0
        async for msg in ctx.channel.history(limit=None, oldest_first=True):
            content = msg.content or ""
            files = [await a.to_file() for a in msg.attachments]

            try:
                await target.send(content, files=files)
                moved += 1
            except:
                continue  # ignore failed sends

        # Confirmation message in the *original* channel
        await ctx.send(f"✅ Moved {moved} messages to {target.mention}")

moveall_logic()
