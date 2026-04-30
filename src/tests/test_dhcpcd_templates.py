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

import os
from unittest import TestCase
from vyos.template import render_to_string

_REPO_ROOT = os.path.normpath(
    os.path.join(os.path.abspath(os.path.dirname(__file__)), '../..')
)
_TMPL_DIR = os.path.join(_REPO_ROOT, 'data/templates')


def _render(template, config):
    return render_to_string(template, config, location=_TMPL_DIR)


CONF_TMPL = 'dhcp-client/ipv6.j2'
OVERRIDE_TMPL = 'dhcp-client/ipv6.override.conf.j2'


class TestDhcpcdConfigTemplate(TestCase):

    def _base_config(self):
        return {
            'ifname': 'eth0',
            'address': ['dhcpv6'],
            'dhcpv6_options': {},
            'dhcpcd6_client_dir': '/run/dhcpcd',
        }

    def test_ia_na_default(self):
        config = self._base_config()
        result = _render(CONF_TMPL, config)
        self.assertIn('ia_na', result)
        self.assertNotIn('ia_ta', result)
        self.assertNotIn('ia_pd', result)

    def test_temporary_address(self):
        config = self._base_config()
        config['dhcpv6_options'] = {'temporary': {}}
        result = _render(CONF_TMPL, config)
        self.assertIn('ia_ta', result)
        self.assertNotIn('ia_na', result)

    def test_rapid_commit(self):
        config = self._base_config()
        config['dhcpv6_options'] = {'rapid_commit': {}}
        result = _render(CONF_TMPL, config)
        self.assertIn('option dhcp6_rapid_commit', result)

    def test_no_release(self):
        config = self._base_config()
        config['dhcpv6_options'] = {'no_release': {}}
        result = _render(CONF_TMPL, config)
        self.assertNotIn('release', result.splitlines())

    def test_release_emitted_by_default(self):
        config = self._base_config()
        result = _render(CONF_TMPL, config)
        self.assertIn('release', result.splitlines())

    def test_parameters_only_suppresses_ia_na(self):
        config = self._base_config()
        config['dhcpv6_options'] = {'parameters_only': {}}
        result = _render(CONF_TMPL, config)
        self.assertNotIn('ia_na', result)
        self.assertNotIn('ia_ta', result)

    def test_parameters_only_emits_inform6(self):
        config = self._base_config()
        config['dhcpv6_options'] = {'parameters_only': {}}
        result = _render(CONF_TMPL, config)
        self.assertIn('inform6', result.splitlines())

    def test_no_inform6_without_parameters_only(self):
        config = self._base_config()
        result = _render(CONF_TMPL, config)
        self.assertNotIn('inform6', result)

    def test_dns_requested_by_default(self):
        # dhcp6_ prefix required; bare name hits NULL IPv4 table in our build
        config = self._base_config()
        result = _render(CONF_TMPL, config)
        lines = result.splitlines()
        self.assertIn('option dhcp6_name_servers', lines)
        self.assertNotIn('nooption dhcp6_name_servers', lines)
        self.assertIn('option dhcp6_domain_search', lines)
        self.assertNotIn('nooption dhcp6_domain_search', lines)
        self.assertNotIn('option domain_name_servers', lines)
        self.assertNotIn('option domain_search', lines)

    def test_no_request_dns(self):
        config = self._base_config()
        config['dhcpv6_options'] = {'no_request_dns': {}}
        result = _render(CONF_TMPL, config)
        lines = result.splitlines()
        self.assertIn('nooption dhcp6_name_servers', lines)
        self.assertNotIn('option dhcp6_name_servers', lines)

    def test_no_request_domain_name(self):
        config = self._base_config()
        config['dhcpv6_options'] = {'no_request_domain_name': {}}
        result = _render(CONF_TMPL, config)
        lines = result.splitlines()
        self.assertIn('nooption dhcp6_domain_search', lines)
        self.assertNotIn('option dhcp6_domain_search', lines)

    def test_nooption_ntp_never_emitted(self):
        # DHCPv4-only option; no DHCPv6 equivalent exists
        config = self._base_config()
        result = _render(CONF_TMPL, config)
        self.assertNotIn('ntp_servers', result)

    def test_timeout_zero_always_present(self):
        config = self._base_config()
        result = _render(CONF_TMPL, config)
        self.assertIn('timeout 0', result)

    def test_noipv6rs_always_present(self):
        config = self._base_config()
        result = _render(CONF_TMPL, config)
        self.assertIn('noipv6rs', result)

    def test_nolladdr_never_emitted(self):
        # compile-time --disable-lladdr; no runtime directive
        config = self._base_config()
        result = _render(CONF_TMPL, config)
        self.assertNotIn('nolladdr', result)

    def test_no_ipv4_directives_emitted(self):
        # --disable-ipv4 build: none of these code paths exist in the binary
        config = self._base_config()
        result = _render(CONF_TMPL, config)
        for token in ('ipv4', 'noipv4', 'ipv4ll', 'arping', 'noarp'):
            self.assertNotIn(token, result)

    def test_pd_no_interfaces(self):
        config = self._base_config()
        config['dhcpv6_options'] = {
            'pd': {'0': {'length': '56', '_ia_pd_suffix': ''}}
        }
        result = _render(CONF_TMPL, config)
        self.assertIn('ia_pd 0/::/56', result)

    def test_pd_auto_sla_id(self):
        config = self._base_config()
        config['dhcpv6_options'] = {
            'pd': {
                '0': {
                    'length': '56',
                    '_ia_pd_suffix': 'dum0/0/64/1 dum1/1/64/2',
                    'interface': {
                        'dum0': {'address': '1'},
                        'dum1': {'address': '2'},
                    },
                }
            }
        }
        result = _render(CONF_TMPL, config)
        self.assertIn('ia_pd 0/::/56', result)
        self.assertIn('dum0/0/64/1', result)
        self.assertIn('dum1/1/64/2', result)

    def test_pd_manual_sla_id(self):
        config = self._base_config()
        config['dhcpv6_options'] = {
            'pd': {
                '0': {
                    'length': '56',
                    '_ia_pd_suffix': 'dum0/5/64/3',
                    'interface': {
                        'dum0': {'sla_id': '5', 'address': '3'},
                    },
                }
            }
        }
        result = _render(CONF_TMPL, config)
        self.assertIn('dum0/5/64/3', result)

    def test_pd_no_address(self):
        config = self._base_config()
        config['dhcpv6_options'] = {
            'pd': {
                '0': {
                    'length': '60',
                    '_ia_pd_suffix': 'dum0/2/64',
                    'interface': {
                        'dum0': {'sla_id': '2'},
                    },
                }
            }
        }
        result = _render(CONF_TMPL, config)
        self.assertIn('dum0/2/64', result)

    def test_duid_emitted_when_set(self):
        config = self._base_config()
        config['dhcpv6_options'] = {'duid': '00:03:00:01:de:ad:be:ef:ca:fe'}
        result = _render(CONF_TMPL, config)
        self.assertIn('duid 00:03:00:01:de:ad:be:ef:ca:fe', result)

    def test_duid_absent_when_not_set(self):
        config = self._base_config()
        result = _render(CONF_TMPL, config)
        self.assertNotIn('duid ', result)


class TestDhcpcdOverrideTemplate(TestCase):

    def _base_config(self):
        return {
            'ifname': 'eth0',
            'address': ['dhcpv6'],
            'dhcpv6_options': {},
            'dhcpcd6_client_dir': '/run/dhcpcd',
            'vrf': 'mgmt',
        }

    def test_clears_then_sets_execstart(self):
        config = self._base_config()
        result = _render(OVERRIDE_TMPL, config)
        lines = result.splitlines()
        # bare ExecStart= clears the inherited value; order matters
        idx_clear = lines.index('ExecStart=')
        idx_set = next(
            i for i, l in enumerate(lines) if l.startswith('ExecStart=ip')
        )
        self.assertLess(idx_clear, idx_set)

    def test_vrf_exec_prefix(self):
        config = self._base_config()
        result = _render(OVERRIDE_TMPL, config)
        self.assertIn('ip vrf exec mgmt /usr/sbin/dhcpcd', result)

    def test_vrf_name_in_command(self):
        config = self._base_config()
        config['vrf'] = 'red'
        result = _render(OVERRIDE_TMPL, config)
        self.assertIn('ip vrf exec red', result)

    def test_conf_and_hook_paths(self):
        config = self._base_config()
        result = _render(OVERRIDE_TMPL, config)
        self.assertIn('-f /run/dhcpcd/dhcpcd6.eth0.conf', result)
        self.assertIn('--script /etc/dhcpcd6/dhcpcd6.eth0.hook', result)

    def test_no_inform6_in_override(self):
        config = self._base_config()
        config['dhcpv6_options'] = {'parameters_only': {}}
        result = _render(OVERRIDE_TMPL, config)
        self.assertNotIn('inform6', result)
        self.assertNotIn('--inform6', result)

    def test_nobackground_flag_present_in_override(self):
        # -B suppresses the launcher fork; systemd loses MainPID without it
        config = self._base_config()
        result = _render(OVERRIDE_TMPL, config)
        self.assertIn(' -B ', result)
