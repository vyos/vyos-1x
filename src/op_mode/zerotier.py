#!/usr/bin/env python3
#
# Copyright VyOS maintainers and contributors <maintainers@vyos.io>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 2 or later as
# published by the Free Software Foundation.

import argparse
import json
from sys import exit

from tabulate import tabulate

from vyos.config import Config
from vyos.utils.misc import install_into_config
from vyos.utils.process import cmd
from vyos.zerotier import ZeroTierAPIError
from vyos.zerotier import api_request
from vyos.zerotier import identity_public


def _format_bool(value):
    return 'yes' if value else 'no'


def _format_list(values):
    return ','.join(values) if values else '-'


def _format_routes(routes):
    if not routes:
        return '-'

    formatted = []
    for route in routes:
        target = route.get('target') or route.get('targetPrefix') or ''
        via = route.get('via') or ''
        formatted.append(f'{target} via {via}' if via else target)

    return ','.join(formatted) if formatted else '-'


def _format_latency(value):
    try:
        latency = int(value)
    except (TypeError, ValueError):
        return '-'
    if latency < 0:
        return '-'
    return f'{latency} ms'


def _active_paths(paths):
    return [path for path in paths if path.get('active') and not path.get('expired')]


def _preferred_path(paths):
    active = _active_paths(paths)
    for path in active:
        if path.get('preferred'):
            return path.get('address') or '-'

    if active:
        return active[0].get('address') or '-'

    return '-'


def _show_networks(data):
    rows = []
    for network in data:
        rows.append({
            'Interface': network.get('portDeviceName') or '-',
            'Network ID': network.get('nwid') or network.get('id') or '-',
            'Name': network.get('name') or '-',
            'Status': network.get('status') or '-',
            'Type': network.get('type') or '-',
            'Managed': _format_bool(network.get('allowManaged', False)),
            'Addresses': _format_list(network.get('assignedAddresses', [])),
            'Routes': _format_routes(network.get('routes', [])),
        })

    if not rows:
        print('No ZeroTier networks joined')
        return

    print(tabulate(rows, headers='keys', tablefmt='simple', numalign='left'))


def _show_peers(data):
    rows = []
    for peer in data:
        paths = peer.get('paths', [])
        rows.append({
            'Address': peer.get('address') or '-',
            'Role': peer.get('role') or '-',
            'Version': peer.get('version') or '-',
            'Latency': _format_latency(peer.get('latency')),
            'Bonded': _format_bool(peer.get('isBonded', False)),
            'Tunneled': _format_bool(peer.get('tunneled', False)),
            'Active paths': len(_active_paths(paths)),
            'Preferred path': _preferred_path(paths),
        })

    if not rows:
        print('No ZeroTier peers')
        return

    print(tabulate(rows, headers='keys', tablefmt='simple', numalign='left'))


def generate_identity(install=False):
    secret = cmd('zerotier-idtool generate').strip()
    public = identity_public(secret)

    if install:
        install_into_config(Config(), [f"service zerotier identity secret '{secret}'"])
        print(f"ZeroTier public identity: '{public}'")
        return

    print(secret)
    print(public)


def show(path, raw_json=False):
    data = api_request('GET', path)
    if raw_json:
        print(json.dumps(data, indent=2, sort_keys=True))
        return

    if path == '/status':
        print(f"address: {data.get('address', '')}")
        print(f"online: {data.get('online', False)}")
        print(f"version: {data.get('version', '')}")
        return

    if path == '/network':
        _show_networks(data)
        return

    if path == '/peer':
        _show_peers(data)
        return

    print(json.dumps(data, indent=2, sort_keys=True))


def main():
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest='command', required=True)

    identity = subparsers.add_parser('generate-identity')
    identity.add_argument('--install', action='store_true')

    status = subparsers.add_parser('status')
    status.add_argument('--json', action='store_true')

    networks = subparsers.add_parser('networks')
    networks.add_argument('--json', action='store_true')

    moons = subparsers.add_parser('moons')
    moons.add_argument('--json', action='store_true')

    peers = subparsers.add_parser('peers')
    peers.add_argument('--json', action='store_true')

    args = parser.parse_args()

    try:
        if args.command == 'generate-identity':
            generate_identity(install=args.install)
        elif args.command == 'status':
            show('/status', raw_json=args.json)
        elif args.command == 'networks':
            show('/network', raw_json=args.json)
        elif args.command == 'moons':
            show('/moon', raw_json=args.json)
        elif args.command == 'peers':
            show('/peer', raw_json=args.json)
    except ZeroTierAPIError as e:
        print(e)
        exit(1)


if __name__ == '__main__':
    main()
