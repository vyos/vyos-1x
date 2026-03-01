#!/usr/bin/env python3
#
# Copyright VyOS maintainers and contributors <maintainers@vyos.io>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 2 or later as
# published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import json
import os
import pty
import pwd
import socket
import time
import unittest

from base_vyostest_shim import VyOSUnitTestSHIM
from vyos.utils.file import read_file
from vyos.utils.process import cmd

from vyos.configsession import ConfigSessionError

SERVICE_NAMES = [ "gpsd.socket", "gpsd.service" ]
CONFIG_FILE = "/run/gpsd/default"
SOCKET_FILE = "/lib/systemd/system/gpsd.socket"


def _systemctl(*args: str) -> str:
    out = cmd(" ".join(["systemctl", *args]))
    return out.strip() if isinstance(out, str) else str(out).strip()


def _gpsd_get_devices(host, port, timeout=3.0):
    """
    Connect to gpsd, request a DEVICES report, and return it as a dict.
    """
    with socket.create_connection((host, port), timeout=timeout) as sock:
        sock.settimeout(timeout)
        f = sock.makefile("rwb", buffering=0)

        def send(cmd: str) -> None:
            f.write(cmd.encode("ascii"))

        def recv_json_line(deadline: float):
            # Read line-delimited JSON messages until we see one we want
            while time.time() < deadline:
                line = f.readline()
                if not line:
                    raise AssertionError("gpsd closed the connection")
                line = line.strip()
                if not line:
                    continue
                try:
                    msg = json.loads(line.decode("utf-8", errors="strict"))
                except json.JSONDecodeError:
                    # gpsd should send JSON lines; if it doesn't, treat as protocol error
                    raise AssertionError(f"non-JSON from gpsd: {line!r}")
                return msg
            raise TimeoutError("timed out waiting for gpsd JSON")

        deadline = time.time() + timeout

        # Enable JSON watcher output.
        send('?WATCH={"enable":true,"json":true}\n')

        # Ask specifically for devices (should return {"class":"DEVICES", ...}).
        send("?DEVICES;\n")

        # Read messages until we get the DEVICES class
        while True:
            msg = recv_json_line(deadline)
            if isinstance(msg, dict) and msg.get("class") == "DEVICES":
                return msg
            # otherwise ignore (e.g. VERSION, WATCH, TPV, SKY)


def _assert_gpsd_devices_contains(expected_paths, host,
                                  port, timeout=3.0):
    """
    expected_paths: iterable of device paths you expect, e.g. ["/dev/ttyACM0"].
    Raises AssertionError if missing.
    """
    report = None
    attempt = 0
    while attempt < 3:
        try:
            report = _gpsd_get_devices(host=host, port=port, timeout=timeout)
            break
        except TimeoutError:
            attempt += 1
            if attempt == 3:
                raise

    devices = report.get("devices", [])
    if not isinstance(devices, list):
        raise AssertionError(
            f"gpsd DEVICES report has unexpected 'devices' type: {type(devices)}")

    got_paths = []
    for d in devices:
        if isinstance(d, dict) and "path" in d:
            got_paths.append(d["path"])

    missing = [p for p in expected_paths if p not in got_paths]
    if missing:
        raise AssertionError(
            f"gpsd devices missing expected path(s): {missing}. "
            f"Got paths: {got_paths}. Full report: {report}"
        )

    return report


def _get_pty() -> tuple[int, str]:
    # Create a PTY to act as a "virtual" GPS device
    primary_fd, secondary_fd = pty.openpty()
    secondary_path = os.ttyname(secondary_fd)

    gpsd = pwd.getpwnam("gpsd")
    os.fchown(secondary_fd, gpsd.pw_uid, gpsd.pw_gid)
    os.fchmod(secondary_fd, 0o600)  # gpsd user only

    # Close our copy of secondary_fd; gpsd will open by path.
    os.close(secondary_fd)
    return primary_fd, secondary_path


class TestServiceGPSD(VyOSUnitTestSHIM.TestCase):
    @classmethod
    def setUpClass(cls):
        # Initializes cls._session (required)
        super().setUpClass()

        cls.base_path = ["service", "gpsd"]

        # Ensure clean slate (pylint-friendly in classmethod context)
        cls.cli_delete(cls, cls.base_path)
        cls.cli_commit(cls)

    @classmethod
    def tearDownClass(cls):
        # Cleanup and close the session
        cls.cli_delete(cls, cls.base_path)
        cls.cli_commit(cls)
        super().tearDownClass()

    def tearDown(self):
        # Normal instance methods: no special handling needed
        self.cli_delete(self.base_path)
        self.cli_commit()

    def _assert_service_state(self, *, enabled: bool | None = None, active: bool | None = None):
        # Small blocking wait here to make sure systemctl has stabilised
        time.sleep(0.5)

        for service in SERVICE_NAMES:
            if enabled is not None:
                try:
                    st = _systemctl("is-enabled", f"{service}")
                except OSError:
                    st = "disabled"
                if enabled:
                    self.assertIn(st, "enabled", f"Expected service {service} to be enabled but it was {st}")
                else:
                    self.assertIn(st, "disabled", f"Expected service {service} to be disabled but it was {st}")

            if active is not None:
                try:
                    st = _systemctl("is-active", f"{service}")
                except OSError:
                    st = "inactive"

                if active:
                    self.assertIn(st, "active", f"Expected service {service} to be active but it was {st}")
                else:
                    self.assertIn(st, "inactive", f"Expected service {service} to be inactive but it was {st}")

    def test_01_basic_enable_and_render(self):
        primary_fd, secondary_path = _get_pty()

        try:
            self.cli_set(self.base_path + ["source", secondary_path])
            self.cli_commit()

            data = read_file(CONFIG_FILE)

            self.assertIn(f'DEVICES="{secondary_path}"', data, "Incorrect devices in gpsd config file")
            self.assertIn('GPSD_OPTIONS="-S 2947 "', data, "Incorrect options in gpsd config file")
            self.assertIn('USBAUTO="true"', data, "USBAUTO set incorrectly in gpsd config file")

            socket = read_file(SOCKET_FILE)

            self.assertIn("ListenStream=[::1]:2947", socket, "Incorrect ListenStream in gpsd.socket")
            self.assertIn("ListenStream=127.0.0.1:2947", socket, "Incorrect ListenStream in gpsd.socket")

            self._assert_service_state(enabled=True, active=True)

            _assert_gpsd_devices_contains([secondary_path], "127.0.0.1", 2947, 3.0)
        finally:
            # Cleanup
            try:
                os.close(primary_fd)
            except OSError:
                pass

    def test_02_full_option_enable(self):
        primary_fd, secondary_path = _get_pty()

        try:
            self.cli_set(self.base_path + ["source", secondary_path])
            self.cli_set(self.base_path + ["source", "udp://127.0.0.1:9999"])

            self.cli_set(self.base_path + ["bad-time"])
            self.cli_set(self.base_path + ["disable-usb-auto"])
            self.cli_set(self.base_path + ["listen-any"])
            self.cli_set(self.base_path + ["no-wait"])
            self.cli_set(self.base_path + ["read-only"])

            self.cli_set(self.base_path + ["debug", "2"])
            self.cli_set(self.base_path + ["framing", "8N1"])
            self.cli_set(self.base_path + ["speed", "9600"])
            self.cli_set(self.base_path + ["port", "2948"])

            self.cli_commit()

            data = read_file(CONFIG_FILE)

            self.assertIn(f'DEVICES="{secondary_path} udp://127.0.0.1:9999"', data, "Incorrect devices in gpsd config file")
            self.assertIn('GPSD_OPTIONS="-b -D 2 -f 8N1 -G -n -r -S 2948 -s 9600 "', data, "Incorrect options in gpsd config file")

            # usb-auto should be disabled
            self.assertIn('USBAUTO="false"', data, "USBAUTO set incorrectly in gpsd config file")

            socket = read_file(SOCKET_FILE)

            self.assertIn("ListenStream=[::]:2948", socket, "Incorrect ListenStream in gpsd.socket")
            self.assertIn("ListenStream=0.0.0.0:2948", socket, "Incorrect ListenStream in gpsd.socket")

            self._assert_service_state(enabled=True, active=True)

            _assert_gpsd_devices_contains([secondary_path, "udp://127.0.0.1:9999"], "127.0.0.1", 2948, 3.0)
        finally:
            # Cleanup
            try:
                os.close(primary_fd)
            except OSError:
                pass

    def test_03_bad_config(self):
        # Deliberately set bad config and make sure errors are thrown
        bad_sources = [self.base_path + ["source", "/file/that/doesnt/exist"],
                       self.base_path + ["source", "http://127.0.0.1:12345"]]

        for bad_source in bad_sources:
            with self.assertRaises(ConfigSessionError):
                self.cli_set(bad_source)

        # Need to set a valid source to test other failures
        self.cli_set(self.base_path + ["source", "/dev/null"])

        bad_paths = [ self.base_path + ["debug", "512"],
                      self.base_path + ["framing", "4Z5"],
                      self.base_path + ["speed", "5000"],
                      self.base_path + ["port", "65537"],
                      self.base_path + ["usb-auto", "foobar123"] ]

        for bad_path in bad_paths:
            with self.assertRaises(ConfigSessionError):
                self.cli_set(bad_path)

    def test_04_disable_service_on_delete(self):
        primary_fd, secondary_path = _get_pty()

        try:
            self.cli_set(self.base_path + ["source", "/dev/null"])
            self.cli_commit()
            self._assert_service_state(enabled=True, active=True)

            self.cli_delete(self.base_path)
            self.cli_commit()
            self._assert_service_state(enabled=False, active=False)
        finally:
            # Cleanup
            try:
                os.close(primary_fd)
            except OSError:
                pass


if __name__ == "__main__":
    unittest.main(verbosity=2, failfast=VyOSUnitTestSHIM.TestCase.debug_on)
