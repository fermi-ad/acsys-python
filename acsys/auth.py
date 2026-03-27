"""Authentication helpers for the acsys library.

This module provides several ways to obtain a Keycloak JWT for
authenticated operations (e.g. device settings):

1. **Environment variable** ``ACSYS_TOKEN`` – simplest, works everywhere::

       export ACSYS_TOKEN=eyJ...
       python my_script.py

2. **Direct token supply** – :func:`set_token` stores a token you already
   have::

       import acsys.auth
       acsys.auth.set_token('eyJ...')

3. **Browser-based PKCE flow** (headed scripts / notebooks) – :func:`login`
   opens the system browser and returns the access token::

       import acsys.auth
       token = acsys.auth.login()

4. **Device-code flow** (headless scripts, CI, containers) –
   :func:`login_device_code` prints a URL + code for the operator to enter in
   any browser, then polls until they do::

       import acsys.auth
       token = acsys.auth.login_device_code()

Keycloak configuration is read from environment variables (or passed as
keyword arguments to the login functions):

* ``ACSYS_KEYCLOAK_URL``    – base URL, e.g. ``https://keycloak.fnal.gov``
* ``ACSYS_KEYCLOAK_REALM``  – realm name, e.g. ``fnal``
* ``ACSYS_KEYCLOAK_CLIENT`` – OIDC client ID, e.g. ``acsys-client``
"""

from __future__ import annotations

import base64
import hashlib
import json
import logging
import os
import secrets
import time
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Optional

from acsys.exceptions import AcsysAuthError

_log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Environment variable names
# ---------------------------------------------------------------------------

_ENV_TOKEN = 'ACSYS_TOKEN'
_ENV_KC_URL = 'ACSYS_KEYCLOAK_URL'
_ENV_KC_REALM = 'ACSYS_KEYCLOAK_REALM'
_ENV_KC_CLIENT = 'ACSYS_KEYCLOAK_CLIENT'

# Fermilab defaults (may be overridden via env vars or function parameters)
_DEFAULT_KC_URL = 'https://keycloak.fnal.gov'
_DEFAULT_KC_REALM = 'fnal'
_DEFAULT_KC_CLIENT = 'acsys-client'


# ---------------------------------------------------------------------------
# Simple helpers
# ---------------------------------------------------------------------------


def token_from_env() -> Optional[str]:
    """Return the token stored in ``ACSYS_TOKEN``, or ``None``."""
    return os.environ.get(_ENV_TOKEN)


def set_token(token: str) -> None:
    """Store *token* in ``ACSYS_TOKEN`` for automatic use by the library.

    This is the simplest way to supply a JWT in a script::

        import acsys.auth
        acsys.auth.set_token('eyJ...')
        reading = acsys.read('Z:BTE200MUON4')
    """
    os.environ[_ENV_TOKEN] = token


# ---------------------------------------------------------------------------
# Internal Keycloak URL builders
# ---------------------------------------------------------------------------


def _kc_token_url(url: str, realm: str) -> str:
    base = url.rstrip('/')
    return f'{base}/realms/{realm}/protocol/openid-connect/token'


def _kc_auth_url(url: str, realm: str) -> str:
    base = url.rstrip('/')
    return f'{base}/realms/{realm}/protocol/openid-connect/auth'


def _kc_device_url(url: str, realm: str) -> str:
    base = url.rstrip('/')
    return f'{base}/realms/{realm}/protocol/openid-connect/auth/device'


def _resolve_kc_config(
    url: Optional[str],
    realm: Optional[str],
    client_id: Optional[str],
) -> tuple[str, str, str]:
    return (
        url or os.environ.get(_ENV_KC_URL, _DEFAULT_KC_URL),
        realm or os.environ.get(_ENV_KC_REALM, _DEFAULT_KC_REALM),
        client_id or os.environ.get(_ENV_KC_CLIENT, _DEFAULT_KC_CLIENT),
    )


def _post_form(url: str, data: dict[str, str], timeout: int = 15) -> dict:
    """POST an ``application/x-www-form-urlencoded`` form and return the
    parsed JSON response.  Raises :exc:`AcsysAuthError` on failure."""
    req = urllib.request.Request(
        url,
        data=urllib.parse.urlencode(data).encode(),
        headers={'Content-Type': 'application/x-www-form-urlencoded'},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # nosec
            return json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        try:
            body = json.loads(exc.read())
        except Exception:
            body = {}
        raise AcsysAuthError(
            f'Keycloak request to {url} failed ({exc.code}): '
            f'{body.get("error_description", body.get("error", exc.reason))}'
        ) from exc
    except Exception as exc:
        raise AcsysAuthError(
            f'Keycloak request to {url} failed: {exc}') from exc


# ---------------------------------------------------------------------------
# Browser-based PKCE flow  (headed)
# ---------------------------------------------------------------------------


def login(
    url: Optional[str] = None,
    realm: Optional[str] = None,
    client_id: Optional[str] = None,
    redirect_port: int = 8765,
) -> str:
    """Obtain a JWT via the browser-based OAuth 2.0 PKCE flow (headed).

    Opens the system browser to the Keycloak login page, waits for the
    authorization-code redirect, exchanges the code for tokens and returns
    the access token.  The token is also stored in ``ACSYS_TOKEN``.

    Parameters
    ----------
    url : str, optional
        Keycloak base URL.  Falls back to ``ACSYS_KEYCLOAK_URL`` or
        ``https://keycloak.fnal.gov``.
    realm : str, optional
        Keycloak realm.  Falls back to ``ACSYS_KEYCLOAK_REALM`` or
        ``fnal``.
    client_id : str, optional
        OIDC public client ID.  Falls back to ``ACSYS_KEYCLOAK_CLIENT`` or
        ``acsys-client``.
    redirect_port : int, optional
        Local TCP port for the redirect callback server (default 8765).

    Returns
    -------
    str
        The JWT access token.

    Raises
    ------
    AcsysAuthError
        On login failure (e.g. user cancelled, state mismatch, Keycloak
        error).
    """
    url, realm, client_id = _resolve_kc_config(url, realm, client_id)
    redirect_uri = f'http://localhost:{redirect_port}/callback'

    # PKCE: code_verifier + SHA-256 code_challenge
    code_verifier = secrets.token_urlsafe(64)
    digest = hashlib.sha256(code_verifier.encode('ascii')).digest()
    code_challenge = base64.urlsafe_b64encode(digest).rstrip(b'=').decode()

    state = secrets.token_urlsafe(16)
    auth_params = urllib.parse.urlencode({
        'response_type': 'code',
        'client_id': client_id,
        'redirect_uri': redirect_uri,
        'scope': 'openid',
        'state': state,
        'code_challenge': code_challenge,
        'code_challenge_method': 'S256',
    })
    auth_endpoint = f'{_kc_auth_url(url, realm)}?{auth_params}'

    # Tiny local HTTP server to catch the redirect
    _result: dict[str, str] = {}

    class _Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):  # silence access log
            pass

        def do_GET(self):
            parsed = urllib.parse.urlparse(self.path)
            if parsed.path == '/callback':
                _result.update(
                    urllib.parse.parse_qsl(parsed.query))
                self.send_response(200)
                self.send_header('Content-type', 'text/html; charset=utf-8')
                self.end_headers()
                self.wfile.write(
                    b'<html><body>'
                    b'<h2>Login successful.</h2>'
                    b'<p>You may close this tab and return to your script.</p>'
                    b'</body></html>')
            else:
                self.send_response(404)
                self.end_headers()

    server = HTTPServer(('localhost', redirect_port), _Handler)
    server.timeout = 120  # 2-minute window to complete login

    _log.info('opening browser for Keycloak login')
    webbrowser.open(auth_endpoint)
    print(f'Waiting for browser login…\n'
          f'If the browser did not open automatically, visit:\n'
          f'  {auth_endpoint}\n')

    server.handle_request()
    server.server_close()

    if 'error' in _result:
        raise AcsysAuthError(
            f'Keycloak login failed: '
            f'{_result.get("error_description", _result["error"])}')
    if 'code' not in _result:
        raise AcsysAuthError(
            'No authorization code received from Keycloak '
            '(did you complete the login before the 2-minute timeout?)')
    if _result.get('state') != state:
        raise AcsysAuthError(
            'OAuth2 state parameter mismatch – possible CSRF attack')

    # Exchange authorization code → tokens
    tokens = _post_form(_kc_token_url(url, realm), {
        'grant_type': 'authorization_code',
        'client_id': client_id,
        'code': _result['code'],
        'redirect_uri': redirect_uri,
        'code_verifier': code_verifier,
    })

    if 'access_token' not in tokens:
        raise AcsysAuthError(
            f'Keycloak did not return an access_token: {tokens}')

    access_token: str = tokens['access_token']
    set_token(access_token)
    _log.info('browser login successful – token stored in ACSYS_TOKEN')
    return access_token


# ---------------------------------------------------------------------------
# Device-code flow  (headless)
# ---------------------------------------------------------------------------


def login_device_code(
    url: Optional[str] = None,
    realm: Optional[str] = None,
    client_id: Optional[str] = None,
    poll_timeout: int = 300,
) -> str:
    """Obtain a JWT via the OAuth 2.0 device-code flow (headless).

    Prints a verification URL and user code for the operator to enter in
    any browser on any machine, then polls Keycloak until the operator
    completes the login.  The token is also stored in ``ACSYS_TOKEN``.

    Parameters
    ----------
    url, realm, client_id : str, optional
        Keycloak configuration (see :func:`login` for defaults).
    poll_timeout : int, optional
        Maximum number of seconds to wait for the operator (default 300).

    Returns
    -------
    str
        The JWT access token.

    Raises
    ------
    AcsysAuthError
        On login failure or timeout.
    """
    url, realm, client_id = _resolve_kc_config(url, realm, client_id)

    # Request device + user codes
    device_resp = _post_form(_kc_device_url(url, realm), {
        'client_id': client_id,
        'scope': 'openid',
    })

    verification_uri = device_resp.get(
        'verification_uri_complete',
        device_resp.get('verification_uri', ''))
    user_code = device_resp.get('user_code', '')
    device_code = device_resp.get('device_code', '')
    interval = device_resp.get('interval', 5)
    expires_in = device_resp.get('expires_in', poll_timeout)

    print(f'\nTo authorize this script, open the following URL in a browser:')
    print(f'  {verification_uri}')
    if user_code:
        print(f'User code: {user_code}')
    print()

    token_url = _kc_token_url(url, realm)
    deadline = time.monotonic() + min(expires_in, poll_timeout)

    while time.monotonic() < deadline:
        time.sleep(interval)
        req = urllib.request.Request(
            token_url,
            data=urllib.parse.urlencode({
                'grant_type':
                    'urn:ietf:params:oauth:grant-type:device_code',
                'client_id': client_id,
                'device_code': device_code,
            }).encode(),
            headers={'Content-Type': 'application/x-www-form-urlencoded'},
        )
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:  # nosec
                tokens = json.loads(resp.read())
        except urllib.error.HTTPError as exc:
            try:
                body = json.loads(exc.read())
            except Exception:
                body = {}
            err = body.get('error', '')
            if err == 'authorization_pending':
                continue
            if err == 'slow_down':
                interval = min(interval + 5, 30)
                continue
            raise AcsysAuthError(
                f'Device-code poll failed: {body}') from exc
        except Exception as exc:
            raise AcsysAuthError(
                f'Device-code poll failed: {exc}') from exc

        if 'access_token' in tokens:
            access_token: str = tokens['access_token']
            set_token(access_token)
            _log.info('device-code login successful')
            return access_token

    raise AcsysAuthError('Device-code login timed out')
