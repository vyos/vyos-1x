#!/usr/bin/env python3
#
# Copyright (C) VyOS Inc.
#
# This library is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 2.1 of the License, or (at your option) any later version.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this library.  If not, see <http://www.gnu.org/licenses/>.

import json
import urllib3
import requests
from typing import Optional
from typing import Union
from dataclasses import dataclass

from vyos.version import get_version
from vyos.template import bracketize_ipv6


class ApiError(Exception):
    """Generic VyOS HTTP API client error"""


class ApiAuthError(ApiError):
    """Authentication/authorization error"""


class ApiTransportError(ApiError):
    """Network/transport error (timeouts, connection errors, etc.)"""


class ApiResponseError(ApiError):
    """Server responded, but payload is invalid or indicates an error"""

    def __init__(self, message, response=None):
        super().__init__(message)
        self.response = response


@dataclass(frozen=True)
class ApiClientConfig:
    host: str
    key: str
    port: int = 443
    timeout: Optional[int] = None
    # TLS peer verification, forwarded verbatim to requests' ``verify``:
    #   True       - verify against the system CA store (secure default)
    #   False      - disable verification (insecure; opt-in only)
    #   "<path>"   - verify against a custom CA bundle file/dir
    verify_tls: Union[bool, str] = True


class ApiClient:
    """Small helper for talking to VyOS HTTP API using requests.

    Design goals:
    - minimal surface area (thin wrapper around requests)
    - consistent error handling + typed exceptions
    - secure defaults (verify_tls=True); deployments using self-signed
      certificates opt into verify_tls=False or supply a CA bundle path
    """

    _DEFAULT_HEADERS = {
        'Content-Type': 'application/json',
        'User-Agent': f'VyOS/{get_version()}',
    }

    def __init__(self, config: ApiClientConfig):
        assert isinstance(config, ApiClientConfig)

        self._cfg = config
        self._host = bracketize_ipv6(config.host)

        self._session = requests.Session()
        self._session.headers.update(self._DEFAULT_HEADERS)

        # Only silence the insecure-request warning when verification has been
        # explicitly disabled. A CA bundle path or True must keep warnings on.
        if config.verify_tls is False:
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    @property
    def base_url(self) -> str:
        return f'https://{self._host}:{self._cfg.port}'

    def post(
        self,
        endpoint: str,
        payload: dict,
        *,
        params: Optional[dict] = None,
        raise_on_error: bool = True,
    ) -> dict:
        """POST JSON to API and return decoded JSON response.

        Args:
            endpoint: URL path, e.g. '/configure-section' or 'configure'
            payload: dict that will be JSON-encoded and sent as request body
            params: Optional query parameters
            raise_on_error: If True, raise when response envelope contains bad status code

        Raises:
            ApiTransportError: network problems/timeouts
            ApiAuthError: 401/403 responses
            ApiResponseError: non-2xx responses or invalid JSON
        """
        if not endpoint.startswith('/'):
            endpoint = f'/{endpoint}'

        # Most VyOS endpoints in this repo expect 'key' inside body.
        body = dict(payload)
        body.setdefault('key', self._cfg.key)

        url = f'{self.base_url}{endpoint}'

        try:
            resp = self._session.post(
                url,
                data=json.dumps(body),
                params=params,
                timeout=self._cfg.timeout,
                verify=self._cfg.verify_tls,
            )
        except requests.exceptions.Timeout as e:
            raise ApiTransportError(f'Request timed out: {e}') from e
        except requests.exceptions.RequestException as e:
            raise ApiTransportError(f'Request failed: {e}') from e

        if not resp.ok:
            text = resp.text.strip()
            err_msg = f'HTTP {resp.status_code} from {endpoint}: {text}'

            if resp.status_code in (401, 403):
                raise ApiAuthError(err_msg)
            elif resp.status_code >= 500:
                raise ApiResponseError(err_msg, response=resp)

            if raise_on_error:
                raise ApiResponseError(err_msg, response=resp)

        try:
            return resp.json()
        except json.JSONDecodeError as e:
            raise ApiResponseError(
                f'Invalid JSON response from {endpoint}: {e}',
                response=resp,
            ) from e
