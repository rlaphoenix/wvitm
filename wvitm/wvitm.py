import logging

import aiohttp
from aiohttp import web

from wvitm.services import services

PORT = 8118


async def startup(app: web.Application):
    app["session"] = aiohttp.ClientSession(
        skip_auto_headers=["User-Agent"],
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:101.0) Gecko/20100101 Firefox/101.0"
        }
    )


async def cleanup(app: web.Application):
    if not app["session"].closed:
        await app["session"].close()


def main():
    app = web.Application()
    app.add_routes(services)
    app.on_startup.append(startup)
    app.on_cleanup.append(cleanup)
    logging.basicConfig(level=logging.INFO)
    web.run_app(app, port=PORT)
