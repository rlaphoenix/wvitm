import re

import aiohttp
from aiohttp import web

from wvitm.services import services


@services.get("/rte/{channel}.mpd")
async def rte(request: web.Request) -> web.Response:
    """
    Convert an RTE Channel ID to an MPEG-DASH MPD stream.
    E.g., /rte/channel1.mpd (RTE One HD)

    This defeats the Widevine DRM applied on the streams by simply intercepting
    the stream calls with MiTM URL injection and decrypting them before returning
    the data to the client. It's hacky, somewhat works, but it works.
    """
    session: aiohttp.ClientSession = request.app["session"]

    channel = request.match_info["channel"]

    base_url = f"https://live.rte.ie/live/a/{channel}/{channel}.isml"
    mpd_url = f"{base_url}/.mpd"

    async with session.get(
        url=mpd_url,  # .m3u8 exists but is FPS only
        params={
            # these don't seem to actually matter lol
            "dvr_window_length": "30",
            "available": "1653483300",
            "expiry": "1653513414",
            "filter": "systemBitrate<=7000000",
        }
    ) as r:
        mpd = await r.text()
        if r.status != 200:
            return web.json_response({
                "status": r.status,
                "message": f"An unexpected error occurred while getting the {channel} Manifest: {mpd}"
            })

        # Disable Base Url and inject decrypt service
        mpd = mpd \
            .replace("<BaseURL>dash/</BaseURL>", f"") \
            .replace('initialization="', f'initialization="/shaka/rte/{channel}/init/') \
            .replace('media="', f'media="/shaka/rte/{channel}/data/')

        # Remove all Content Protections
        mpd = re.sub(r"<ContentProtection[\s\S]*?</ContentProtection>", "", mpd)

        # Remove all Representations except best
        for representation in re.finditer(r'<Representation\s*id="(.*)"[\s\S]*?</Representation>', mpd):
            rep_id = representation.group(1)
            if rep_id not in ("audio_128k=128000", "video=6000000"):
                mpd = mpd.replace(representation.group(0), "")

        return web.Response(text=mpd, content_type="application/dash+xml")
