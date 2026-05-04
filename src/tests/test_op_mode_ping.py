# Copyright VyOS maintainers and contributors <maintainers@vyos.io>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 2 or later as
# published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import contextlib
import importlib.util
import io
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch


def load_ping_module():
    module_path = Path(__file__).resolve().parents[1] / 'op_mode' / 'ping.py'
    spec = importlib.util.spec_from_file_location('op_mode_ping', module_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ping = load_ping_module()


class FakeNpingProcess:
    def __init__(self, lines, returncode=0):
        self.stdout = iter(lines)
        self.returncode = returncode
        self.terminated = False

    def wait(self):
        return self.returncode

    def terminate(self):
        self.terminated = True


class TestVyOSOpModePingTcp(TestCase):
    def test_parse_tcp_args(self):
        config = ping.parse_tcp_args(
            [
                'example.com',
                'tcp',
                'port',
                '443',
                'count',
                '3',
                'interface',
                'eth0',
                'source-address',
                '192.0.2.1',
                'vrf',
                'red',
            ]
        )

        self.assertEqual(config['host'], 'example.com')
        self.assertEqual(config['port'], 443)
        self.assertEqual(config['count'], 3)
        self.assertEqual(config['interface'], 'eth0')
        self.assertEqual(config['source_address'], '192.0.2.1')
        self.assertEqual(config['vrf'], 'red')

    def test_parse_tcp_args_rejects_invalid_input(self):
        cases = [
            [],
            ['example.com'],
            ['example.com', 'tcp'],
            ['example.com', 'tcp', 'port', '0'],
            ['example.com', 'tcp', 'port', '65536'],
            ['example.com', 'tcp', 'port', 'ssh'],
            ['example.com', 'tcp', 'port', '443', 'count', '0'],
            [
                'example.com',
                'tcp',
                'port',
                '443',
                'source-address',
                'not-an-address',
            ],
            ['example.com', 'tcp', 'port', '443', 'bogus', 'value'],
        ]

        for argv in cases:
            with self.subTest(argv=argv):
                with self.assertRaises(ping.UsageError):
                    ping.parse_tcp_args(argv)

    def test_tcp_completion(self):
        icmp_options = (
            'audible adaptive allow-broadcast bypass-route count deadline '
            'do-not-fragment flood interface interval ipv4 ipv6 mark numeric '
            'no-loopback pattern timestamp tos quiet record-route size '
            'source-address ttl vrf verbose tcp'
        )

        self.assertEqual(
            ping.get_completion(ping.List(['ping', '192.0.2.1', ''])),
            icmp_options,
        )
        self.assertEqual(
            ping.get_completion(ping.List(['ping', '192.0.2.1', 'tc'])), 'tcp'
        )
        self.assertEqual(
            ping.get_completion(ping.List(['ping', '192.0.2.1', 'tcp', ''])),
            'count interface port source-address vrf',
        )
        self.assertEqual(
            ping.get_completion(ping.List(['ping', '192.0.2.1', 'tcp', 'p'])),
            'port',
        )
        self.assertEqual(
            ping.get_completion(ping.List(['ping', '192.0.2.1', 'tcp', 'port', ''])),
            '<port>',
        )

        completions = ping.get_completion(
            ping.List(['ping', '192.0.2.1', 'tcp', 'port', '443', ''])
        )
        self.assertIn('count', completions)
        self.assertIn('interface', completions)
        self.assertIn('source-address', completions)
        self.assertIn('vrf', completions)
        self.assertNotIn('port', completions)
        self.assertNotIn('tcp', completions)

    def test_has_tcp_option_respects_option_values(self):
        self.assertTrue(ping.has_tcp_option(['ping', '192.0.2.1', 'tcp']))
        self.assertTrue(ping.has_tcp_option(['ping', '192.0.2.1', 'tc']))
        self.assertFalse(ping.has_tcp_option(['ping', '192.0.2.1', 't']))
        self.assertFalse(ping.has_tcp_option(['ping', '192.0.2.1', 'pattern', 'tcp']))

    def test_build_tcp_nping_command_defaults_to_continuous(self):
        config = ping.parse_tcp_args(['example.com', 'tcp', 'port', '443'])

        self.assertEqual(
            ping.build_tcp_nping_command(config),
            [
                ping.NPING,
                '--tcp-connect',
                '--dest-port',
                '443',
                '--count',
                '0',
                '--delay',
                ping.TCP_DELAY,
                'example.com',
            ],
        )

    def test_build_tcp_nping_command_includes_count(self):
        config = ping.parse_tcp_args(
            ['example.com', 'tcp', 'port', '443', 'count', '2']
        )

        command = ping.build_tcp_nping_command(config)

        self.assertIn('--count', command)
        self.assertEqual(command[command.index('--count') + 1], '2')

    def test_build_tcp_nping_command_for_interface_uses_sudo(self):
        config = ping.parse_tcp_args(
            ['example.com', 'tcp', 'port', '443', 'interface', 'eth0']
        )

        self.assertEqual(
            ping.build_tcp_nping_command(config),
            [
                'sudo',
                ping.NPING,
                '--tcp-connect',
                '--dest-port',
                '443',
                '--count',
                '0',
                '--delay',
                ping.TCP_DELAY,
                '--interface',
                'eth0',
                'example.com',
            ],
        )

    def test_build_tcp_nping_command_for_source_address_uses_sudo(self):
        config = ping.parse_tcp_args(
            ['example.com', 'tcp', 'port', '443', 'source-address', '192.0.2.1']
        )

        self.assertEqual(
            ping.build_tcp_nping_command(config),
            [
                'sudo',
                ping.NPING,
                '--tcp-connect',
                '--dest-port',
                '443',
                '--count',
                '0',
                '--delay',
                ping.TCP_DELAY,
                '--source-ip',
                '192.0.2.1',
                'example.com',
            ],
        )

    def test_build_tcp_nping_command_for_vrf_uses_ip_vrf_exec(self):
        config = ping.parse_tcp_args(
            ['example.com', 'tcp', 'port', '443', 'vrf', 'red']
        )

        self.assertEqual(
            ping.build_tcp_nping_command(config),
            [
                'sudo',
                '/bin/ip',
                'vrf',
                'exec',
                'red',
                ping.NPING,
                '--tcp-connect',
                '--dest-port',
                '443',
                '--count',
                '0',
                '--delay',
                ping.TCP_DELAY,
                'example.com',
            ],
        )

    def test_build_tcp_nping_command_for_ipv6_literal(self):
        config = ping.parse_tcp_args(['2001:db8::1', 'tcp', 'port', '443'])

        command = ping.build_tcp_nping_command(config)

        self.assertIn('-6', command)

    def test_run_tcp_nping_returns_success_when_any_connection_succeeds(self):
        process = FakeNpingProcess(
            [
                'Starting Nping\n',
                'Nping done: 1 IP address pinged in 1.02 seconds\n',
                'Successful connections: 1\n',
            ]
        )

        def popen(command, **kwargs):
            self.assertEqual(command, [ping.NPING])
            self.assertEqual(kwargs['stdout'], ping.subprocess.PIPE)
            self.assertEqual(kwargs['stderr'], ping.subprocess.STDOUT)
            self.assertTrue(kwargs['text'])
            return process

        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            rc = ping.run_tcp_nping([ping.NPING], popen=popen)

        self.assertEqual(rc, 0)
        self.assertIn('Successful connections: 1', output.getvalue())

    def test_run_tcp_nping_returns_failure_when_no_connection_succeeds(self):
        process = FakeNpingProcess(['Successful connections: 0\n'])

        with contextlib.redirect_stdout(io.StringIO()):
            rc = ping.run_tcp_nping([ping.NPING], popen=lambda *args, **kwargs: process)

        self.assertEqual(rc, 1)

    def test_run_tcp_nping_returns_setup_error_without_statistics(self):
        process = FakeNpingProcess(['nping failed\n'], returncode=2)

        with contextlib.redirect_stdout(io.StringIO()):
            rc = ping.run_tcp_nping([ping.NPING], popen=lambda *args, **kwargs: process)

        self.assertEqual(rc, 2)

    def test_run_tcp_ping_executes_nping(self):
        with patch.object(ping, 'run_tcp_nping', return_value=7) as run_nping:
            rc = ping.run_tcp_ping(['example.com', 'tcp', 'port', '443', 'count', '1'])

        self.assertEqual(rc, 7)
        run_nping.assert_called_once_with(
            [
                ping.NPING,
                '--tcp-connect',
                '--dest-port',
                '443',
                '--count',
                '1',
                '--delay',
                ping.TCP_DELAY,
                'example.com',
            ]
        )

    def test_run_tcp_ping_returns_usage_error(self):
        output = io.StringIO()

        with contextlib.redirect_stderr(output):
            rc = ping.run_tcp_ping(['example.com', 'tcp'])

        self.assertEqual(rc, 2)
        self.assertIn('missing port option', output.getvalue())
