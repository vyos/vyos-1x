#!/usr/bin/env python3
#
# Copyright (C) 2020 VyOS maintainers and contributors
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

import unittest, sys, pathlib
from copy import deepcopy
from vyos.configsession import ConfigSessionError
from vyos.xml_ref.child_specification import CSChildSpecification

# NOTE: The configuration and XML spec does not follow a real configuration,
#       this is a synthetic config intended to test all cases.
RPATH = ["container", "name", "example"]
BASE_CONF = {
    "image": "busybox:stable",
    "label": {
            "username": {"value":"River"},
            "password": {"value":"Song"},
            "proxy-auth-server": {"value": "oauth.example.com"},
    },
    "network": {"home": {"address": "192.168.1.1"}, "corp": {"address": "10.11.12.13"}},
    "rootless": True,
    "volume": {"application": {"source": "/opt/app", "destination": "/mnt/app"}},
    "port": {"http": {"source": 8080}},
    "uid": 1337,
    "gid": 8008
}
CHILD_SPEC = CSChildSpecification(
    {
        "requiredChildren": [
            ["child", "image"],
            [
                "descendant",
                [
                    "label",
                    [
                        ["child", "value"],
                    ],
                ],
            ],
            ["descendant", ["volume", [["child", "source"]]]],
        ],
        "atLeastOneOf": [
            [
                ["child", "allow-host-networks"],
                ["descendant", ["network", [["child", "address"]]]],
            ],
            [["child", "rootless"], ["child", "privileged"]],
            [["child", "host-name"], ["descendant", ["port", [["child", "source"]]]]],
        ],
        "mutuallyExclusiveChildren": [
            [["child", "network"], ["child", "allow-host-networks"]],
            [
                ["child", "host-name"],
                ["descendant", ["port", [["child", "source"]]]],
            ],
            [
                ["child", "image"],
                ["descendant", ["allow-host-networks", [["value", True]]]],
            ],
        ],
        "mutuallyDependantChildren": [
            [["descendant", ["image", [["value", "vyos"]]]], ["descendant", ["port", [["child", "protocol"]]]]],
        ],
        "oneWayDependantChildren": [
            {"dependants": [["child", "gid"]], "dependees": [["child", "uid"]]}
        ],
    }
)

class TestChildSpecification(unittest.TestCase):
    def test_all_good(self):
        # Verify good config
        CHILD_SPEC.verify(RPATH, BASE_CONF)

    def test_required_child(self):
        # Verify missing child
        tmp_conf = deepcopy(BASE_CONF)
        tmp_conf.pop("image")
        with self.assertRaises(ConfigSessionError):
            CHILD_SPEC.verify(RPATH, tmp_conf)

        # Verify missing descendant
        tmp_conf = deepcopy(BASE_CONF)
        tmp_conf.pop("label")
        with self.assertRaises(ConfigSessionError):
            CHILD_SPEC.verify(RPATH, tmp_conf)

        # Verify missing child of descendant
        tmp_conf = deepcopy(BASE_CONF)
        tmp_conf["label"]["username"] = {"missing":"value"}
        with self.assertRaises(ConfigSessionError):
            CHILD_SPEC.verify(RPATH, tmp_conf)

    def test_at_least_one_of(self):
        # Verify missing child
        tmp_conf = deepcopy(BASE_CONF)
        tmp_conf.pop("rootless")
        with self.assertRaises(ConfigSessionError):
            CHILD_SPEC.verify(RPATH, tmp_conf)

        # Verify missing descendant
        tmp_conf = deepcopy(BASE_CONF)
        tmp_conf.pop("network")
        with self.assertRaises(ConfigSessionError):
            CHILD_SPEC.verify(RPATH, tmp_conf)

        # Verify missing child of descendant (tag node)
        tmp_conf = deepcopy(BASE_CONF)
        for k in tmp_conf["network"]:
            tmp_conf["network"][k].pop("address")
        with self.assertRaises(ConfigSessionError):
            CHILD_SPEC.verify(RPATH, tmp_conf)

    def test_mutually_exclusive_children(self):
        # Verify conflicting children
        tmp_conf = deepcopy(BASE_CONF)
        tmp_conf["allow-host-networks"] = True
        with self.assertRaises(ConfigSessionError):
            CHILD_SPEC.verify(RPATH, tmp_conf)

        # Verify conflicting children on different levels
        tmp_conf = deepcopy(BASE_CONF)
        tmp_conf["host-name"] = "cont1"
        with self.assertRaises(ConfigSessionError):
            CHILD_SPEC.verify(RPATH, tmp_conf)

        # Verify conflicting child and value
        tmp_conf = deepcopy(BASE_CONF)
        tmp_conf["image"] = "kali:airgap"
        tmp_conf["allow-host-networks"] = True
        tmp_conf.pop("network")
        with self.assertRaises(ConfigSessionError):
            CHILD_SPEC.verify(RPATH, tmp_conf)

    def test_mutually_dependant_children(self):
        # Verify dependance on different levels with value
        tmp_conf = deepcopy(BASE_CONF)
        tmp_conf["image"] = "vyos"
        with self.assertRaises(ConfigSessionError):
            CHILD_SPEC.verify(RPATH, tmp_conf)

    def test_one_way_dependant_children(self):
        # Verify same level dependance
        tmp_conf = deepcopy(BASE_CONF)
        tmp_conf.pop("gid")
        CHILD_SPEC.verify(RPATH, tmp_conf)
        tmp_conf = deepcopy(BASE_CONF)
        tmp_conf.pop("uid")
        with self.assertRaises(ConfigSessionError):
            CHILD_SPEC.verify(RPATH, tmp_conf)

if __name__ == "__main__":
    unittest.main(verbosity=2, failfast=True)
