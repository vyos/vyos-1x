# Copyright (C) 2020 VyOS maintainers and contributors
#
# This library is free software; you can redistribute it and/or modify it under the terms of
# the GNU Lesser General Public License as published by the Free Software Foundation;
# either version 2.1 of the License, or (at your option) any later version.
#
# This library is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY;
# without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
# See the GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License along with this library;
# if not, write to the Free Software Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA 02111-1307 USA 

from os.path import join
from os.path import abspath
from os.path import dirname

import xmltodict

from vyos import debug
from vyos.xml import kw
from vyos.xml import definition

from vyos.xml.files import listing
from vyos.xml.files import include

# where the files are located

_here = dirname(__file__)

configuration_definition = abspath(join(_here, '..', '..' ,'..', 'interface-definitions'))
configuration_cache = abspath(join(_here, 'cache', 'configuration.py'))

operational_definition = abspath(join(_here, '..', '..' ,'..', 'op-mode-definitions'))
operational_cache = abspath(join(_here, 'cache', 'operational.py'))

configuration_xml = '/usr/share/vyos/xml/configuration.xml'
operational_xml = '/usr/share/vyos/xml/operational.xml'

# This code is only ran during the creation of the debian package
# therefore we accept that failure can be fatal and not handled
# gracefully.


def _fatal(debug_info=''):
    """
    raise a RuntimeError or if in developer mode stop the code
    """
    if not debug.enabled('developer'):
        raise RuntimeError(str(debug_info))

    if debug_info:
        print(debug_info)
    breakpoint()


def _safe_update(dict1, dict2):
    """
    return a dict made of two, raise if any root key would be overwritten
    """
    if set(dict1).intersection(dict2):
        raise RuntimeError('overlapping configuration')
    return {**dict1, **dict2}


def _merge_dict(dict1, dict2, inside=[]):
    """
    merge dict2 in to dict1 and return it
    """
    for k in list(dict2):
        old = dict1.get(k, None)
        new = dict2[k]

        if old is None:
            dict1[k] = new
            continue

        if isinstance(old, dict) and isinstance(new, dict):
            dict1[k] = _merge_dict(old, new, inside + [k])
            continue

        if isinstance(old, list) and isinstance(new, list):
            dict1[k].extend(new)
            continue

        if old == new:
            # A definition shared between multiple files
            # if k not in (kw.valueless, kw.multi, kw.hidden, kw.node, kw.summary, kw.owner, kw.priority):
            if not kw.found(k):
                _fatal('parsing issue - undefined leaf?')
            continue

        _fatal(f'parsing issue with ({k})\n\n{old}\n\n{new}')
    return dict1

def _format_nodes(inside, conf, xml):
    r = {}
    while conf:
        nodetype = ''
        nodename = ''
        if 'node' in conf.keys():
            nodetype = 'node'
            nodename = kw.plainNode
        elif 'leafNode' in conf.keys():
            nodetype = 'leafNode'
            nodename = kw.leafNode
        elif 'tagNode' in conf.keys():
            nodetype = 'tagNode'
            nodename = kw.tagNode
        elif 'syntaxVersion' in conf.keys():
            r[kw.version] = conf.pop('syntaxVersion')['@version']
            continue
        else:
            _fatal(conf.keys())

        nodes = conf.pop(nodetype)
        if isinstance(nodes, list):
            for node in nodes:
                name = node.pop('@name')
                into = inside + [name]
                r[name] = _format_node(into, node, xml)
                r[name][kw.node] = nodename
                xml[kw.tags].append(' '.join(into))
        else:
            node = nodes
            name = node.pop('@name')
            into = inside + [name]

            r[name] = _format_node(inside + [name], node, xml)
            r[name][kw.node] = nodename
            xml[kw.tags].append(' '.join(into))
    return r


def _set_validator(r, validator):
    v = {}
    while validator:
        if '@name' in validator:
            v[kw.name] = validator.pop('@name')
        elif '@argument' in validator:
            v[kw.argument] = validator.pop('@argument')
        else:
            _fatal(validator)
    r[kw.constraint][kw.validator].append(v)


def _format_node(inside, conf, xml):
    r = {
        kw.valueless: False,
        kw.multi: False,
        kw.hidden: False,
    }

    if '@owner' in conf:
        owner = conf.pop('@owner', '')
        r[kw.owner] = owner
        xml[kw.owners][' '.join(inside)] = owner

    while conf:
        keys = conf.keys()
        if 'children' in keys:
            children = conf.pop('children')

            if isinstance(conf, list):
                for child in children:
                    r = _safe_update(r, _format_nodes(inside, child, xml))
            else:
                child = children
                r = _safe_update(r, _format_nodes(inside, child, xml))

        elif 'properties' in keys:
            properties = conf.pop('properties')

            while properties:
                if 'help' in properties:
                    helpname = properties.pop('help')
                    r[kw.help] = {}
                    r[kw.help][kw.summary] = helpname

                elif 'valueHelp' in properties:
                    valuehelps = properties.pop('valueHelp')
                    if kw.valuehelp in r[kw.help]:
                        _fatal(valuehelps)
                    r[kw.help][kw.valuehelp] = []
                    if isinstance(valuehelps, list):
                        for valuehelp in valuehelps:
                            r[kw.help][kw.valuehelp].append(dict(valuehelp))
                    else:
                        valuehelp = valuehelps
                        r[kw.help][kw.valuehelp].append(dict(valuehelp))

                elif 'constraint' in properties:
                    constraint = properties.pop('constraint')
                    r[kw.constraint] = {}
                    while constraint:
                        if 'regex' in constraint:
                            regexes = constraint.pop('regex')
                            if kw.regex in kw.constraint:
                                _fatal(regexes)
                            r[kw.constraint][kw.regex] = []
                            if isinstance(regexes, list):
                                r[kw.constraint][kw.regex] = []
                                for regex in regexes:
                                    r[kw.constraint][kw.regex].append(regex)
                            else:
                                regex = regexes
                                r[kw.constraint][kw.regex].append(regex)
                        elif 'validator' in constraint:
                            validators = constraint.pop('validator')
                            if kw.validator in r[kw.constraint]:
                                _fatal(validators)
                            r[kw.constraint][kw.validator] = []
                            if isinstance(validators, list):
                                for validator in validators:
                                    _set_validator(r, validator)
                            else:
                                validator = validators
                                _set_validator(r, validator)
                        else:
                            _fatal(constraint)

                elif 'constraintErrorMessage' in properties:
                    r[kw.error] = properties.pop('constraintErrorMessage')

                elif 'valueless' in properties:
                    properties.pop('valueless')
                    r[kw.valueless] = True

                elif 'multi' in properties:
                    properties.pop('multi')
                    r[kw.multi] = True

                elif 'hidden' in properties:
                    properties.pop('hidden')
                    r[kw.hidden] = True

                elif 'completionHelp' in properties:
                    completionHelp = properties.pop('completionHelp')
                    r[kw.completion] = {}
                    while completionHelp:
                        if 'list' in completionHelp:
                            r[kw.completion][kw.list] = completionHelp.pop('list')
                        elif 'script' in completionHelp:
                            r[kw.completion][kw.script] = completionHelp.pop('script')
                        elif 'path' in completionHelp:
                            r[kw.completion][kw.path] = completionHelp.pop('path')
                        else:
                            _fatal(completionHelp.keys())

                elif 'priority' in properties:
                    priority = int(properties.pop('priority'))
                    r[kw.priority] = priority
                    xml[kw.priorities].setdefault(priority, []).append(' '.join(inside))

                else:
                    _fatal(properties.keys())

        elif 'defaultValue' in keys:
            default = conf.pop('defaultValue')
            x = xml[kw.default]
            for k in inside[:-1]:
                x = x.setdefault(k, {})
            x[inside[-1]] = '' if default is None else default

        elif 'command' in keys:
            command = conf.pop('command')
            r[kw.command] = command

        else:
            _fatal(conf)

    return r


def _add_root_node(xml):
    # fix the configuration root node for completion
    # as we moved all the name "up" the chain to use them as index.
    xml[kw.tree][kw.node] = kw.plainNode
    return xml


def from_folder(folder):
    """
    read all the xml files in the folder and return a parsed python dict
    """

    xml = definition.XML()
    for fname in listing(folder):
        parsed = xmltodict.parse(include(fname))
        formated = _format_nodes([], parsed['interfaceDefinition'], xml)
        _merge_dict(xml[kw.tree], formated)

    return _add_root_node(xml)


def from_file(fname):
    """
    read an xml file and return a parsed python dict
    """

    xml = definition.XML()
    with open(fname, 'rt') as r:
        print(f'reading {fname}\n')
        raw = r.read()
        # using r instead of raw does not work!
        parsed = xmltodict.parse(raw)
        xml[kw.tree] = _format_nodes([], parsed['interfaceDefinition'], xml)

    return _add_root_node(xml)
