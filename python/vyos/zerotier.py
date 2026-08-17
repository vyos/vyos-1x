# Copyright VyOS maintainers and contributors <maintainers@vyos.io>
#
# This library is free software; you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published
# by the Free Software Foundation; either version 2.1 of the License, or
# (at your option) any later version.

import json
import socket
import tempfile
import time

from pathlib import Path

from vyos.utils.process import cmd
from vyos.utils.file import write_file


ZEROTIER_HOME = Path('/run/vyos-zerotier')
ZEROTIER_API_SOCKET = ZEROTIER_HOME / 'api.sock'
ZEROTIER_UNIT = 'vyos-zerotier.service'
ZEROTIER_USER = 'zerotier-one'
ZEROTIER_GROUP = 'zerotier-one'


class ZeroTierAPIError(Exception):
    pass


def identity_public(secret: str) -> str:
    with tempfile.NamedTemporaryFile(mode='w', prefix='zt-identity-', delete=True) as f:
        f.write(secret.rstrip() + '\n')
        f.flush()
        return cmd(f'zerotier-idtool getpublic {f.name}').strip()


def write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    write_file(str(path), json.dumps(data, indent=2, sort_keys=True) + '\n',
               user=ZEROTIER_USER, group=ZEROTIER_GROUP, mode=0o644)


def write_identity(secret: str) -> None:
    ZEROTIER_HOME.mkdir(parents=True, exist_ok=True)
    write_file(str(ZEROTIER_HOME / 'identity.secret'), secret.rstrip() + '\n',
               user=ZEROTIER_USER, group=ZEROTIER_GROUP, mode=0o600)
    write_file(str(ZEROTIER_HOME / 'identity.public'), identity_public(secret) + '\n',
               user=ZEROTIER_USER, group=ZEROTIER_GROUP, mode=0o644)


def network_settings(interface: dict) -> dict:
    return {
        'allowManaged': interface.get('allow_managed', 'true') == 'true',
        'allowGlobal': 'allow_global' in interface,
        'allowDefault': 'allow_default_route' in interface,
        'allowDNS': False,
    }


def local_conf(service: dict) -> dict:
    settings = {
        'primaryPort': int(service.get('port', {}).get('primary', 9993)),
        'portMappingEnabled': 'disable_port_mapping' not in service,
        'allowSecondaryPort': 'disable_secondary_port' not in service,
        'allowTcpFallbackRelay': 'disable_tcp_fallback' not in service,
        'softwareUpdate': 'disable',
    }

    if 'listen_address' in service:
        settings['bind'] = service['listen_address']
    if 'interface_blacklist' in service:
        settings['interfacePrefixBlacklist'] = service['interface_blacklist']
    if 'force_tcp_relay' in service:
        settings['forceTcpRelay'] = True
    if 'tcp_relay' in service:
        settings['tcpFallbackRelay'] = service['tcp_relay']
    if service.get('port', {}).get('secondary'):
        settings['secondaryPort'] = int(service['port']['secondary'])
    if service.get('port', {}).get('tertiary'):
        settings['tertiaryPort'] = int(service['port']['tertiary'])

    multicore = service.get('multicore', {})
    if 'enable' in multicore:
        settings['multicoreEnabled'] = True
    if multicore.get('core_count'):
        settings['concurrency'] = int(multicore['core_count'])
    if 'cpu_pinning' in multicore:
        settings['cpuPinningEnabled'] = True

    physical = {}
    for prefix, config in service.get('physical', {}).items():
        physical[prefix] = {}
        if 'blacklist' in config:
            physical[prefix]['blacklist'] = True
        if 'mtu' in config:
            physical[prefix]['mtu'] = int(config['mtu'])

    virtual = {}
    for peer, config in service.get('peer', {}).items():
        if 'path' in config:
            virtual[peer] = {'try': config['path']}

    result = {'settings': settings}
    if physical:
        result['physical'] = physical
    if virtual:
        result['virtual'] = virtual

    return result


def api_request(method: str, path: str, body: dict | None = None) -> object:
    request = {
        'method': method,
        'path': path,
        'body': json.dumps(body) if body is not None else '',
    }
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
            sock.settimeout(60)
            sock.connect(str(ZEROTIER_API_SOCKET))
            sock.sendall(json.dumps(request).encode() + b'\n')
            response = b''
            while not response.endswith(b'\n'):
                chunk = sock.recv(65536)
                if not chunk:
                    break
                response += chunk
    except OSError as e:
        raise ZeroTierAPIError('ZeroTier local API is not ready') from e

    try:
        result = json.loads(response.decode())
    except ValueError as e:
        raise ZeroTierAPIError('Invalid ZeroTier local API response') from e

    response_body = result.get('body', '')
    status = int(result.get('status', 500))
    if status < 200 or status >= 300:
        raise ZeroTierAPIError(f'{method} {path} failed: HTTP {status}: {response_body}')

    if response_body:
        try:
            return json.loads(response_body)
        except ValueError:
            return response_body

    return {}


def wait_for_api(timeout: int = 15) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            api_request('GET', '/status')
            return True
        except ZeroTierAPIError:
            time.sleep(1)

    return False
