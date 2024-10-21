# Copyright 2022-2024 VyOS maintainers and contributors <maintainers@vyos.io>
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
from humps import decamelize


class Error(Exception):
    """Any error that makes requested operation impossible to complete
    for reasons unrelated to the user input or script logic.

    This is the base class, scripts should not use it directly
    and should raise more specific errors instead,
    whenever possible.
    """

    pass


class UnconfiguredSubsystem(Error):
    """Requested operation is valid, but cannot be completed
    because corresponding subsystem is not configured
    and thus is not running.
    """

    pass


class UnconfiguredObject(UnconfiguredSubsystem):
    """Requested operation is valid but cannot be completed
    because its parameter refers to an object that does not exist
    in the system configuration.
    """

    pass


class DataUnavailable(Error):
    """Requested operation is valid, but cannot be completed
    because data for it is not available.
    This error MAY be treated as temporary because such issues
    are often caused by transient events such as service restarts.
    """

    pass


class PermissionDenied(Error):
    """Requested operation is valid, but the caller has no permission
    to perform it.
    """

    pass


class InsufficientResources(Error):
    """Requested operation and its arguments are valid but the system
    does not have enough resources (such as drive space or memory)
    to complete it.
    """

    pass


class UnsupportedOperation(Error):
    """Requested operation is technically valid but is not implemented yet."""

    pass


class IncorrectValue(Error):
    """Requested operation is valid, but an argument provided has an
    incorrect value, preventing successful completion.
    """

    pass


class CommitInProgress(Error):
    """Requested operation is valid, but not possible at the time due
    to a commit being in progress.
    """

    pass


class InternalError(Error):
    """Any situation when VyOS detects that it could not perform
    an operation correctly due to logic errors in its own code
    or errors in underlying software.
    """

    pass


def _is_op_mode_function_name(name):
    if re.match(
        r'^(show|clear|reset|restart|add|update|delete|generate|set|renew|release|execute|import|mtr)',
        name,
    ):
        return True
    else:
        return False


def _capture_output(name):
    if re.match(r'^(show|generate)', name):
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
    for name, thunk in funcs:
        funcs_dict[name] = thunk

    return funcs_dict


def _is_optional_type(t):
    # Optional[t] is internally an alias for Union[t, NoneType]
    # and there's no easy way to get union members it seems
    if type(t) is typing._UnionGenericAlias:
        if len(t.__args__) == 2:
            if t.__args__[1] is type(None):
                return True

    return False


def _get_arg_type(t):
    """Returns the type itself if it's a primitive type,
    or the "real" type of typing.Optional

    Doesn't work with anything else at the moment!
    """
    if _is_optional_type(t):
        return t.__args__[0]
    else:
        return t


def _is_literal_type(t):
    if _is_optional_type(t):
        t = _get_arg_type(t)

    if typing.get_origin(t) == typing.Literal:
        return True

    return False


def _get_literal_values(t):
    """Returns the tuple of allowed values for a Literal type"""
    if not _is_literal_type(t):
        return tuple()
    if _is_optional_type(t):
        t = _get_arg_type(t)

    return typing.get_args(t)


def _normalize_field_name(name):
    # Convert the name to string if it is not
    # (in some cases they may be numbers)
    name = str(name)

    # Replace all separators with underscores
    name = re.sub(r'(\s|[\(\)\[\]\{\}\-\.\,:\"\'\`])+', '_', name)

    # Replace specific characters with textual descriptions
    name = re.sub(r'@', '_at_', name)
    name = re.sub(r'%', '_percentage_', name)
    name = re.sub(r'~', '_tilde_', name)

    # Force all letters to lowercase
    name = name.lower()

    # Remove leading and trailing underscores, if any
    name = re.sub(r'(^(_+)(?=[^_])|_+$)', '', name)

    # Ensure there are only single underscores
    name = re.sub(r'_+', '_', name)

    return name


def _normalize_dict_field_names(old_dict):
    new_dict = {}

    for key in old_dict:
        new_key = _normalize_field_name(key)
        new_dict[new_key] = _normalize_field_names(old_dict[key])

    # Sanity check
    if len(old_dict) != len(new_dict):
        raise InternalError('Dictionary fields do not allow unique normalization')
    else:
        return new_dict


def _normalize_field_names(value):
    if isinstance(value, dict):
        return _normalize_dict_field_names(value)
    elif isinstance(value, list):
        return list(map(lambda v: _normalize_field_names(v), value))
    else:
        return value


def run(module):
    from argparse import ArgumentParser

    functions = _get_op_mode_functions(module)

    parser = ArgumentParser()
    subparsers = parser.add_subparsers(dest='subcommand')

    for function_name in functions:
        subparser = subparsers.add_parser(
            function_name, help=functions[function_name].__doc__
        )

        type_hints = typing.get_type_hints(functions[function_name])
        if 'return' in type_hints:
            del type_hints['return']
        for opt in type_hints:
            th = type_hints[opt]

            # Function argument names use underscores as separators
            # but command-line options should use hyphens
            # Without this, we'd get options like "--foo_bar"
            opt = re.sub(r'_', '-', opt)

            if _get_arg_type(th) is bool:
                subparser.add_argument(f'--{opt}', action='store_true')
            else:
                if _is_optional_type(th):
                    if _is_literal_type(th):
                        subparser.add_argument(
                            f'--{opt}',
                            choices=list(_get_literal_values(th)),
                            default=None,
                        )
                    else:
                        subparser.add_argument(
                            f'--{opt}',
                            type=_get_arg_type(th),
                            default=None,
                        )
                else:
                    if _is_literal_type(th):
                        subparser.add_argument(
                            f'--{opt}',
                            choices=list(_get_literal_values(th)),
                            required=True,
                        )
                    else:
                        subparser.add_argument(
                            f'--{opt}', type=_get_arg_type(th), required=True
                        )

    # Get options as a dict rather than a namespace,
    # so that we can modify it and pack for passing to functions
    args = vars(parser.parse_args())

    if not args['subcommand']:
        print('Subcommand required!')
        parser.print_usage()
        sys.exit(1)

    function_name = args['subcommand']
    func = functions[function_name]

    # Remove the subcommand from the arguments,
    # it would cause an extra argument error when we pass the dict to a function
    del args['subcommand']

    # Show and generate commands must always get the "raw" argument,
    # but other commands (clear/reset/restart/add/delete) should not,
    # because they produce no output and it makes no sense for them.
    if ('raw' not in args) and _capture_output(function_name):
        args['raw'] = False

    if _capture_output(function_name):
        # Show and generate commands are slightly special:
        # they may return human-formatted output
        # or a raw dict that we need to serialize in JSON for printing
        res = func(**args)
        if not args['raw']:
            return res
        else:
            if not isinstance(res, dict) and not isinstance(res, list):
                raise InternalError(
                    f'Bare literal is not an acceptable raw output, must be a list or an object.\
                    The output was:{res}'
                )
            res = decamelize(res)
            res = _normalize_field_names(res)
            from json import dumps

            return dumps(res, indent=4)
    else:
        # Other functions should not return anything,
        # although they may print their own warnings or status messages
        func(**args)
