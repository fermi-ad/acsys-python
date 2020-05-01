import logging
import acsys.dpm.dpm_protocol
from acsys.dpm.dpm_protocol import (ServiceDiscovery_request, OpenList_request)

_log = logging.getLogger('asyncio')

class DPM():
    def __init__(self, con, node):
        self.desired_node = node or 'MCAST'
        self.dpm_task = None
        self.list_id = None
        self.con = con
        self.gen = None

    async def _find_dpm(self):
        task = 'DPMD@' + self.desired_node
        msg = ServiceDiscovery_request()
        try:
            replier, _, _ = await self.con.request_reply(task, msg,
                                                         proto=dpm_protocol)
            self.dpm_task = 'DPMD@' + (await self.con.get_name(replier))
            _log.info('using DPM task: %s', self.dpm_task)
        except:
            self.dpm_task = None
            raise

    async def _connect(self):
        await self._find_dpm()

        # Send an OPEN LIST request to the DPM.

        gen = self.con.request_stream(self.dpm_task, OpenList_request(),
                                      proto=dpm_protocol)
        _, _, msg = await gen.asend(None)
        _log.info('DPM returned list id %d', msg.list_id)

        # Update object state.

        self.gen = gen
        self.list_id = msg.list_id

    async def _shutdown(self):
        await self.gen.aclose()

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
