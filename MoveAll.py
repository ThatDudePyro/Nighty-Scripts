import re

async def moveall_logic():
    @bot.command(
        name="moveall",
        description="Move all messages from the current channel into another channel (ID, mention, or link)."
    )
    async def moveall_cmd(ctx, target_ref: str):
        # auto-clean the trigger
        try:
            await ctx.message.delete()
        except:
            pass

        # parse input (ID, mention, or link)
        match = re.search(r"(\d{17,20})$", target_ref)
        if not match:
            await ctx.send("❌ Could not parse the channel reference.")
            return
        channel_id = int(match.group(1))

        target = bot.get_channel(channel_id)
        if not target:
            await ctx.send("❌ Invalid channel ID or I don’t have access.")
            return

        moved = 0
        async for msg in ctx.channel.history(limit=None, oldest_first=True):
            content = msg.content or ""
            files = []
            for a in msg.attachments:
                try:
                    files.append(await a.to_file())
                except:
                    continue

            try:
                await target.send(content, files=files)
                moved += 1
            except:
                continue

        await ctx.send(f"✅ Moved {moved} messages to {target.mention}")

moveall_logic()
