"""ACSys Python client library.

This module provides two complementary APIs for accessing the Fermilab
ACSys control system via its GraphQL endpoint:

**Simple / procedural (recommended for most scripts)**::

    import acsys

    # Read a single value (blocks until data arrives)
    reading = acsys.read('Z:BTE200MUON4')
    print(reading.value, reading.timestamp)

    # Stream readings (synchronous generator)
    for reading in acsys.subscribe('Z:BTE200MUON4@P,1S'):
        print(reading.value)

    # Apply a setting (requires authentication)
    acsys.configure(token='<bearer-token>')
    acsys.set_device('Z:BTE200MUON4.SETTING', 42.0)

**Object-oriented**::

    from acsys import Device

    d = Device('Z:BTE200MUON4')
    reading = d.read()
    d.set(42.0)

    for reading in d.subscribe('@P,1S'):
        print(reading.value)

**Authentication**

Set the bearer token via the ``ACSYS_TOKEN`` environment variable or by
calling :func:`configure`::

    acsys.configure(token='<bearer-token>')

For interactive scripts, obtain a token via the browser::

    import acsys.auth
    acsys.auth.login()           # headed: opens system browser
    acsys.auth.login_device_code()  # headless: prints URL for operator

**Endpoint configuration**

The default endpoint is ``https://acsys-proxy.fnal.gov:8000``.  Override it
via the ``ACSYS_URL`` environment variable or by calling :func:`configure`::

    acsys.configure(url='https://my-server:8000')

**Async API**

All operations have async counterparts suitable for integration with
``asyncio``::

    reading = await acsys.aread('Z:BTE200MUON4')

    async for reading in acsys.asubscribe('Z:BTE200MUON4@P,1S'):
        print(reading.value)

**Legacy API (deprecated)**

The :func:`run_client` / :class:`~acsys.dpm.DPMContext` pattern from the
previous version is still supported but deprecated.  Migrate to the new API
above.
"""

from __future__ import annotations

import asyncio
import datetime
import logging
import os
import warnings
from typing import Any, Iterator, Optional, AsyncIterator

from importlib import metadata

import nest_asyncio
nest_asyncio.apply()

import acsys.status as status
from acsys.exceptions import (          # re-export for user convenience
    AcsysError,
    AcsysConfigurationError,
    AcsysAuthError,
    AcsysNetworkError,
    AcsysAPIError,
    AcsysStreamError,
    AcsysTimeoutError,
)
from acsys.reading import Reading

__version__ = metadata.version('acsys')
__all__ = [
    '__version__',
    # New API
    'configure',
    'read',
    'set_device',
    'subscribe',
    'aread',
    'aset_device',
    'asubscribe',
    'Device',
    'Reading',
    # Exceptions
    'AcsysError',
    'AcsysConfigurationError',
    'AcsysAuthError',
    'AcsysNetworkError',
    'AcsysAPIError',
    'AcsysStreamError',
    'AcsysTimeoutError',
    # Legacy (deprecated)
    'Connection',
    'run_client',
]

_log = logging.getLogger(__name__)

_DEFAULT_URL = os.environ.get('ACSYS_URL', 'https://acsys-proxy.fnal.gov:8000')

# ---------------------------------------------------------------------------
# Global configuration
# ---------------------------------------------------------------------------

#: Module-level URL and token; updated by :func:`configure`.
_global_url: str = _DEFAULT_URL
_global_token: Optional[str] = os.environ.get('ACSYS_TOKEN')


def configure(
    url: Optional[str] = None,
    token: Optional[str] = None,
) -> None:
    """Configure the global ACSys client.

    Parameters
    ----------
    url : str, optional
        GraphQL endpoint base URL (e.g. ``https://acsys-proxy.fnal.gov:8000``).
        Falls back to the ``ACSYS_URL`` environment variable if not supplied.
    token : str, optional
        JWT bearer token used for authenticated requests (e.g. settings).
        Falls back to the ``ACSYS_TOKEN`` environment variable if not
        supplied.

    Examples
    --------
    ::

        acsys.configure(token='eyJ...')  # supply token, keep default URL
        acsys.configure(url='https://my-server:8000', token='eyJ...')
    """
    global _global_url, _global_token
    if url is not None:
        _global_url = url.rstrip('/')
    if token is not None:
        _global_token = token


def _get_url() -> str:
    return _global_url.rstrip('/')


def _get_token() -> Optional[str]:
    # Always re-read the env var so that acsys.auth.set_token() is picked up.
    return _global_token or os.environ.get('ACSYS_TOKEN')


def _ws_url(http_url: str) -> str:
    return (http_url
            .replace('https://', 'wss://')
            .replace('http://', 'ws://'))


def _run_sync(coro) -> Any:
    """Run *coro* synchronously, compatible with Jupyter notebooks."""
    loop = asyncio.get_event_loop()
    return loop.run_until_complete(coro)


# ---------------------------------------------------------------------------
# Internal async helpers
# ---------------------------------------------------------------------------


async def _async_read(drf: str) -> Reading:
    """Async implementation of a single device read."""
    from acsys import _graphql as gql

    url = _get_url()
    token = _get_token()
    replies = await gql.http_query(url, token, [drf])
    if not replies:
        raise AcsysAPIError(f'No data returned for {drf!r}')
    reply = replies[0]
    if not reply.get('data'):
        raise AcsysAPIError(f'Empty data for {drf!r}')
    data_info = reply['data'][0]
    value = gql.extract_value(data_info['result'])
    ts = datetime.datetime.fromtimestamp(
        data_info['timestamp'], tz=datetime.timezone.utc)
    return Reading(drf, value, ts)


async def _async_set(drf: str, value: Any) -> None:
    """Async implementation of a single device setting."""
    from acsys import _graphql as gql

    url = _get_url()
    token = _get_token()
    if not token:
        raise AcsysAuthError(
            'A bearer token is required for device settings.  '
            'Call acsys.configure(token=...) or set ACSYS_TOKEN.')
    await gql.http_set_device(url, token, drf, value)


async def _async_subscribe_gen(
    drf: str,
    count: Optional[int],
    start_time: Optional[float],
    end_time: Optional[float],
):
    """Async generator yielding Readings from a WS subscription."""
    from acsys import _graphql as gql

    url = _get_url()
    token = _get_token()
    n = 0
    async for reply in gql.ws_subscribe(
        _ws_url(url), token, [drf],
        start_time=start_time, end_time=end_time,
    ):
        for data_info in reply['data']:
            value = gql.extract_value(data_info['result'])
            ts = datetime.datetime.fromtimestamp(
                data_info['timestamp'], tz=datetime.timezone.utc)
            yield Reading(drf, value, ts)
            n += 1
            if count is not None and n >= count:
                return


# ---------------------------------------------------------------------------
# Public simple (synchronous) API
# ---------------------------------------------------------------------------


def read(drf: str) -> Reading:
    """Read a single value from a device.

    Blocks until the control system returns a reply.  This is the simplest
    way to retrieve a device value::

        reading = acsys.read('Z:BTE200MUON4')
        print(reading.value)

    Parameters
    ----------
    drf : str
        A DRF2 device-request string, e.g. ``'Z:BTE200MUON4'`` or
        ``'Z:BTE200MUON4.SETTING'``.

    Returns
    -------
    Reading
        The device reading with ``value`` and ``timestamp`` fields.

    Raises
    ------
    AcsysNetworkError
        If the server cannot be reached.
    AcsysAPIError
        If the GraphQL API returns an error.
    """
    return _run_sync(_async_read(drf))


def set_device(drf: str, value: Any) -> None:
    """Set a device value (requires a bearer token).

    Configure authentication first::

        acsys.configure(token='eyJ...')
        acsys.set_device('Z:BTE200MUON4.SETTING', 42.0)

    Parameters
    ----------
    drf : str
        DRF2 string for the device property to set (e.g.
        ``'Z:BTE200MUON4.SETTING'`` or ``'Z:BTE200MUON4.CONTROL'``).
    value :
        The value to apply.  Accepted types: ``float``, ``int``,
        ``list[float]``, ``str``, ``list[str]``, ``bytes``.

    Raises
    ------
    AcsysAuthError
        If no bearer token is configured.
    AcsysNetworkError
        If the server cannot be reached.
    AcsysAPIError
        If the GraphQL API returns an error or a fatal ACNET status.
    """
    _run_sync(_async_set(drf, value))


def subscribe(
    drf: str,
    *,
    count: Optional[int] = None,
    start_time: Optional[datetime.datetime] = None,
    end_time: Optional[datetime.datetime] = None,
) -> Iterator[Reading]:
    """Subscribe to a stream of device readings.

    Returns a synchronous generator that yields :class:`Reading` objects::

        for reading in acsys.subscribe('Z:BTE200MUON4@P,1S'):
            print(reading.value)

    Parameters
    ----------
    drf : str
        DRF2 device-request string including an event specifier
        (e.g. ``'Z:BTE200MUON4@P,1S'`` for 1-second periodic).
    count : int, optional
        Stop after yielding *count* readings.
    start_time : datetime.datetime, optional
        Request historical data starting at this UTC timestamp.
    end_time : datetime.datetime, optional
        Request historical data up to this UTC timestamp.

    Yields
    ------
    Reading
        Device readings as they arrive.

    Raises
    ------
    AcsysNetworkError
        If the server cannot be reached.
    AcsysStreamError
        If the subscription returns an error.
    """
    st = start_time.timestamp() if start_time is not None else None
    et = end_time.timestamp() if end_time is not None else None

    gen = _async_subscribe_gen(drf, count=count, start_time=st, end_time=et)
    loop = asyncio.get_event_loop()
    while True:
        try:
            yield loop.run_until_complete(gen.__anext__())
        except StopAsyncIteration:
            break


# ---------------------------------------------------------------------------
# Public async API
# ---------------------------------------------------------------------------


async def aread(drf: str) -> Reading:
    """Async version of :func:`read`.

    For use inside an ``async`` function or Jupyter cell::

        reading = await acsys.aread('Z:BTE200MUON4')
    """
    return await _async_read(drf)


async def aset_device(drf: str, value: Any) -> None:
    """Async version of :func:`set_device`.

    ::

        await acsys.aset_device('Z:BTE200MUON4.SETTING', 42.0)
    """
    await _async_set(drf, value)


async def asubscribe(
    drf: str,
    *,
    count: Optional[int] = None,
    start_time: Optional[datetime.datetime] = None,
    end_time: Optional[datetime.datetime] = None,
) -> AsyncIterator[Reading]:
    """Async version of :func:`subscribe`.

    ::

        async for reading in acsys.asubscribe('Z:BTE200MUON4@P,1S'):
            print(reading.value)
    """
    st = start_time.timestamp() if start_time is not None else None
    et = end_time.timestamp() if end_time is not None else None
    async for reading in _async_subscribe_gen(
        drf, count=count, start_time=st, end_time=et
    ):
        yield reading


# ---------------------------------------------------------------------------
# Object-oriented Device interface
# ---------------------------------------------------------------------------


class Device:
    """Object-oriented interface to a single ACSys device.

    Wraps a DRF2 device string and exposes ``read``, ``set``, and
    ``subscribe`` methods::

        d = acsys.Device('Z:BTE200MUON4')
        reading = d.read()
        d.set(42.0)

        for r in d.subscribe('@P,1S'):
            print(r.value)

    Parameters
    ----------
    drf : str
        The device name or DRF2 string (e.g. ``'Z:BTE200MUON4'``).
        A property or event specifier may be included (e.g.
        ``'Z:BTE200MUON4.RAW'``).  When calling :meth:`subscribe`, the
        event specifier may be passed there instead.
    """

    def __init__(self, drf: str) -> None:
        self._drf = drf

    # -- properties -----------------------------------------------------------

    @property
    def drf(self) -> str:
        """The DRF2 string for this device."""
        return self._drf

    # -- synchronous interface ------------------------------------------------

    def read(self) -> Reading:
        """Read the current value of this device.

        Returns
        -------
        Reading
        """
        return read(self._drf)

    def set(self, value: Any) -> None:
        """Set this device to *value* (requires authentication).

        Parameters
        ----------
        value :
            See :func:`set_device` for accepted types.
        """
        set_device(self._drf, value)

    def subscribe(
        self,
        event: str = '',
        *,
        count: Optional[int] = None,
        start_time: Optional[datetime.datetime] = None,
        end_time: Optional[datetime.datetime] = None,
    ) -> Iterator[Reading]:
        """Subscribe to a stream of readings for this device.

        Parameters
        ----------
        event : str, optional
            An event specifier to append, e.g. ``'@P,1S'``.  If the
            device DRF already contains an event specifier this parameter
            can be omitted.
        count : int, optional
            Stop after *count* readings.
        start_time, end_time : datetime.datetime, optional
            Historical time range.

        Yields
        ------
        Reading
        """
        drf = self._drf + event
        return subscribe(drf, count=count,
                         start_time=start_time, end_time=end_time)

    # -- async interface ------------------------------------------------------

    async def aread(self) -> Reading:
        """Async version of :meth:`read`."""
        return await _async_read(self._drf)

    async def aset(self, value: Any) -> None:
        """Async version of :meth:`set`."""
        await _async_set(self._drf, value)

    async def asubscribe(
        self,
        event: str = '',
        *,
        count: Optional[int] = None,
        start_time: Optional[datetime.datetime] = None,
        end_time: Optional[datetime.datetime] = None,
    ) -> AsyncIterator[Reading]:
        """Async version of :meth:`subscribe`."""
        drf = self._drf + event
        st = start_time.timestamp() if start_time is not None else None
        et = end_time.timestamp() if end_time is not None else None
        async for reading in _async_subscribe_gen(
            drf, count=count, start_time=st, end_time=et
        ):
            yield reading

    def __repr__(self) -> str:
        return f'Device({self._drf!r})'

    def __str__(self) -> str:
        return self._drf


# ---------------------------------------------------------------------------
# Legacy Connection / run_client  (deprecated)
# ---------------------------------------------------------------------------


class Connection:
    """Manages the connection to the ACSys control system via GraphQL.

    .. deprecated::
        Use the top-level :func:`configure`, :func:`read`,
        :func:`set_device`, and :func:`subscribe` functions instead, or
        the :class:`Device` OOP interface.  The ``Connection`` class and
        :func:`run_client` will be removed in a future version.
    """

    def __init__(self, url: Optional[str] = None,
                 token: Optional[str] = None) -> None:
        self.url = (url or _DEFAULT_URL).rstrip('/')
        self._token = token
        self.handle = 'graphql'

    @property
    def token(self) -> Optional[str]:
        """Optional bearer token for authenticated requests."""
        return self._token

    @token.setter
    def token(self, value: Optional[str]) -> None:
        self._token = value

    @property
    def ws_url(self) -> str:
        """WebSocket base URL derived from the HTTP URL."""
        return _ws_url(self.url)

    @staticmethod
    async def create(url: Optional[str] = None) -> 'Connection':
        """Create and return a :class:`Connection` object.

        .. deprecated::
            Use :func:`configure` instead.
        """
        return Connection(url)


def run_client(main, **kwargs):
    """Start an async ACSys session (legacy entry point).

    .. deprecated::
        Use the simpler top-level functions instead::

            reading = acsys.read('Z:BTE200MUON4')

        Or for async code::

            async def main():
                reading = await acsys.aread('Z:BTE200MUON4')

        :func:`run_client` will be removed in a future version.

    Parameters
    ----------
    main : coroutine function
        An ``async def main(con, **kwargs)`` function.  *con* is a
        :class:`Connection` object.

    Returns
    -------
    Any
        The return value of *main*.
    """
    warnings.warn(
        'acsys.run_client() is deprecated. '
        'Use acsys.read(), acsys.subscribe(), or acsys.Device instead.',
        DeprecationWarning,
        stacklevel=2,
    )

    async def _runner():
        con = await Connection.create()
        try:
            return await main(con, **kwargs)
        finally:
            del con

    loop = asyncio.get_event_loop()
    client_fut = asyncio.Task(_runner())
    try:
        return loop.run_until_complete(client_fut)
    except Exception:
        client_fut.cancel()
        try:
            loop.run_until_complete(client_fut)
        except Exception:
            pass
        raise
