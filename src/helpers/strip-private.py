#!/usr/bin/python3

# Copyright 2021-2024 VyOS maintainers and contributors <maintainers@vyos.io>
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
# You should have received a copy of the GNU Lesser General Public
# License along with this library.  If not, see <http://www.gnu.org/licenses/>.

import sys
import copy

import vyos.configtree


def anonymize_password(v):
    return "<PASSWORD REDACTED>"

def anonymize_key(v):
    return "<KEY DATA REDACTED>"

def anonymize_data(v):
    return "<DATA REDACTED>"


secret_paths = [
  # System user password hashes
  {"base_path": ['system', 'login', 'user'], "secret_path": ["authentication", "encrypted-password"], "func": anonymize_password},

  # PKI data
  {"base_path": ["pki", "ca"], "secret_path": ["private", "key"], "func": anonymize_key},
  {"base_path": ["pki", "ca"], "secret_path": ["certificate"], "func": anonymize_key},
  {"base_path": ["pki", "ca"], "secret_path": ["crl"], "func": anonymize_key},
  {"base_path": ["pki", "certificate"], "secret_path": ["private", "key"], "func": anonymize_key},
  {"base_path": ["pki", "certificate"], "secret_path": ["certificate"], "func": anonymize_key},
  {"base_path": ["pki", "certificate"], "secret_path": ["acme", "email"], "func": anonymize_data},
  {"base_path": ["pki", "key-pair"], "secret_path": ["private", "key"], "func": anonymize_key},
  {"base_path": ["pki", "key-pair"], "secret_path": ["public", "key"], "func": anonymize_key},
  {"base_path": ["pki", "openssh"], "secret_path": ["private", "key"], "func": anonymize_key},
  {"base_path": ["pki", "openssh"], "secret_path": ["public", "key"], "func": anonymize_key},
  {"base_path": ["pki", "openvpn", "shared-secret"], "secret_path": ["key"], "func": anonymize_key},
  {"base_path": ["pki", "dh"], "secret_path": ["parameters"], "func": anonymize_key},

  # IPsec pre-shared secrets
  {"base_path": ['vpn', 'ipsec', 'authentication', 'psk'], "secret_path": ["secret"], "func": anonymize_password},

  # IPsec x509 passphrases
  {"base_path": ['vpn', 'ipsec', 'site-to-site', 'peer'], "secret_path": ['authentication', 'x509'], "func": anonymize_password},

  # IPsec remote-access secrets and passwords
  {"base_path": ["vpn", "ipsec", "remote-access", "connection"], "secret_path": ["authentication", "pre-shared-secret"], "func": anonymize_password},
  # Passwords in remote-access IPsec local users have their own fixup
  # due to deeper nesting.

  # PPTP passwords
  {"base_path": ['vpn', 'pptp', 'remote-access', 'authentication', 'local-users', 'username'], "secret_path": ['password'], "func": anonymize_password},

  # L2TP passwords
  {"base_path": ['vpn', 'l2tp', 'remote-access', 'authentication', 'local-users', 'username'], "secret_path": ['password'], "func": anonymize_password},
  {"path": ['vpn', 'l2tp', 'remote-access', 'ipsec-settings', 'authentication', 'pre-shared-secret'], "func": anonymize_password},

  # SSTP passwords
  {"base_path": ['vpn', 'sstp', 'remote-access', 'authentication', 'local-users', 'username'], "secret_path": ['password'], "func": anonymize_password},

  # OpenConnect passwords
  {"base_path": ['vpn', 'openconnect', 'authentication', 'local-users', 'username'], "secret_path": ['password'], "func": anonymize_password},

  # PPPoE server passwords
  {"base_path": ['service', 'pppoe-server', 'authentication', 'local-users', 'username'], "secret_path": ['password'], "func": anonymize_password},

  # RADIUS PSKs for VPN services
  {"base_path": ["vpn", "sstp", "authentication", "radius", "server"], "secret_path": ["key"], "func": anonymize_password},
  {"base_path": ["vpn", "l2tp", "authentication", "radius", "server"], "secret_path": ["key"], "func": anonymize_password},
  {"base_path": ["vpn", "pptp", "authentication", "radius", "server"], "secret_path": ["key"], "func": anonymize_password},
  {"base_path": ["vpn", "openconnect", "authentication", "radius", "server"], "secret_path": ["key"], "func": anonymize_password},
  {"base_path": ["service", "ipoe-server", "authentication", "radius", "server"], "secret_path": ["key"], "func": anonymize_password},
  {"base_path": ["service", "pppoe-server", "authentication", "radius", "server"], "secret_path": ["key"], "func": anonymize_password},

  # VRRP passwords
  {"base_path": ['high-availability', 'vrrp', 'group'], "secret_path": ['authentication', 'password'], "func": anonymize_password},

  # BGP neighbor and peer group passwords
  {"base_path": ['protocols', 'bgp', 'neighbor'], "secret_path": ["password"], "func": anonymize_password},
  {"base_path": ['protocols', 'bgp', 'peer-group'], "secret_path": ["password"], "func": anonymize_password},

  # WireGuard private keys
  {"base_path": ["interfaces", "wireguard"], "secret_path": ["private-key"], "func": anonymize_password},

  # NHRP passwords
  {"base_path": ["protocols", "nhrp", "tunnel"], "secret_path": ["cisco-authentication"], "func": anonymize_password},

  # RIP passwords
  {"base_path": ["protocols", "rip", "interface"], "secret_path": ["authentication", "plaintext-password"], "func": anonymize_password},

  # IS-IS passwords
  {"path": ["protocols", "isis", "area-password", "plaintext-password"], "func": anonymize_password},
  {"base_path": ["protocols", "isis", "interface"], "secret_path": ["password", "plaintext-password"], "func": anonymize_password},

  # HTTP API servers
  {"base_path": ["service", "https", "api", "keys", "id"], "secret_path": ["key"], "func": anonymize_password},

  # Telegraf
  {"path": ["service", "monitoring", "telegraf", "prometheus-client", "authentication", "password"], "func": anonymize_password},
  {"path": ["service", "monitoring", "telegraf", "influxdb", "authentication", "token"], "func": anonymize_password},
  {"path": ["service", "monitoring", "telegraf", "azure-data-explorer", "authentication", "client-secret"], "func": anonymize_password},
  {"path": ["service", "monitoring", "telegraf", "splunk", "authentication", "token"], "func": anonymize_password},

  # SNMPv3 passwords
  {"base_path": ["service", "snmp", "v3", "user"], "secret_path": ["privacy", "encrypted-password"], "func": anonymize_password},
  {"base_path": ["service", "snmp", "v3", "user"], "secret_path": ["privacy", "plaintext-password"], "func": anonymize_password},
  {"base_path": ["service", "snmp", "v3", "user"], "secret_path": ["auth", "encrypted-password"], "func": anonymize_password},
  {"base_path": ["service", "snmp", "v3", "user"], "secret_path": ["auth", "encrypted-password"], "func": anonymize_password},
]

def prepare_secret_paths(config_tree, secret_paths):
    """ Generate a list of secret paths for the current system,
        adjusted for variable parts such as VRFs and remote access IPsec instances
    """

    # Fixup for remote-access IPsec local users that are nested under two tag nodes
    # We generate the list of their paths dynamically
    ipsec_ra_base = {"base_path": ["vpn", "ipsec", "remote-access", "connection"], "func": anonymize_password}
    if config_tree.exists(ipsec_ra_base["base_path"]):
        for conn in config_tree.list_nodes(ipsec_ra_base["base_path"]):
            if config_tree.exists(ipsec_ra_base["base_path"] + [conn] + ["authentication", "local-users", "username"]):
                for u in config_tree.list_nodes(ipsec_ra_base["base_path"] + [conn] + ["authentication", "local-users", "username"]):
                    p = copy.copy(ipsec_ra_base)
                    p["base_path"] = p["base_path"] + [conn] + ["authentication", "local-users", "username"]
                    p["secret_path"] = ["password"]
                    secret_paths.append(p)

    # Fixup for VRFs that may contain routing protocols and other nodes nested under them
    vrf_paths = []
    vrf_base_path = ["vrf", "name"]
    if config_tree.exists(vrf_base_path):
        for v in config_tree.list_nodes(vrf_base_path):
            vrf_secret_paths = copy.deepcopy(secret_paths)
            for sp in vrf_secret_paths:
                if "base_path" in sp:
                    sp["base_path"] = vrf_base_path + [v] + sp["base_path"]
                elif "path" in sp:
                    sp["path"] = vrf_base_path + [v] + sp["path"]
                vrf_paths.append(sp)

    secret_paths = secret_paths + vrf_paths

    # Fixup for user SSH keys, that are nested under a tag node
    #ssh_key_base_path = {"base_path": ['system', 'login', 'user'], "secret_path": ["authentication", "encrypted-password"], "func": anonymize_password},
    user_base_path = ['system', 'login', 'user']
    ssh_key_paths = []
    if config_tree.exists(user_base_path):
        for u in config_tree.list_nodes(user_base_path):
            kp = {"base_path": user_base_path + [u, "authentication", "public-keys"], "secret_path": ["key"], "func": anonymize_key}
            ssh_key_paths.append(kp)

    secret_paths = secret_paths + ssh_key_paths

    return secret_paths

def strip_private(ct, secret_paths):
    for sp in secret_paths:
        if "base_path" in sp:
            if ct.exists(sp["base_path"]):
                for n in ct.list_nodes(sp["base_path"]):
                    if ct.exists(sp["base_path"] + [n] + sp["secret_path"]):
                        secret = ct.return_value(sp["base_path"] + [n] + sp["secret_path"])
                        ct.set(sp["base_path"] + [n] + sp["secret_path"], value=sp["func"](secret))
        elif "path" in sp:
            if ct.exists(sp["path"]):
                secret = ct.return_value(sp["path"])
                ct.set(sp["path"], value=sp["func"](secret))
        else:
            raise ValueError("Malformed secret path dict, has neither base_path nor path in it ")


    return ct.to_string()

def read_input():
    try:
        return sys.stdin.read()
    # stdin can be cut for any reason, such as user interrupt or the pager terminating before the text can be read.
    # All we can do is gracefully exit.
    except (BrokenPipeError, EOFError, KeyboardInterrupt):
        sys.exit(1)

if __name__ == "__main__":
    try:
        config_source = read_input()
        config_tree = vyos.configtree.ConfigTree(config_source)
        secret_paths = prepare_secret_paths(config_tree, secret_paths)
        stripped_config = strip_private(config_tree, secret_paths)
        print(stripped_config)
    except ValueError:
        # Most definitely caused by trying to run the filter
        # on something else than a config
        print('strip-private filter error: could not parse the input as a VyOS config', file=sys.stderr)
        print('Hint: if want to see your config as commands, run "show | strip-private | commands"', file=sys.stderr)
