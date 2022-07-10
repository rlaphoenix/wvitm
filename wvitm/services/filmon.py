from urllib.parse import urljoin

import aiohttp
from aiohttp import web

from wvitm.services import services


@services.get("/filmon/{channel}/{quality}.m3u8")
async def filmon(request: web.Request) -> web.Response:
    """
    Convert a FilmOn Channel ID to a free unlimited duration HLS M3U stream.
    E.g., /filmon/65/high.m3u8 (E4 480p)

    The FilmOn links are intended to play as 30s previews but the URL usually lasts up to
    2 minutes. However, we can bypass this by simply grabbing a new stream URL every time
    the player calls your proxy URL.
    """
    session: aiohttp.ClientSession = request.app["session"]

    channel = request.match_info["channel"]
    if not channel.isdigit():
        raise ValueError(f"Expecting channel to be a number, not '{channel}'")

    quality = request.match_info["quality"]
    if quality not in ("low", "high"):
        raise ValueError(f"Expecting quality to be 'low' or 'high', not '{quality}'")

    async with session.get(
        url=f"http://www.filmon.com/api-v2/channel/{channel}",
        params={"protocol": "hls"}
    ) as r:
        res = await r.json()
        if r.status != 200:
            return web.json_response({
                "status": r.status,
                "message": res["message"]
            })

        channel_data = res["data"]
        stream_url = next((x["url"] for x in channel_data["streams"] if x["quality"] == quality), None)
        if not stream_url:
            return web.json_response({
                "status": 404,
                "message": f"No stream with the quality '{quality}' available for Channel {channel}"
            })

        async with session.get(stream_url) as s:
            if s.status != 200:
                return web.json_response({
                    "status": s.status,
                    "message": f"An unknown error occurred loading FilmOn {quality.title()} Quality Stream"
                })

            m3u = "\n".join([
                # relative to absolute
                urljoin(stream_url, line) if not line.startswith(("http", "#")) else line
                for line in (await s.text()).splitlines(keepends=False)
            ])

            return web.Response(text=m3u)
