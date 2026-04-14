def VCValues():
    IDLE_TS = "6372891638687"

    def _ts() -> str:
        return str(int(datetime.now().timestamp() * 1000))

    def _cfg(key: str, fallback: str = "") -> str:
        return getConfigData().get(key, fallback)

    def _join(channel, muted: bool, deafened: bool):
        is_dm = not hasattr(channel, 'guild') or channel.guild is None
        if is_dm:
            try:
                other = [m for m in channel.recipients if m.id != bot.user.id]
                dm_user = "someone"
            except Exception:
                dm_user = "someone"
            updateConfigData("_vci", f"DM call with {dm_user}")
        else:
            updateConfigData("_vci", f"{channel.name} (server: {channel.guild.name})")
        updateConfigData("_vic", "true")
        updateConfigData("_vcm", "true" if muted else "false")
        updateConfigData("_vdf", "true" if deafened else "false")
        updateConfigData("_vcd", _ts())

    def _leave():
        updateConfigData("_vic", "false")
        updateConfigData("_vci", "")
        updateConfigData("_vcm", "false")
        updateConfigData("_vdf", "false")
        updateConfigData("_vcd", IDLE_TS)

    try:
        selfbot = bot.user
        if selfbot:
            found = None
            found_member = None
            for guild in bot.guilds:
                member = guild.get_member(selfbot.id)
                if member and member.voice and member.voice.channel:
                    found = member.voice.channel
                    found_member = member
                    break
            if found:
                if _cfg("_vcd", IDLE_TS) == IDLE_TS:
                    _join(
                        found,
                        found_member.voice.self_mute or found_member.voice.mute,
                        found_member.voice.self_deaf or found_member.voice.deaf
                    )
                else:
                    is_dm = not hasattr(found, 'guild') or found.guild is None
                    if not is_dm:
                        updateConfigData("_vci", f"{found.name} (server: {found.guild.name})")
            else:
                _leave()
    except Exception as e:
        print(f"[VCValues] {e}", type_="ERROR")

    @bot.listen("on_voice_state_update")
    async def _vsu(member, before, after):
        try:
            if member.id != bot.user.id:
                return
            bc = before.channel if before else None
            ac = after.channel if after else None
            if ac is not None:
                _join(
                    ac,
                    after.self_mute or after.mute,
                    after.self_deaf or after.deaf
                )
            elif bc is not None:
                _leave()
        except Exception as e:
            print(f"[VCValues] {e}", type_="ERROR")

    def vc_status():
        if _cfg("_vic") != "true":
            return "Disconnected from voice:"
        if _cfg("_vdf") == "true":
            return "Deafened in voice:"
        if _cfg("_vcm") == "true":
            return "Muted in voice:"
        return "Connected to voice:"

    def vc_info():
        return _cfg("_vci")

    def vc_start():
        return _cfg("_vcd", IDLE_TS)

    addDRPCValue("vc_status", vc_status)
    addDRPCValue("vc_info",   vc_info)
    addDRPCValue("vc_start",  vc_start)

VCValues()