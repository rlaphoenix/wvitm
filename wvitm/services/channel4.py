import re

import aiohttp
from aiohttp import web

from wvitm.services import services


@services.get("/channel4/{channel}.mpd")
async def channel4(request: web.Request) -> web.Response:
    """
    Convert a Channel 4 Channel ID to an MPEG-DASH MPD stream.
    E.g., /channel4/c4.mpd (Channel 4 576p)

    This defeats the Widevine DRM applied on the streams by simply intercepting
    the stream calls with MiTM URL injection and decrypting them before returning
    the data to the client. It's hacky, somewhat works, but it works.
    """
    session: aiohttp.ClientSession = request.app["session"]

    channel = request.match_info["channel"]

    async with session.get(
        # .m3u8 exists but is FPS only
        url=f"https://csm-e-c4ukdash-eb.tls1.yospace.com/csm/extlive/channelfour01,{channel}-v2-iso-dash-h12.mpd",
        params={
            "yo.ac": "false",
            "yo.br": "false",
            "siteSectionId": f"watchlive.channel4.com/{channel}",
            "GUID": "f6d8b7b0-3ef5-4764-88dd-af5d7a136611"
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
            .replace(f"<BaseURL>https://cdn.live.dash.c4assets.com/v2/iso-dash-mp/{channel}/</BaseURL>", f"") \
            .replace('initialization="', f'initialization="/shaka/channel4/{channel}/init/') \
            .replace('media="', f'media="/shaka/channel4/{channel}/data/')

        # Remove Location URLs
        mpd = re.sub(r"<Location[\s\S]*?</Location>", "", mpd)

        # Remove all Content Protections
        mpd = re.sub(r"<ContentProtection[\s\S]*?</ContentProtection>", "", mpd)

        # Remove all Representations except best
        wanted_reps = ("item-07item", {
            "c4": "item-12item",
            "e4": "item-09item",
            "m4": "item-12item",
            "f4": "item-09item",
            "4s": "item-09item"
        }[channel])
        for representation in re.finditer(r'<Representation.*?id="(.*?)"/>', mpd):
            if not representation.group(1).endswith(wanted_reps):
                mpd = mpd.replace(representation.group(0), "")

        return web.Response(text=mpd, content_type="application/dash+xml")
