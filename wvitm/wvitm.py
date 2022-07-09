import logging
from urllib.parse import urljoin

import aiohttp
from aiohttp import web

PORT = 8118

session: aiohttp.ClientSession
routes = web.RouteTableDef()


async def startup(_):
    global session
    session = aiohttp.ClientSession(
        skip_auto_headers=["User-Agent"],
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:101.0) Gecko/20100101 Firefox/101.0"
        }
    )


async def cleanup(_):
    if not session.closed:
        await session.close()


@routes.get("/ping")
async def ping(_):
    return web.json_response({
        "status": 200,
        "message": "pong"
    })


def main():
    app = web.Application()
    app.add_routes(routes)
    app.on_startup.append(startup)
    app.on_cleanup.append(cleanup)
    logging.basicConfig(level=logging.INFO)
    web.run_app(app, port=PORT)
