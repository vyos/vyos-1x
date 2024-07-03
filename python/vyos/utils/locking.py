# Copyright 2024 VyOS maintainers and contributors <maintainers@vyos.io>
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

import fcntl
import re
import time
from pathlib import Path


class LockTimeoutError(Exception):
    """Custom exception raised when lock acquisition times out."""

    pass


class InvalidLockNameError(Exception):
    """Custom exception raised when the lock name is invalid."""

    pass


class Lock:
    """Lock class to acquire and release a lock file"""

    def __init__(self, lock_name: str) -> None:
        """Lock class constructor

        Args:
            lock_name (str): Name of the lock file

        Raises:
            InvalidLockNameError: If the lock name is invalid
        """
        # Validate lock name
        if not re.match(r'^[a-zA-Z0-9_\-]+$', lock_name):
            raise InvalidLockNameError(f'Invalid lock name: {lock_name}')

        self.__lock_dir = Path('/run/vyos/lock')
        self.__lock_dir.mkdir(parents=True, exist_ok=True)

        self.__lock_file_path: Path = self.__lock_dir / f'{lock_name}.lock'
        self.__lock_file = None

        self._is_locked = False

    def __del__(self) -> None:
        """Ensure the lock file is removed when the object is deleted"""
        self.release()

    @property
    def is_locked(self) -> bool:
        """Check if the lock is acquired

        Returns:
            bool: True if the lock is acquired, False otherwise
        """
        return self._is_locked

    def __unlink_lockfile(self) -> None:
        """Remove the lock file if it is not currently locked."""
        try:
            with self.__lock_file_path.open('w') as f:
                fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
                self.__lock_file_path.unlink(missing_ok=True)
        except IOError:
            # If we cannot acquire the lock, it means another process has it, so we do nothing.
            pass

    def acquire(self, timeout: int = 0) -> None:
        """Acquire a lock file

        Args:
            timeout (int, optional): A time to wait for lock. Defaults to 0.

        Raises:
            LockTimeoutError: If lock could not be acquired within timeout
        """
        start_time: float = time.time()
        while True:
            try:
                self.__lock_file = self.__lock_file_path.open('w')
                fcntl.flock(self.__lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
                self._is_locked = True
                return
            except IOError:
                if timeout > 0 and (time.time() - start_time) >= timeout:
                    if self.__lock_file:
                        self.__lock_file.close()
                    raise LockTimeoutError(
                        f'Could not acquire lock within {timeout} seconds'
                    )
                time.sleep(0.1)

    def release(self) -> None:
        """Release a lock file"""
        if self.__lock_file and self._is_locked:
            try:
                fcntl.flock(self.__lock_file, fcntl.LOCK_UN)
                self._is_locked = False
            finally:
                self.__lock_file.close()
                self.__lock_file = None
                self.__unlink_lockfile()
