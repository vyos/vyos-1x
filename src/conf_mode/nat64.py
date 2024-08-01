#!/usr/bin/env python3
#
# Copyright (C) 2023-2024 VyOS maintainers and contributors
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 2 or later as
# published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

# pylint: disable=empty-docstring,missing-module-docstring

import csv
import os
import re

from ipaddress import IPv6Network, IPv6Address
from json import dumps as json_write

from vyos import ConfigError
from vyos import airbag
from vyos.config import Config
from vyos.configdict import is_node_changed
from vyos.utils.dict import dict_search
from vyos.utils.file import write_file
from vyos.utils.kernel import check_kmod
from vyos.utils.process import cmd
from vyos.utils.process import run

airbag.enable()

INSTANCE_REGEX = re.compile(r"instance-(\d+)")
JOOL_CONFIG_DIR = "/run/jool"


def get_config(config: Config | None = None) -> None:
    if config is None:
        config = Config()

    base = ["nat64"]
    nat64 = config.get_config_dict(base, key_mangling=("-", "_"), get_first_key=True)

    return nat64


def verify(nat64) -> None:
    check_kmod(["jool"])
    base_src = ["nat64", "source", "rule"]

    # Load in existing instances so we can destroy any unknown
    lines = cmd("jool instance display --csv").splitlines()
    for _, instance, _ in csv.reader(lines):
        match = INSTANCE_REGEX.fullmatch(instance)
        if not match:
            # FIXME: Instances that don't match should be ignored but WARN'ed to the user
            continue
        num = match.group(1)

        rules = nat64.setdefault("source", {}).setdefault("rule", {})
        # Mark it for deletion
        if num not in rules:
            rules[num] = {"deleted": True}
            continue

        # If the user changes the mode, recreate the instance else Jool fails with:
        # Jool error: Sorry; you can't change an instance's framework for now.
        if is_node_changed(config, base_src + [f"instance-{num}", "mode"]):
            rules[num]["recreate"] = True

        # If the user changes the pool6, recreate the instance else Jool fails with:
        # Jool error: Sorry; you can't change a NAT64 instance's pool6 for now.
        if dict_search("source.prefix", rules[num]) and is_node_changed(
            config,
            base_src + [num, "source", "prefix"],
        ):
            rules[num]["recreate"] = True

    if not nat64:
        # nothing left to do
        return

    if dict_search("source.rule", nat64):
        # Ensure only 1 netfilter instance per namespace
        nf_rules = filter(
            lambda i: "deleted" not in i and i.get('mode') == "netfilter",
            nat64["source"]["rule"].values(),
        )
        next(nf_rules, None)  # Discard the first element
        if next(nf_rules, None) is not None:
            raise ConfigError(
                "Jool permits only 1 NAT64 netfilter instance (per network namespace)"
            )

        for rule, instance in nat64["source"]["rule"].items():
            if "deleted" in instance:
                continue

            # Verify that source.prefix is set and is a /96
            if not dict_search("source.prefix", instance):
                raise ConfigError(f"Source NAT64 rule {rule} missing source prefix")
            src_prefix = IPv6Network(instance["source"]["prefix"])
            if src_prefix.prefixlen != 96:
                raise ConfigError(f"Source NAT64 rule {rule} source prefix must be /96")
            if (int(src_prefix[0]) & int(IPv6Address('0:0:0:0:ff00::'))) != 0:
                raise ConfigError(
                    f'Source NAT64 rule {rule} source prefix is not RFC6052-compliant: '
                    'bits 64 to 71 (9th octet) must be zeroed'
                )

            pools = dict_search("translation.pool", instance)
            if pools:
                for num, pool in pools.items():
                    if "address" not in pool:
                        raise ConfigError(
                            f"Source NAT64 rule {rule} translation pool "
                            f"{num} missing address/prefix"
                        )
                    if "port" not in pool:
                        raise ConfigError(
                            f"Source NAT64 rule {rule} translation pool "
                            f"{num} missing port(-range)"
                        )


def generate(nat64) -> None:
    if not nat64:
        return

    os.makedirs(JOOL_CONFIG_DIR, exist_ok=True)

    if dict_search("source.rule", nat64):
        for rule, instance in nat64["source"]["rule"].items():
            if "deleted" in instance:
                # Delete the unused instance file
                os.unlink(os.path.join(JOOL_CONFIG_DIR, f"instance-{rule}.json"))
                continue

            name = f"instance-{rule}"
            config = {
                "instance": name,
                "framework": "netfilter",
                "global": {
                    "pool6": instance["source"]["prefix"],
                    "manually-enabled": "disable" not in instance,
                },
                # "bib": [],
            }

            if "description" in instance:
                config["comment"] = instance["description"]

            if dict_search("translation.pool", instance):
                pool4 = []
                # mark
                mark = ''
                if dict_search("match.mark", instance):
                    mark = instance["match"]["mark"]

                for pool in instance["translation"]["pool"].values():
                    if "disable" in pool:
                        continue

                    protos = pool.get("protocol", {}).keys() or ("tcp", "udp", "icmp")
                    for proto in protos:
                        obj = {
                            "protocol": proto.upper(),
                            "prefix": pool["address"],
                            "port range": pool["port"],
                        }
                        if mark:
                            obj["mark"] = int(mark)
                        if "description" in pool:
                            obj["comment"] = pool["description"]

                        pool4.append(obj)

                if pool4:
                    config["pool4"] = pool4

            write_file(f'{JOOL_CONFIG_DIR}/{name}.json', json_write(config, indent=2))


def apply(nat64) -> None:
    if not nat64:
        unload_kmod(['jool'])
        return

    if dict_search("source.rule", nat64):
        # Deletions first to avoid conflicts
        for rule, instance in nat64["source"]["rule"].items():
            if not any(k in instance for k in ("deleted", "recreate")):
                continue

            ret = run(f"jool instance remove instance-{rule}")
            if ret != 0:
                raise ConfigError(
                    f"Failed to remove nat64 source rule {rule} (jool instance instance-{rule})"
                )

        # Now creations
        for rule, instance in nat64["source"]["rule"].items():
            if "deleted" in instance:
                continue

            name = f"instance-{rule}"
            ret = run(f"jool -i {name} file handle {JOOL_CONFIG_DIR}/{name}.json")
            if ret != 0:
                raise ConfigError(f"Failed to set jool instance {name}")


if __name__ == "__main__":
    try:
        c = get_config()
        verify(c)
        generate(c)
        apply(c)
    except ConfigError as e:
        print(e)
        exit(1)
