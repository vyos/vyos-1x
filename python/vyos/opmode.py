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

import typing


def _is_op_mode_function_name(name):
    from re import match

    if match(r"^(show|clear|reset|restart)", name):
        return True
    else:
        return False

def _is_show(name):
    from re import match

    if match(r"^show", name):
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
        t.__args__[0]
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
        for opt in type_hints:
            th = type_hints[opt]

            # Show commands require an option to choose between raw JSON and human-readable
            # formatted output.
            # For interactive use, they default to formatted output.
            if (function_name == "show") and (opt == "raw"):
                subparser.add_argument(f"--raw",  action='store_true')
            elif _is_optional_type(th):
                subparser.add_argument(f"--{opt}", type=_get_arg_type(th), default=None)
            else:
                subparser.add_argument(f"--{opt}", type=_get_arg_type(th), required=True)

    # Get options as a dict rather than a namespace,
    # so that we can modify it and pack for passing to functions
    args = vars(parser.parse_args())

    func = functions[args["subcommand"]]

    # Remove the subcommand from the arguments,
    # it would cause an extra argument error when we pass the dict to a function
    del args["subcommand"]

    if "raw" not in args:
        args["raw"] = False

    if function_name == "show":
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

