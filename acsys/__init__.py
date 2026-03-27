"""This module provides access to the ACSys Control System via the
GraphQL API, allowing Python scripts to communicate with ACSys
services and use ACSys resources.

To use this library, your main function should be marked `async` and
take a single parameter which will be the ACSys Connection object.
Your function should get passed to `acsys.run_client()`.

This library writes to the 'acsys' logger. Your script can configure
the logger as it sees fit.

NOTE: Due to security concerns, you cannot access the control system
offsite unless you use Fermi's VPN.

NOTE: When developing scripts, you may find it useful to put the async
scheduler in "debug mode". How to do it and what it does is described
here:

    https://docs.python.org/3/library/asyncio-dev.html#asyncio-debug-mode


EXAMPLE #1: Specifying your script's starting function.

This simple example displays the ACSys handle that is assigned to the
script when it connects to ACSys. It shows how to register a starting
function and shows how it receives a Connection object you can use.

    import acsys

    async def main(con):
        print(f'assigned handle: {con.handle}')

    acsys.run_client(main)

Your function can create as many asynchronous tasks as it wants.
However, when the primary function returns, all other tasks will be
stopped and your script will continue execution after the
`acsys.run_client()` call.

The Connection object is used to configure access to the ACSys
GraphQL API. Most Python libraries will take this object and wrap an
API around it when supporting a popular ACSys service (e.g. DPM.)

A custom GraphQL endpoint URL may be supplied via the ``ACSYS_URL``
environment variable, or by passing ``url=`` to ``Connection.create()``.

To enable authenticated requests (e.g. device settings), set a Bearer
token on the connection::

    con.token = '<your-bearer-token>'

"""

import asyncio
import logging
import os
import acsys.status as status


from importlib import metadata


__version__ = metadata.version('acsys')
__all__ = [
    '__version__',
    'Connection',
]

import nest_asyncio
nest_asyncio.apply()

_log = logging.getLogger(__name__)

_DEFAULT_URL = os.environ.get('ACSYS_URL', 'https://acsys-proxy.fnal.gov:8000')


class Connection:
    """Manages the connection to the ACSys control system via the GraphQL API.

This object holds the GraphQL endpoint URL and an optional Bearer token
for authenticated requests.  Scripts should receive a properly created
instance via `acsys.run_client()` rather than constructing one directly.

A custom endpoint may be supplied through the ``ACSYS_URL`` environment
variable or via the ``url`` parameter to `Connection.create()`.

To enable authenticated requests (e.g. device settings), set the
``token`` attribute before calling :meth:`~acsys.dpm.DPM.enable_settings`::

    con.token = '<your-bearer-token>'

    """

    def __init__(self, url=None, token=None):
        """Constructor.

Creates a Connection object pointing at the given GraphQL endpoint.
Scripts should not call this directly; use `acsys.run_client()` instead.

        """
        self.url = (url or _DEFAULT_URL).rstrip('/')
        self._token = token
        self.handle = 'graphql'

    @property
    def token(self):
        """Optional Bearer token sent with every authenticated request."""
        return self._token

    @token.setter
    def token(self, value):
        self._token = value

    @property
    def ws_url(self):
        """WebSocket base URL derived from the HTTP URL."""
        return (self.url
                .replace('https://', 'wss://')
                .replace('http://', 'ws://'))

    @staticmethod
    async def create(url=None):
        """Create and return a Connection object.

        The URL may be overridden by the ``ACSYS_URL`` environment variable
        or by passing a ``url`` keyword argument.
        """
        _log.info('using GraphQL endpoint: %s',
                  url or _DEFAULT_URL)
        return Connection(url)


async def __client_main(main, **kwargs):
    con = await Connection.create()
    try:
        result = (await main(con, **kwargs))
    finally:
        del con

    return result


def run_client(main, **kwargs):
    """Starts an asynchronous session for ACSys clients.

This function starts up an ACSys session. The parameter, `main`, is
an async function with the signature:

    async def main(con, **kwargs):

This function will be passed `con` -- a fully initialized `Connection`
object. It will also get passed `kwargs`.

When 'main()' resolves, `run_client()` will return the value returned
by `main()`.

    """
    loop = asyncio.get_event_loop()
    client_fut = asyncio.Task(__client_main(main, **kwargs))
    try:
        return loop.run_until_complete(client_fut)
    except:
        client_fut.cancel()
        try:
            return loop.run_until_complete(client_fut)
        except:
            pass
        raise
