from objects.player import Player
from constants.status import bStatus
from packets import writer
from objects import glob

class Louise:
    @classmethod
    async def init(cls):
        if not (bot := await glob.sql.fetch("SELECT id, username, privileges, passhash FROM users WHERE id = 1")):
            return False

        p = Player(
            bot["username"],
            bot["id"], 
            bot["privileges"], 
            bot["passhash"],
            "127.0.0.1"
        )

        p.status = bStatus.WATCHING
        p.status_text = "over Aoba and Simon."

        await glob.players.add_user(p)
        for player in glob.players.players:
            player.enqueue(await writer.UserPresence(p) + await writer.UpdateStats(p))
        
        return True

    @classmethod
    async def special_init(cls):
        p = Player(
            Player.generate_token(),
            len(glob.players.players)+5, 
            1, 
            "none",
            "127.0.0.1"
        )

        p.status = bStatus.WATCHING
        p.status_text = "over what Aoba and Simon are doing..."

        p.bot = True

        await glob.players.add_user(p)
        for player in glob.players.players:
            player.enqueue(await writer.UserPresence(p) + await writer.UpdateStats(p))

        return True