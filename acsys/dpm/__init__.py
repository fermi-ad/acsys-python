import asyncio
import logging
import acsys.dpm.dpm_protocol
from acsys.dpm.dpm_protocol import (ServiceDiscovery_request, OpenList_request,
                                    AddToList_request, RemoveFromList_request,
                                    StartList_request, StopList_request)

_log = logging.getLogger('asyncio')

class DPM():
    def __init__(self, con, node):
        self.desired_node = node or 'MCAST'
        self.dpm_task = None
        self.list_id = None
        self._dev_list_sem = asyncio.Semaphore()
        self._dev_list = {}
        self.con = con
        self.gen = None

    async def __aiter__(self):
        return self.gen

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

    def get_entry(self, tag):
        """Returns the DRF string associated with the 'tag'.
        """
        self._dev_list.get(tag)

    async def add_entry(self, tag, drf):
        """Add an entry to the list of devices to be acquired.

        This updates the list of device requests. The 'tag' parameter
        is used to mark this request's device data. When the script
        starts receiving ItemData objects, it can correlate the data
        using the 'tag' field. The 'tag' must be an integer -- the
        method will raise a ValueError if it's not.

        The 'drf' parameter is a DRF2 string representing the data to
        be read along with the sampling event. If it isn't a string,
        ValueError will be raised.

        If this method is called with a tag that was previously used,
        it replaces the previous request. If data is currently being
        returned, it won't reflect the new entry until the 'start'
        method is called.

        If simultaneous calls are made to this method and all are
        using the same 'tag', which 'drf' string is ultimately
        associated with the tag is non-deterministic.
        """

        # Make sure the tag parameter is an integer and the drf
        # parameter is a string. Otherwise throw a ValueError
        # exception.

        if isinstance(tag, int):
            if isinstance(drf, str):
                # Create the message and set the fields appropriately.

                msg = AddToList_request()

                msg.list_id = self.list_id
                msg.ref_id = tag
                msg.drf_request = drf

                async with self._dev_list_sem:
                    # Perform the request. If the request returns a
                    # fatal error, the status will be raised for
                    # us. If the DPM returns a fatal status in the
                    # reply message, we raise it ourselves.

                    _log.debug('adding tag:%d, drf:%s to list:%d', tag, drf,
                               msg.list_id)
                    _, _, msg = await self.con.request_reply(self.dpm_task, msg,
                                                             proto=dpm_protocol)
                    sts = acsys.status.Status(msg.status)

                    if sts.isFatal:
                        raise sts

                    # DPM has been updated so we can safely add the
                    # entry to our device list.

                    self._dev_list[tag] = drf
            else:
                raise ValueError('drf must be a string')
        else:
            raise ValueError('tag must be an integer')

    async def remove_entry(self, tag):
        """Removes an entry from the list of devices to be acquired.

        This updates the list of device requests. The 'tag' parameter
        is used to specify which request should be removed from the
        list.  The 'tag' must be an integer -- the method will raise a
        ValueError if it's not.

        Data associated with the 'tag' will continue to be returned
        until the '.start()' method is called.
        """

        # Make sure the tag parameter is an integer and the drf
        # parameter is a string. Otherwise throw a ValueError
        # exception.

        if isinstance(tag, int):
            # Create the message and set the fields appropriately.

            msg = RemoveFromList_request()

            msg.list_id = self.list_id
            msg.ref_id = tag

            async with self._dev_list_sem:
                _log.debug('removing tag:%d from list:%d', tag, msg.list_id)
                _, _, msg = await self.con.request_reply(self.dpm_task, msg,
                                                         proto=dpm_protocol)
                sts = acsys.status.Status(msg.status)

                if sts.isFatal:
                    raise sts

                # DPM has been updated so we can safely remove the
                # entry from our device list.

                del self._dev_list[tag]
        else:
            raise ValueError('tag must be an integer')

    async def start(self):
        """Start/restart data acquisition using the current request list.

        Calls to '.add_entry()' and '.remove_entry()' make changes to
        the list of requests but don't actually affect data
        acquisition until this method is called. This allows a script
        to make major adjustments and then enable the changes all at
        once.
        """

        msg = StartList_request()

        msg.list_id = self.list_id

        async with self._dev_list_sem:
            _log.debug('starting list %d', msg.list_id)
            _, _, msg = await self.con.request_reply(self.dpm_task, msg,
                                                     proto=dpm_protocol)
            sts = acsys.status.Status(msg.status)

            if sts.isFatal:
                raise sts

    async def stop(self):
        """Stops data acquisition.

        This method stops data acquisition. The list of requests is
        unaffected so a call to '.start()' will restart the list.

        Due to the asynchronous nature of network communications,
        after calling this method, a few readings may still get
        delivered.
        """

        msg = StopList_request()

        msg.list_id = self.list_id

        async with self._dev_list_sem:
            _log.debug('stopping list %d', msg.list_id)
            _, _, msg = await self.con.request_reply(self.dpm_task, msg,
                                                     proto=dpm_protocol)
            sts = acsys.status.Status(msg.status)

            if sts.isFatal:
                raise sts

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
