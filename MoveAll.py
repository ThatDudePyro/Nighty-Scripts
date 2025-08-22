import re

async def moveall_logic():
    @bot.command(
        name="moveall",
        description="Move all messages from the current channel into another channel (ID, mention, or link)."
    )
    async def moveall_cmd(ctx, target_ref: str):  # STRING to handle mentions/links/IDs
        # auto-delete the trigger message
        try:
            await ctx.message.delete()
        except:
            pass

        # extract numeric channel ID from mention, link, or plain ID
        match = re.search(r"(\d{17,20})", target_ref)
        if not match:
            await ctx.send("❌ Could not parse the channel reference.")
            return
        channel_id = int(match.group(1))

        # get the target channel globally
        target = bot.get_channel(channel_id)
        if not target:
            await ctx.send("❌ Invalid channel ID or you don't have access.")
            return

        moved = 0
        # move all messages from current channel
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
                continue  # skip messages that fail

        # confirmation message in the source channel
        await ctx.send(f"✅ Moved {moved} messages to {target.mention}")

# call the logic function to register the command
moveall_logic()
