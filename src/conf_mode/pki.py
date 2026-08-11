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

from sys import argv
from sys import exit

from vyos.config import Config
from vyos.config import config_dict_merge
from vyos.configdep import set_dependents
from vyos.configdep import call_dependents
from vyos.configdict import node_changed
from vyos.configdiff import Diff
from vyos.configdiff import get_config_diff
from vyos.defaults import directories
from vyos.defaults import internal_ports
from vyos.defaults import systemd_services
from vyos.pki import encode_certificate
from vyos.pki import find_chain
from vyos.pki import is_ca_certificate
from vyos.pki import load_certificate
from vyos.pki import load_public_key
from vyos.pki import load_openssh_public_key
from vyos.pki import load_openssh_private_key
from vyos.pki import load_private_key
from vyos.pki import load_crl
from vyos.pki import load_dh_parameters
from vyos.utils.boot import boot_configuration_complete
from vyos.utils.dict import dict_search
from vyos.utils.dict import dict_search_args
from vyos.utils.dict import dict_search_recursive
from vyos.utils.dict import dict_set_nested
from vyos.utils.file import read_file
from vyos.utils.network import check_port_availability
from vyos.utils.process import call
from vyos.utils.process import cmdl
from vyos.utils.process import is_systemd_service_active
from vyos.utils.process import is_systemd_service_running
from vyos import ConfigError
from vyos import airbag
airbag.enable()

vyos_certbot_dir = directories['certbot']
vyos_ca_certificates_dir = directories['ca_certificates']

# keys to recursively search for under specified path
sync_search = [
    {
        'keys': ['certificate'],
        'path': ['service', 'https'],
    },
    {
        'keys': ['key'],
        'path': ['service', 'ssh'],
    },
    {
        'keys': ['certificate', 'ca_certificate'],
        'path': ['interfaces', 'ethernet'],
    },
    {
        'keys': ['certificate', 'ca_certificate', 'dh_params', 'shared_secret_key', 'auth_key', 'crypt_key'],
        'path': ['interfaces', 'openvpn'],
    },
    {
        'keys': ['ca_certificate'],
        'path': ['interfaces', 'sstpc'],
    },
    {
        'keys': ['certificate', 'ca_certificate'],
        'path': ['load_balancing', 'haproxy'],
        'orig_path': ['load-balancing', 'haproxy'],
    },
    {
        'keys': ['key'],
        'path': ['protocols', 'rpki', 'cache'],
    },
    {
        'keys': ['certificate', 'ca_certificate', 'local_key', 'remote_key'],
        'path': ['vpn', 'ipsec'],
    },
    {
        'keys': ['certificate', 'ca_certificate'],
        'path': ['vpn', 'openconnect'],
    },
    {
        'keys': ['certificate', 'ca_certificate'],
        'path': ['vpn', 'sstp'],
    },
    {
        'keys': ['certificate', 'ca_certificate'],
        'path': ['service', 'stunnel'],
    }
]

# key from other config nodes -> key in pki['changed'] and pki
sync_translate = {
    'certificate': 'certificate',
    'ca_certificate': 'ca',
    'dh_params': 'dh',
    'local_key': 'key_pair',
    'remote_key': 'key_pair',
    'shared_secret_key': 'openvpn',
    'auth_key': 'openvpn',
    'crypt_key': 'openvpn',
    'key': 'openssh',
}

def dispatch_dependents_for_reference(pki_system, search, key, item_name, conf, D):
    """If item_name is referenced under key somewhere below search['path']
    in the full system config, register that service (search['path'][1])
    as a dependent to be regenerated/reloaded via call_dependents().
    """
    search_dict = dict_search_args(pki_system, *search['path'])
    if not search_dict:
        return
    for found_name, found_path in dict_search_recursive(search_dict, key):
        if isinstance(found_name, list) and item_name not in found_name:
            continue
        if isinstance(found_name, str) and found_name != item_name:
            continue

        # prefer orig_path over path when unmangling is needed
        path = search.get('orig_path', search.get('path'))
        if path[0] == 'interfaces':
            ifname = found_path[0]
            if not D.node_changed_presence(path + [ifname]):
                set_dependents(path[1], conf, ifname)
        else:
            if not D.node_changed_presence(path):
                set_dependents(path[1], conf)

certbot_log_file = '/var/log/letsencrypt/letsencrypt.log'

def certbot_log_offset() -> int:
    """Current size of certbot's own debug log, to be passed to
    certbot_error_reason() after a failed invocation so it only looks at
    what this specific invocation appended - certbot's log is shared
    across all certificates and accumulates across every past run.
    """
    return os.path.getsize(certbot_log_file) if os.path.exists(certbot_log_file) else 0

def certbot_error_reason(offset: int) -> str | None:
    """Pull the actual ACME protocol error (e.g. rate limiting, failed
    domain validation) out of certbot's own debug log.

    certbot's non-interactive stdout/stderr reporting can itself crash
    on an unrelated certbot/josepy bug while trying to report an ACME
    error (AttributeError: can't set attribute, seen live), which masks
    the real reason entirely from cmdl()'s captured output. The real
    reason is still always written to the debug log first, so read it
    directly instead of relying on certbot's own top-level reporting.
    """
    try:
        with open(certbot_log_file) as f:
            f.seek(offset)
            log_tail = f.read()
    except OSError:
        return None

    reason = None
    prefix = 'acme.messages.Error:'
    for line in log_tail.splitlines():
        if line.startswith(prefix):
            reason = line[len(prefix):].strip()
    return reason

def certbot_delete(certificate):
    if not boot_configuration_complete():
        return
    if os.path.exists(f'{vyos_certbot_dir}/renewal/{certificate}.conf'):
        cmdl(['certbot', 'delete', '--non-interactive', '--config-dir',
              vyos_certbot_dir, '--cert-name', certificate])

def certbot_backup_path(name: str) -> str:
    return f'{vyos_certbot_dir}/.vyos-backup/{name}'

def certbot_backup(name: str) -> None:
    """Move a certificate's live/archive/renewal-config files aside rather
    than deleting them outright, so certbot_restore()/certbot_discard_backup()
    can put them back (or drop them) once the caller knows whether the
    replacement certbot_request() actually succeeded.

    Without this, certbot_delete() followed by a failed certbot_request()
    (a rate limit, a transient ACME/network issue) leaves the certificate
    missing entirely, with no way back short of a fresh, successful ACME
    issuance.
    """
    import shutil
    backup = certbot_backup_path(name)
    if os.path.exists(backup):
        shutil.rmtree(backup)
    os.makedirs(backup)
    for sub in ('live', 'archive'):
        src = f'{vyos_certbot_dir}/{sub}/{name}'
        if os.path.exists(src):
            shutil.move(src, f'{backup}/{sub}')
    renewal_conf = f'{vyos_certbot_dir}/renewal/{name}.conf'
    if os.path.exists(renewal_conf):
        shutil.move(renewal_conf, f'{backup}/renewal.conf')

def certbot_restore(name: str) -> None:
    """Restore a backup made by certbot_backup(), if one exists."""
    import shutil
    backup = certbot_backup_path(name)
    if not os.path.isdir(backup):
        return
    for sub in ('live', 'archive'):
        src = f'{backup}/{sub}'
        if os.path.exists(src):
            dst = f'{vyos_certbot_dir}/{sub}/{name}'
            if os.path.exists(dst):
                shutil.rmtree(dst)
            shutil.move(src, dst)
    renewal_src = f'{backup}/renewal.conf'
    if os.path.exists(renewal_src):
        shutil.move(renewal_src, f'{vyos_certbot_dir}/renewal/{name}.conf')
    shutil.rmtree(backup, ignore_errors=True)

def certbot_discard_backup(name: str) -> None:
    import shutil
    shutil.rmtree(certbot_backup_path(name), ignore_errors=True)

def certbot_request(name: str, config: dict, dry_run: bool=True) -> None:
    # We do not call certbot when booting the system - there is no need to do so and
    # request new certificates during boot/image upgrade as the certbot configuration
    # is stored persistent under /config - thus we do not open the door to transient
    # errors
    if not boot_configuration_complete():
        return None

    tmp = ['certbot', 'certonly', '--non-interactive', '--config-dir',
           vyos_certbot_dir, '--cert-name', name,
           '--standalone', '--agree-tos', '--no-eff-email', '--expand',
           '--server', config['url'],
           '--email', config['email'], '--key-type', 'rsa',
           '--rsa-key-size', str(config['rsa_key_size'])]
    for domain in config['domain_name']:
        tmp += ['--domains', domain]

    listen_address = None
    if 'listen_address' in config:
        listen_address = config['listen_address']

    # When ACME is used behind a reverse proxy, we always bind to localhost
    # whatever the CLI listen-address is configured for.
    if ('used_by' in config and 'haproxy' in config['used_by'] and
        is_systemd_service_running(systemd_services['haproxy']) and
        not check_port_availability(listen_address, 80)):
        tmp += ['--http-01-address', '127.0.0.1', '--http-01-port',
                str(internal_ports["certbot_haproxy"])]
    elif listen_address:
        tmp += ['--http-01-address', listen_address]

    # verify() does not need to actually request a cert but only test for plausibility
    if dry_run:
        tmp += ['--dry-run']

    offset = certbot_log_offset()
    try:
        cmdl(tmp, raising=ConfigError, message=f'Certbot request failed for "{name}"!')
    except ConfigError as e:
        reason = certbot_error_reason(offset)
        if reason:
            raise ConfigError(f'Certbot request failed for "{name}": {reason}') from e
        raise
    return None

def certbot_renewal_due(name: str) -> bool:
    """Approximate check for whether this certbot-managed certificate is
    within its renewal window, without invoking certbot itself - so the
    caller can skip certbot renew (and its unconditional --pre-hook)
    entirely when nothing needs renewing.

    VyOS never overrides certbot's own --renew-before-expiry (30 days),
    so that default is used directly here rather than parsing it back out
    of the renewal config, which certbot itself only ever writes as a
    commented-out placeholder in the absence of an override.

    Fails open (returns True) if the local certificate can't be read, so
    this can never itself block a renewal that should actually happen -
    worst case, the same check just runs again next time.
    """
    from datetime import datetime
    from datetime import timedelta

    tmp = read_file(f'{vyos_certbot_dir}/live/{name}/cert.pem', defaultonfailure=None)
    if tmp is None:
        return True
    try:
        expiry = load_certificate(tmp, wrap_tags=False).not_valid_after
    except Exception:
        return True

    renew_before_expiry_days = 30
    return datetime.utcnow() >= expiry - timedelta(days=renew_before_expiry_days)

def any_certbot_renewal_due(certificates: dict) -> bool:
    """True if any ACME-managed certificate in this pki['certificate']
    dict is within its renewal window - see certbot_renewal_due(). False
    (not due) if there are no ACME-managed certificates at all. Shared by
    get_config() (deciding whether to mark ACME certs as "changed" at
    all) and certbot_renew() (deciding whether to actually invoke
    certbot), so both agree on whether this certbot_renew pass is a real
    one - see the comment above get_config()'s use of this for why that
    matters.
    """
    acme_certs = [name for name, cert_conf in certificates.items() if 'acme' in cert_conf]
    return any(certbot_renewal_due(name) for name in acme_certs)

def certbot_renew(config: dict, force: bool=False) -> None:
    """ Renew all certificates managed via certbot """
    if not force and not any_certbot_renewal_due(config.get('certificate', {})):
        print('No certificates due for renewal - skipping certbot renew.')
        return None

    tmp = ['certbot', 'renew', '--no-random-sleep-on-renew',
           '--config-dir', vyos_certbot_dir]

    # Determine services using ACME based certificates
    pre_hook_services = []
    stop_services = []
    for used_by, _ in dict_search_recursive(config, 'used_by'):
        pre_hook_services.extend(used_by)
    # Remove duplicate items from list
    pre_hook_services = list(set(pre_hook_services))
    # Automatically add services in use to pre_hook_services depending on service
    # name in vyos.defaults.systemd_services
    if pre_hook_services:
        for service in pre_hook_services:
            if service in systemd_services:
                stop_services.append(systemd_services[service])
        tmp += ['--pre-hook', 'systemctl stop ' + ' '.join(stop_services)]

    if force:
        tmp += ['--force-renewal']

    offset = certbot_log_offset()
    try:
        print(cmdl(tmp, raising=ConfigError, message=f'Certbot renew failed!'))
    except ConfigError as e:
        reason = certbot_error_reason(offset)
        print(f'Certbot renew failed: {reason}' if reason else e)
        for service in stop_services:
            print(f'Restarting "{service}" with non-renewed certificate...')
            cmdl(['systemctl', 'restart', service])
    return None

def leaf_cert_base64(name: str, cert_conf: dict):
    """Return a certificate's own base64-encoded content for chain
    resolution purposes: the CLI-configured value for a regular
    certificate, or - since ACME certificates never carry one on the CLI -
    read live from certbot's own cert.pem. Returns None if neither is
    available (e.g. an ACME certificate not yet issued).
    """
    if 'certificate' in cert_conf:
        return cert_conf['certificate']
    if 'acme' not in cert_conf:
        return None
    tmp = read_file(f'{vyos_certbot_dir}/live/{name}/cert.pem', defaultonfailure=None)
    if tmp is None:
        return None
    tmp = load_certificate(tmp, wrap_tags=False)
    if not tmp:
        return None
    return "".join(encode_certificate(tmp).strip().split("\n")[1:-1])

def get_config(config=None):
    if config:
        conf = config
    else:
        conf = Config()
    base = ['pki']

    pki = conf.get_config_dict(base, key_mangling=('-', '_'),
                                     get_first_key=True,
                                     no_tag_node_value_mangle=True)

    if len(argv) > 1 and argv[1] == 'certbot_renew':
        pki['certbot_renew'] = {}
    elif len(argv) > 1 and argv[1] == 'certbot_renew_force':
        pki['certbot_renew'] = {'force': {}}

    # Walk through the list of sync_translate mapping and build a list
    # which is later used to check if the node was changed in the CLI config
    changed_keys = []
    for value in sync_translate.values():
        if value not in changed_keys:
            changed_keys.append(value)
    # Check for changes to said given keys in the CLI config
    for key in changed_keys:
        tmp = node_changed(conf, base + [key], recursive=True, expand_nodes=Diff.DELETE | Diff.ADD)
        if tmp:
            dict_set_nested(f'changed.{key.replace("-", "_")}', tmp, pki)

    # We only merge on the defaults if there is a configuration at all
    if conf.exists(base):
        # We have gathered the dict representation of the CLI, but there are default
        # options which we need to update into the dictionary retrieved.
        default_values = conf.get_config_defaults(**pki.kwargs, recursive=True)
        # remove ACME default configuration if unused by CLI
        if 'certificate' in pki:
            for name, cert_config in pki['certificate'].items():
                if 'acme' not in cert_config:
                    # Remove ACME default values
                    del default_values['certificate'][name]['acme']

        # merge CLI and default dictionary
        pki = config_dict_merge(default_values, pki)

    # Certbot triggered an external renew of the certificates.
    # Mark all ACME based certificates as "changed" to trigger
    # update of dependent services - but only if certbot_renew() below is
    # actually going to invoke certbot: this would otherwise run
    # unconditionally on every timer-triggered pass, making apply()'s
    # call_dependents() regenerate and reload every dependent service
    # (HAProxy, HTTPS, ...) twice a day even when nothing was due for
    # renewal.
    if 'certificate' in pki and 'certbot_renew' in pki:
        force = 'force' in pki['certbot_renew']
        if force or any_certbot_renewal_due(pki['certificate']):
            renew = []
            for name, cert_config in pki['certificate'].items():
                if 'acme' in cert_config:
                    renew.append(name)
            if renew:
                # Get the current list of changed certificates
                tmp = pki.get('changed', {}).get('certificate', [])
                # and extend it with the list of ACME based certificates
                tmp += renew
                # remove any duplicates if necessary
                tmp = set(tmp)
                dict_set_nested('changed.certificate', tmp, pki)

    # We need to get the entire system configuration to verify that we are not
    # deleting a certificate that is still referenced somewhere!
    pki['system'] = conf.get_config_dict([], key_mangling=('-', '_'),
                                         get_first_key=True,
                                         no_tag_node_value_mangle=True)
    D = get_config_diff(conf)

    for search in sync_search:
        for key in search['keys']:
            changed_key = sync_translate[key]
            if 'changed' not in pki or changed_key not in pki['changed']:
                continue

            for item_name in pki['changed'][changed_key]:
                node_present = False
                if changed_key == 'openvpn':
                    node_present = dict_search_args(pki, 'openvpn', 'shared_secret', item_name)
                else:
                    node_present = dict_search_args(pki, changed_key, item_name)

                if node_present:
                    dispatch_dependents_for_reference(pki['system'], search, key, item_name, conf, D)

    # find_chain() based consumers (HAProxy, HTTPS, stunnel, sstpc,
    # openconnect, IPsec, eapol, ...) build their full certificate chain
    # dynamically from the entire pki['ca'] pool, not from an explicit,
    # per-service CA reference - so adding, changing, or removing a CA can
    # change a certificate's resolved chain even though that CA is never
    # referenced by name anywhere, which the named-reference matching
    # above would miss. Only trigger a certificate's dependents when its
    # actually-resolved chain differs before vs after, so an
    # unrelated/unused CA edit does not needlessly reload every
    # certificate-consuming service.
    #
    # This deliberately dispatches dependents directly instead of adding
    # these certificates to changed.certificate: that list is also used
    # by verify()/generate() to decide whether to re-request an ACME
    # certificate from the CA, and a CA-only edit must never cause an
    # unrelated, unnecessary ACME re-issuance of a certificate whose own
    # content did not change.
    if dict_search_args(pki, 'changed', 'ca') and 'certificate' in pki:
        old_ca = conf.get_config_dict(['pki', 'ca'], effective=True,
                                       key_mangling=('-', '_'),
                                       no_tag_node_value_mangle=True,
                                       get_first_key=True) or {}
        new_ca = pki.get('ca', {})

        def _ca_pool(ca_dict):
            return [cert for cert in (
                load_certificate(ca['certificate'])
                for ca in ca_dict.values() if 'certificate' in ca
            ) if cert]

        old_pool = _ca_pool(old_ca)
        new_pool = _ca_pool(new_ca)

        for name, cert_conf in pki['certificate'].items():
            leaf_base64 = leaf_cert_base64(name, cert_conf)
            if not leaf_base64:
                continue
            leaf = load_certificate(leaf_base64)
            if not leaf:
                continue
            old_chain = [encode_certificate(c) for c in find_chain(leaf, old_pool)]
            new_chain = [encode_certificate(c) for c in find_chain(leaf, new_pool)]
            if old_chain == new_chain:
                continue

            for search in sync_search:
                if 'certificate' not in search['keys']:
                    continue
                dispatch_dependents_for_reference(pki['system'], search, 'certificate', name, conf, D)

    # Check PKI certificates if they are auto-generated by ACME. If they are,
    # traverse the current configuration and determine the service where the
    # certificate is used by.
    # Required to check if we might need to run certbot behind a reverse proxy.
    if 'certificate' in pki:
        for name, cert_config in pki['certificate'].items():
            if 'acme' not in cert_config:
                continue
            if not dict_search('system.load_balancing.haproxy', pki):
                continue
            # Determine which service depends on ACME issued certificates
            # We only need to add services blocking the default certbot ports
            # 80 and 443. For instance there won't be a conflict with strongSwan
            # as it runs on different ports.
            used_by = []
            # We start with HAProxy
            for cert_list, _ in dict_search_recursive(
                pki['system']['load_balancing']['haproxy'], 'certificate'):
                if name in cert_list:
                    used_by.append('haproxy')
            # Check if OpenConnect consumes an ACME certificate
            tmp = dict_search('system.vpn.openconnect.ssl.certificate', pki)
            if tmp and tmp in cert_list:
                used_by.append('openconnect')

            if used_by:
                pki['certificate'][name]['acme'].update({'used_by': used_by})

    return pki

def is_valid_certificate(raw_data):
    # If it loads correctly we're good, or return False
    return load_certificate(raw_data, wrap_tags=True)

def is_valid_ca_certificate(raw_data):
    # Check if this is a valid certificate with CA attributes
    cert = load_certificate(raw_data, wrap_tags=True)
    if not cert:
        return False
    return is_ca_certificate(cert)

def is_valid_public_key(raw_data):
    # If it loads correctly we're good, or return False
    return load_public_key(raw_data, wrap_tags=True)

def is_valid_private_key(raw_data, protected=False):
    # If it loads correctly we're good, or return False
    # With encrypted private keys, we always return true as we cannot ask for password to verify
    if protected:
        return True
    return load_private_key(raw_data, passphrase=None, wrap_tags=True)

def is_valid_openssh_public_key(raw_data, type):
    # If it loads correctly we're good, or return False
    return load_openssh_public_key(raw_data, type)

def is_valid_openssh_private_key(raw_data, protected=False):
    # If it loads correctly we're good, or return False
    # With encrypted private keys, we always return true as we cannot ask for password to verify
    if protected:
        return True
    return load_openssh_private_key(raw_data, passphrase=None, wrap_tags=True)

def is_valid_crl(raw_data):
    # If it loads correctly we're good, or return False
    return load_crl(raw_data, wrap_tags=True)

def is_valid_dh_parameters(raw_data):
    # If it loads correctly we're good, or return False
    return load_dh_parameters(raw_data, wrap_tags=True)

def verify(pki):
    if not pki:
        return None

    if 'ca' in pki:
        for name, ca_conf in pki['ca'].items():
            if 'certificate' in ca_conf:
                if not is_valid_ca_certificate(ca_conf['certificate']):
                    raise ConfigError(f'Invalid certificate on CA certificate "{name}"')

            if 'private' in ca_conf and 'key' in ca_conf['private']:
                private = ca_conf['private']
                protected = 'password_protected' in private

                if not is_valid_private_key(private['key'], protected):
                    raise ConfigError(f'Invalid private key on CA certificate "{name}"')

            if 'crl' in ca_conf:
                ca_crls = ca_conf['crl']
                if isinstance(ca_crls, str):
                    ca_crls = [ca_crls]

                for crl in ca_crls:
                    if not is_valid_crl(crl):
                        raise ConfigError(f'Invalid CRL on CA certificate "{name}"')

    if 'certificate' in pki:
        for name, cert_conf in pki['certificate'].items():
            if 'certificate' in cert_conf:
                if not is_valid_certificate(cert_conf['certificate']):
                    raise ConfigError(f'Invalid certificate on certificate "{name}"')

            if 'private' in cert_conf and 'key' in cert_conf['private']:
                private = cert_conf['private']
                protected = 'password_protected' in private

                if not is_valid_private_key(private['key'], protected):
                    raise ConfigError(f'Invalid private key on certificate "{name}"')

            if 'acme' in cert_conf:
                if 'domain_name' not in cert_conf['acme']:
                    raise ConfigError(f'At least one domain-name is required to request '\
                                    f'certificate for "{name}" via ACME!')

                if 'email' not in cert_conf['acme']:
                    raise ConfigError(f'An email address is required to request '\
                                    f'certificate for "{name}" via ACME!')

                listen_address = None
                if 'listen_address' in cert_conf['acme']:
                    listen_address = cert_conf['acme']['listen_address']

                if 'used_by' not in cert_conf['acme']:
                    # A call to check_port_availability() will always fail during system
                    # boot when listen_address is set and the address is not yet assigned
                    # to an interface. This happens b/c PKI subsystem is called prior
                    # to any interface - e.g. ethernet - and thus the OS will always
                    # be unable to bind() a socket() to a non existing IP address.
                    if boot_configuration_complete() and not check_port_availability(listen_address, 80):
                        raise ConfigError('Port 80 is already in use and not available '\
                                          f'to provide ACME challenge for "{name}"!')

                # Only run the ACME command if something on this entity changed,
                # as this is time intensive
                if 'certbot_renew' not in pki:
                    tmp = dict_search('changed.certificate', pki)
                    if tmp != None and name in tmp:
                        certbot_request(name, cert_conf['acme'])

    if 'dh' in pki:
        for name, dh_conf in pki['dh'].items():
            if 'parameters' in dh_conf:
                if not is_valid_dh_parameters(dh_conf['parameters']):
                    raise ConfigError(f'Invalid DH parameters on "{name}"')

    if 'key_pair' in pki:
        for name, key_conf in pki['key_pair'].items():
            if 'public' in key_conf and 'key' in key_conf['public']:
                if not is_valid_public_key(key_conf['public']['key']):
                    raise ConfigError(f'Invalid public key on key-pair "{name}"')

            if 'private' in key_conf and 'key' in key_conf['private']:
                private = key_conf['private']
                protected = 'password_protected' in private
                if not is_valid_private_key(private['key'], protected):
                    raise ConfigError(f'Invalid private key on key-pair "{name}"')

    if 'openssh' in pki:
        for name, key_conf in pki['openssh'].items():
            if 'public' in key_conf and 'key' in key_conf['public']:
                if 'type' not in key_conf['public']:
                    raise ConfigError(f'Must define OpenSSH public key type for "{name}"')
                if not is_valid_openssh_public_key(key_conf['public']['key'], key_conf['public']['type']):
                    raise ConfigError(f'Invalid OpenSSH public key "{name}"')

            if 'private' in key_conf and 'key' in key_conf['private']:
                private = key_conf['private']
                protected = 'password_protected' in private
                if not is_valid_openssh_private_key(private['key'], protected):
                    raise ConfigError(f'Invalid OpenSSH private key "{name}"')

    if 'x509' in pki:
        if 'default' in pki['x509']:
            default_values = pki['x509']['default']
            if 'country' in default_values:
                country = default_values['country']
                if len(country) != 2 or not country.isalpha():
                    raise ConfigError('Invalid default country value. '\
                                      'Value must be 2 alpha characters.')

    if 'changed' in pki:
        # if the list is getting longer, we can move to a dict() and also embed the
        # search key as value from line 173 or 176
        for search in sync_search:
            for key in search['keys']:
                changed_key = sync_translate[key]
                if changed_key not in pki['changed']:
                    continue
                for item_name in pki['changed'][changed_key]:
                    node_present = False
                    if changed_key == 'openvpn':
                        node_present = dict_search_args(pki, 'openvpn', 'shared_secret', item_name)
                    else:
                        node_present = dict_search_args(pki, changed_key, item_name)
                    # If the node is still present, we can skip the check
                    # as we are not deleting it
                    if node_present:
                        continue

                    search_dict = dict_search_args(pki['system'], *search['path'])
                    if not search_dict:
                        continue

                    for found_name, found_path in dict_search_recursive(search_dict, key):
                        # Check if the name matches either by string compare, or being
                        # part of a list
                        if ((isinstance(found_name, str) and found_name == item_name) or
                            (isinstance(found_name, list) and item_name in found_name)):
                            # We do not support _ in CLI paths - this is only a convenience
                            # as we mangle all - to _, now it's time to reverse this!
                            path_str = ' '.join(search['path'] + found_path).replace('_','-')
                            object = changed_key.replace('_','-')
                            tmp = f'Embedded PKI {object} with name "{item_name}" is still '\
                                  f'in use by CLI path "{path_str}"'
                            raise ConfigError(tmp)

    return None

def cleanup_system_ca():
    if not os.path.exists(vyos_ca_certificates_dir):
        os.mkdir(vyos_ca_certificates_dir)
    else:
        for filename in os.listdir(vyos_ca_certificates_dir):
            full_path = os.path.join(vyos_ca_certificates_dir, filename)
            if os.path.isfile(full_path):
                os.unlink(full_path)

def generate(pki):
    if not pki:
        cleanup_system_ca()
        return None

    # Create or cleanup CA install directory
    if 'changed' in pki and 'ca' in pki['changed']:
        cleanup_system_ca()

        if 'ca' in pki:
            for ca, ca_conf in pki['ca'].items():
                if 'system_install' in ca_conf:
                    ca_obj = load_certificate(ca_conf['certificate'])
                    ca_path = os.path.join(vyos_ca_certificates_dir, f'{ca}.crt')

                    with open(ca_path, 'w') as f:
                        f.write(encode_certificate(ca_obj))

    # Certbot renewal only needs to re-trigger the services to load up the
    # new PEM file
    if 'certbot_renew' in pki:
        force = 'force' in pki['certbot_renew']
        return certbot_renew(config=pki, force=force)

    certbot_list = []
    certbot_list_on_disk = []
    if os.path.exists(f'{vyos_certbot_dir}/live'):
        certbot_list_on_disk = [f.path.split('/')[-1] for f in os.scandir(f'{vyos_certbot_dir}/live') if f.is_dir()]

    if 'certificate' in pki:
        changed_certificates = dict_search('changed.certificate', pki)
        for name, cert_conf in pki['certificate'].items():
            if 'acme' in cert_conf:
                certbot_list.append(name)
                # There is no ACME/certbot managed certificate presend on the
                # system, generate it
                if name not in certbot_list_on_disk:
                    certbot_request(name, cert_conf['acme'], dry_run=False)
                    certbot_list_on_disk.append(name)
                # We already had an ACME managed certificate on the system, but
                # something changed in the configuration
                elif changed_certificates != None and name in changed_certificates:
                    have_backup = False
                    # Back up (rather than outright delete) the old ACME
                    # certificate first, so it can be restored if the
                    # replacement request below fails for any reason - a
                    # rate limit, a transient ACME/network issue, or
                    # anything else. Without this, a failed request here
                    # left the certificate missing entirely until the next
                    # successful issuance.
                    if name in certbot_list_on_disk:
                        certbot_backup(name)
                        have_backup = True
                        certbot_delete(name)
                    # Request new certificate via certbot
                    try:
                        certbot_request(name, cert_conf['acme'], dry_run=False)
                    except Exception:
                        if have_backup:
                            certbot_restore(name)
                        raise
                    if have_backup:
                        # A request made while boot_configuration_complete()
                        # is False silently no-ops (see certbot_request()) -
                        # verify the certificate is actually back on disk
                        # before discarding the backup, rather than trusting
                        # the absence of an exception alone.
                        if os.path.exists(f'{vyos_certbot_dir}/live/{name}/cert.pem'):
                            certbot_discard_backup(name)
                        else:
                            certbot_restore(name)

    # Cleanup certbot configuration and certificates if no longer in use by CLI
    # Get foldernames under vyos_certbot_dir which each represent a certbot cert
    #
    # Note: the intermediate CA certbot obtains alongside each of these
    # certificates (chain.pem) is intentionally never imported into the
    # CLI here - it is derived data, not configuration, and is instead
    # read live from disk by whatever needs it (find_chain() consumers,
    # "show pki ca") - see vyos.pki.acme_chain_ca_entry().
    if os.path.exists(f'{vyos_certbot_dir}/live'):
        for cert in certbot_list_on_disk:
            # ACME certificate is no longer in use by CLI remove it
            if cert not in certbot_list:
                certbot_delete(cert)

    return None

def apply(pki):
    systemd_certbot_name = 'certbot.timer'
    if not pki:
        call(f'systemctl stop {systemd_certbot_name}')
        call('update-ca-certificates')
        return None

    has_certbot = False
    if 'certificate' in pki:
        for name, cert_conf in pki['certificate'].items():
            if 'acme' in cert_conf:
                has_certbot = True
                break

    if not has_certbot:
        call(f'systemctl stop {systemd_certbot_name}')
    elif has_certbot and not is_systemd_service_active(systemd_certbot_name):
        call(f'systemctl restart {systemd_certbot_name}')

    if 'changed' in pki:
        call_dependents()

        # Rebuild ca-certificates bundle
        if 'ca' in pki['changed']:
            call('update-ca-certificates')

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
