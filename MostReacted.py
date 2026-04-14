def most_reacted_script():
    import asyncio
    from datetime import datetime, timedelta

    @bot.command(
        name="mostreacted",
        description="Finds the most reacted message in a channel."
    )
    async def mostreacted(ctx, *, args: str):
        await ctx.message.delete()

        try:
            channel_id = int(args)
        except ValueError:
            await ctx.send("Invalid channel ID.")
            return

        channel = bot.get_channel(channel_id)
        if not channel:
            await ctx.send("Channel not found.")
            return

        most_reacted_message = None
        max_reactions = -1

        status_message = await ctx.send(f"Searching for the most reacted message in {channel.name}...")

        try:
            async for message in channel.history(limit=None):
                if message.reactions:
                    reaction_count = sum(reaction.count for reaction in message.reactions)
                    if reaction_count > max_reactions:
                        max_reactions = reaction_count
                        most_reacted_message = message
        except Exception as e:
            await status_message.edit(content=f"An error occurred: {e}")
            print(f"Error in mostreacted: {e}", type_="ERROR")
            return


        if most_reacted_message:
            new_content = (
                f"**Most Reacted Message in #{channel.name}**\n\n"
                f"> {most_reacted_message.content}\n\n"
                f"- **{max_reactions}** reactions\n"
                f"- Sent by **{most_reacted_message.author.name}**\n\n"
                f"{most_reacted_message.jump_url}"
            )
            await status_message.edit(content=new_content)
        else:
            await status_message.edit(content=f"No messages with reactions found in {channel.name}.")

most_reacted_script()