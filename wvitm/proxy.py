import re
from typing import Union
from urllib.parse import unquote_plus, urljoin, quote_plus

import aiohttp
from aiohttp import web

NORD_AUTH = None  # "serviceCredsUser:serviceCredsPass"


async def _proxy(session: aiohttp.ClientSession, server: str, url: str) -> Union[bytes, str]:
    if server == "docoja":
        req = session.get(
            url="https://www.docoja.com/blue/browse.php",
            params={
                "u": url,
                "b": 4,
                "f": "norefer"
            },
            headers={
                "Referer": "https://www.docoja.com/blue/"
            }
        )
    elif server == "duong":
        req = session.get(
            url="https://duong.id.au/proxy/index.php",
            params={
                "q": url,
                "hl": "3e5"
            }
        )
    elif server == "zalmos":
        req = session.get(
            url="https://proxy.zalmos.com/",
            params={"u": url}
        )
    else:
        if not NORD_AUTH:
            raise ValueError("NordVPN proxy is not currently supported.")
        proxy_hostname = f"{server}.nordvpn.com"
        req = session.get(
            url=url,
            proxy=f"https://{NORD_AUTH}@{proxy_hostname}:89"
        )

    async with req as r:
        res = await r.read()
        if res.startswith(b"#EXTM3U"):
            m3u8 = (await r.text()).splitlines(keepends=False)
            # relative to absolute
            m3u8 = [
                # urljoin(url, line).split("?")[0]
                urljoin(url, line) if line and not line.startswith(("http", "#")) else line
                for line in m3u8
            ]
            # use proxied ts url
            m3u8 = [
                f"/proxy/{server}?url={quote_plus(line)}" if line and not line.startswith("#") else line
                for line in m3u8
            ]
            # rejoin
            m3u8 = "\n".join(m3u8)
            # use proxied playlist urls
            for uri in re.finditer(r',URI="(.+?)"', m3u8):
                # urljoin(url, uri.group(1)).split("?")[0]
                m3u8 = m3u8.replace(uri.group(0), f',URI="/proxy/{server}?url={quote_plus(urljoin(url, uri.group(1)))}"')
            return m3u8
        else:
            # assume data stream
            return res


async def proxy(request: web.Request) -> web.Response:
    """
    Download the specified URL using a Proxy.
    Effectively just a web-proxy as an API with no fuss.

    If the URL is to an m3u(8) document, it will rewrite the URLs within it to also be
    proxied with the same server. This may fail if the specified URL or any URL within
    the M3U8 is too long.

    Possible Server values:
    - NordVPN Proxy put E.g., 'uk2020'. See https://nordvpn.com/servers/tools/
    - Docoja.com/blue UK Web Proxy put 'docoja'.
    """
    session: aiohttp.ClientSession = request.app["session"]

    server = request.match_info["server"]

    url = unquote_plus(request.rel_url.query.get("url") or "")
    if not url:
        web.json_response({
            "status": 400,
            "message": "The 'url' query parameter must be supplied."
        })

    proxied_data = await _proxy(session, server, url)

    if isinstance(proxied_data, str):
        return web.Response(text=proxied_data, content_type="application/mpegURL")
    else:
        return web.Response(body=proxied_data, content_type="application/octet-stream")
