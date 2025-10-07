import asyncio
import json
import re
from pathlib import Path

def VerifyScript():

    import os
    CONFIG_PATH = Path(os.environ['APPDATA']) / "Nighty Selfbot" / "data" / "scripts" / "json" / "VerifyConfig.json"

    def load_config():
        if not CONFIG_PATH.exists():
            CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
            CONFIG_PATH.write_text(json.dumps({}))
        return json.loads(CONFIG_PATH.read_text())

    def save_config(cfg):
        CONFIG_PATH.write_text(json.dumps(cfg, indent=4))

    config = load_config()

    def ensure_guild_entry(guild):
        gid = str(guild.id)
        if gid not in config:
            config[gid] = {
                "server_name": guild.name,
                "verify_role": None,
                "unverified_role": None,
                "verify_message": "Welcome!"
            }
            save_config(config)

    def extract_id(text):
        """Extract ID from mention or return the text if it's already an ID"""
        if not text:
            return None
        
        mention_match = re.search(r'<@!?(\d+)>', text)
        if mention_match:
            return mention_match.group(1)
        
        role_mention_match = re.search(r'<@&(\d+)>', text)
        if role_mention_match:
            return role_mention_match.group(1)
        
        if text.strip().isdigit():
            return text.strip()
        
        return None

    def format_role(guild, role_id):
        """Format role for display"""
        if not role_id:
            return "Not set"
        role = guild.get_role(int(role_id)) if role_id else None
        if role:
            return f"{role_id} | {role.name}"
        return f"{role_id} | (Role not found)"

    def get_delete_delay():
        """Get delete delay from config or default to 3 seconds"""
        return getConfigData().get("delete_delay", 3)

    @bot.command(
        name="verify",
        description="Verify a user or manage verification settings"
    )
    async def verify_command(ctx, *, args: str = ""):
        await ctx.message.delete()
        ensure_guild_entry(ctx.guild)
        guild_config = config[str(ctx.guild.id)]
        
        parts = args.strip().split()
        if not parts:
            help_msg = f"""**Verify System Commands:**
• `{getConfigData().get('prefix', '!')}verify <@user/ID>` - Verify a user
• `{getConfigData().get('prefix', '!')}verify verifiedrole <@role/ID>` - Set verified role
• `{getConfigData().get('prefix', '!')}verify unverifiedrole <@role/ID>` - Set unverified role  
• `{getConfigData().get('prefix', '!')}verify message <text>` - Set welcome message
• `{getConfigData().get('prefix', '!')}verify list` - Show current settings
• `{getConfigData().get('prefix', '!')}verify list all` - Show all server settings"""
            await ctx.send(help_msg)
            return
        
        subcommand = parts[0].lower()
        
        if subcommand == "verifiedrole":
            if len(parts) < 2:
                msg = await ctx.send("❌ Please specify a role: `@role` or `RoleID`")
                await asyncio.sleep(get_delete_delay())
                await msg.delete()
                return
            
            role_id = extract_id(parts[1])
            if not role_id:
                msg = await ctx.send("❌ Invalid role format. Use `@role` or `RoleID`")
                await asyncio.sleep(get_delete_delay())
                await msg.delete()
                return
            
            role = ctx.guild.get_role(int(role_id))
            if not role:
                msg = await ctx.send("❌ Role not found in this server.")
                await asyncio.sleep(get_delete_delay())
                await msg.delete()
                return
            
            config[str(ctx.guild.id)]["verify_role"] = int(role_id)
            config[str(ctx.guild.id)]["server_name"] = ctx.guild.name
            save_config(config)
            
            msg = await ctx.send(f"✅ Verified role set to `{role.name}`.")
            await asyncio.sleep(get_delete_delay())
            await msg.delete()
            
        elif subcommand == "unverifiedrole":
            if len(parts) < 2:
                msg = await ctx.send("❌ Please specify a role: `@role` or `RoleID`")
                await asyncio.sleep(get_delete_delay())
                await msg.delete()
                return
            
            role_id = extract_id(parts[1])
            if not role_id:
                msg = await ctx.send("❌ Invalid role format. Use `@role` or `RoleID`")
                await asyncio.sleep(get_delete_delay())
                await msg.delete()
                return
            
            role = ctx.guild.get_role(int(role_id))
            if not role:
                msg = await ctx.send("❌ Role not found in this server.")
                await asyncio.sleep(get_delete_delay())
                await msg.delete()
                return
            
            config[str(ctx.guild.id)]["unverified_role"] = int(role_id)
            config[str(ctx.guild.id)]["server_name"] = ctx.guild.name
            save_config(config)
            
            msg = await ctx.send(f"✅ Unverified role set to `{role.name}`.")
            await asyncio.sleep(get_delete_delay())
            await msg.delete()
            
        elif subcommand == "message":
            if len(parts) < 2:
                msg = await ctx.send("❌ Please specify a message.")
                await asyncio.sleep(get_delete_delay())
                await msg.delete()
                return
            
            message = " ".join(parts[1:])
            config[str(ctx.guild.id)]["verify_message"] = message
            config[str(ctx.guild.id)]["server_name"] = ctx.guild.name
            save_config(config)
            
            msg = await ctx.send("✅ Verify message updated.")
            await asyncio.sleep(get_delete_delay())
            await msg.delete()
            
        elif subcommand == "list":
            show_all = len(parts) > 1 and parts[1].lower() == "all"
            
            if show_all:
                if not config:
                    await ctx.send("❌ No verification settings found.")
                    return
                
                response = "> **📋 All Server Verification Settings**\n> \n"
                for gid, cfg in config.items():
                    name = cfg.get("server_name", "Unknown")
                    vr = format_role(ctx.guild, cfg.get("verify_role"))
                    ur = format_role(ctx.guild, cfg.get("unverified_role"))
                    msg_text = cfg.get("verify_message", "Not set")
                    
                    response += (
                        f"> **🏠 {name}** (`{gid}`)\n"
                        f"> ✅ **Verified Role:** {vr}\n"
                        f"> ❌ **Unverified Role:** {ur}\n"
                        f"> 💬 **Welcome Message:** {msg_text}\n"
                        f"\n"
                    )
                await ctx.send(response)
            else:
                cfg = guild_config
                vr = format_role(ctx.guild, cfg.get("verify_role"))
                ur = format_role(ctx.guild, cfg.get("unverified_role"))
                msg_text = cfg.get("verify_message", "Not set")
                
                response = (
                    f"> **⚙️ Verification Settings for {ctx.guild.name}**\n"
                    f"> \n"
                    f"> ✅ **Verified Role:** {vr}\n"
                    f"> ❌ **Unverified Role:** {ur}\n"
                    f"> 💬 **Welcome Message:** {msg_text}"
                )
                await ctx.send(response)
                
        else:
            member = None
            target_id = None
            
            if ctx.message.reference:
                try:
                    ref = ctx.message.reference
                    replied = await ctx.channel.fetch_message(ref.message_id)
                    member = replied.author
                    target_id = str(member.id)
                except Exception as e:
                    print(f"Error fetching replied message: {e}", type_="ERROR")
                    msg = await ctx.send("❌ Could not fetch the replied user.")
                    await asyncio.sleep(get_delete_delay())
                    await msg.delete()
                    return
            else:
                target_id = extract_id(subcommand)
                if target_id:
                    try:
                        member = await bot.fetch_user(int(target_id))
                    except Exception as e:
                        print(f"Error fetching user {target_id}: {e}", type_="ERROR")
                        msg = await ctx.send("❌ Could not find that user.")
                        await asyncio.sleep(get_delete_delay())
                        await msg.delete()
                        return
            
            if not member:
                msg = await ctx.send("❌ Please specify a user: `@user`, `UserID`, or reply to their message.")
                await asyncio.sleep(get_delete_delay())
                await msg.delete()
                return
            
            verify_role_id = guild_config.get("verify_role")
            if not verify_role_id:
                msg = await ctx.send("❌ Verified role is not set. Use `verify verifiedrole @role` first.")
                await asyncio.sleep(get_delete_delay())
                await msg.delete()
                return
            
            verify_role = ctx.guild.get_role(int(verify_role_id))
            if not verify_role:
                msg = await ctx.send("❌ Could not find the verified role in this server.")
                await asyncio.sleep(get_delete_delay())
                await msg.delete()
                return
            
            try:
                guild_member = ctx.guild.get_member(int(target_id))
                if not guild_member:
                    msg = await ctx.send("❌ User is not in this server.")
                    await asyncio.sleep(get_delete_delay())
                    await msg.delete()
                    return
            except Exception as e:
                print(f"Error getting guild member: {e}", type_="ERROR")
                msg = await ctx.send("❌ Could not verify user in this server.")
                await asyncio.sleep(get_delete_delay())
                await msg.delete()
                return
            
            try:
                await guild_member.add_roles(verify_role)
                
                unverified_role_id = guild_config.get("unverified_role")
                if unverified_role_id:
                    unverified_role = ctx.guild.get_role(int(unverified_role_id))
                    if unverified_role and unverified_role in guild_member.roles:
                        await guild_member.remove_roles(unverified_role)
                
                welcome_message = guild_config.get("verify_message", "Welcome!")
                await ctx.send(f"{guild_member.mention} {welcome_message}")
                
                print(f"Successfully verified {guild_member.name} in {ctx.guild.name}", type_="SUCCESS")
                
            except Exception as e:
                print(f"Error managing roles: {e}", type_="ERROR")
                msg = await ctx.send("❌ Failed to manage roles. Check bot permissions.")
                await asyncio.sleep(get_delete_delay())
                await msg.delete()

    print("Verify System loaded successfully", type_="INFO")

VerifyScript()