from objects.player import Player
from constants.player import bStatus
from packets import writer
from objects import glob


class Louise:
    @staticmethod
    async def init() -> bool:
        if not (
            bot := await glob.sql.fetch(
                "SELECT id, username, privileges, passhash FROM users WHERE id = 1"
            )
        ):
            return False

        p = Player(bot["username"], bot["id"], bot["privileges"], bot["passhash"])

        p.status = bStatus.WATCHING
        p.status_text = "over deez nutz"

        p.bot = True

        glob.bot = p

        glob.players.add_user(p)

        for player in glob.players.players:
            player.enqueue(await writer.UserPresence(p) + await writer.UpdateStats(p))

        return True
