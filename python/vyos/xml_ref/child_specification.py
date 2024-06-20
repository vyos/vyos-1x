# Copyright 2023 VyOS maintainers and contributors <maintainers@vyos.io>
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

"""
This file contains structures matching the XML schema for childSpecification,
intended to make it easier to work with a known structure instead of raw lists and dicts.

Keeping the public interface to just the CSChildSpecification class makes it easier to do any later refactoring.
"""

from typing import Any
from vyos.configsession import ConfigSessionError

class ChildSpecificationError(ValueError):
    pass

class _CSChildName(str):
    XML_NAME = "child"

class _CSValueValue(str):
    XML_NAME = "value"

class _CSDescendant:
    XML_NAME = "descendant"

    descendant: dict[_CSChildName, "_CSDescendant"]
    child: list[_CSChildName]
    value: list[_CSValueValue]

    def __init__(self, descendant_tree) -> None:
        self.descendant = {}
        self.child = []
        self.value = []

        self._add(descendant_tree)

    def _add(self, descendant_tree):
        for node in descendant_tree:
            node_type = node[0]
            node_spec = node[1]
            match node_type:
                case _CSDescendant.XML_NAME:
                    descendant_name = _CSChildName(node_spec[0])
                    descendant_spec_grouping = node_spec[1]
                    if descendant_name in self.descendant:
                        self.descendant[descendant_name]._add(descendant_spec_grouping)
                    else:
                        self.descendant[descendant_name] = _CSDescendant(
                            descendant_spec_grouping
                        )
                case _CSChildName.XML_NAME:
                    self.child.append(_CSChildName(node_spec))
                case _CSValueValue.XML_NAME:
                    self.value.append(_CSValueValue(node_spec))
                case _:
                    raise ChildSpecificationError(
                        f"Unsupported descendant specification xml name: {node_type}"
                    )

    def find_missing(
        self, root_path: list[str], conf: dict[str, Any]
    ) -> list[list[str]]:
        missing = []

        # Due to is_tag being defined in __init__.py we must import it here to avoid circular dependancies.
        #  TODO: investiagte overhead impact of importing over and over
        from vyos.xml_ref import is_tag
        if is_tag(root_path):
            for k, v in conf.items():
                path = root_path + [k]
                sub = self.find_missing(path, conf[k])
                if sub:
                    missing.extend(sub)
            return missing

        for k, v in self.descendant.items():
            path = root_path + [k]

            if k not in conf:
                missing.append(path)
                continue

            sub = v.find_missing(path, conf[k])
            if sub:
                missing.extend(sub)

        for v in self.child:
            if v not in conf:
                missing.append(root_path + [v])

        return missing

    def find_provided(
        self, root_path: list[str], conf: dict[str, Any]
    ) -> list[list[str]]:
        provided = []

        # Due to is_tag being defined in __init__.py we must import it here to avoid circular dependancies.
        #  TODO: investiagte overhead impact of importing over and over
        from vyos.xml_ref import is_tag
        if is_tag(root_path):
            for k, v in conf.items():
                path = root_path + [k]
                sub = self.find_provided(path, conf[k])
                if sub:
                    provided.extend(sub)
            return provided

        for k, v in self.descendant.items():
            path = root_path + [k]
            if k in conf:
                sub = v.find_provided(path, conf[k])
                if sub:
                    provided.extend(sub)

        for v in self.child:
            if v in conf:
                provided.append(root_path + [v])

        for v in self.value:
            if str(v) == str(conf):
                provided.append(root_path + [v])

        return provided

class _CSRequiredChildren(_CSDescendant):
    XML_KEY = "requiredChildren"

    def verify(self, root_path: list[str], conf: dict[str, Any]):
        missing = self.find_missing(root_path, conf)
        if len(missing) >= 1:
            raise ConfigSessionError(f"Missing required config: [{' '.join(missing[0])}]")


class _CSAtLeastOneOf(_CSDescendant):
    XML_KEY = "atLeastOneOf"

    def verify(self, root_path: list[str], conf: dict[str, Any]):
        provided = self.find_provided(root_path, conf)
        if len(provided) <= 0:
            missing = self.find_missing(root_path, conf)
            s = '], ['.join([' '.join(x) for x in missing])
            raise ConfigSessionError(f"At least one of the following must be configured: [{s}]")

class _CSMutuallyExclusiveChildren(_CSDescendant):
    XML_KEY = "mutuallyExclusiveChildren"

    def verify(self, root_path: list[str], conf: dict[str, Any]):
        provided = self.find_provided(root_path, conf)
        if len(provided) > 1:
            s = '], ['.join([' '.join(x) for x in provided])
            raise ConfigSessionError(f"Only one of the following can be configured at the same time: [{s}]")

class _CSMutuallyDependantChildren(_CSDescendant):
    XML_KEY = "mutuallyDependantChildren"

    def verify(self, root_path: list[str], conf: dict[str, Any]):
        provided = self.find_provided(root_path, conf)
        if len(provided) > 0:
            missing = self.find_missing(root_path, conf)
            if len(missing) > 0:
                sp = '], ['.join([' '.join(x) for x in provided])
                sm = '], ['.join([' '.join(x) for x in missing])
                raise ConfigSessionError(f"[{sp}] requires configuration of [{sm}]")

class _CSOneWayDependantChildren:
    XML_KEY = "oneWayDependantChildren"

    dependants: list[_CSDescendant]
    dependees: list[_CSDescendant]

    def __init__(self, spec) -> None:
        self.dependants = []
        self.dependees = []

        for relationship, grouping in spec.items():
            match relationship:
                case "dependants":
                    self.dependants.append(_CSDescendant(grouping))
                case "dependees":
                    self.dependees.append(_CSDescendant(grouping))
                case _:
                    raise ChildSpecificationError(
                        f"Unsupported one-way-dependancy relationship: {relationship}"
                    )

    def verify(self, root_path: list[str], conf: dict[str, Any]):
        provided_dependants = []
        for dependant in self.dependants:
            provided_dependants.extend(dependant.find_provided(root_path, conf))

        if len(provided_dependants) > 0:
            missing_dependees = []
            for dependee in self.dependees:
                missing_dependees.extend(dependee.find_missing(root_path, conf))

            if len(missing_dependees) > 0:
                sp = '], ['.join([' '.join(x) for x in provided_dependants])
                sm = '], ['.join([' '.join(x) for x in missing_dependees])
                raise ConfigSessionError(f"[{sp}] requires configuration of [{sm}]")

class CSChildSpecification:
    required_children: _CSRequiredChildren
    at_least_one_of: list[_CSAtLeastOneOf]
    mutually_exclusive_children: list[_CSMutuallyExclusiveChildren]
    mutually_dependant_children: list[_CSMutuallyDependantChildren]
    one_way_dependant_children: list[_CSOneWayDependantChildren]

    def __init__(self, child_specification_from_xml) -> None:
        self.required_children = None
        self.at_least_one_of = []
        self.mutually_exclusive_children = []
        self.mutually_dependant_children = []
        self.one_way_dependant_children = []

        if not child_specification_from_xml:
            return

        for spec_name, spec in child_specification_from_xml.items():
            match spec_name:
                case _CSRequiredChildren.XML_KEY:
                    self.required_children = _CSRequiredChildren(spec)
                case _CSAtLeastOneOf.XML_KEY:
                    for grouping in spec:
                        self.at_least_one_of.append(_CSAtLeastOneOf(grouping))
                case _CSMutuallyExclusiveChildren.XML_KEY:
                    for grouping in spec:
                        self.mutually_exclusive_children.append(
                            _CSMutuallyExclusiveChildren(grouping)
                        )
                case _CSMutuallyDependantChildren.XML_KEY:
                    for grouping in spec:
                        self.mutually_dependant_children.append(
                            _CSMutuallyDependantChildren(grouping)
                        )
                case _CSOneWayDependantChildren.XML_KEY:
                    for grouping in spec:
                        self.one_way_dependant_children.append(
                            _CSOneWayDependantChildren(grouping)
                        )
                case _:
                    raise ChildSpecificationError(
                        f"Unsupported specification child xml key: {spec_name}"
                    )

    def verify(self, rpath: list[str], raw_config_dict: dict):
        """verify verifies config based on XML data

        Verifies that configuration fulfills the requirements specified in the
        XML schema for the node and its subnodes using the root path and config
        dict with unmangled keys.

        Args:
            rpath (list[str]): node root path
            raw_config_dict (dict): config to verify

        Raises:
            ConfigSessionError: If the provided path and config does not fulfill the specifications.
        """

        if self.required_children:
            self.required_children.verify(rpath, raw_config_dict)
        for spec in self.at_least_one_of:
            spec.verify(rpath, raw_config_dict)
        for spec in self.mutually_exclusive_children:
            spec.verify(rpath, raw_config_dict)
        for spec in self.mutually_dependant_children:
            spec.verify(rpath, raw_config_dict)
        for spec in self.one_way_dependant_children:
            spec.verify(rpath, raw_config_dict)

    def __repr__(self):
        return str(vars(self))
