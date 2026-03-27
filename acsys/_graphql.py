"""Internal GraphQL transport helpers.

This module is an **implementation detail** of the acsys library.
Public-facing code lives in :mod:`acsys` (top-level API) and
:mod:`acsys.dpm` (legacy DPM interface).
"""

from __future__ import annotations

import json
import logging
from typing import Any, AsyncIterator

from acsys.exceptions import AcsysAPIError, AcsysNetworkError, AcsysStreamError

_log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# GraphQL operations
# ---------------------------------------------------------------------------

#: One-shot read query (HTTP POST to /acsys).
#: The server automatically appends ``@i`` and strips any existing event.
_QUERY_ACCELERATOR_DATA = """
query AcceleratorData($deviceList: [String!]!) {
  acceleratorData(deviceList: $deviceList) {
    refId
    data {
      timestamp
      result {
        __typename
        ... on Scalar      { scalarValue }
        ... on ScalarArray { scalarArrayValue }
        ... on StatusReply { status }
        ... on Raw         { rawValue }
        ... on Text        { textValue }
        ... on TextArray   { textArrayValue }
      }
    }
  }
}
"""

#: Streaming subscription (WebSocket /acsys/s).
_SUBSCRIPTION_ACCELERATOR_DATA = """
subscription AcceleratorData(
  $drfs: [String!]!,
  $startTime: Float,
  $endTime: Float,
  $validateTimestamp: Boolean
) {
  acceleratorData(
    drfs: $drfs,
    startTime: $startTime,
    endTime: $endTime,
    validateTimestamp: $validateTimestamp
  ) {
    refId
    data {
      timestamp
      result {
        __typename
        ... on Scalar      { scalarValue }
        ... on ScalarArray { scalarArrayValue }
        ... on StatusReply { status }
        ... on Raw         { rawValue }
        ... on Text        { textValue }
        ... on TextArray   { textArrayValue }
      }
    }
  }
}
"""

#: Mutation for device settings.
_MUTATION_SET_DEVICE = """
mutation SetDevice($device: String!, $value: DevValue!) {
  _setDevice(device: $device, value: $value) {
    status
  }
}
"""

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def extract_value(result: dict[str, Any]) -> Any:
    """Convert a GraphQL ``DataType`` union dict to a plain Python value."""
    typename = result.get('__typename')
    if typename == 'Scalar':
        return result['scalarValue']
    if typename == 'ScalarArray':
        return result['scalarArrayValue']
    if typename == 'Raw':
        return bytes(result['rawValue'])
    if typename == 'Text':
        return result['textValue']
    if typename == 'TextArray':
        return result['textArrayValue']
    if typename == 'StatusReply':
        return result['status']
    return result


def build_dev_value(value: Any) -> dict[str, Any]:
    """Convert a Python value into a GraphQL ``DevValue`` input dict."""
    if isinstance(value, (bytearray, bytes)):
        return {'rawVal': list(value)}
    if isinstance(value, str):
        return {'textVal': value}
    if isinstance(value, list):
        if value and isinstance(value[0], str):
            return {'textArrayVal': value}
        return {'scalarArrayVal': [float(v) for v in value]}
    return {'scalarVal': float(value)}


def _auth_headers(token: str | None) -> dict[str, str]:
    headers: dict[str, str] = {'Content-Type': 'application/json'}
    if token:
        headers['Authorization'] = f'Bearer {token}'
    return headers


# ---------------------------------------------------------------------------
# HTTP query (one-shot read)
# ---------------------------------------------------------------------------


async def http_query(
    url: str,
    token: str | None,
    device_list: list[str],
) -> list[dict[str, Any]]:
    """POST the ``acceleratorData`` query and return the reply list.

    Returns a list of ``{'refId': int, 'data': [...]}`` dicts in the
    same order as *device_list*.

    Raises
    ------
    AcsysNetworkError
        On connection / transport failures.
    AcsysAPIError
        When the GraphQL response contains ``errors``.
    """
    import aiohttp

    endpoint = url.rstrip('/') + '/acsys'
    payload = {
        'query': _QUERY_ACCELERATOR_DATA,
        'variables': {'deviceList': device_list},
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                endpoint,
                json=payload,
                headers=_auth_headers(token),
            ) as resp:
                resp.raise_for_status()
                body = await resp.json()
    except aiohttp.ClientError as exc:
        raise AcsysNetworkError(
            f'HTTP request to {endpoint} failed: {exc}') from exc

    if 'errors' in body:
        msgs = '; '.join(
            e.get('message', str(e)) for e in body['errors'])
        raise AcsysAPIError(
            f'GraphQL error: {msgs}', errors=body['errors'])

    return body['data']['acceleratorData']


# ---------------------------------------------------------------------------
# HTTP mutation (settings)
# ---------------------------------------------------------------------------


async def http_set_device(
    url: str,
    token: str | None,
    drf: str,
    value: Any,
) -> None:
    """POST the ``_setDevice`` mutation.

    Raises
    ------
    AcsysNetworkError
        On connection / transport failures.
    AcsysAPIError
        When the GraphQL response contains ``errors`` or a fatal ACNET status.
    """
    import aiohttp
    import acsys.status as _status

    endpoint = url.rstrip('/') + '/acsys'
    payload = {
        'query': _MUTATION_SET_DEVICE,
        'variables': {
            'device': drf,
            'value': build_dev_value(value),
        },
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                endpoint,
                json=payload,
                headers=_auth_headers(token),
            ) as resp:
                resp.raise_for_status()
                body = await resp.json()
    except aiohttp.ClientError as exc:
        raise AcsysNetworkError(
            f'HTTP request to {endpoint} failed: {exc}') from exc

    if 'errors' in body:
        msgs = '; '.join(
            e.get('message', str(e)) for e in body['errors'])
        raise AcsysAPIError(
            f'GraphQL error: {msgs}', errors=body['errors'])

    data = (body.get('data') or {})
    result = data.get('_setDevice')
    if result is not None:
        sts = _status.Status(result['status'])
        if sts.is_fatal:
            raise AcsysAPIError(
                f'Device setting rejected – ACNET status {sts}')
    else:
        _log.warning('_setDevice returned no result for %r', drf)


# ---------------------------------------------------------------------------
# WebSocket subscription (streaming reads)
# ---------------------------------------------------------------------------


async def ws_subscribe(
    ws_url: str,
    token: str | None,
    drfs: list[str],
    start_time: float | None = None,
    end_time: float | None = None,
    validate_timestamp: bool | None = None,
) -> AsyncIterator[dict[str, Any]]:
    """Subscribe to ``acceleratorData`` and yield raw reply dicts.

    Each yielded dict has ``{'refId': int, 'data': [...]}`` shape.

    Raises
    ------
    AcsysNetworkError
        On connection / transport failures.
    AcsysStreamError
        When the subscription itself returns an error message.
    """
    import aiohttp

    endpoint = ws_url.rstrip('/') + '/acsys/s'
    headers: dict[str, str] = {}
    if token:
        headers['Authorization'] = f'Bearer {token}'

    variables: dict[str, Any] = {'drfs': drfs}
    if start_time is not None:
        variables['startTime'] = start_time
    if end_time is not None:
        variables['endTime'] = end_time
    if validate_timestamp is not None:
        variables['validateTimestamp'] = validate_timestamp

    try:
        async with aiohttp.ClientSession() as session:
            async with session.ws_connect(
                endpoint,
                protocols=['graphql-transport-ws'],
                headers=headers,
            ) as ws:
                # Handshake
                await ws.send_str(json.dumps(
                    {'type': 'connection_init', 'payload': {}}))

                msg_raw = await ws.receive()
                if msg_raw.type != aiohttp.WSMsgType.TEXT:
                    raise AcsysStreamError(
                        f'Unexpected WS message type: {msg_raw.type}')
                msg = json.loads(msg_raw.data)
                if msg.get('type') != 'connection_ack':
                    raise AcsysStreamError(
                        f'Expected connection_ack, got {msg.get("type")!r}')

                # Subscribe
                await ws.send_str(json.dumps({
                    'type': 'subscribe',
                    'id': '1',
                    'payload': {
                        'query': _SUBSCRIPTION_ACCELERATOR_DATA,
                        'variables': variables,
                    },
                }))

                # Yield replies
                while True:
                    msg_raw = await ws.receive()

                    if msg_raw.type == aiohttp.WSMsgType.TEXT:
                        msg = json.loads(msg_raw.data)
                        msg_type = msg.get('type')

                        if msg_type == 'next':
                            yield msg['payload']['data']['acceleratorData']
                        elif msg_type == 'ping':
                            await ws.send_str(
                                json.dumps({'type': 'pong'}))
                        elif msg_type == 'complete':
                            return
                        elif msg_type == 'error':
                            errors = msg.get('payload') or []
                            msgs = '; '.join(
                                e.get('message', str(e)) for e in errors)
                            raise AcsysStreamError(
                                f'Subscription error: {msgs}')

                    elif msg_raw.type in (
                        aiohttp.WSMsgType.CLOSE,
                        aiohttp.WSMsgType.CLOSING,
                        aiohttp.WSMsgType.CLOSED,
                        aiohttp.WSMsgType.ERROR,
                    ):
                        return

    except (AcsysStreamError, AcsysNetworkError):
        raise
    except aiohttp.ClientError as exc:
        raise AcsysNetworkError(
            f'WebSocket connection to {endpoint} failed: {exc}') from exc
