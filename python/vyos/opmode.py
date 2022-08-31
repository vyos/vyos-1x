# Copyright 2022 VyOS maintainers and contributors <maintainers@vyos.io>
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

import re
import sys
import typing


class Error(Exception):
    """ Any error that makes requested operation impossible to complete
        for reasons unrelated to the user input or script logic.
    """
    pass

class UnconfiguredSubsystem(Error):
    """ Requested operation is valid, but cannot be completed
        because corresponding subsystem is not configured and running.
    """
    pass

class DataUnavailable(Error):
    """ Requested operation is valid, but cannot be completed
        because data for it is not available.
        This error MAY be treated as temporary because such issues
        are often caused by transient events such as service restarts.
    """
    pass

class PermissionDenied(Error):
    """ Requested operation is valid, but the caller has no permission
        to perform it.
    """
    pass


def _is_op_mode_function_name(name):
    if re.match(r"^(show|clear|reset|restart)", name):
        return True
    else:
        return False

def _is_show(name):
    if re.match(r"^show", name):
        return True
    else:
        return False

def _get_op_mode_functions(module):
    from inspect import getmembers, isfunction

    # Get all functions in that module
    funcs = getmembers(module, isfunction)

    # getmembers returns (name, func) tuples
    funcs = list(filter(lambda ft: _is_op_mode_function_name(ft[0]), funcs))

    funcs_dict = {}
    for (name, thunk) in funcs:
        funcs_dict[name] = thunk

    return funcs_dict

def _is_optional_type(t):
    # Optional[t] is internally an alias for Union[t, NoneType]
    # and there's no easy way to get union members it seems
    if (type(t) == typing._UnionGenericAlias):
        if (len(t.__args__) == 2):
            if t.__args__[1] == type(None):
                return True

    return False

def _get_arg_type(t):
    """ Returns the type itself if it's a primitive type,
        or the "real" type of typing.Optional

       Doesn't work with anything else at the moment!
    """
    if _is_optional_type(t):
        return t.__args__[0]
    else:
        return t

def run(module):
    from argparse import ArgumentParser

    functions = _get_op_mode_functions(module)

    parser = ArgumentParser()
    subparsers = parser.add_subparsers(dest="subcommand")

    for function_name in functions:
        subparser = subparsers.add_parser(function_name, help=functions[function_name].__doc__)

        type_hints = typing.get_type_hints(functions[function_name])
        if 'return' in type_hints:
            del type_hints['return']
        for opt in type_hints:
            th = type_hints[opt]

            if _get_arg_type(th) == bool:
                subparser.add_argument(f"--{opt}", action='store_true')
            else:
                if _is_optional_type(th):
                    subparser.add_argument(f"--{opt}", type=_get_arg_type(th), default=None)
                else:
                    subparser.add_argument(f"--{opt}", type=_get_arg_type(th), required=True)

    # Get options as a dict rather than a namespace,
    # so that we can modify it and pack for passing to functions
    args = vars(parser.parse_args())

    if not args["subcommand"]:
        print("Subcommand required!")
        parser.print_usage()
        sys.exit(1)

    function_name = args["subcommand"]
    func = functions[function_name]

    # Remove the subcommand from the arguments,
    # it would cause an extra argument error when we pass the dict to a function
    del args["subcommand"]

    # Show commands must always get the "raw" argument,
    # but other commands (clear/reset/restart) should not,
    # because they produce no output and it makes no sense for them.
    if ("raw" not in args) and _is_show(function_name):
        args["raw"] = False

    if re.match(r"^show", function_name):
        # Show commands are slightly special:
        # they may return human-formatted output
        # or a raw dict that we need to serialize in JSON for printing
        res = func(**args)
        if not args["raw"]:
            return res
        else:
            from json import dumps
            return dumps(res, indent=4)
    else:
        # Other functions should not return anything,
        # although they may print their own warnings or status messages
        func(**args)

