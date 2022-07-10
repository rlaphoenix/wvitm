from aiohttp import web

services = web.RouteTableDef()

# must import services after services route table above

from wvitm.services.filmon import filmon
from wvitm.services.ping import ping
from wvitm.services.rte import rte
from wvitm.services.youtube import youtube
