import asyncio
import subprocess

import aiohttp
import yarl
from aiohttp import web

from wvitm.services import services


@services.get("/youtube/{video_id}.m3u8")
async def youtube(request: web.Request) -> web.Response:
    """
    Convert a YouTube Video Stream ID to an HLS M3U stream.
    E.g., /youtube/9Auq9mYxFEE.m3u8 (Sky News)

    Note that the returned stream will be restricted to the Server's Country.
    The initial manifest is restricted to the Server's IP, but the playlists and
    files within are restricted only to the Caller's Country.
    """
    session: aiohttp.ClientSession = request.app["session"]

    video_id = request.match_info["video_id"]

    try:
        proc = await asyncio.create_subprocess_exec(
            "youtube-dl",
            "-f", "96",
            "-g",
            f"https://www.youtube.com/watch?v={video_id}",
            stdout=asyncio.subprocess.PIPE
        )
        stdout, stderr = await proc.communicate()

        playlist_url = stdout.decode().strip()
    except subprocess.CalledProcessError as e:
        return web.json_response({
            "status": 400,
            "message": f"An unexpected error has occurred: {e.output}"
        })

    # must keep percent-coding
    playlist_url = yarl.URL(playlist_url, encoded=True)

    async with session.get(playlist_url) as r:
        m3u8 = await r.text()
        return web.Response(text=m3u8)
