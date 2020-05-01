import logging
import acsys.dpm.dpm_protocol
from acsys.dpm.dpm_protocol import (ServiceDiscovery_request, OpenList_request)

_log = logging.getLogger('asyncio')

class DPM():
    def __init__(self, con, node):
        self.desired_node = node
        self.active_node = None
        self.list_id = None
        self.con = con

    async def _connect(self):
        print('_connect()')
        pass

    async def _shutdown(self):
        print('_shutdown()')
        pass

class DPMContext():
    def __init__(self, con, *, dpm_node=None):
        self.dpm = DPM(con, dpm_node)

    async def __aenter__(self):
        _log.debug('entering DPM context')
        await self.dpm._connect()
        return self.dpm

    async def __aexit__(self, exc_type, exc, tb):
        _log.debug('exiting DPM context')
        await self.dpm._shutdown()
        return False
