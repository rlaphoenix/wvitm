import logging

import aiohttp
from aiohttp import web
import click

from wvitm.services import services


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


@click.command(
    context_settings=dict(
        help_option_names=["-?", "-h", "--help"],  # default only has --help
        max_content_width=116,  # max PEP8 line-width, -4 to adjust for initial indent
    )
)
@click.option("-h", "--host", type=str, default="::", help="Port to run Web Server On")
@click.option("-p", "--port", type=int, default=8080, help="Port to run Web Server On")
def main(host: str, port: int):
    app = web.Application()
    app.add_routes(services)
    app.on_startup.append(startup)
    app.on_cleanup.append(cleanup)
    logging.basicConfig(level=logging.INFO)
    web.run_app(app, host=host, port=port)
