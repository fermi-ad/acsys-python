import acsys.dpm.dpm_protocol

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
        print('entering DPM context')
        await self.dpm._connect()
        return self.dpm

    async def __aexit__(self, exc_type, exc, tb):
        print('exiting DPM context')
        await self.dpm._shutdown()
        return False
