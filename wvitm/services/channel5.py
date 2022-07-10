import re

import aiohttp
from aiohttp import web

from wvitm.services import services


@services.get("/channel5/{channel}.mpd")
async def channel5(request: web.Request) -> web.Response:
    """
    Convert a Channel 5 Channel ID to an MPEG-DASH MPD stream.
    E.g., /channel5/5usa.mpd (5USA 576p)

    This defeats the Widevine DRM applied on the streams by simply intercepting
    the stream calls with MiTM URL injection and decrypting them before returning
    the data to the client. It's hacky, somewhat works, but it works.
    """
    session: aiohttp.ClientSession = request.app["session"]

    channel = request.match_info["channel"]

    # has geoblock to uk
    async with session.get({
        "channel5": "https://akadashlive-c5.akamaized.net/out/v1/07646f4532504e45a2a8647f59372d1c/index.mpd",
        "5usa": "https://akadashlive-5usa.akamaized.net/out/v1/5fd4d85d778f431985cfa11190826777/index.mpd",
        "5star": "https://akadashlive-5star.akamaized.net/out/v1/c7150fa2d717466cae6740c9b75e0973/index.mpd",
        "5action": "https://akadashlive-paramount.akamaized.net/out/v1/074b4a2bf3564611b4a6908d78b8e2c0/index.mpd",
        "5select": "https://akadashlive-5select.akamaized.net/out/v1/f23dc3e45f1b4824a36cb33c1aafaa8a/index.mpd"
    }[channel]) as r:
        mpd = await r.text()
        if r.status != 200:
            return web.json_response({
                "status": r.status,
                "message": f"An unexpected error occurred while getting the {channel} Manifest: {mpd}"
            })

        # Disable Base Url and inject decrypt service
        mpd = mpd \
            .replace('initialization="', f'initialization="/shaka/channel5/{channel}/init/') \
            .replace('media="', f'media="/shaka/channel5/{channel}/data/')

        # Remove all Content Protections
        mpd = re.sub(r"<ContentProtection[\s\S]*?</ContentProtection>", "", mpd)

        return web.Response(text=mpd, content_type="application/dash+xml")
