import datetime
import asyncio
import json
import logging
import warnings
import acsys.status

_log = logging.getLogger(__name__)


class _ItemCommon:
    """Base class that defines common attributes of ItemData and
ItemStatus."""

    def __init__(self, tag):
        self._tag = tag

    @property
    def tag(self):
        return self._tag

    @property
    def isReading(self):
        """Returns True if this object is an ItemData object."""
        warnings.warn(
            "deprecated in favor of the snake_case version, err_code",
            DeprecationWarning)
        return self.is_reading

    @property
    def is_reading(self):
        """Returns True if this object is an ItemData object."""
        return False

    @property
    def isStatus(self):
        """Returns True if this object is an ItemStatus object."""
        warnings.warn(
            "deprecated in favor of the snake_case version, is_status",
            DeprecationWarning)
        return self.is_status

    @property
    def is_status(self):
        """Returns True if this object is an ItemStatus object."""
        return False

    def isReadingFor(self, *tags):
        """Returns True if this object is an ItemData object and its 'tag'
field matches the parameter 'tag'.

        """
        warnings.warn(
            "deprecated in favor of the snake_case version, is_reading_for",
            DeprecationWarning)
        return self.is_reading_for()

    def is_reading_for(self, *tags):
        """Returns True if this object is an ItemData object and its 'tag'
field matches the parameter 'tag'.

        """
        return False

    def isStatusFor(self, *tags):
        """Returns True if this object is an ItemStatus object and its 'tag'
field matches the parameter 'tag'.

        """
        warnings.warn(
            "deprecated in favor of the snake_case version, is_status_for",
            DeprecationWarning)
        return self.is_status_for()

    def is_status_for(self, *tags):
        """Returns True if this object is an ItemStatus object and its 'tag'
field matches the parameter 'tag'.

        """
        return False


class ItemData(_ItemCommon):
    """An object that holds a reading from a device.

DPM delivers device data using a stream of ItemData objects. The 'tag'
field corresponds to the tag parameter used when the '.add_entry()'
method was used to add the device to the list.

The 'stamp' field is the timestamp when the data occurred.

The 'data' field is the requested data. The data will be of the type
asked in the corresponding DRF2 (specified in the call to the
'.add_entry()' method.) For instance, if .RAW was specified, the
'data' field will contain a bytes(). Otherwise it will contain a
scaled, floating point value (or an array, if it's an array device),
or a dictionary -- in the case of basic status or alarm blocks.

    """

    def __init__(self, tag, stamp, data, micros=None, meta={}):
        super().__init__(tag)
        delta = datetime.timedelta(milliseconds=stamp)
        tz = datetime.timezone.utc

        self._stamp = datetime.datetime(1970, 1, 1, tzinfo=tz) + delta
        self._data = data
        self._meta = meta
        self._micros = micros

    @property
    def stamp(self):
        """The timestamp of when the 'data' was sampled."""
        return self._stamp

    @property
    def data(self):
        """The sampled value of the device. The type of this field depends
upon the device and what scaling was requested. Most readings will be
'floats' but if a raw reading was requested, it'll be returned as a
bytes.

        """
        return self._data

    @property
    def meta(self):
        """Contains a dictionary of extra information about the device.

The 'name' key holds the device name. 'di' contains the device
index. If the device has scaling, a 'units' key will be present and
hold the engineering units of the reading.

        """
        return self._meta

    @property
    def micros(self):
        """Contains a list of microsecond timestamps for each datum in data.

The index of each timestamp corresponds to the same index in 'data'.

        """
        return self._micros

    @property
    def isReading(self):
        warnings.warn(
            "deprecated in favor of the snake_case version, is_reading",
            DeprecationWarning)
        return self.is_reading

    @property
    def is_reading(self):
        return True

    def __str__(self):
        guaranteed_fields = f'{{ tag: {self.tag}, stamp: {self.stamp}, data: {self.data}, meta: {self.meta}'

        if self.micros:
            return f'{guaranteed_fields}, micros: {self.micros}}}'
        return f'{guaranteed_fields}}}'

    def isReadingFor(self, *tags):
        warnings.warn(
            "deprecated in favor of the snake_case version, is_reading_for",
            DeprecationWarning)
        return self.is_reading_for(*tags)

    def is_reading_for(self, *tags):
        return self.tag in tags


class ItemStatus(_ItemCommon):
    """An object reporting status of an item in a DPM list.

If there was an error in a request, this object will be in the stream
instead of a ItemData object. The 'tag' field corresponds to the tag
parameter used in the call to the '.add_entry()' method.

The 'status' field describes the error that occurred with this item.

If this message appears as a result of a reading request, there will
never be an ItemData object for the 'tag' until the error condition is
fixed and the list restarted.

There will always be one of these objects generated to indicate the
result of a setting.

    """

    def __init__(self, tag, status):
        super().__init__(tag)
        self._status = acsys.status.Status(status)

    @property
    def status(self):
        """Indicates the resulting status of the request associated with
'tag'."""
        return self._status

    @property
    def isStatus(self):
        warnings.warn(
            "deprecated in favor of the snake_case version, is_status",
            DeprecationWarning)
        return self.is_status

    @property
    def is_status(self):
        return True

    def __str__(self):
        return f'{{ tag: {self.tag}, status: {self.status} }}'

    def isStatusFor(self, *tags):
        warnings.warn(
            "deprecated in favor of the snake_case version, is_status_for",
            DeprecationWarning)
        return self.is_status_for(*tags)

    def is_status_for(self, *tags):
        return self.tag in tags


async def find_dpm(con, *, node=None):
    """Return None – DPM node discovery is not needed with the GraphQL backend.

This function is kept for backward compatibility.  The GraphQL API
provides a unified endpoint and does not require discovering individual
DPM nodes.

    """
    return None


async def available_dpms(con):
    """Return an empty list – DPM discovery is not needed with the GraphQL backend.

This function is kept for backward compatibility.  The GraphQL API
provides a unified endpoint and does not require discovering individual
DPM nodes.

    """
    return []


# ---------------------------------------------------------------------------
# GraphQL subscription query used by the DPM class.
# ---------------------------------------------------------------------------

_SUBSCRIPTION_QUERY = """
subscription AcceleratorData($drfs: [String!]!) {
  acceleratorData(drfs: $drfs) {
    refId
    data {
      timestamp
      result {
        __typename
        ... on Scalar { scalarValue }
        ... on ScalarArray { scalarArrayValue }
        ... on StatusReply { status }
        ... on Raw { rawValue }
        ... on Text { textValue }
        ... on TextArray { textArrayValue }
      }
    }
  }
}
"""

# GraphQL mutation used when applying settings.
_MUTATION_SET_DEVICE = """
mutation SetDevice($device: String!, $value: DevValue!) {
  _setDevice(device: $device, value: $value) {
    status
  }
}
"""


class DPM:
    """Manages data acquisition from the ACSys control system via GraphQL.

This class replaces the legacy ACNET/DPM protocol with GraphQL
WebSocket subscriptions, while preserving the same public API.

Usage example::

    async with acsys.dpm.DPMContext(con) as dpm:
        await dpm.add_entry(0, 'Z:BTE200MUON4@i')
        await dpm.start()
        async for item in dpm.replies():
            if item.is_reading:
                print(f'{item.tag}: {item.data}')

    """

    def __init__(self, con, node=None):
        self.con = con
        self.meta = {}

        # Public, kept for backward compatibility.
        self.list_id = 0
        self.active = False
        self.can_set = False
        self.model = None

        # Internal state.
        self._dev_list = {}   # tag (int) -> drf (str)
        self._rpy_q = asyncio.Queue()
        self._sub_task = None

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _xlat_graphql(self, tag, data_info):
        """Translate one GraphQL DataInfo dict into an ItemData or ItemStatus."""
        # GraphQL timestamps are seconds since epoch (float).  ItemData
        # expects milliseconds.
        stamp_ms = data_info['timestamp'] * 1000.0
        result = data_info['result']
        typename = result.get('__typename')

        if typename == 'StatusReply':
            return ItemStatus(tag, result['status'])
        if typename == 'Scalar':
            return ItemData(tag, stamp_ms, result['scalarValue'],
                            meta=self.meta.get(tag, {}))
        if typename == 'ScalarArray':
            return ItemData(tag, stamp_ms, result['scalarArrayValue'],
                            meta=self.meta.get(tag, {}))
        if typename == 'Raw':
            return ItemData(tag, stamp_ms, bytes(result['rawValue']),
                            meta=self.meta.get(tag, {}))
        if typename == 'Text':
            return ItemData(tag, stamp_ms, result['textValue'],
                            meta=self.meta.get(tag, {}))
        if typename == 'TextArray':
            return ItemData(tag, stamp_ms, result['textArrayValue'],
                            meta=self.meta.get(tag, {}))
        _log.warning('unknown GraphQL data type: %s', typename)
        return None

    async def _run_subscription(self, drfs, ref_id_to_tag):
        """Long-running task: subscribe via WebSocket and push items into
        the reply queue."""
        import aiohttp

        url = self.con.ws_url + '/acsys/s'
        headers = {}
        if self.con.token:
            headers['Authorization'] = f'Bearer {self.con.token}'

        try:
            async with aiohttp.ClientSession() as session:
                async with session.ws_connect(
                    url,
                    protocols=['graphql-transport-ws'],
                    headers=headers,
                ) as ws:
                    # 1. Initialise the graphql-transport-ws session.
                    await ws.send_str(json.dumps({
                        'type': 'connection_init',
                        'payload': {}
                    }))

                    msg_raw = await ws.receive()
                    if msg_raw.type != aiohttp.WSMsgType.TEXT:
                        raise ConnectionError(
                            f'unexpected WebSocket message type: {msg_raw.type}')
                    msg = json.loads(msg_raw.data)
                    if msg.get('type') != 'connection_ack':
                        raise ConnectionError(
                            f'expected connection_ack, got {msg.get("type")!r}')

                    # 2. Subscribe to acceleratorData.
                    await ws.send_str(json.dumps({
                        'type': 'subscribe',
                        'id': '1',
                        'payload': {
                            'query': _SUBSCRIPTION_QUERY,
                            'variables': {'drfs': drfs}
                        }
                    }))

                    # 3. Receive a continuous stream of data.
                    while True:
                        msg_raw = await ws.receive()

                        if msg_raw.type == aiohttp.WSMsgType.TEXT:
                            msg = json.loads(msg_raw.data)
                            msg_type = msg.get('type')

                            if msg_type == 'next':
                                reply = msg['payload']['data']['acceleratorData']
                                ref_id = reply['refId']
                                tag = ref_id_to_tag.get(ref_id)
                                if tag is not None:
                                    for data_info in reply['data']:
                                        item = self._xlat_graphql(tag, data_info)
                                        if item is not None:
                                            await self._rpy_q.put(item)

                            elif msg_type == 'ping':
                                # Respond to server keep-alive pings.
                                await ws.send_str(json.dumps({'type': 'pong'}))

                            elif msg_type == 'complete':
                                break

                            elif msg_type == 'error':
                                errors = msg.get('payload') or []
                                err_msg = (errors[0].get('message', 'subscription error')
                                           if errors else 'subscription error')
                                raise RuntimeError(err_msg)

                        elif msg_raw.type in (
                            aiohttp.WSMsgType.CLOSE,
                            aiohttp.WSMsgType.CLOSING,
                            aiohttp.WSMsgType.CLOSED,
                            aiohttp.WSMsgType.ERROR,
                        ):
                            break

        except asyncio.CancelledError:
            raise
        except Exception as e:
            _log.error('DPM subscription error: %s', e, exc_info=True)
            await self._rpy_q.put(e)
        finally:
            # Signal end-of-stream.
            await self._rpy_q.put(None)

    async def _stop_subscription(self):
        """Cancel the running subscription task and wait for it to finish."""
        if self._sub_task is not None and not self._sub_task.done():
            self._sub_task.cancel()
            try:
                await self._sub_task
            except (asyncio.CancelledError, Exception):
                pass
            self._sub_task = None

    def _drain_queue(self):
        """Discard any queued items (called when restarting acquisition)."""
        while not self._rpy_q.empty():
            try:
                self._rpy_q.get_nowait()
            except asyncio.QueueEmpty:
                break

    # ------------------------------------------------------------------
    # Public API – iteration
    # ------------------------------------------------------------------

    def __aiter__(self):
        return self

    async def __anext__(self):
        """Return the next reply, or raise StopAsyncIteration at end of stream."""
        item = await self._rpy_q.get()
        if item is None:
            raise StopAsyncIteration
        if isinstance(item, BaseException):
            raise item
        return item

    async def replies(self, tmo=None):
        """Return an async generator that yields each reply from DPM.

The optional *tmo* parameter is the maximum number of seconds to wait
between replies before raising :exc:`asyncio.TimeoutError`.

        """
        while True:
            try:
                ii = await asyncio.wait_for(self.__anext__(), tmo)
            except StopAsyncIteration:
                return
            if ii is None:
                return
            yield ii

    # ------------------------------------------------------------------
    # Public API – list management
    # ------------------------------------------------------------------

    def get_entry(self, tag):
        """Return the DRF string associated with *tag*, or ``None``."""
        return self._dev_list.get(tag)

    async def clear_list(self):
        """Remove all entries from the device list.

Clearing the list does not stop incoming replies.  After clearing,
call :meth:`start` or :meth:`stop`.

        """
        _log.debug('clearing device list')
        self._dev_list = {}

    async def add_entry(self, tag, drf):
        """Add a device to the acquisition list.

*tag* is a user-supplied integer that identifies this device in
subsequent :class:`ItemData` and :class:`ItemStatus` objects.
*drf* is a DRF2 string describing the device and how it should be
read (e.g. ``'Z:BTE200MUON4@i'``).

Changes take effect the next time :meth:`start` is called.

        """
        if not isinstance(tag, int):
            raise ValueError(f'tag must be an integer -- found {tag!r}')
        if not isinstance(drf, str):
            raise ValueError(f'drf must be a string -- found {drf!r}')
        _log.debug('adding tag:%d, drf:%s', tag, drf)
        self._dev_list[tag] = drf

    async def add_entries(self, entries):
        """Add multiple ``(tag, drf)`` pairs to the acquisition list.

This is a convenience wrapper around :meth:`add_entry`.  Changes take
effect the next time :meth:`start` is called.

        """
        for tag, drf in entries:
            if not isinstance(tag, int):
                raise ValueError(f'tag must be an integer -- found {tag!r}')
            if not isinstance(drf, str):
                raise ValueError(f'drf must be a string -- found {drf!r}')
        for tag, drf in entries:
            self._dev_list[tag] = drf

    async def remove_entry(self, tag):
        """Remove a device from the acquisition list.

*tag* must be an integer; a :exc:`ValueError` is raised otherwise.
Data associated with the removed tag continues to be delivered until
:meth:`start` is called.

        """
        if not isinstance(tag, int):
            raise ValueError('tag must be an integer')
        _log.debug('removing tag:%d', tag)
        del self._dev_list[tag]

    # ------------------------------------------------------------------
    # Public API – acquisition control
    # ------------------------------------------------------------------

    async def start(self, model=None):
        """Start (or restart) data acquisition with the current device list.

Any previously running subscription is stopped first.  The *model*
parameter is accepted for backward compatibility but is ignored.

        """
        self.model = model

        await self._stop_subscription()
        self._drain_queue()

        if not self._dev_list:
            _log.debug('no devices in list; not starting subscription')
            return

        # Build a stable ordering: sort by tag so that ref_id 0 always
        # corresponds to the smallest tag, etc.
        tags = sorted(self._dev_list.keys())
        drfs = [self._dev_list[tag] for tag in tags]
        ref_id_to_tag = {i: tag for i, tag in enumerate(tags)}

        _log.debug('starting GraphQL subscription for %d device(s)', len(drfs))
        self._sub_task = asyncio.create_task(
            self._run_subscription(drfs, ref_id_to_tag)
        )
        self.active = True

    async def stop(self):
        """Stop data acquisition.

The device list is preserved; call :meth:`start` to resume.

        """
        _log.debug('stopping DPM')
        await self._stop_subscription()
        self.active = False

    async def _restore_state(self):
        """Restart acquisition if the DPM was previously active."""
        if self.active and self._dev_list:
            await self.start(self.model)

    async def _shutdown(self):
        """Shut down the DPM completely."""
        await self.stop()

    # ------------------------------------------------------------------
    # Public API – settings
    # ------------------------------------------------------------------

    async def enable_settings(self, role=None):
        """Enable device settings for this DPM session.

With the GraphQL backend, authenticated settings require a Bearer token.
Set ``con.token = '<your-bearer-token>'`` on the :class:`~acsys.Connection`
object **before** calling this method.

The *role* parameter is accepted for backward compatibility.

        """
        if self.con.token:
            self.can_set = True
            _log.info('DPM settings enabled via Bearer token')
        else:
            warnings.warn(
                'No Bearer token found on the Connection object. '
                'Set con.token before calling enable_settings(). '
                'Settings will not be available.',
                UserWarning,
                stacklevel=2,
            )
            self.can_set = False

    @staticmethod
    def _build_dev_value(value):
        """Convert a Python value into a GraphQL DevValue input dict."""
        if isinstance(value, (bytearray, bytes)):
            return {'rawVal': list(value)}
        if isinstance(value, str):
            return {'textVal': value}
        if isinstance(value, list):
            if value and isinstance(value[0], str):
                return {'textArrayVal': value}
            return {'scalarArrayVal': [float(v) for v in value]}
        return {'scalarVal': float(value)}

    async def apply_settings(self, input_array):
        """Apply settings to one or more devices.

*input_array* is a list of ``(tag, value)`` tuples.  *tag* must be an
integer that was previously registered via :meth:`add_entry`.

Requires :meth:`enable_settings` to have been called successfully.

        """
        import aiohttp

        if not self.can_set:
            raise RuntimeError('settings are disabled')

        if not isinstance(input_array, list):
            input_array = [input_array]

        url = self.con.url + '/acsys'
        headers = {
            'Content-Type': 'application/json',
        }
        if self.con.token:
            headers['Authorization'] = f'Bearer {self.con.token}'

        async with aiohttp.ClientSession() as session:
            for ref_id, value in input_array:
                drf = self._dev_list.get(ref_id)
                if drf is None:
                    raise ValueError(
                        f'setting for undefined ref_id, {ref_id}')

                dev_value = self._build_dev_value(value)
                payload = {
                    'query': _MUTATION_SET_DEVICE,
                    'variables': {
                        'device': drf,
                        'value': dev_value,
                    }
                }

                async with session.post(
                    url, json=payload, headers=headers
                ) as resp:
                    resp.raise_for_status()
                    result = await resp.json()

                if 'errors' in result:
                    err = result['errors'][0].get('message', 'unknown error')
                    raise RuntimeError(f'GraphQL error: {err}')

                data = result.get('data', {})
                set_result = data.get('_setDevice')
                if set_result is None:
                    _log.warning(
                        'apply_settings: _setDevice returned no result for %s',
                        drf)
                else:
                    sts = acsys.status.Status(set_result['status'])
                    if sts.is_fatal:
                        raise sts


class DPMContext:
    """Creates a communication context with DPM.

This context should be used in an ``async with`` statement so that
resources are properly released when the block is exited::

    async with DPMContext(con) as dpm:
        await dpm.add_entry(0, 'Z:BTE200MUON4@i')
        await dpm.start()
        async for item in dpm.replies():
            ...

    """

    def __init__(self, con, *, dpm_node=None):
        self.dpm = DPM(con, dpm_node)

    async def __aenter__(self):
        _log.debug('entering DPM context')
        return self.dpm

    async def __aexit__(self, exc_type, exc, tb):
        _log.debug('exiting DPM context')
        await self.dpm._shutdown()
        return False


