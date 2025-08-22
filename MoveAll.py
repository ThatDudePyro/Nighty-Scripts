import discord
from discord.ext import commands

def moveall_logic(bot):
    async def move_messages(ctx, target_channel_id: int):
        target_channel = ctx.guild.get_channel(target_channel_id)
        if target_channel is None:
            await ctx.send("❌ Invalid channel ID")
            return

        async for message in ctx.channel.history(limit=None, oldest_first=True):
            if not message.content.strip():
                continue
            await target_channel.send(message.content)

        await ctx.send("✅ All messages moved.")

    @bot.command(name="moveall")
    async def moveall_cmd(ctx, channel_id: int):
        await move_messages(ctx, channel_id)

# 🔑 this line is what actually registers the command when exec’d
moveall_logic(bot)
