from constants.player import bStatus, Privileges
from constants.packets import BanchoPackets
from packets.reader import Reader, Packet
from constants import commands as cmd
from objects.beatmap import Beatmap
from constants.playmode import Mode
from lenhttp import Router, Request
from objects.player import Player
from constants.mods import Mods
from constants.match import *
from typing import Callable
from packets import writer
from utils import general
from objects import glob
from utils import score
from utils import log
from oppai import *
import asyncio
import bcrypt
import struct
import time
import copy
import os
import re

def register_event(packet: BanchoPackets, restricted: bool = False) -> Callable:
    def decorator(cb: Callable) -> Callable:
        glob.packets |= {packet.value: Packet(
            packet=packet,
            callback=cb,
            restricted=restricted
        )}

    return decorator

glob.bancho = Router({re.compile(rf"^c[e4-6]?.mitsuha.pw$"), f"127.0.0.1:{glob.port}"})

IGNORED_PACKETS: list[int] = [4, 79]

@glob.bancho.add_endpoint("/", methods=["POST"])
async def handle_bancho(req: Request):
    if not "User-Agent" in req.headers.keys() or req.headers["User-Agent"] != "osu!":
        return "no"

    if not "osu-token" in req.headers:
        return await login(req)

    token = req.headers["osu-token"]

    if not (player := glob.players.get_user(token)):
        return await writer.Notification("Server has restarted") + await writer.ServerRestart()

    for p in (sr := Reader(req.body)):
        if player.is_restricted and (not p.restricted):
            continue

        start = time.time_ns()

        await p.callback(player, sr)

        end = (time.time_ns() - start) / 1e6

        if glob.debug and p.packet.value not in IGNORED_PACKETS:
            log.debug(
                f"Packet <{p.packet.value} | {p.packet.name}> has been requested by {player.username} - {round(end, 2)}ms"
            )

    req.add_header("Content-Type", "text/html; charset=UTF-8")
    player.last_update = time.time()

    return player.dequeue() or b""

async def login(req: Request):
    req.add_header("cho-token", "no")
    
    start = time.time_ns()
    data = bytearray(await writer.ProtocolVersion(19))
    # parse login info and client info.
    # {0}
    login_info = req.body.decode().split("\n")[:-1]


    # {0}|{1}|{2}|{3}|{4}
    # 0 = Build name, 1 = Time offset
    # 2 = Display city location, 3 = Client hash
    # 4 = Block nonfriend PMs
    client_info = login_info[2].split("|")

    # the players ip address
    ip = req.headers["X-Real-IP"]

    # get all user needed information
    if not (
        user_info := await glob.sql.fetch(
            "SELECT username, id, privileges, "
            "passhash, lon, lat, country, cc FROM users "
            "WHERE safe_username = %s",
            [login_info[0].lower().replace(" ", "_")],
        )
    ):
        return await writer.UserID(-1)

    # encode user password and input password.
    phash = user_info["passhash"].encode("utf-8")
    pmd5 = login_info[1].encode("utf-8")

    # check if the password is correct
    if phash in glob.bcrypt_cache:
        if pmd5 != glob.bcrypt_cache[phash]:
            log.warn(
                f"USER {user_info['username']} ({user_info['id']}) | Login fail. (WRONG PASSWORD)"
            )

            return await writer.UserID(-1)
    else:
        if not bcrypt.checkpw(pmd5, phash):
            log.warn(
                f"USER {user_info['username']} ({user_info['id']}) | Login fail. (WRONG PASSWORD)"
            )

            return await writer.UserID(-1)

        glob.bcrypt_cache[phash] = pmd5

    if glob.players.get_user(user_info["username"]):
        # user is already online? sus
        return await writer.Notification("You're already online on the server!") + await writer.UserID(-1)

    # invalid security hash (old ver probably using that)
    if len(client_info[3].split(":")) < 4:
        return await writer.UserID(-2)

    # check if user is restricted; pretty sure its like this lol
    if not user_info["privileges"] & Privileges.VERIFIED and (not user_info["privileges"] & Privileges.PENDING):
        data += await writer.Notification(
            "Your account has been set in restricted mode."
        )

    # only allow 2021 clients
    # if not client_info[0].startswith("b2021"):
    #     return await writer.UserID(-2)

    # check if the user is banned.
    if user_info["privileges"] & Privileges.BANNED:
        log.info(
            f"{user_info['username']} tried to login, but failed to do so, since they're banned."
        )

        return await writer.UserID(-3)

    # TODO: Hardware ban check (security[3] and [4])
    """
    if (UserManager.CheckBannedHardwareId(securityHashParts[3], securityHashParts[4]))
    {
        SendRequest(RequestType.Bancho_LoginReply, new bInt(-5));
        return false;
    }
    """
    # if my_balls > sussy_balls:
    #   return BanchoResponse(await writer.UserID(-5))

    kwargs = {
        "block_nonfriend": client_info[4],
        "version": client_info[0],
        "time_offset": int(client_info[1]),
        "ip": ip
    }

    p = Player(**user_info, **kwargs)

    p.last_update = time.time()

    glob.players.add_user(p)

    await asyncio.gather(*[p.get_friends(), p.update_stats_cache()])

    if p.privileges & Privileges.PENDING:
        await p.shout("Tell simon to verify your account")
        #await glob.bot.send_message("Since we're still in beta, you'll need to verify your account with a beta key given by one of the founders. You'll have 30 minutes to verify the account, or the account will be deleted. To verify your account, please enter !key <your beta key>", reciever=p)

    if not (user_info["lon"] or user_info["lat"] or user_info["cc"]) or user_info["country"] == "XX":
        await p.set_location()
        await p.save_location()

    asyncio.create_task(p.check_loc())

    data += await writer.UserID(p.id)
    data += await writer.UserPriv(p.privileges)
    data += await writer.MainMenuIcon()
    data += await writer.FriendsList(*p.friends)
    data += await writer.UserPresence(p)
    data += await writer.UpdateStats(p)

    for chan in glob.channels.channels:
        if chan.public:
            data += await writer.ChanInfo(chan.name)

            if chan.auto_join:
                data += await writer.ChanAutoJoin(chan.name)
                await p.join_channel(chan)

        if (chan.staff and p.is_staff):
            data += await writer.ChanInfo(chan.name)
            data += await writer.ChanJoin(chan.name)
            await p.join_channel(chan)

    for player in glob.players.players:
        if player != p:
            player.enqueue(await writer.UserPresence(p) + await writer.UpdateStats(p))

        data += await writer.UserPresence(player)
        data += await writer.UpdateStats(player)

    data += await writer.ChanInfoEnd()
    
    et = (time.time_ns() - start) / 1e6

    data += await writer.Notification(
        "Welcome to Ragnarok!\n"
        "made by Aoba and Simon.\n"
        "\n"
        "Authorization took " + str(general.rag_round(et, 2)) + "ms."
    )

    log.info(f"<{user_info['username']} | {user_info['id']}; {p.token}> logged in.")

    req.add_header("cho-token", p.token)

    return data

# id: 0
@register_event(BanchoPackets.OSU_CHANGE_ACTION, restricted=True)
async def change_action(p: Player, sr: Reader):
    p.status = bStatus(sr.read_uint8())
    p.status_text = sr.read_str()
    p.beatmap_md5 = sr.read_str()
    p.current_mods = sr.read_int32()
    p.play_mode = sr.read_uint8()
    p.beatmap_id = sr.read_int32()

    p.relax = int(bool(p.current_mods & Mods.RELAX))
    asyncio.create_task(p.update_stats_cache())

    if not p.is_restricted:
        glob.players.enqueue(await writer.UpdateStats(p))

# id: 1
@register_event(BanchoPackets.OSU_SEND_PUBLIC_MESSAGE)
async def send_public_message(p: Player, sr: Reader):
    # sender; but unused since 
    # we know who sent it lol
    sr.read_str()

    msg = sr.read_str()
    chan_name = sr.read_str()

    if not msg or msg.isspace():
        return

    if chan_name == "#multiplayer":
        if not (m := p.match):
            return
        
        chan = m.chat
    elif chan_name == "#spectator":
        # im not sure how to handle this
        chan = None
    else:
        chan = glob.channels.get_channel(chan_name)

    if not chan:
        await p.shout("You can't send messages to a channel, you're not already connected to.")
        return

    if msg[0] == glob.prefix:
        if resp := await cmd.handle_commands(message=msg, sender=p, reciever=chan):
            await chan.send(resp, sender=glob.bot)

    await chan.send(msg, p)

# id: 2
@register_event(BanchoPackets.OSU_LOGOUT, restricted=True)
async def logout(p: Player, sr: Reader):
    if (time.time() - p.login_time) < 1:
        return

    log.info(f"{p.username} logged out.")

    await p.logout()

# id: 3
@register_event(BanchoPackets.OSU_REQUEST_STATUS_UPDATE, restricted=True)
async def update_stats(p: Player, sr: Reader):
    p.enqueue(await writer.UpdateStats(p))

# id: 16
@register_event(BanchoPackets.OSU_START_SPECTATING)
async def start_spectate(p: Player, sr: Reader):
    spec = sr.read_int32()

    if not (host := glob.players.get_user(spec)):
        return

    await host.add_spectator(p)

# id: 17
@register_event(BanchoPackets.OSU_STOP_SPECTATING)
async def stop_spectate(p: Player, sr: Reader):
    host = p.spectating

    if not host:
        return

    await host.remove_spectator(p)

# id: 18
@register_event(BanchoPackets.OSU_SPECTATE_FRAMES)
async def spectating_frames(p: Player, sr: Reader):
    # fix spec crash
    # had to do a little offset, else it will stuck in loophole
    # TODO: make a proper R/W instead of echoing like this
    data = (
        struct.pack("<HxI", BanchoPackets.CHO_SPECTATE_FRAMES, len(sr.packet_data[7:]))
        + sr.packet_data[7:]
    )

    for t in p.spectators:
        t.enqueue(data)

# id: 21
@register_event(BanchoPackets.OSU_CANT_SPECTATE)
async def unable_to_spec(p: Player, sr: Reader):
    host = p.spectating

    if not host:
        return

    id = sr.read_int32()

    ret = await writer.UsrCantSpec(id)

    host.enqueue(ret)

    for t in host.spectators:
        t.enqueue(ret)

# id: 25
@register_event(BanchoPackets.OSU_SEND_PRIVATE_MESSAGE)
async def send_private_message(p: Player, sr: Reader):
    # sender - but unused, since we already know
    # who the sender is lol
    sr.read_str()

    msg = sr.read_str()
    reciever_id = sr.read_str

    if not (reciever := glob.players.get_user(reciever_id)):
        await p.shout("The player you're trying to reach is currently offline.")
        return

    if not reciever.bot:
        await p.send_message(msg, reciever=reciever)
    else:
        if (np := glob.regex["np"].search(msg)):
            p.last_np = await Beatmap.get_beatmap(beatmap_id=np.groups(1)[0])

        if msg[0] == glob.prefix:
            if resp := await cmd.handle_commands(message=msg, sender=p, reciever=glob.player):
                await glob.bot.send_message(resp, reciever=p)


        await glob.bot.send_message("beep boop", reciever=p)

# id: 29
@register_event(BanchoPackets.OSU_PART_LOBBY)
async def lobby_part(p: Player, sr: Reader):
    p.in_lobby = False

    # if (lobby := glob.channels.get_channel("#lobby")) in p.channels:
    #     await p.leave_channel(lobby)

# id: 30
@register_event(BanchoPackets.OSU_JOIN_LOBBY)
async def lobby_join(p: Player, sr: Reader):
    p.in_lobby = True

    if p.match:
        await p.leave_match()

    for match in glob.matches.matches:
        if match.connected:
            p.enqueue(await writer.Match(match))

# id: 31
@register_event(BanchoPackets.OSU_CREATE_MATCH)
async def mp_create_match(p: Player, sr: Reader):
    m = sr.read_match()

    await glob.matches.add_match(m)

    await p.join_match(m, pwd=m.match_pass)

# id: 32
@register_event(BanchoPackets.OSU_JOIN_MATCH)
async def mp_join(p: Player, sr: Reader):
    matchid = sr.read_int32()
    matchpass = sr.read_str()

    if p.match:
        return

    if not (m := await glob.matches.find_match(matchid)):
        p.enqueue(await writer.MatchFail())
        return

    await p.join_match(m, pwd=matchpass)

# id: 33
@register_event(BanchoPackets.OSU_PART_MATCH)
async def mp_leave(p: Player, sr: Reader):
    if p.match:
        await p.leave_match()

# id: 38
@register_event(BanchoPackets.OSU_MATCH_CHANGE_SLOT)
async def mp_change_slot(p: Player, sr: Reader):
    slot_id = sr.read_int16()

    if not (m := p.match):
        return

    slot = m.slots[slot_id]

    if slot.status == SlotStatus.OCCUPIED:
        log.error(f"{p.username} tried to change to an occupied slot ({m!r})")
        return

    if not (old_slot := m.find_user(p)):
        return

    slot.copy_from(old_slot)

    old_slot.reset()

    await m.enqueue_state()

# id: 39
@register_event(BanchoPackets.OSU_MATCH_READY)
async def mp_ready_up(p: Player, sr: Reader):
    if not (m := p.match):
        return

    slot = m.find_user(p)

    if slot.status == SlotStatus.READY:
        return

    slot.status = SlotStatus.READY

    await m.enqueue_state()

# id: 40
@register_event(BanchoPackets.OSU_MATCH_LOCK)
async def mp_lock_slot(p: Player, sr: Reader):
    slot_id = sr.read_int16()

    if not (m := p.match):
        return

    slot = m.slots[slot_id]

    if slot.status == SlotStatus.LOCKED:
        slot.status = SlotStatus.OPEN
    else:
        slot.status = SlotStatus.LOCKED

    await m.enqueue_state()

# id: 41
@register_event(BanchoPackets.OSU_MATCH_CHANGE_SETTINGS)
async def mp_change_settings(p: Player, sr: Reader):
    if not (m := p.match):
        return
    
    new_match = sr.read_match()

    if m.host != p.id:
        return

    if new_match.map_md5 != m.map_md5:
        map = await Beatmap.get_beatmap(new_match.map_md5)

        if map:
            m.map_md5 = map.hash_md5
            m.map_title = map.full_title
            m.map_id = map.map_id
            m.mode = Mode(map.mode)
        else:
            m.map_md5 = new_match.map_md5
            m.map_title = new_match.map_title
            m.map_id = new_match.map_id
            m.mode = Mode(new_match.mode)

    if new_match.match_name != m.match_name:
        m.match_name = new_match.match_name

    if new_match.freemods != m.freemods:
        if new_match.freemods:
            m.mods = Mods(m.mods & Mods.MULTIPLAYER)
        else:
            for slot in m.slots:
                if slot.mods:
                    slot.mods = 0

        m.freemods = new_match.freemods

    if new_match.scoring_type != m.scoring_type:
        m.scoring_type = new_match.scoring_type

    if new_match.team_type != m.team_type:
        m.team_type = new_match.team_type

    await m.enqueue_state()

# id: 44
@register_event(BanchoPackets.OSU_MATCH_START)
async def mp_start(p: Player, sr: Reader):
    if not (m := p.match):
        return

    if not p.id == m.host:
        log.warn(f"{p.username} tried to start the match, while not being the host.")
        return

    for slot in m.slots:
        if slot.status & SlotStatus.OCCUPIED:
            if slot.status != SlotStatus.NOMAP:
                slot.status = SlotStatus.PLAYING
                slot.p.enqueue(await writer.MatchStart(m))

    await m.enqueue_state(lobby=True)

# id: 47
@register_event(BanchoPackets.OSU_MATCH_SCORE_UPDATE)
async def mp_score_update(p: Player, sr: Reader):
    if not (m := p.match):
        return

    raw_sr = copy.copy(sr)

    raw = raw_sr.read_raw()

    s = sr.read_scoreframe()

    if m.mods & Mods.RELAX:
        if os.path.isfile(f".data/beatmaps/{m.map_id}.osu"):
            acc = general.rag_round(score.calculate_accuracy(
                m.mode, s.count_300, s.count_100, s.count_50,
                s.count_geki, s.count_katu, s.count_miss
            ), 2) if s.count_300 != 0 else 0

            ez = ezpp_new()

            if m.mods:
                ezpp_set_mods(ez, m.mods)

            ezpp_set_combo(ez, s.max_combo)
            ezpp_set_nmiss(ez, s.count_miss)
            ezpp_set_accuracy_percent(ez, acc)

            ezpp(ez, f".data/beatmaps/{m.map_id}.osu")
            s.score = int(ezpp_pp(ez)) if acc != 0 else 0

            ezpp_free(ez)
        else:
            log.fail(f"MATCH {m.id}: Couldn't find the osu beatmap.")

    slot_id = m.find_user_slot(p)

    if glob.debug:
        log.debug(f"{p.username} has slot id {slot_id} and has incoming score update.")

    m.enqueue(await writer.MatchScoreUpdate(s, slot_id, raw))

# id: 49
@register_event(BanchoPackets.OSU_MATCH_COMPLETE)
async def mp_complete(p: Player, sr: Reader):
    if not (m := p.match):
        return

    played = [slot.p for slot in m.slots if slot.status == SlotStatus.PLAYING]

    for slot in m.slots:
        if slot.p in played:
            slot.status = SlotStatus.NOTREADY

    m.in_progress = False

    for pl in played:
        pl.enqueue(await writer.MatchComplete())

    await m.enqueue_state(lobby=True)

# id: 51
@register_event(BanchoPackets.OSU_MATCH_CHANGE_MODS)
async def mp_change_mods(p: Player, sr: Reader):
    mods = sr.read_int16()

    if not (m := p.match):
        return

    if m.freemods:
        if m.host == p.id:
            if mods & Mods.MULTIPLAYER:
                m.mods = Mods(mods & Mods.MULTIPLAYER)
        
        slot = m.find_user(p)

        slot.mods = mods - (mods & Mods.MULTIPLAYER)
    else:
        if m.host != p.id:
            return

        m.mods = Mods(mods)

    await m.enqueue_state()

# id: 52
@register_event(BanchoPackets.OSU_MATCH_LOAD_COMPLETE)
async def mp_load_complete(p: Player, sr: Reader):
    if not (m := p.match):
        return
        
    m.find_user(p).loaded = True

    if all(s.loaded for s in m.slots if s.status == SlotStatus.PLAYING):
        m.enqueue(await writer.MatchAllReady())

# id: 54
@register_event(BanchoPackets.OSU_MATCH_NO_BEATMAP)
async def mp_no_beatmap(p: Player, sr: Reader):
    if not (m := p.match):
        return

    m.find_user(p).status = SlotStatus.NOMAP

    await m.enqueue_state()

# id: 55
@register_event(BanchoPackets.OSU_MATCH_NOT_READY)
async def mp_unready(p: Player, sr: Reader):
    if not p.match:
        return

    slot = p.match.find_user(p)

    if slot.status == SlotStatus.NOTREADY:
        return

    slot.status = SlotStatus.NOTREADY

    await p.match.enqueue_state()

@register_event(BanchoPackets.OSU_MATCH_HAS_BEATMAP)
async def has_beatmap(p: Player, sr: Reader):
    if not (m := p.match):
        return

    m.find_user(p).status = SlotStatus.NOTREADY

    await m.enqueue_state()

# id: 63
@register_event(BanchoPackets.OSU_CHANNEL_JOIN, restricted=True)
async def join_osu_channel(p: Player, sr: Reader):
    channel = sr.read_str()

    if not (c := glob.channels.get_channel(channel)):
        await p.shout("Channel couldn't be found.")
        return

    await p.join_channel(c)

# id: 70
@register_event(BanchoPackets.OSU_MATCH_TRANSFER_HOST)
async def mp_transfer_host(p: Player, sr: Reader):
    slot_id = sr.read_int16()
    
    if not (m := p.match):
        return

    if not (slot := m.find_slot(slot_id)):
        return

    m.host = slot.p.id
    slot.p.enqueue(await writer.MatchTransferHost())

    m.enqueue(await writer.Notification(f"{slot.p.username} became host!"))

    await m.enqueue_state()

# id: 73 and 74
@register_event(BanchoPackets.OSU_FRIEND_ADD, restricted=True)
@register_event(BanchoPackets.OSU_FRIEND_REMOVE, restricted=True)
async def friend(p: Player, sr: Reader):
    user = sr.read_int32()

    await p.handle_friend(user)

# id: 77
@register_event(BanchoPackets.OSU_MATCH_CHANGE_TEAM)
async def mp_change_team(p: Player, sr: Reader):
    if not (m := p.match):
        return

    slot = m.find_user(p)

    if slot.team == SlotTeams.BLUE:
        slot.team = SlotTeams.RED
    else:
        slot.team = SlotTeams.BLUE

    await m.enqueue_state()

# id: 78
@register_event(BanchoPackets.OSU_CHANNEL_PART, restricted=True)
async def leave_osu_channel(p: Player, sr: Reader):
    chan = sr.read_str()

    if chan[0] == "#":
        if not (chan := glob.channels.get_channel(chan)) in p.channels:
            await p.shout("You can't leave something, you're not already in.")
            return

        await p.leave_channel(chan)

# id: 85
@register_event(BanchoPackets.OSU_USER_STATS_REQUEST, restricted=True)
async def request_stats(p: Player, sr: Reader):
    # people id's that current online rn
    users = sr.read_i32_list()

    if len(users) > 32:
        return

    for user in users:
        if user == p.id:
            continue

        u = glob.players.get_user(user)

        if not u:
            continue

        u.enqueue(await writer.UpdateStats(u))

# id: 87
@register_event(BanchoPackets.OSU_MATCH_INVITE)
async def mp_invite(p: Player, sr: Reader):
    reciever = sr.read_int32()

    if not (m := p.match):
        return

    if not (reciever := glob.players.get_user(reciever)):
        await p.shout("You can't invite someone who's offline.")
        return

    await writer.MatchInvite(m, p, reciever.username)


# id: 97
@register_event(BanchoPackets.OSU_USER_PRESENCE_REQUEST, restricted=True)
async def request_stats(p: Player, sr: Reader):
    # people id's that current online rn
    users = sr.read_i32_list()

    if len(users) > 256:
        return

    for user in users:
        if user == p.id:
            continue

        u = glob.players.get_user(user)

        if not u:
            continue

        u.enqueue(await writer.UserPresence(u))

# id: 98
@register_event(BanchoPackets.OSU_USER_PRESENCE_REQUEST_ALL, restricted=True)
async def request_stats(p: Player, sr: Reader):
    for player in glob.players.players:
        player.enqueue(await writer.UserPresence(player))
