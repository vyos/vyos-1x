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
import socket
import json

from sys import exit
from shutil import rmtree

from vyos.config import Config
from vyos.configdict import is_node_changed
from vyos.configverify import verify_pki_ca_certificate
from vyos.configverify import verify_pki_certificate
from vyos.configverify import verify_vrf
from vyos.ifconfig import Section
from vyos.pki import encode_certificate
from vyos.pki import find_chain
from vyos.pki import load_certificate
from vyos.pki import wrap_certificate
from vyos.pki import wrap_private_key
from vyos.template import render
from vyos.utils.convert import human_to_seconds
from vyos.utils.dict import dict_search
from vyos.utils.file import write_file_atomic
from vyos.utils.dict import dict_search_args
from vyos.utils.file import makedir
from vyos.utils.file import write_file
from vyos.utils.process import call
from vyos.utils.permission import chown
from vyos.utils.process import cmdl
from vyos.xml_ref import default_value
from vyos import ConfigError
from vyos import airbag
airbag.enable()

cache_dir = '/etc/telegraf/.cache'
config_dir = '/run/telegraf'
telegraf_env = f'{config_dir}/telegraf.env'
cert_dir = f'{config_dir}/certs'
config_telegraf = f'{config_dir}/telegraf.conf'
custom_scripts_dir = '/etc/telegraf/custom_scripts'
syslog_telegraf = '/etc/rsyslog.d/50-telegraf.conf'
systemd_override = '/run/systemd/system/telegraf.service.d/10-override.conf'

# Output plugins (CLI node names, mangled) supporting the 'tls' node
# defined in 'include/monitoring/telegraf-output-tls.xml.i'
supported_tls_outputs = ['influxdb']


def _cleanup_tls_certs():
    if os.path.isdir(cert_dir):
        rmtree(cert_dir, ignore_errors=True)


def _verify_tls(monitoring: dict, output: str) -> None:
    """Verify the common 'tls' node of a Telegraf output plugin"""

    tls = dict_search_args(monitoring, output, 'tls')
    if not tls:
        return

    cli_output = output.replace('_', '-')
    if 'insecure' in tls and 'ca_certificate' in tls:
        raise ConfigError(
            f'Telegraf {cli_output} TLS options "ca-certificate" '
            'and "insecure" are mutually exclusive!'
        )

    if 'ca_certificate' in tls:
        verify_pki_ca_certificate(monitoring, tls['ca_certificate'])

    if 'certificate' in tls:
        verify_pki_certificate(
            monitoring, tls['certificate'], no_password_protected=True
        )

    url = dict_search_args(monitoring, output, 'url')
    if url and not url.lower().startswith('https://'):
        raise ConfigError(
            f'Telegraf {cli_output} TLS options have no effect as "url" does not use HTTPS!'
        )


def _client_certificate_chain(monitoring: dict, cert_name: str) -> str:
    """
    Return the PEM encoded client certificate followed by all intermediate CA
    certificates found in the PKI configuration.
    """
    pki_cert = monitoring['pki']['certificate'][cert_name]
    leaf = load_certificate(pki_cert['certificate'])

    ca_certs = set()
    for ca_config in (dict_search_args(monitoring, 'pki', 'ca') or {}).values():
        ca_cert = load_certificate(ca_config.get('certificate', ''))
        if ca_cert:
            ca_certs.add(ca_cert)

    chain = find_chain(leaf, ca_certs)
    return '\n'.join(encode_certificate(cert) for cert in chain)


def _generate_tls(monitoring: dict, output: str):
    """
    Write PKI objects referenced by the 'tls' node of a Telegraf output plugin
    to disk and store the resulting file paths in the config dict for the
    template engine.
    """

    tls = dict_search_args(monitoring, output, 'tls')
    if not tls:
        return

    prefix = os.path.join(cert_dir, output.replace('_', '-'))

    user = group = 'telegraf'
    owner = dict(user=user, group=group)
    # The file's owner can read and write to the file, while everyone else can only read it
    cert_mode = 0o644
    # The owner can read and write the file
    key_mode = 0o600

    if 'ca_certificate' in tls:
        ca_name = tls['ca_certificate']
        pki_ca = monitoring['pki']['ca'][ca_name]
        tls['ca_certificate_file'] = f'{prefix}-ca.pem'
        write_file(
            tls['ca_certificate_file'],
            wrap_certificate(pki_ca['certificate']),
            mode=cert_mode,
            **owner,
        )

    if 'certificate' in tls:
        cert_name = tls['certificate']
        pki_cert = monitoring['pki']['certificate'][cert_name]
        tls['certificate_file'] = f'{prefix}-cert.pem'
        tls['certificate_key_file'] = f'{prefix}-cert.key'

        # Include intermediate CA certificates, otherwise mutual TLS fails if
        # the server only trusts the root CA
        write_file(
            tls['certificate_file'],
            _client_certificate_chain(monitoring, cert_name),
            mode=cert_mode,
            **owner,
        )
        write_file(
            tls['certificate_key_file'],
            wrap_private_key(pki_cert['private']['key']),
            mode=key_mode,
            **owner,
        )

def get_nft_filter_chains():
    """ Get nft chains for table filter """
    try:
        nft = cmdl(['nft', '--json', 'list', 'table', 'ip', 'vyos_filter'])
    except Exception:
        print('nft table ip vyos_filter not found')
        return []
    nft = json.loads(nft)
    chain_list = []

    for output in nft['nftables']:
        if 'chain' in output:
            chain = output['chain']['name']
            chain_list.append(chain)

    return chain_list

def get_hostname() -> str:
    try:
        hostname = socket.getfqdn()
    except socket.gaierror:
        hostname = socket.gethostname()
    return hostname

def get_config(config=None):
    if config:
        conf = config
    else:
        conf = Config()
    base = ['service', 'monitoring', 'telegraf']
    if not conf.exists(base):
        return None

    monitoring = conf.get_config_dict(
        base,
        key_mangling=('-', '_'),
        get_first_key=True,
        no_tag_node_value_mangle=True,
        with_pki=True,
    )

    tmp = is_node_changed(conf, base + ['vrf'])
    if tmp: monitoring.update({'restart_required': {}})

    # A reload keeps the old environment, a new token needs a restart
    tmp = is_node_changed(conf, base + ['influxdb', 'authentication', 'token'])
    if tmp:
        monitoring.update({'restart_required': {}})

    # Azure credentials are only read from the environment at startup,
    # changing them requires a restart, a reload is not enough
    tmp = is_node_changed(conf, base + ['azure-data-explorer', 'authentication'])
    if tmp:
        monitoring.update({'restart_required': {}})

    # We have gathered the dict representation of the CLI, but there are default
    # options which we need to update into the dictionary retrieved.
    monitoring = conf.merge_defaults(monitoring, recursive=True)

    monitoring['custom_scripts_dir'] = custom_scripts_dir
    monitoring['telegraf_env_file'] = telegraf_env
    monitoring['hostname'] = get_hostname()
    monitoring['interfaces_ethernet'] = Section.interfaces('ethernet', vlan=False)
    if conf.exists('firewall'):
        monitoring['nft_chains'] = get_nft_filter_chains()

    # Redefine azure group-metrics 'single-table' and 'table-per-metric'
    if 'azure_data_explorer' in monitoring:
        if 'single-table' in monitoring['azure_data_explorer']['group_metrics']:
            monitoring['azure_data_explorer']['group_metrics'] = 'SingleTable'
        else:
            monitoring['azure_data_explorer']['group_metrics'] = 'TablePerMetric'

    # Ignore default XML values if config doesn't exists
    # Delete key from dict
    if not conf.exists(base + ['influxdb']):
        del monitoring['influxdb']

    if not conf.exists(base + ['prometheus-client']):
        del monitoring['prometheus_client']

    if not conf.exists(base + ['azure-data-explorer']):
        del monitoring['azure_data_explorer']

    if not conf.exists(base + ['loki']):
        del monitoring['loki']

    # T9260: relay the local Prometheus frr-exporter endpoint through
    # Telegraf's inputs.prometheus plugin, so FRR routing state can reach the
    # already configured Telegraf outputs without an external Prometheus
    # scraper having to be given inbound access to the router.
    if 'frr_metrics' in monitoring:
        frr_exporter_base = ['service', 'monitoring', 'prometheus', 'frr-exporter']
        if not conf.exists(frr_exporter_base):
            # frr_exporter isn't configured/running - nothing to relay
            monitoring['frr_metrics'] = {'not_configured': True}
        else:
            frr_exporter = conf.get_config_dict(
                frr_exporter_base,
                key_mangling=('-', '_'),
                get_first_key=True,
                with_recursive_defaults=True,
            )

            # frr_exporter listens on all addresses when no listen-address is
            # configured, so a loopback scrape is always possible in that case
            address = '127.0.0.1'
            if 'listen_address' in frr_exporter:
                address = frr_exporter['listen_address'][0]

            # Keep the Prometheus input in sync with the prometheus-client
            # output metric_version, when that output is configured
            if 'prometheus_client' in monitoring:
                metric_version = monitoring['prometheus_client']['metric_version']
            else:
                metric_version = default_value(
                    base + ['prometheus-client', 'metric-version']
                )

            monitoring['frr_metrics'] = {
                'address': address,
                'port': frr_exporter['port'],
                'metric_version': metric_version,
            }

            # frr_exporter runs under "ip vrf exec" when a VRF is set - if
            # Telegraf runs in a different VRF (or none), the loopback
            # scrape will not reach it
            if frr_exporter.get('vrf') != monitoring.get('vrf'):
                monitoring['frr_metrics']['vrf_mismatch'] = {}

    return monitoring

def verify(monitoring):
    # bail out early - looks like removal from running config
    if not monitoring:
        return None

    verify_vrf(monitoring)

    # Verify global-tag
    if 'global_tag' in monitoring:
        for tag, tag_config in monitoring['global_tag'].items():
            if 'value' not in tag_config:
                raise ConfigError(f'Global tag "{tag}" has no value assigned!')

    # Verify agent
    # Telegraf can handle up to 9223372036854775807ns
    # Which is roughly 9223372036s
    max_agent_duration_s = 9223372036

    if 'agent' in monitoring:
        for option in (
            'interval',
            'collection_jitter',
            'flush_interval',
            'flush_jitter',
        ):
            if option not in monitoring['agent']:
                continue

            duration_s = human_to_seconds(monitoring['agent'][option])

            if duration_s > max_agent_duration_s:
                raise ConfigError(f'{option.replace("_", "-")} value is too large')

    # Verify influxdb
    if 'influxdb' in monitoring:
        if 'authentication' not in monitoring['influxdb'] or \
           'organization' not in monitoring['influxdb']['authentication'] or \
           'token' not in monitoring['influxdb']['authentication']:
            raise ConfigError(f'influxdb authentication "organization and token" are mandatory!')

        if 'url' not in monitoring['influxdb']:
            raise ConfigError(f'Monitoring influxdb "url" is mandatory!')

    # Verify azure-data-explorer
    if 'azure_data_explorer' in monitoring:
        if 'authentication' not in monitoring['azure_data_explorer'] or \
           'client_id' not in monitoring['azure_data_explorer']['authentication'] or \
           'client_secret' not in monitoring['azure_data_explorer']['authentication'] or \
           'tenant_id' not in monitoring['azure_data_explorer']['authentication']:
            raise ConfigError(f'Authentication "client-id, client-secret and tenant-id" are mandatory!')

        if 'database' not in monitoring['azure_data_explorer']:
            raise ConfigError(f'Monitoring "database" is mandatory!')

        if 'url' not in monitoring['azure_data_explorer']:
            raise ConfigError(f'Monitoring "url" is mandatory!')

        if monitoring['azure_data_explorer']['group_metrics'] == 'SingleTable' and \
            'table' not in monitoring['azure_data_explorer']:
             raise ConfigError(f'Monitoring "table" name for single-table mode is mandatory!')

    # Verify Splunk
    if 'splunk' in monitoring:
        if 'authentication' not in monitoring['splunk'] or \
           'token' not in monitoring['splunk']['authentication']:
            raise ConfigError(f'Authentication "organization and token" are mandatory!')

        if 'url' not in monitoring['splunk']:
            raise ConfigError(f'Monitoring splunk "url" is mandatory!')

    # Verify Loki
    if 'loki' in monitoring:
        if 'url' not in monitoring['loki']:
            raise ConfigError(f'Monitoring loki "url" is mandatory!')
        if 'authentication' in monitoring['loki']:
            if (
                'username' not in monitoring['loki']['authentication']
                or 'password' not in monitoring['loki']['authentication']
            ):
                raise ConfigError(
                    f'Authentication "username" and "password" are mandatory!'
                )

    # Verify local FRR metrics relay
    if 'frr_metrics' in monitoring:
        if 'not_configured' in monitoring['frr_metrics']:
            raise ConfigError(
                '"service monitoring prometheus frr-exporter" must be '
                'configured before FRR metrics can be relayed via Telegraf!'
            )

        if 'vrf_mismatch' in monitoring['frr_metrics']:
            raise ConfigError(
                'Telegraf and the Prometheus frr-exporter must run in the '
                'same VRF for FRR metrics to be relayed locally!'
            )

    # Verify TLS settings of all outputs supporting them
    for output in supported_tls_outputs:
        _verify_tls(monitoring, output)

    return None

def generate(monitoring):
    # Re-create PKI files referenced by output plugins - always start from
    # an empty directory so no stale certificates/keys are left behind
    _cleanup_tls_certs()

    if not monitoring:
        # Delete config and systemd files
        config_files = [
            config_telegraf,
            telegraf_env,
            systemd_override,
            syslog_telegraf,
        ]
        for file in config_files:
            if os.path.isfile(file):
                os.unlink(file)

        # Delete old directories
        if os.path.isdir(cache_dir):
            rmtree(cache_dir, ignore_errors=True)

        return None

    # Telegraf must own its runtime directory (e.g. for the PID file), ensure
    # it is created with proper ownership before the certificate directory
    makedir(config_dir, user='telegraf', group='telegraf')
    for output in supported_tls_outputs:
        _generate_tls(monitoring, output)

    # Create telegraf cache dir
    if not os.path.exists(cache_dir):
        os.makedirs(cache_dir)

    chown(cache_dir, 'telegraf', 'telegraf')

    # Create custom scripts dir
    if not os.path.exists(custom_scripts_dir):
        os.mkdir(custom_scripts_dir)

    # Render telegraf configuration and systemd override
    render(config_telegraf, 'telegraf/telegraf.j2', monitoring, user='telegraf', group='telegraf')
    render(systemd_override, 'telegraf/override.conf.j2', monitoring)
    render(syslog_telegraf, 'telegraf/syslog_telegraf.j2', monitoring)

    # Secrets reach telegraf through a root-only EnvironmentFile. Environment=
    # would expose them to every user via "systemctl show". Written atomically
    # so the file is never readable by others.
    env_dict = {}

    token = dict_search('influxdb.authentication.token', monitoring)
    if token:
        env_dict['INFLUX_TOKEN'] = token

    for key in ['client_id', 'client_secret', 'tenant_id']:
        value = dict_search(f'azure_data_explorer.authentication.{key}', monitoring)
        if value:
            env_dict[f'AZURE_{key.upper()}'] = value

    if env_dict:
        data = ''.join(f'{key}={value}\n' for key, value in env_dict.items())
        write_file_atomic(telegraf_env, data)
    elif os.path.isfile(telegraf_env):
        os.unlink(telegraf_env)

    return None

def apply(monitoring):
    # Reload systemd manager configuration
    systemd_service = 'telegraf.service'
    call('systemctl daemon-reload')
    if not monitoring:
        call(f'systemctl stop {systemd_service}')
        return

    # we need to restart the service if e.g. the VRF name changed
    systemd_action = 'reload-or-restart'
    if 'restart_required' in monitoring:
        systemd_action = 'restart'

    call(f'systemctl {systemd_action} {systemd_service}')

    # Telegraf include custom rsyslog config changes
    call('systemctl reload-or-restart rsyslog')

if __name__ == '__main__':
    try:
        c = get_config()
        verify(c)
        generate(c)
        apply(c)
    except ConfigError as e:
        print(e)
        exit(1)
