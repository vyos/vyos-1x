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
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import os
import shutil

from sys import exit

from vyos.base import Warning
from vyos.config import Config
from vyos.configverify import verify_vrf
from vyos.configverify import verify_pki_certificate
from vyos.configverify import verify_pki_ca_certificate
from vyos.defaults import systemd_services
from vyos.utils.network import is_addr_assigned
from vyos.utils.process import call
from vyos.utils.dict import dict_search
from vyos.utils.file import write_file
from vyos.pki import wrap_certificate
from vyos.pki import wrap_private_key
from vyos.template import render
from vyos.template import is_ipv4
from vyos.template import is_ipv6
from vyos import ConfigError
from vyos import airbag
airbag.enable()

cert_dir = '/etc/rsyslog.d/certs'
rsyslog_conf = '/run/rsyslog/rsyslog.conf'
logrotate_conf = '/etc/logrotate.d/vyos-rsyslog'

systemd_socket = 'syslog.socket'
systemd_service = systemd_services['syslog']


def _cleanup_tls_certs():
    if os.path.exists(cert_dir):
        shutil.rmtree(cert_dir, ignore_errors=True)


def _remote_has_tls(remote_options):
    return 'tls' in remote_options


def _verify_tls_remote_options(remote, remote_options, syslog):
    auth_mode = dict_search('tls.auth_mode', remote_options)
    certificate = dict_search('tls.certificate', remote_options)
    ca_certificate = dict_search('tls.ca_certificate', remote_options)

    if auth_mode != "anon" and not ca_certificate:
        raise ConfigError(
            f'Option "ca-certificate" is required for remote "{remote}" when TLS is enabled with auth-mode "{auth_mode}"!'
        )

    if certificate:
        verify_pki_certificate(syslog, certificate, no_password_protected=True)

    if ca_certificate:
        verify_pki_ca_certificate(syslog, ca_certificate)

    permitted_peers = dict_search('tls.permitted_peer', remote_options)
    if not permitted_peers:
        if auth_mode == "fingerprint":
            raise ConfigError(
                f'Auth mode "fingerprint" for remote "{remote}" requires "permitted-peer" to be configured!'
            )
        elif auth_mode == "name":
            raise ConfigError(
                f'Auth mode "name" for remote "{remote}" requires "permitted-peer" to specify allowed subject names!'
            )


def _save_tls_certificates_for_remote(syslog, remote_options):
    ca_certificate = remote_options['tls'].get('ca_certificate')
    ca_cert_file_path = None
    if ca_certificate:
        ca_cert_file_path = os.path.join(cert_dir, f'{ca_certificate}.pem')
        pki_ca = syslog['pki']['ca'][ca_certificate]

        ca_cert = wrap_certificate(pki_ca['certificate'])
        write_file(ca_cert_file_path, ca_cert)
    remote_options['tls']['ca_certificate_path'] = ca_cert_file_path

    cert_name = remote_options['tls'].get('certificate')
    cert_file_path = cert_key_path = None
    if cert_name:
        cert_file_path = os.path.join(cert_dir, f'{cert_name}.pem')
        cert_key_path = os.path.join(cert_dir, f'{cert_name}.key')
        pki_cert = syslog['pki']['certificate'][cert_name]

        write_file(cert_file_path, wrap_certificate(pki_cert['certificate']))
        write_file(cert_key_path, wrap_private_key(pki_cert['private']['key']))

    remote_options['tls']['certificate_path'] = cert_file_path
    remote_options['tls']['certificate_key_path'] = cert_key_path

def get_config(config=None):
    if config:
        conf = config
    else:
        conf = Config()
    base = ['system', 'syslog']
    if not conf.exists(base):
        return None

    syslog = conf.get_config_dict(
        base,
        key_mangling=('-', '_'),
        get_first_key=True,
        no_tag_node_value_mangle=True,
        with_pki=True,
    )

    syslog.update({ 'logrotate' : logrotate_conf })

    syslog = conf.merge_defaults(syslog, recursive=True)
    if syslog.from_defaults(['local']):
        del syslog['local']

    if 'preserve_fqdn' in syslog:
        if conf.exists(['system', 'host-name']):
            tmp = conf.return_value(['system', 'host-name'])
            syslog['preserve_fqdn']['host_name'] = tmp
        if conf.exists(['system', 'domain-name']):
            tmp  = conf.return_value(['system', 'domain-name'])
            syslog['preserve_fqdn']['domain_name'] = tmp

    # prune 'remote <remote> tls' if it was not set by user
    for remote in syslog.get('remote', {}):
        if syslog.from_defaults(['remote', remote, 'tls']):
            del syslog['remote'][remote]['tls']

    return syslog

def verify(syslog):
    if not syslog:
        return None

    if 'preserve_fqdn' in syslog:
        if 'host_name' not in syslog['preserve_fqdn']:
            Warning('No "system host-name" defined - cannot set syslog FQDN!')
        if 'domain_name' not in syslog['preserve_fqdn']:
            Warning('No "system domain-name" defined - cannot set syslog FQDN!')

    if 'remote' in syslog:
        for remote, remote_options in syslog['remote'].items():
            if 'protocol' in remote_options and remote_options['protocol'] == 'udp':
                if 'format' in remote_options and 'octet_counted' in remote_options['format']:
                    Warning(f'Syslog UDP transport for "{remote}" should not use octet-counted format!')

            if 'vrf' in remote_options:
                verify_vrf(remote_options)

            if 'source_address' in remote_options:
                vrf = None
                if 'vrf' in remote_options:
                    vrf = remote_options['vrf']
                if not is_addr_assigned(remote_options['source_address'], vrf):
                    raise ConfigError('No interface with given address specified!')

                source_address = remote_options['source_address']
                if ((is_ipv4(remote) and is_ipv6(source_address)) or
                    (is_ipv6(remote) and is_ipv4(source_address))):
                    raise ConfigError(f'Source-address "{source_address}" does not match '\
                                      f'address-family of remote "{remote}"!')

            if _remote_has_tls(remote_options):
                _verify_tls_remote_options(remote, remote_options, syslog)

                if 'protocol' in remote_options and remote_options['protocol'] == 'udp':
                    raise ConfigError(
                        f'TLS is enabled for remote "{remote}", but protocol is set to UDP. TLS is only supported with protocol TCP!'
                    )


def generate(syslog):
    _cleanup_tls_certs()

    if not syslog:
        if os.path.exists(rsyslog_conf):
            os.unlink(rsyslog_conf)
        if os.path.exists(logrotate_conf):
            os.unlink(logrotate_conf)

        return None

    if 'remote' in syslog:
        for _, remote_options in syslog['remote'].items():
            if _remote_has_tls(remote_options):
                _save_tls_certificates_for_remote(syslog, remote_options)

    render(rsyslog_conf, 'rsyslog/rsyslog.conf.j2', syslog)
    render(logrotate_conf, 'rsyslog/logrotate.j2', syslog)
    return None

def apply(syslog):
    if not syslog:
        call(f'systemctl stop {systemd_service} {systemd_socket}')
        return None

    call(f'systemctl reload-or-restart {systemd_service}')
    return None

if __name__ == '__main__':
    try:
        c = get_config()
        verify(c)
        generate(c)
        apply(c)
    except ConfigError as e:
        print(e)
        exit(1)
