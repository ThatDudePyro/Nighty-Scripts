import re
import aiohttp
import discord

async def moveall_logic():
    @bot.command(
        name="moveall",
        description="Move all messages from the current channel into another channel using a webhook (plain text)."
    )
    async def moveall_cmd(ctx, target_ref: str):  # STRING to allow mention/link/ID
        # auto-delete the trigger message
        try:
            await ctx.message.delete()
        except:
            pass

        # extract numeric ID from mention, link, or plain ID
        match = re.search(r"(\d{17,20})", target_ref)
        if not match:
            await ctx.send("❌ Could not parse the channel reference.")
            return
        channel_id = int(match.group(1))

        target = bot.get_channel(channel_id)
        if not target:
            await ctx.send("❌ Invalid channel ID or you don’t have access.")
            return

        # create a webhook in the target channel
        try:
            webhook = await target.create_webhook(name="MoveAll Temp Webhook")
        except:
            await ctx.send("❌ Failed to create a webhook in the target channel.")
            return

        moved = 0
        async for msg in ctx.channel.history(limit=None, oldest_first=True):
            content = msg.content or ""
            if not content.strip():
                continue
            try:
                await webhook.send(content, username=ctx.author.display_name, avatar_url=ctx.author.avatar.url)
                moved += 1
            except:
                continue  # skip messages that fail

        # clean up webhook
        try:
            await webhook.delete()
        except:
            pass

        # confirmation message in source channel
        await ctx.send(f"✅ Moved {moved} messages to {target.mention}")

# register the command
moveall_logic()
