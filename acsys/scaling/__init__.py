import logging
import acsys.status
from acsys.scaling.scaling_protocol import (ServiceDiscovery_request,
                                            Scale_request)

_log = logging.getLogger(__name__)


async def find_service(con, node=None):
    """Use Service Discovery to find an available SCALE service.
    """

    task = f'SCALE@{node or "MCAST"}'
    msg = ServiceDiscovery_request()
    try:
        replier, _ = await con.request_reply(
            task, msg, timeout=150, proto=acsys.scaling.scaling_protocol)
        node = await con.get_name(replier)
        _log.debug('found SCALE service at node %s', node)
        return node
    except acsys.status.AcnetRequestTimeOutQueuedAtDestination:
        raise acsys.status.AcnetNoSuchRequestOrReply()
    except acsys.status.AcnetUserGeneratedNetworkTimeout:
        return None
    except acsys.status.Status:
        raise


async def convert_data(con, drf, data, node=None):
    """Returns converted data.

'con' is an acsys.Connection object. 'drf' is the DRF request that
describes what conversion is desired. If the DRF string contains
".RAW", it is assumed 'data' is an array of floating point values
which will be unscaled into a binary buffer. If the DRF string
specifies a scaled request, then 'data' is assumed to be a binary
buffer that needs to be scaled.

The scaling service will use the length fields in the database to
determine how the binary data is formatted.

The return value is an array of floats, if scaling from a binary
buffer, or a binary buffer, if unscaling a list of floats..

If no SCALE services are found, this function raises
`acsys.status.ACNET_NO_NODE`. A slow SCALE service could also result
in `acsys.status.ACNET_UTIME` being raised.

    """

    # Verify parameters.

    assert isinstance(con, acsys.Connection)
    assert isinstance(drf, str)
    assert isinstance(data, (bytes, bytearray, list, float, int))

    # Build request.

    msg = Scale_request()
    msg.drf_request = drf

    if isinstance(data, (float, int)):
        data = [float(data)]

    if isinstance(data, list):
        _log.debug('converting %s scaled data, %s, to unscaled', drf, data)
        msg.scaled = data
    else:
        _log.debug('converting %s unscaled data, %s, to scaled', drf, data)
        msg.raw = data

    if node is None:
        node = await find_service(con)
        if node is None:
            raise acsys.status.AcnetNoSuchLogicalNode()

    _, reply = await con.request_reply(f'SCALE@{node}', msg, timeout=1000,
                                       proto=acsys.scaling.scaling_protocol)

    status = acsys.status.Status.create(reply.status)

    if status.is_success:
        if hasattr(reply, 'raw'):
            return reply.raw

        return reply.scaled

    raise status
