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
# You should have received a copy of the GNU Lesser General Public
# License along with this library.  If not, see <http://www.gnu.org/licenses/>.

def print_error(str='', end='\n'):
    """
    Print `str` to stderr, terminated with `end`.
    Used for warnings and out-of-band messages to avoid mangling precious
     stdout output.
    """
    import sys
    sys.stderr.write(str)
    sys.stderr.write(end)
    sys.stderr.flush()

def ask_input(question, default='', numeric_only=False, valid_responses=[]):
    question_out = question
    if default:
        question_out += f' (Default: {default})'
    response = ''
    while True:
        response = input(question_out + ' ').strip()
        if not response and default:
            return default
        if numeric_only:
            if not response.isnumeric():
                print("Invalid value, try again.")
                continue
            response = int(response)
        if valid_responses and response not in valid_responses:
            print("Invalid value, try again.")
            continue
        break
    return response

def ask_yes_no(question, default=False) -> bool:
    """Ask a yes/no question via input() and return their answer."""
    from sys import stdout
    default_msg = "[Y/n]" if default else "[y/N]"
    while True:
        try:
            stdout.write("%s %s " % (question, default_msg))
            c = input().lower()
            if c == '':
                return default
            elif c in ("y", "ye", "yes"):
                return True
            elif c in ("n", "no"):
                return False
            else:
                stdout.write("Please respond with yes/y or no/n\n")
        except EOFError:
            stdout.write("\nPlease respond with yes/y or no/n\n")

def is_interactive():
    """Try to determine if the routine was called from an interactive shell."""
    import os, sys
    return os.getenv('TERM', default=False) and sys.stderr.isatty() and sys.stdout.isatty()

def is_dumb_terminal():
    """Check if the current TTY is dumb, so that we can disable advanced terminal features."""
    import os
    return os.getenv('TERM') in ['vt100', 'dumb']

def select_entry(l: list, list_msg: str = '', prompt_msg: str = '') -> str:
    """Select an entry from a list

    Args:
        l (list): a list of entries
        list_msg (str): a message to print before listing the entries
        prompt_msg (str): a message to print as prompt for selection

    Returns:
        str: a selected entry
    """
    en = list(enumerate(l, 1))
    print(list_msg)
    for i, e in en:
        print(f'\t{i}: {e}')
    select = ask_input(prompt_msg, numeric_only=True,
                       valid_responses=range(1, len(l)+1))
    return next(filter(lambda x: x[0] == select, en))[1]
