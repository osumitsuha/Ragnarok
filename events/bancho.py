from lib.responses import BanchoResponse
from starlette.requests import Request
from starlette.responses import HTMLResponse
from decorators import register, register_event
from constants.mods import Mods
from utils import log
from constants.privileges import Privileges
from utils import log
from objects import glob
from objects.player import Player
from packets import writer, reader
from constants.packets import BanchoPackets
from constants.status import bStatus
import asyncio
import bcrypt
import time

@register("/", methods=["GET", "POST"])
async def handle_bancho(req: Request):
    if req.method == "POST":
        if not "user-agent" in req.headers \
            or req.headers["user-agent"] != "osu!":
            return BanchoResponse("no")

        body = await req.body()

        if not "osu-token" in req.headers:
            return await login(
                body, req.headers["X-Real-IP"]
            )

        token = req.headers["osu-token"]
        packet_id = body[0]
        
        if not (player := await glob.players.get_user(token)):
            return BanchoResponse(bytes(
                await writer.Notification("Server has restarted") + await writer.ServerRestart()
            ))

        response = bytearray()

        if not any(h["packet"] == packet_id for h in glob.registered_packets) and not packet_id == 4:
            if glob.debug:
                log.warning(f"Packet <{packet_id} | {BanchoPackets(packet_id).name}> has been requested by {player.username} but isn't a registered packet.")
            
            return BanchoResponse(b"", token=player.token)

        for handle in glob.registered_packets:
            if packet_id == handle["packet"]:
                start = time.time_ns()
                # ignore restricted user trying 
                # to do unrestricted packets
                if player.is_restricted and (not handle["restricted"]):
                    continue

                await handle["func"](player, body)

                if glob.debug:
                    log.debug(f"Packet <{packet_id} | {BanchoPackets(packet_id).name}> has been requested by {player.username} - {round((time.time_ns() - start) / 1e6, 2)}ms")

        if player.queue:
            response += player.dequeue()

        return BanchoResponse(bytes(response), token=player.token)

    return HTMLResponse(f"<pre>{glob.title_card}<br>first attempt pog</pre>")


async def login(
    body: bytes,
    ip: str
) -> BanchoResponse:
    start = time.time_ns()
    data = bytearray(await writer.ProtocolVersion(19))
    # parse login info and client info.
    # {0}
    login_info = body.decode().split("\n")[:-1]

    # {0}|{1}|{2}|{3}|{4}
    # 0 = Build name, 1 = Time offset
    # 2 = Display city location, 3 = Client hash
    # 4 = Block nonfriend PMs
    client_info = login_info[2].split("|")

    # get all user needed information
    if not (user_info := await glob.sql.fetch(
        "SELECT username, id, privileges, passhash "
        "FROM users WHERE safe_username = %s",
        [login_info[0].lower().replace(" ", "_")]
    )):
        return BanchoResponse(await writer.UserID(-1))

    # encode user password and input password.
    phash = user_info["passhash"].encode("utf-8")
    pmd5 = login_info[1].encode("utf-8")

    # check if the password is correct
    if phash in glob.bcrypt_cache:
        if pmd5 != glob.bcrypt_cache[phash]:
            log.warning(f"USER {user_info['username']} ({user_info['id']}) | Login fail. (WRONG PASSWORD)")
            
            return BanchoResponse(await writer.UserID(-1))
    else:
        if not bcrypt.checkpw(pmd5, phash):
            log.warning(f"USER {user_info['username']} ({user_info['id']}) | Login fail. (WRONG PASSWORD)")
            
            return BanchoResponse(await writer.UserID(-1))

        glob.bcrypt_cache[phash] = pmd5

    if await glob.players.get_user(user_info["username"]):
        # user is already online? sus
        return BanchoResponse(
            await writer.Notification("You're already online on the server!") + \
            await writer.UserID(-1)
        )

    # invalid security hash (old ver probably using that)
    if len(client_info[3].split(":")) < 4:
        return BanchoResponse(await writer.UserID(-2))

    # check if user is restricted; pretty sure its like this lol
    if not user_info["privileges"] & Privileges.VERIFIED:
        data += await writer.Notification("Your account has been set in restricted mode.")

    # only allow 2021 clients
    if not client_info[0].startswith("b2021"):
        old_client_resp = await writer.UserID(-2)

        return BanchoResponse(old_client_resp)

    # check if the user is banned.
    if user_info["privileges"] & Privileges.BANNED:
        log.info(f"{user_info['username']} tried to login, but failed to do so, since they're banned.")
        
        return BanchoResponse(await writer.UserID(-3))

    # TODO: Hardware ban check (security[3] and [4])
    """
    if (UserManager.CheckBannedHardwareId(securityHashParts[3], securityHashParts[4]))
    {
        SendRequest(RequestType.Bancho_LoginReply, new bInt(-5));
        return false;
    }
    """
    #if my_balls > sussy_balls:
    #   return BanchoResponse(await writer.UserID(-5))
    
    user_info["ip"] = ip

    kwargs = {
        "block_nonfriend": client_info[4],
        "version": client_info[0],
        "time_offset": client_info[1],
    }

    p = Player(
        **user_info, **kwargs
    )

    await glob.players.add_user(p)

    await asyncio.gather(*[
        p.get_friends()
    ])

    data += await writer.UserID(p.id)
    data += await writer.UserPriv(p.privileges)
    data += await writer.MainMenuIcon()
    data += await writer.FriendsList(*p.friends)
    data += await writer.UserPresence(p)
    data += await writer.UpdateStats(p)
    data += await writer.ChanInfoEnd()

    for channel in glob.channels.channels:
        if channel.public:
            data += await writer.ChanInfo(channel.name)

        if channel.staff and p.is_staff:
            data += await writer.ChanInfo(channel.name)
            data += await writer.ChanJoin(channel.name)
            await glob.channels.join_channel(p, channel.name)
        
        if channel.auto_join:
            data += await writer.ChanJoin(channel.name)
            await glob.channels.join_channel(p, channel.name)

    for player in glob.players.players:
        player.enqueue(await writer.UserPresence(p) + await writer.UpdateStats(p))
        
        data += await writer.UserPresence(player)
        data += await writer.UpdateStats(player)

    data += await writer.Notification(
        "Welcome to Ragnarok!\n"
        "made by Aoba and Simon.\n"
        "\n"
        "Authorization took " + str(round((time.time_ns() - start) / 1e6, 2)) + "ms."
    ) 

    log.info(f"<{user_info['username']} | {user_info['id']}; {p.token}> logged in.")

    return BanchoResponse(bytes(data), p.token)

# id: 0
@register_event(BanchoPackets.OSU_CHANGE_ACTION, restricted=True)
async def change_action(p: Player, packet):
    stats = reader.read_packet(packet, (
        ("status", writer.Types.byte),
        ("status_text", writer.Types.string),
        ("beatmap_md5", writer.Types.string),
        ("current_mods", writer.Types.int32),
        ("play_mode", writer.Types.byte),
        ("beatmap_id", writer.Types.int32) 
    ))

    p.status = bStatus(stats["status"])
    p.status_text = stats["status_text"]
    p.beatmap_md5 = stats["beatmap_md5"]
    p.current_mods = stats["current_mods"]
    p.play_mode = stats["play_mode"]
    p.beatmap_id = stats["beatmap_id"]

    p.relax = int(bool(p.current_mods & Mods.RELAX))

    glob.players.enqueue(await writer.UpdateStats(p))

# id: 1
@register_event(BanchoPackets.OSU_SEND_PUBLIC_MESSAGE)
async def send_public_message(p: Player, packet):
    data = reader.read_packet(packet, (
        ("_", writer.Types.string),
        ("message", writer.Types.string),
        ("channel", writer.Types.string)
    ))

    await glob.channels.message(p, data["message"], data["channel"])


# id: 2
@register_event(BanchoPackets.OSU_LOGOUT, restricted=True)
async def logout(p: Player, packet):
    if (time.time() - p.login_time) < 5:
        return 

    log.info(f"{p.username} left the server.")

    await p.logout()

# id: 3
@register_event(BanchoPackets.OSU_REQUEST_STATUS_UPDATE, restricted=True)
async def update_stats(p: Player, packet):
    p.enqueue(
        await writer.UpdateStats(p)
    )

# id: 16
@register_event(BanchoPackets.OSU_START_SPECTATING, restricted=True)
async def start_spectate(p: Player, packet):
    data = reader.read_packet(packet, (
        ("user", writer.Types.int32),
    ))
    host = await glob.players.get_user(data["user"])

    if not host:
        return

    await host.add_spectator(p)

# id: 17
@register_event(BanchoPackets.OSU_STOP_SPECTATING, restricted=True)
async def stop_spectate(p: Player, packet):
    host = p.spectating
    if not host:
        return
    await host.remove_spectator(p)

# id: 18
@register_event(BanchoPackets.OSU_SPECTATE_FRAMES, restricted=True)
async def spectating_frames(p: Player, packet):
    data = reader.read_packet(packet, (
        ("frames", writer.Types.raw),
    ))

    for t in p.spectators:
        t.enqueue(await writer.SpecFramesData(data["frames"]))

# id: 21
@register_event(BanchoPackets.OSU_CANT_SPECTATE)
async def unable_to_spec(p: Player, packet):
    host = p.spectating
    if not host:
        return
    data = reader.read_packet(packet, (
        ("users", writer.Types.int32),
    ))
    host.enqueue(await writer.UsrCantSpec(data["users"]))
    for t in host.spectators:
            t.enqueue(await writer.UsrCantSpec(data["users"]))

# id: 25
@register_event(BanchoPackets.OSU_SEND_PRIVATE_MESSAGE)
async def send_public_message(p: Player, packet):
    data = reader.read_packet(packet, (
        ("_", writer.Types.string),
        ("message", writer.Types.string),
        ("user", writer.Types.string)
    ))

    await glob.channels.message(p, data["message"], data["user"])

# id: 63
@register_event(BanchoPackets.OSU_CHANNEL_JOIN, restricted=True)
async def join_osu_channel(p: Player, packet):
    data = reader.read_packet(packet, (
        ("channel", writer.Types.string),
    ))

    await glob.channels.join_channel(p, data["channel"])

# id: 73
@register_event(BanchoPackets.OSU_FRIEND_ADD)
async def add_friend(p: Player, packet):
    data = reader.read_packet(packet, (
        ("user", writer.Types.int32),
    ))

    await p.handle_friend(data["user"])

# id: 74
@register_event(BanchoPackets.OSU_FRIEND_REMOVE)
async def remove_friend(p: Player, packet):
    data = reader.read_packet(packet, (
        ("user", writer.Types.int32),
    ))

    await p.handle_friend(data["user"])

# id: 78
@register_event(BanchoPackets.OSU_CHANNEL_PART, restricted=True)
async def leave_osu_channel(p: Player, packet):
    data = reader.read_packet(packet, (
        ("channel", writer.Types.string),
    ))

    await glob.channels.leave_channel(p, data["channel"])

# id: 79
@register_event(BanchoPackets.OSU_RECEIVE_UPDATES, restricted=True)
async def presencefilter(p: Player, packet):
    # yes, i handle this but it doesnt do shit to client
    data = reader.read_packet(packet, (
        ("val", writer.Types.int32),
    ))

# id: 85
@register_event(BanchoPackets.OSU_USER_STATS_REQUEST, restricted=True)
async def request_stats(p: Player, packet):
    # people id's that current online rn
    data = reader.read_packet(packet, (
        ("users", writer.Types.int32_list),
    ))

    if len(data["users"]) > 32:
        return

    for user in data["users"]:
        if user == p.id:
            return

        u = await glob.players.get_user(user)

        u.enqueue(await writer.UpdateStats(u))

# id: 97
@register_event(BanchoPackets.OSU_USER_PRESENCE_REQUEST, restricted=True)
async def request_stats(p: Player, packet):
    # people id's that current online rn
    data = reader.read_packet(packet, (
        ("users", writer.Types.int32_list),
    ))

    if len(data["users"]) > 256:
        return

    for user in data["users"]:
        if user == p.id:
            return

        u = await glob.players.get_user(user)

        u.enqueue(await writer.UserPresence(u))

# id: 98
@register_event(BanchoPackets.OSU_USER_PRESENCE_REQUEST_ALL, restricted=True)
async def request_stats(p: Player, packet):
    for player in glob.players.players:
        player.enqueue(await writer.UserPresence(player))