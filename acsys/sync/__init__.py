import datetime
import asyncio
import logging
import acsys.sync.syncd_protocol

_log = logging.getLogger('acsys')

class ClockEvent:
    """Simple class that holds clock event information."""

    def __init__(self, stamp, event, number):
        self._stamp = stamp
        self._event = event
        self._number = number

    @property
    def stamp(self):
        """Returns the timestamp of the clock event."""
        return self._stamp

    @property
    def event(self):
        """Returns the event number."""
        return self._event

    @property
    def number(self):
        """Returns the instance number of the event."""
        return self._number

    def __str__(self):
        return f'<TCLK event:{self.event}, stamp:{self.stamp}>'

class StateEvent:
    """Simple class that holds state event information."""

    def __init__(self, stamp, di, value):
        self._stamp = stamp
        self._di = di
        self._value = value

    @property
    def stamp(self):
        """Returns the timestamp of the state event."""
        return self._stamp

    @property
    def di(self):
        """Returns the device index assicated with the state event."""
        return self._di

    @property
    def value(self):
        """Returns the state device value that caused the event to fire."""
        return self._value

    def __str__(self):
        return f'<STATE di:{self.di}, value:{self.value}, stamp:{self.stamp}>'

async def find_service(con, node=None):
    """Use Service Discovery to find an available SYNCD service.

    """

    task = 'SYNC@' + (node or 'MCAST')
    msg = syncd_protocol.Discover_request()
    try:
        replier, _ = await con.request_reply(task, msg, timeout=150,
                                             proto=syncd_protocol)
        return (await con.get_name(replier))
    except acsys.status.Status as e:
        if e != acsys.status.ACNET_UTIME:
            raise
        else:
            return None

async def get_available(con):
    """Find active SYNCD services.

Returns a list containing ACNET nodes tha support the SYNC service. If
no nodes are found, an empty list is returned.

    """
    result = []
    msg = syncd_protocol.Discover_request()
    gen = con.request_stream('SYNC@MCAST', msg, proto=syncd_protocol,
                             timeout=150)
    try:
        async for replier, _ in gen:
            result.append(await con.get_name(replier))
    except acsys.status.Status as e:
        if e != acsys.status.ACNET_UTIME:
            raise
    return result

async def get_events(con, ev_str, sync_node=None):
    """Returns an async generator that yields event information.

'con' is an acsys.Connection object. 'ev_str' is a list of
strings. Each string describes an event to monitor, using DRF2 format
for events. 'sync_node', if specified, is a string indicating a
particular ACNET node to use for the SYNC service. If not provided,
one will be chosen.

The generator will yield ClockEvent and StateEvent objects as they
occur.

    """

    # Verify parameters

    assert isinstance(con, acsys.Connection)
    assert isinstance(ev_str, list)
    assert sync_node is None or isinstance(sync_node, str)

    # Build the request message.

    msg = syncd_protocol.Register_request()
    msg.evTclk = ev_str

    while True:
        node = await find_service(con, node=sync_node)

        if node is None:
            raise acsys.status.ACNET_NO_NODE

        _log.info('using SYNC service on %s', node)

        try:
            gen = con.request_stream('SYNC@' + node, msg, proto=syncd_protocol)
            async for _, ii in gen:
                assert isinstance(ii, syncd_protocol.Report_reply)

                for jj in ii.events:
                    delta = datetime.timedelta(seconds=jj.stamp // 1000)
                    tz = datetime.timezone.utc
                    stamp = datetime.datetime(1970, 1, 1, tzinfo=tz) + delta

                    if hasattr(jj, 'state'):
                        yield StateEvent(stamp, jj.state.device_index,
                                         jj.state.value)
                    else:
                        yield ClockEvent(stamp, jj.clock.event, jj.clock.number)
        except acsys.status.Status as e:
            if e == acsys.status.ACNET_DISCONNETED:
                raise
            _log.warning('lost connection with SYNC service')
            await asyncio.sleep(0.5)
