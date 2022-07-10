from aiohttp import web

from wvitm.services import services


@services.get("/ping")
async def ping(_) -> web.Response:
    return web.json_response({
        "status": 200,
        "message": "pong"
    })
