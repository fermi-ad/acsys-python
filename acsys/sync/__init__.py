import datetime
import asyncio
import logging
import acsys.status
from acsys.sync.syncd_protocol import (Clock_Tclk, Discover_request,
                                       Register_request, Report_reply)

_log = logging.getLogger(__name__)


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
        return f'<TCLK event:{hex(self.event)}, stamp:{self.stamp}>'


class StateEvent:
    """Simple class that holds state event information."""

    def __init__(self, stamp, device_index, value):
        self._stamp = stamp
        self._device_index = device_index
        self._value = value

    @property
    def stamp(self):
        """Returns the timestamp of the state event."""
        return self._stamp

    @property
    def device_index(self):
        """Returns the device index assicated with the state event."""
        return self._device_index

    @property
    def value(self):
        """Returns the state device value that caused the event to fire."""
        return self._value

    def __str__(self):
        return f'<STATE device_index:{self.device_index}, value:{self.value}, stamp:{self.stamp}>'


async def find_service(con, clock=Clock_Tclk, node=None):
    """Use Service Discovery to find an available SYNCD service.

    """

    task = f'SYNC@{node or "MCAST"}'
    msg = Discover_request()
    msg.clock = clock
    try:
        replier, _ = await con.request_reply(task, msg, timeout=150,
                                             proto=acsys.sync.syncd_protocol)
        return await con.get_name(replier)
    except acsys.status.AcnetUserGeneratedNetworkTimeout:
        return None


async def get_available(con, clock=Clock_Tclk):
    """Find active SYNCD services.

Returns a list containing ACNET nodes tha support the SYNC service. If
no nodes are found, an empty list is returned.

    """
    result = []
    msg = Discover_request()
    msg.clock = clock
    gen = con.request_stream(
        'SYNC@MCAST', msg, proto=acsys.sync.syncd_protocol, timeout=150)
    try:
        async for replier, _ in gen:
            result.append(await con.get_name(replier))
    except acsys.status.AcnetUserGeneratedNetworkTimeout:
        return result
    except acsys.status.Status as exception:
        raise
    


async def get_events(con, ev_str, sync_node=None, clock=Clock_Tclk):
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

    msg = Register_request()
    msg.evTclk = ev_str

    while True:
        if sync_node is None:
            node = await find_service(con, clock=clock, node=sync_node)
            if node is None:
                raise acsys.status.AcnetNoSuchLogicalNode()
        else:
            node = sync_node

        _log.info('using SYNC service on %s', node)

        try:
            utc_timezone = datetime.timezone.utc
            gen = con.request_stream(f'SYNC@{node}', msg, proto=acsys.sync.syncd_protocol)
            async for _, reply in gen:
                assert isinstance(reply, Report_reply)

                for event in reply.events:
                    delta = datetime.timedelta(milliseconds=event.stamp)
                    stamp = datetime.datetime(1970, 1, 1, tzinfo=utc_timezone) + delta

                    if hasattr(event, 'state'):
                        yield StateEvent(stamp, event.state.device_index,
                                         event.state.value)
                    else:
                        yield ClockEvent(stamp, event.clock.event, event.clock.number)
        except acsys.status.AcnetReplyTaskDisconnected:
            raise
        except acsys.status.Status as exception:
            _log.warning('lost connection with SYNC service')
            await asyncio.sleep(0.5)
