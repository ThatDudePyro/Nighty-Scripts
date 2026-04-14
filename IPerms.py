def iperms_script():
    import asyncio
    import traceback

    #  SESSION STATE
    active_sessions = {}

    PERMISSION_FLAGS = [
        ("View Channel",         1 << 10),
        ("Send Messages",        1 << 11),
        ("Send TTS Messages",    1 << 12),
        ("Manage Messages",      1 << 13),
        ("Embed Links",          1 << 14),
        ("Attach Files",         1 << 15),
        ("Read Message History", 1 << 16),
        ("Mention Everyone",     1 << 17),
        ("Use External Emojis",  1 << 18),
        ("Add Reactions",        1 << 6),
        ("Connect",              1 << 20),
        ("Speak",                1 << 21),
        ("Mute Members",         1 << 22),
        ("Deafen Members",       1 << 23),
    ]
    #  HELPERS
    def get_existing_overwrite(channel, target_id):
        for ow in channel.overwrites:
            if ow.id == target_id:
                return ow.allow.value, ow.deny.value
        return 0, 0

    def build_channel_list(guild):
        text_channels = [c for c in guild.channels if hasattr(c, 'topic')]
        text_channels.sort(key=lambda c: c.position)
        return list(enumerate(text_channels, start=1))

    def build_role_list(guild):
        roles = sorted(guild.roles, key=lambda r: r.position, reverse=True)
        return list(enumerate(roles, start=1))

    def build_perms_display(allow_val, deny_val, pending: dict):
        lines = []
        for i, (name, bit) in enumerate(PERMISSION_FLAGS, start=1):
            if bit in pending:
                state = pending[bit]
            elif allow_val & bit:
                state = True
            elif deny_val & bit:
                state = False
            else:
                state = None

            icon = "✅" if state is True else ("❌" if state is False else "⬜")
            lines.append(f"`{i:>2}.` {icon} {name}")
        return "\n".join(lines)

    async def cleanup_session(user_id, step_msg=None):
        if user_id in active_sessions:
            del active_sessions[user_id]
        if step_msg:
            try:
                await step_msg.delete()
            except Exception:
                pass

    async def replace_step_msg(session, content):
        old = session.get("step_msg")
        if old:
            try:
                await old.delete()
            except Exception:
                pass
        new_msg = await session["ctx_channel"].send(content)
        session["step_msg"] = new_msg
        return new_msg

    async def edit_step_msg(session, content):
        msg = session.get("step_msg")
        if msg:
            try:
                await msg.edit(content=content)
                return msg
            except Exception:
                pass
        new_msg = await session["ctx_channel"].send(content)
        session["step_msg"] = new_msg
        return new_msg

    #  MAIN COMMAND 
    @bot.command(
        name="setperms",
        aliases=["sp", "iperms"],
        usage="",
        description="Interactive guided flow to set channel permissions for a role."
    )
    async def setperms_main(ctx, *, args: str = ""):
        await ctx.message.delete()

        if not ctx.guild:
            await ctx.send("❌ This only works in a server.")
            return

        user_id = bot.user.id

        if user_id in active_sessions:
            await ctx.send("⚠️ Session already active. Type `cancel` to end it first.")
            return

        channel_list = build_channel_list(ctx.guild)
        if not channel_list:
            await ctx.send("❌ No text channels found.")
            return

        lines = ["**Step 1/3 — Pick a channel** (type its number, or `cancel`):\n"]
        for idx, ch in channel_list:
            lines.append(f"{idx}. - `#{ch.name}`")

        step_msg = await ctx.send("\n".join(lines))

        active_sessions[user_id] = {
            "step": 1,
            "channel": None,
            "role": None,
            "pending": {},
            "channel_list": channel_list,
            "role_list": None,
            "allow_val": 0,
            "deny_val": 0,
            "step_msg": step_msg,
            "ctx_channel": ctx.channel,
            "locked": False,
        }

    #  EVENT LISTENER
    @bot.listen("on_message")
    async def setperms_flow(message):
        if message.author.id != bot.user.id:
            return

        user_id = bot.user.id
        if user_id not in active_sessions:
            return

        session = active_sessions[user_id]

        if message.channel.id != session["ctx_channel"].id:
            return

        if session["locked"]:
            return

        step_msg = session.get("step_msg")
        if step_msg and message.id == step_msg.id:
            return

        session["locked"] = True

        raw = message.content.strip()

        try:
            await message.delete()
        except Exception:
            pass

        try:
            if raw.lower() == "cancel":
                await cleanup_session(user_id, step_msg)
                await session["ctx_channel"].send("🚫 Permission setup cancelled.")
                return

            step = session["step"]

            # ---- STEP 1: channel pick ----
            if step == 1:
                channel_list = session["channel_list"]
                try:
                    choice = int(raw)
                    assert 1 <= choice <= len(channel_list)
                except (ValueError, AssertionError):
                    lines = ["❌ That's not a valid number. Pick one from the list below, or type `cancel`:\n"]
                    for idx, ch in channel_list:
                        lines.append(f"{idx}. - `#{ch.name}`")
                    await replace_step_msg(session, "\n".join(lines))
                    return

                selected_channel = channel_list[choice - 1][1]
                session["channel"] = selected_channel

                role_list = build_role_list(message.guild)
                session["role_list"] = role_list

                lines = [
                    f"**Step 2/3 — Pick a role** for **`#{selected_channel.name}`**"
                    f" (type its number, or `cancel`):\n"
                ]
                for idx, role in role_list:
                    lines.append(f"{idx}. - `{role.name}`")

                await replace_step_msg(session, "\n".join(lines))
                session["step"] = 2

            # ---- STEP 2: role pick ----
            elif step == 2:
                role_list = session["role_list"]
                try:
                    choice = int(raw)
                    assert 1 <= choice <= len(role_list)
                except (ValueError, AssertionError):
                    lines = ["❌ That's not a valid number. Pick one from the list below, or type `cancel`:\n"]
                    for idx, role in role_list:
                        lines.append(f"{idx}. - `{role.name}`")
                    await replace_step_msg(session, "\n".join(lines))
                    return

                selected_role = role_list[choice - 1][1]
                session["role"] = selected_role

                allow_val, deny_val = get_existing_overwrite(session["channel"], selected_role.id)
                session["allow_val"] = allow_val
                session["deny_val"] = deny_val
                session["pending"] = {}

                perms_display = build_perms_display(allow_val, deny_val, {})
                msg_text = (
                    f"**Step 3/3 — Toggle permissions** for **`{selected_role.name}`**"
                    f" in **`#{session['channel'].name}`**\n\n"
                    f"✅ Allow  ❌ Deny  ⬜ Neutral (inherited)\n\n"
                    f"{perms_display}\n\n"
                    f"Type **`<num> A`** to allow, **`<num> D`** to deny, **`<num> N`** for neutral (e.g. `1 A`, `3 D`)\n"
                    f"Type **`done`** to apply, or `cancel` to abort."
                )
                await replace_step_msg(session, msg_text)
                session["step"] = 3

            # ---- STEP 3: permission toggling ----
            elif step == 3:
                if raw.lower() == "done":
                    await _apply_permissions(session)
                    return

                parts = raw.upper().split()
                state_map = {"A": True, "D": False, "N": None}
                explicit_state = ...

                try:
                    choice = int(parts[0])
                    assert 1 <= choice <= len(PERMISSION_FLAGS)
                    if len(parts) >= 2:
                        if parts[1] not in state_map:
                            raise ValueError("bad state token")
                        explicit_state = state_map[parts[1]]
                except (ValueError, AssertionError):
                    perms_display = build_perms_display(
                        session["allow_val"], session["deny_val"], session["pending"]
                    )
                    msg_text = (
                        f"❌ Invalid input. Use `<num> A/D/N` (e.g. `1 A`, `2 D`, `3 N`).\n\n"
                        f"**Step 3/3 — Toggle permissions** for **`{session['role'].name}`**"
                        f" in **`#{session['channel'].name}`**\n\n"
                        f"✅ Allow  ❌ Deny  ⬜ Neutral (inherited)\n\n"
                        f"{perms_display}\n\n"
                        f"Type **`<num> A`** to allow, **`<num> D`** to deny, **`<num> N`** for neutral\n"
                        f"Type **`done`** to apply, or `cancel` to abort."
                    )
                    await edit_step_msg(session, msg_text)
                    return

                _, bit = PERMISSION_FLAGS[choice - 1]
                pending = session["pending"]
                allow_val = session["allow_val"]
                deny_val = session["deny_val"]

                if explicit_state is ...:
                    if bit in pending:
                        current = pending[bit]
                    elif allow_val & bit:
                        current = True
                    elif deny_val & bit:
                        current = False
                    else:
                        current = None
                    pending[bit] = True if current is None else (False if current is True else None)
                else:
                    pending[bit] = explicit_state

                session["pending"] = pending

                perms_display = build_perms_display(allow_val, deny_val, pending)
                msg_text = (
                    f"**Step 3/3 — Toggle permissions** for **`{session['role'].name}`**"
                    f" in **`#{session['channel'].name}`**\n\n"
                    f"✅ Allow  ❌ Deny  ⬜ Neutral (inherited)\n\n"
                    f"{perms_display}\n\n"
                    f"Type **`<num> A`** to allow, **`<num> D`** to deny, **`<num> N`** for neutral\n"
                    f"Type **`done`** to apply, or `cancel` to abort."
                )
                await edit_step_msg(session, msg_text)

        except Exception as e:
            print(f"[iPerms] Unhandled error in flow: {e}", type_="ERROR")
            traceback.print_exc()
        finally:
            if user_id in active_sessions:
                active_sessions[user_id]["locked"] = False

    #  APPLY 
    async def _apply_permissions(session):
        channel = session["channel"]
        role = session["role"]
        pending = session["pending"]
        existing_allow = session["allow_val"]
        existing_deny = session["deny_val"]
        ctx_channel = session["ctx_channel"]
        step_msg = session.get("step_msg")
        user_id = bot.user.id

        if not pending:
            await cleanup_session(user_id, step_msg)
            await ctx_channel.send("⚠️ No changes made. Nothing to apply.")
            return

        new_allow = existing_allow
        new_deny = existing_deny

        for bit, state in pending.items():
            if state is True:
                new_allow |= bit
                new_deny &= ~bit
            elif state is False:
                new_deny |= bit
                new_allow &= ~bit
            else:
                new_allow &= ~bit
                new_deny &= ~bit

        try:
            await bot.http.edit_channel_permissions(
                channel.id,
                role.id,
                new_allow,
                new_deny,
                0  # 0 = role
            )
            await cleanup_session(user_id, step_msg)
            await ctx_channel.send(
                f"✅ Permissions applied for **`{role.name}`** in **`#{channel.name}`**.\n"
                f"Allow: `{new_allow}` | Deny: `{new_deny}`"
            )
            print(
                f"[iPerms] Applied — #{channel.name} | {role.name} "
                f"| Allow: {new_allow} | Deny: {new_deny}",
                type_="SUCCESS"
            )
        except Exception as e:
            await cleanup_session(user_id, step_msg)
            await ctx_channel.send(f"❌ Failed to apply: `{e}`")
            print(f"[iPerms] Failed to apply permissions: {e}", type_="ERROR")
            traceback.print_exc()

    print("[iPerms] Interactive Permission Setter loaded. Try <p>setperms", type_="SUCCESS")


iperms_script()