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

def make_progressbar():
    """
    Make a procedure that takes two arguments `done` and `total` and prints a
     progressbar based on the ratio thereof, whose length is determined by the
     width of the terminal.
    """
    import shutil, math
    col, _ = shutil.get_terminal_size()
    col = max(col - 15, 20)
    def print_progressbar(done, total):
        if done <= total:
            increment = total / col
            length = math.ceil(done / increment)
            percentage = str(math.ceil(100 * done / total)).rjust(3)
            print_error(f'[{length * "#"}{(col - length) * "_"}] {percentage}%', '\r')
            # Print a newline so that the subsequent prints don't overwrite the full bar.
        if done == total:
            print_error()
    return print_progressbar

def make_incremental_progressbar(increment: float):
    """
    Make a generator that displays a progressbar that grows monotonically with
     every iteration.
    First call displays it at 0% and every subsequent iteration displays it
     at `increment` increments where 0.0 < `increment` < 1.0.
    Intended for FTP and HTTP transfers with stateless callbacks.
    """
    print_progressbar = make_progressbar()
    total = 0.0
    while total < 1.0:
        print_progressbar(total, 1.0)
        yield
        total += increment
    print_progressbar(1, 1)
    # Ignore further calls.
    while True:
        yield

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
