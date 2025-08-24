import asyncio
from datetime import datetime, timedelta

async def get_user_info(user_id, ctx):
    """Get comprehensive user information."""
    try:
        user = await ctx.bot.fetch_user(int(user_id))
        return user
    except:
        return None

async def get_mutual_guilds(user_id, ctx):
    """Get mutual servers with the target user."""
    try:
        mutual_guilds = []
        target_user_id = int(user_id)
        
        for guild in ctx.bot.guilds:
            try:
                member = guild.get_member(target_user_id)
                if member:
                    mutual_guilds.append({
                        'name': guild.name,
                        'id': guild.id,
                        'member_count': guild.member_count,
                        'joined_at': member.joined_at
                    })
            except:
                continue
        
        return mutual_guilds
    except:
        return []

async def get_mutual_friends(user_id, ctx):
    """Get mutual friends (users in same servers)."""
    try:
        mutual_friends = set()
        target_user_id = int(user_id)
        
        for guild in ctx.bot.guilds:
            try:
                target_member = guild.get_member(target_user_id)
                if target_member:
                    # Get other members in the same guild
                    for member in guild.members:
                        if member.id != target_user_id and member.id != ctx.bot.user.id:
                            mutual_friends.add((member.id, member.display_name, member.name))
            except:
                continue
        
        return list(mutual_friends)[:10]  # Limit to first 10
    except:
        return []

async def search_user_messages(user_id, ctx, limit=10):
    """Search for recent messages from the user."""
    try:
        messages = []
        target_user_id = int(user_id)
        
        # Search in current channel first
        try:
            async for message in ctx.channel.history(limit=1000):
                if message.author.id == target_user_id:
                    messages.append({
                        'content': message.content[:100] + ('...' if len(message.content) > 100 else ''),
                        'channel': message.channel.name,
                        'guild': message.guild.name if message.guild else 'DM',
                        'created_at': message.created_at,
                        'has_attachments': len(message.attachments) > 0,
                        'attachments': [att.filename for att in message.attachments]
                    })
                    if len(messages) >= limit:
                        break
        except:
            pass
        
        return messages
    except:
        return []

async def check_voice_activity(user_id, ctx):
    """Check if user is currently in a voice channel."""
    try:
        target_user_id = int(user_id)
        
        for guild in ctx.bot.guilds:
            try:
                member = guild.get_member(target_user_id)
                if member and member.voice:
                    return {
                        'in_voice': True,
                        'channel_name': member.voice.channel.name,
                        'guild_name': guild.name,
                        'is_muted': member.voice.mute,
                        'is_deafened': member.voice.deaf
                    }
            except:
                continue
        
        return {'in_voice': False}
    except:
        return {'in_voice': False}

def format_user_info_embed(user, mutual_guilds, mutual_friends, messages, voice_info):
    """Format user information into a rich embed structure."""
    
    # Basic user info
    embed_data = {
        "title": f"👤 User Lookup: {user.display_name}",
        "description": f"**Username:** {user.name}\n**Display Name:** {user.display_name}\n**User ID:** `{user.id}`",
        "color": 0x5865F2,
        "thumbnail": str(user.avatar.url) if user.avatar else None,
        "fields": [],
        "footer": {"text": f"Account created: {user.created_at.strftime('%B %d, %Y')}"}
    }
    
    # Add bio if available (user.bio might not always exist)
    try:
        if hasattr(user, 'bio') and user.bio:
            embed_data["fields"].append({
                "name": "📝 Bio",
                "value": user.bio[:100] + ('...' if len(user.bio) > 100 else ''),
                "inline": False
            })
    except:
        pass
    
    # Voice activity
    if voice_info['in_voice']:
        voice_status = f"🔊 **{voice_info['channel_name']}** in {voice_info['guild_name']}"
        if voice_info['is_muted']:
            voice_status += " (Muted)"
        if voice_info['is_deafened']:
            voice_status += " (Deafened)"
    else:
        voice_status = "❌ Not in voice"
    
    embed_data["fields"].append({
        "name": "🎤 Voice Status",
        "value": voice_status,
        "inline": True
    })
    
    # Mutual servers
    if mutual_guilds:
        guild_list = []
        for guild in mutual_guilds[:5]:  # Show max 5
            joined = guild['joined_at'].strftime('%m/%d/%y') if guild['joined_at'] else 'Unknown'
            guild_list.append(f"• **{guild['name']}** ({guild['member_count']} members) - Joined: {joined}")
        
        guild_text = '\n'.join(guild_list)
        if len(mutual_guilds) > 5:
            guild_text += f"\n*... and {len(mutual_guilds) - 5} more*"
        
        embed_data["fields"].append({
            "name": f"🏰 Mutual Servers ({len(mutual_guilds)})",
            "value": guild_text,
            "inline": False
        })
    else:
        embed_data["fields"].append({
            "name": "🏰 Mutual Servers",
            "value": "No mutual servers found",
            "inline": True
        })
    
    # Mutual friends (limited display)
    if mutual_friends:
        friend_list = [f"• {friend[1]} (`{friend[0]}`)" for friend in mutual_friends[:5]]
        friend_text = '\n'.join(friend_list)
        if len(mutual_friends) > 5:
            friend_text += f"\n*... and {len(mutual_friends) - 5} more*"
        
        embed_data["fields"].append({
            "name": f"👥 Mutual Connections ({len(mutual_friends)})",
            "value": friend_text,
            "inline": False
        })
    
    # Recent messages
    if messages:
        message_list = []
        for msg in messages[:3]:  # Show max 3 recent messages
            time_ago = (datetime.utcnow() - msg['created_at'].replace(tzinfo=None)).days
            time_str = f"{time_ago}d ago" if time_ago > 0 else "Today"
            
            msg_preview = msg['content'] if msg['content'] else "*[No text content]*"
            attachment_info = f" 📎({len(msg['attachments'])})" if msg['has_attachments'] else ""
            
            message_list.append(f"• **{msg['channel']}** ({time_str}){attachment_info}\n  `{msg_preview}`")
        
        embed_data["fields"].append({
            "name": f"💬 Recent Messages ({len(messages)} found)",
            "value": '\n'.join(message_list),
            "inline": False
        })
    else:
        embed_data["fields"].append({
            "name": "💬 Recent Messages",
            "value": "No recent messages found in accessible channels",
            "inline": False
        })
    
    return embed_data

# Initialize default config values
if getConfigData().get("lookup_max_messages") is None:
    updateConfigData("lookup_max_messages", 10)
if getConfigData().get("lookup_max_history") is None:
    updateConfigData("lookup_max_history", 1000)

# Main lookup command
@bot.command(
    name="lookup",
    aliases=["userinfo", "whois", "ui"],
    usage="<user_id> [config]",
    description="Comprehensive user lookup with messages, voice status, and mutual information"
)
async def user_lookup_command(ctx, *, args: str = ""):
    await ctx.message.delete()
    
    args = args.strip()
    parts = args.split()
    
    if not args:
        help_msg = """# **User Lookup Help**

**Usage:** `lookup <user_id>` or `lookup <user_id> config`

**Examples:**
• `lookup 123456789012345678` - Full user lookup
• `lookup config` - Show current settings

**What it shows:**
• Basic user info (username, display name, ID, bio)
• Current voice channel status
• Mutual servers and join dates  
• Mutual friends/connections
• Recent messages and files
• Account creation date"""
        
        await ctx.send(help_msg)
        return
    
    if parts[0].lower() == "config":
        max_messages = getConfigData().get("lookup_max_messages", 10)
        max_history = getConfigData().get("lookup_max_history", 1000)
        
        config_msg = f"""# **Lookup Configuration**
**Max Messages to Show:** {max_messages}
**History Search Limit:** {max_history}

*Use `lookup setconfig <messages> <history>` to change*"""
        
        await ctx.send(config_msg)
        return
    
    if parts[0].lower() == "setconfig" and len(parts) >= 3:
        try:
            max_messages = int(parts[1])
            max_history = int(parts[2])
            
            if 1 <= max_messages <= 20 and 100 <= max_history <= 5000:
                updateConfigData("lookup_max_messages", max_messages)
                updateConfigData("lookup_max_history", max_history)
                await ctx.send(f"# Configuration updated: {max_messages} messages, {max_history} history limit")
                return
            else:
                await ctx.send("# Invalid ranges. Messages: 1-20, History: 100-5000")
                return
        except ValueError:
            await ctx.send("# Invalid numbers provided")
            return
    
    # Extract user ID
    user_id = parts[0]
    
    # Validate user ID format
    try:
        user_id_int = int(user_id)
        if len(user_id) < 17 or len(user_id) > 19:
            await ctx.send("# Invalid user ID format")
            return
    except ValueError:
        await ctx.send("# User ID must be a number")
        return
    
    # Show processing message
    status_msg = await ctx.send("# 🔍 Looking up user information...")
    
    try:
        # Gather all user information
        print(f"Starting user lookup for ID: {user_id}", type_="INFO")
        
        # Get basic user info
        user = await get_user_info(user_id, ctx)
        if not user:
            await status_msg.edit(content="# ❌ User not found or not accessible")
            return
        
        # Get additional information
        mutual_guilds = await get_mutual_guilds(user_id, ctx)
        mutual_friends = await get_mutual_friends(user_id, ctx)
        
        max_messages = getConfigData().get("lookup_max_messages", 10)
        messages = await search_user_messages(user_id, ctx, max_messages)
        
        voice_info = await check_voice_activity(user_id, ctx)
        
        print(f"Lookup complete for {user.name}: {len(mutual_guilds)} guilds, {len(messages)} messages", type_="SUCCESS")
        
        # Format and send the embed
        embed_data = format_user_info_embed(user, mutual_guilds, mutual_friends, messages, voice_info)
        
        # Temporarily disable private mode for embed
        current_private = getConfigData().get("private")
        updateConfigData("private", False)
        
        try:
            await forwardEmbedMethod(
                channel_id=ctx.channel.id,
                content=f"📊 **User Lookup Complete** - Found extensive information",
                **embed_data
            )
            await status_msg.delete()
        except Exception as e:
            print(f"Failed to send embed: {e}", type_="ERROR")
            # Fallback to text format
            text_info = f"""# 👤 **User Lookup: {user.display_name}**

**Username:** {user.name}
**Display Name:** {user.display_name}  
**User ID:** `{user.id}`
**Account Created:** {user.created_at.strftime('%B %d, %Y')}

**Voice Status:** {"🔊 " + voice_info.get('channel_name', 'Not in voice') if voice_info['in_voice'] else "❌ Not in voice"}
**Mutual Servers:** {len(mutual_guilds)}
**Recent Messages:** {len(messages)} found

*Enable embeds for full detailed view*"""
            
            await status_msg.edit(content=text_info)
        finally:
            # Restore private setting
            updateConfigData("private", current_private)
        
    except Exception as e:
        print(f"Error in user lookup: {e}", type_="ERROR")
        await status_msg.edit(content="# ❌ Error during user lookup")

print("User Lookup UI script loaded successfully from GitHub", type_="SUCCESS")