# Copyright 2023-2024 VyOS maintainers and contributors <maintainers@vyos.io>
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

import math
import os
import signal
import subprocess

from vyos.utils.io import is_dumb_terminal
from vyos.utils.io import print_error

class Progressbar:
    def __init__(self, step=None):
        self.total = 0.0
        self.step = step
        # Silently ignore all calls if terminal capabilities are lacking.
        # This will also prevent the output from littering Ansible logs,
        # as `ansible.netcommon.network_cli' coaxes the terminal into believing
        # it is interactive.
        self._dumb = is_dumb_terminal()
    def __enter__(self):
        if not self._dumb:
            # Recalculate terminal width with every window resize.
            signal.signal(signal.SIGWINCH, lambda signum, frame: self._update_cols())
            # Disable line wrapping to prevent the staircase effect.
            subprocess.run(['tput', 'rmam'], check=False)
            self._update_cols()
            # Print an empty progressbar with entry.
            self.progress(0, 1)
        return self
    def __exit__(self, exc_type, kexc_val, exc_tb):
        if not self._dumb:
            # Revert to the default SIGWINCH handler (ie nothing).
            signal.signal(signal.SIGWINCH, signal.SIG_DFL)
            # Reenable line wrapping.
            subprocess.run(['tput', 'smam'], check=False)
    def _update_cols(self):
        # `os.get_terminal_size()' is fast enough for our purposes.
        self.col = max(os.get_terminal_size().columns - 15, 20)
    def increment(self):
        """
        Stateful progressbar taking the step fraction at init and no input at
        callback (for FTP)
        """
        if self.step:
            if self.total < 1.0:
                self.total += self.step
            if self.total >= 1.0:
                self.total = 1.0
                # Ignore superfluous calls caused by fuzzy FTP size calculations.
                self.step = None
            self.progress(self.total, 1.0)
    def progress(self, done, total):
        """
        Stateless progressbar taking no input at init and current progress with
        final size at callback (for SSH)
        """
        if done <= total and not self._dumb:
            length = math.ceil(self.col * done / total)
            percentage = str(math.ceil(100 * done / total)).rjust(3)
            # Carriage return at the end will make sure the line will get overwritten.
            print_error(f'[{length * "#"}{(self.col - length) * "_"}] {percentage}%', end='\r')
        # Print a newline to make sure the full progressbar doesn't get overwritten by the next line.
        if done == total:
            print_error()
