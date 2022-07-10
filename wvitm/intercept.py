import asyncio
import re
import tempfile
from collections import defaultdict
from pathlib import Path
from subprocess import CalledProcessError

import aiohttp
from aiohttp import web


DRM_INIT_CACHE = {}
DRM_SEGMENT_CACHE = defaultdict(dict)
DRM_CONTENT_KEYS = {}
MAX_SEGMENT_CACHE = 100


def recover_url(service: str, channel: str, path: str) -> str:
    if service == "rte":
        return f"https://live.rte.ie/live/a/{channel}/{channel}.isml/dash/{path}"
    if service == "channel4":
        return f"https://cdn.live.dash.c4assets.com/v2/iso-dash-mp/{channel}/{path}"
    if service == "channel5":
        return {
            "channel5": f"https://akadashlive-c5.akamaized.net/out/v1/07646f4532504e45a2a8647f59372d1c/{path}",
            "5usa": f"https://akadashlive-5usa.akamaized.net/out/v1/5fd4d85d778f431985cfa11190826777/{path}",
            "5star": f"https://akadashlive-5star.akamaized.net/out/v1/c7150fa2d717466cae6740c9b75e0973/{path}",
            "5action": f"https://akadashlive-paramount.akamaized.net/out/v1/074b4a2bf3564611b4a6908d78b8e2c0/{path}",
            "5select": f"https://akadashlive-5select.akamaized.net/out/v1/f23dc3e45f1b4824a36cb33c1aafaa8a/{path}"
        }[channel]
    if service == "itv":
        # browser: f"https://itv1simadotcom.cdn1.content.itv.com/playout/pc01/{channel}/cenc.isml/dash/{path}"
        return f"https://{channel}simamobile.cdn1.content.itv.com/playout/mb01/{channel}/cenc.isml/dash/{path}"
    raise ValueError(f"Unrecognized '{service}'/'{channel}' Service/Channel combination")


def recover_presentation_id(service: str, channel: str, path: str) -> str:
    return re.search({
        "rte": rf"{channel}-([a-z]*[^-.]*)-?(?:\d+)?",
        "channel4": r"\d+(item-\d{2}item)",
        "channel5": r"index_(.*?_\d+_\d+)",
        "itv": r"cenc-([a-z]*[^-.]*)-?(?:\d+)?"
    }[service], path).group(1)


def remove_init_data(data: bytes) -> bytes:
    """
    Remove the init data by removing the data before and including the moov segment.
    This is to remove warnings about duplicate MOOV boxes.
    In some cases I've noticed smoother streaming by just leaving it in.
    """
    moov_start = data.rfind(b"moov") - 4
    moov_length = int.from_bytes(data[moov_start:moov_start + 4], "big")
    data = data[moov_start + moov_length:]
    return data


async def shaka(request: web.Request) -> web.Response:
    """
    Decrypts Widevine-encrypted Video and Audio Segments on-the-fly with shaka-packager.
    This method should be injected as a prefix of segment URLs in DASH or HLS manifests.
    Note: Shaka-packager provides no way to pipe input nor output data so this will be
    writing and reading from your drive. This may lower an SSDs life-span.
    """
    session: aiohttp.ClientSession = request.app["session"]

    service = request.match_info["service"]
    channel = request.match_info["channel"]
    seg_type = request.match_info["seg_type"]
    path = request.match_info["path"]

    url = recover_url(service, channel, path)
    presentation_id = recover_presentation_id(service, channel, path)

    service_key = f"{service}-{channel}"
    key_prefix = f"{service_key}-{presentation_id}"

    if seg_type == "init":
        async with session.get(url) as r:
            out = DRM_INIT_CACHE[key_prefix] = await r.read()
    else:
        out = DRM_SEGMENT_CACHE[service_key].get(path)
        if not out:
            init = DRM_INIT_CACHE.get(key_prefix)
            if not init:
                # a player could theoretically attempt loading of the media first
                return web.json_response({
                    "status": 400,
                    "message": f"Cannot decrypt segment {path} that did not have it's init segment loaded."
                })

            if not DRM_CONTENT_KEYS[service].get(channel):
                # TODO: Add a way to automatically get keys
                return web.json_response({
                    "status": 400,
                    "message": f"Cannot decrypt {service} {channel} as there's no decryption keys for it."
                })

            segment_file_path = Path(tempfile.gettempdir(), "wvitm", f"{key_prefix}-{path}.mp4")
            segment_file_path.parent.mkdir(parents=True, exist_ok=True)
            async with session.get(url) as r:
                segment_file_path.write_bytes(init + await r.read())

            try:
                args = [
                    "packager-win-x64",
                    f"input={segment_file_path},stream=0,output={segment_file_path}",
                    "--enable_raw_key_decryption",
                    "--keys",
                    ",".join([
                        f"label={i}:key_id={key[0]}:key={key[1]}"
                        for i, key in enumerate(DRM_CONTENT_KEYS[service][channel])
                    ])
                ]
                proc = await asyncio.create_subprocess_exec(
                    *args,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                stdout, stderr = await proc.communicate()
                if proc.returncode != 0:
                    raise CalledProcessError(proc.returncode, " ".join(args), stdout, stderr)
            except CalledProcessError as e:
                return web.json_response({
                    "status": 400,
                    "message": f"Shaka reported a decryption error: {e.stderr.decode()}"
                })

            out = DRM_SEGMENT_CACHE[service_key][path] = remove_init_data(segment_file_path.read_bytes())
            segment_file_path.unlink()

    if len(DRM_SEGMENT_CACHE[service_key]) > MAX_SEGMENT_CACHE:
        DRM_SEGMENT_CACHE[service_key].pop(list(DRM_SEGMENT_CACHE[service_key])[0])

    return web.Response(body=out, content_type="video/mp4")
