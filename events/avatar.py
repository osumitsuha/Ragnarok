from decorators import register
from starlette.requests import Request
from starlette.responses import Response, FileResponse
import os

@register("/{user_id:int}")
async def handle(req: Request):
    if req.url._url.startswith("https://a.mitsuha.pw"):
        user_id = req.path_params["user_id"]
        if not user_id:
            return Response("You need to pass an id.")

        if not user_id or (not os.path.exists(f".data/avatars/{user_id}.png")):
            return FileResponse(f".data/avatars/0.png")

        return FileResponse(f".data/avatars/{user_id}.png")