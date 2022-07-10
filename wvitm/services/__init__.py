from aiohttp import web

services = web.RouteTableDef()

# must import services after services route table above

from wvitm.services.ping import ping
