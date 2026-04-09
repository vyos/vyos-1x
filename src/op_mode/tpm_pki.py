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
import sys
import shutil
import typing
import tabulate

from cryptography import x509
from cryptography.x509.oid import ExtendedKeyUsageOID

import vyos.opmode

from vyos.utils.io import ask_input
from vyos.utils.io import ask_yes_no
from vyos.utils.process import rc_cmd
from vyos.tpm import tpm_enabled
from vyos.template import render
from vyos.pki import encode_certificate
from vyos.pki import get_certificate_fingerprint
from vyos.pki import load_certificate
from vyos.pki import load_certificate_request
from vyos.tpm_pki import make_tpm_pki_dir
from vyos.tpm_pki import get_tpm_pki_dir
from vyos.tpm_pki import get_path
from vyos.tpm_pki import get_path_str
from vyos.tpm_pki import get_tpm_list
from vyos.tpm_pki import clear_tpm_lockout
from vyos.tpm_pki import ask_passphrase
from vyos.tpm_pki import validate_tpm_private_key
from vyos.tpm_pki import validate_pki_private_key
from vyos.tpm_pki import validate_certificate
from vyos.tpm_pki import validate_csr
from vyos.tpm_pki import validate_public_key
from vyos.tpm_pki import validate_pub_key_against_priv_key
from vyos.tpm_pki import validate_certificate_against_tpm_priv_key
from vyos.tpm_pki import check_pki_key_algorithm
from vyos.tpm_pki import ensure_persistent_primary_handle
from vyos.tpm_pki import validate_san_list

ArgsPkiType = typing.Literal['cert', 'csr', 'kpair', 'cert_with_tpm']
ArgsFingerprint = typing.Literal['sha256', 'sha384', 'sha512']

TMPL_CERT: str = 'openssl/cert.cnf.j2'

x509_default_values: dict[str, str] = {
    'country': 'CA',
    'state': 'ON',
    'locality': 'Toronto',
    'organization': 'ExampleOrg',
    'common_name': 'example.com'
}

# Helper Functions
def gather_tpm_common_config_info(name, pki_type):
    data = {}
    if pki_type == 'csr':
        data['is_csr'] = True

    key_type = ask_input(
        'Enter private key type: [rsa, ec]',
        default='rsa',
        valid_responses=['rsa', 'ec'],
    )

    data['key_type'] = key_type

    size_valid = []
    size_default = 0

    if key_type =='rsa':
        key_bits = 2048
        print('RSA private key bits 2048')
    if key_type == 'ec':
        size_default = 256
        size_valid = [256, 384]

        key_bits = ask_input(
            'Enter private key bits:',
            default=size_default,
            numeric_only=True,
            valid_responses=size_valid,
        )
    data['key_bits'] = key_bits

    if pki_type != 'kpair':
        while True:
            country = ask_input('Enter country code:', default=x509_default_values['country'])
            if len(country) != 2:
                print('Country name must be a 2 character country code')
                continue
            data['country'] = country
            break
        data['state'] = ask_input('Enter state:', default=x509_default_values['state'])
        data['locality'] = ask_input(
            'Enter locality:', default=x509_default_values['locality']
        )
        data['organization'] = ask_input(
            'Enter organization name:', default=x509_default_values['organization']
        )
        data['common_name'] = ask_input('Enter common name:', default=x509_default_values['common_name'])

        # https://docs.openssl.org/3.0/man5/x509v3_config/#subject-alternative-name
        san_list = None
        if ask_yes_no('Do you want to configure Subject Alternative Names?'):
            print(
                'Enter alternative names in a comma separate list, example: ipv4:1.1.1.1,ipv6:fe80::1,dns:igos.net,rfc822:user@igos.net'
            )
            san_list = ask_input('Enter Subject Alternative Names:')
            if not validate_san_list(san_list):
                return False
            data['san_list'] = san_list

        valid_days = None
        cert_type = None
        if pki_type != 'csr':
            valid_days = ask_input(
                'Enter how many days certificate will be valid:',
                default='365',
                numeric_only=True,
            )
            data['valid_days'] = valid_days

            cert_type = ask_input(
                'Enter certificate type: (client, server)',
                default='server',
                valid_responses=['client', 'server'],
            )
            data['cert_type'] = cert_type
            data['cert'] = get_path_str('cert', 'pem', name)
            data['key'] = get_path_str('cert', 'key', name)

    return data

# Generation functions
def generate_tpm_private_key(name, key_type, key_bits, pki_type):
    data = {}
    passphrase = ask_passphrase()
    if passphrase is False:
        print('Error: Invalid passphrase')
        return False
    passphrase_cmd = ''
    passin_pw = ''
    if passphrase:
        passphrase_cmd = f' -pkeyopt user-auth:{passphrase}'
        passin_pw = f'--passin pass:{passphrase}'

    keyopt = None
    if key_type == 'rsa':
        keyopt = f'bits:{key_bits}'
    elif key_type == 'ec':
        keyopt = f'ec_paramgen_curve:P-{key_bits}'

    key_file_path = get_path(pki_type, 'key', name)

    if key_file_path.exists():
        if not ask_yes_no(
            'Do you want to overwrite the existing files?'
        ):
            return False

    clear_tpm_lockout()

    cmd = f"openssl genpkey\
        -provider tpm2\
        -propquery '?provider=tpm2'\
        -algorithm {key_type}\
        -out {str(key_file_path)}\
        -pkeyopt {keyopt}\
        {passphrase_cmd}\
    "

    code, output = rc_cmd(cmd)

    if code != 0:
        if isinstance(output, str) and output.strip():
            print(f'Error: {output.splitlines()[0]}')
        return False
    else:
        clear_tpm_lockout()
        if not validate_tpm_private_key(str(key_file_path), passin_pw):
            return False
    return passin_pw

def generate_certificate_selfsign(name):
    data = gather_tpm_common_config_info(name, 'cert')
    if not data:
        return False

    make_tpm_pki_dir('cert', name)

    passin_pw = generate_tpm_private_key(name, data['key_type'], data['key_bits'], 'cert')
    if passin_pw is False:
        return False

    render(get_path_str('cert', 'cfg', name), TMPL_CERT, data)

    clear_tpm_lockout()

    cmd = f"openssl req\
        -provider tpm2\
        -provider default\
        -propquery '?provider=tpm2'\
        -key {get_path_str('cert', 'key', name)}\
        {passin_pw}\
        -x509 -days {data['valid_days']}\
        -config {get_path_str('cert', 'cfg', name)}\
        -extensions v3_req\
        -out {get_path_str('cert', 'pem', name)}\
    "

    code, output = rc_cmd(cmd)
    if code != 0:
        if isinstance(output, str) and output.strip():
            print(f'Error: {output.splitlines()[0]}')
        return False
    else:
        if not validate_certificate(get_path_str('cert', 'pem', name)):
            return False

        print(f"File written to {get_path_str('cert', 'pem', name)}")
        print(f"File written to {get_path_str('cert', 'key', name)}")

def generate_tpm_csr(name, for_cert=False):
    data = gather_tpm_common_config_info(name, 'csr')
    if not data:
        return False

    make_tpm_pki_dir('csr', name)

    render(get_path_str('csr', 'cfg', name), TMPL_CERT, data)

    passin_pw = generate_tpm_private_key(name, data['key_type'], data['key_bits'], 'csr')
    if passin_pw is False:
        return False

    clear_tpm_lockout()

    cmd = f"openssl req\
        -provider tpm2\
        -provider default\
        -propquery '?provider=tpm2'\
        -new\
        -key {get_path_str('csr', 'key', name)}\
        {passin_pw}\
        -config {get_path_str('csr', 'cfg', name)}\
        -out {get_path_str('csr', 'pem', name)}\
    "

    code, output = rc_cmd(cmd)

    if code != 0:
        if isinstance(output, str) and output.strip():
            print(f'Error: {output.splitlines()[0]}')
        return False
    else:
        if not validate_csr(get_path_str('csr', 'pem', name)):
            return False

        print(f"File written to {get_path_str('csr', 'pem', name)}")
        print(f"File written to {get_path_str('csr', 'key', name)}")

def generate_keypair(name):
    data = gather_tpm_common_config_info(name, 'kpair')
    if not data:
        return False

    make_tpm_pki_dir('kpair', name)

    passin_pw = generate_tpm_private_key(name, data['key_type'], data['key_bits'], 'kpair')
    if passin_pw is False:
        return False

    clear_tpm_lockout()

    cmd = f"openssl pkey\
        -provider tpm2\
        -provider default\
        -propquery '?provider=tpm2'\
        -in {get_path_str('kpair', 'key', name)}\
        {passin_pw}\
        -pubout \
        -out {get_path_str('kpair', 'pem', name)}\
    "

    code, output = rc_cmd(cmd)

    if code != 0:
        if isinstance(output, str) and output.strip():
            print(f'Error: {output.splitlines()[0]}')
        return False
    else:
        if not validate_public_key(get_path_str('kpair', 'pem', name)):
            return False

        print(f"File written to {get_path_str('kpair', 'pem', name)}")
        print(f"File written to {get_path_str('kpair', 'key', name)}")

# Import functions
def import_routine(name, pki_type, path=None, key_path=None):
    algorithm = ''
    pki_str = ''

    if path:
        if not os.path.exists(path):
            print(f'Error: File not found at {path}')
            return False

        if pki_type == 'cert':
            if not validate_certificate(path):
                return False
            pki_str = 'certificate'
        elif pki_type == 'csr':
            if not validate_csr(path):
                return False
            pki_str = 'CSR'
        elif pki_type == 'kpair':
            if not validate_public_key(path):
                return False
            pki_str = 'public key'
    else:
        print(f'Error: Missing absolute path of {pki_str} file')
        return False

    if key_path:
        if not os.path.exists(key_path):
            print(f'Error: Key file not found at {key_path}')
            return False

        passwd_str = validate_pki_private_key(key_path)
        if passwd_str == False:
            return False

        algorithm = check_pki_key_algorithm(key_path, passwd_str)
        if not algorithm:
            return False
    else:
        print('Error: Missing absolute path of private key file')
        return False

    if not validate_pub_key_against_priv_key(pki_type, path, key_path, passwd_str):
        print('Error: Imported 2 files do not match')
        return False

    make_tpm_pki_dir(pki_type, name)

    if get_path(pki_type, 'key', name).exists():
        if not ask_yes_no(
            'Do you want to overwrite the existing files?'
        ):
            return False

    if path != get_path_str(pki_type, 'pem', name):
        shutil.copy(path, get_path(pki_type, 'pem', name))
    else:
        print('Error: Import source and destination are the same')
        return False

    tmp_pub_path = get_tpm_pki_dir()/pki_type/name/'import.pub'
    tmp_priv_path = get_tpm_pki_dir()/pki_type/name/'import.priv'

    handle = get_path(is_handle=True).read_text().strip()

    auth_value_str = ''
    if passwd_str:
        auth_value_str = f'-p {passwd_str.split(":", 1)[1]}'

    cmd = f'tpm2_import -C {handle} -G {algorithm} -i {key_path}\
        {passwd_str} -u {str(tmp_pub_path)} -r {str(tmp_priv_path)}\
        {auth_value_str}\
    '

    clear_tpm_lockout()
    code, output = rc_cmd(cmd)

    if code != 0:
        if isinstance(output, str) and output.strip():
            print(f'Error: {output.splitlines()[0]}')
        return False

    cmd = f"tpm2_encodeobject -C {handle}\
        -u {str(tmp_pub_path)} -r {str(tmp_priv_path)}\
        -o {get_path_str(pki_type, 'key', name)}\
    "

    clear_tpm_lockout()
    code, output = rc_cmd(cmd)

    if code != 0:
        if isinstance(output, str) and output.strip():
            print(f'Error: {output.splitlines()[0]}')
        return False
    else:
        tmp_pub_path.unlink(missing_ok=True)
        tmp_priv_path.unlink(missing_ok=True)

        if not validate_tpm_private_key(get_path_str(pki_type, 'key', name), passwd_str):
            return False

        print(f"File imported to {get_path_str(pki_type, 'pem', name)}")
        print(f"File imported to {get_path_str(pki_type, 'key', name)}")

def import_cert_with_tpm_key(name, path=None, key_path=None):
    if path:
        if not os.path.exists(path):
            print(f'Error: File not found at {path}')
            return False
        if not validate_certificate(path):
            return False
    else:
        print('Error: Missing absolute path of certificate file')
        return False

    if key_path:
        if not os.path.exists(key_path):
            print(f'Error: TPM key file not found at {key_path}')
            return False

        passwd_str = validate_tpm_private_key(key_path, '')
        if passwd_str == False:
            return False
    else:
        print('Error: Missing absolute path of TPM private key file')
        return False

    if not validate_certificate_against_tpm_priv_key(path, key_path):
        print('Error: Imported 2 files do not match')
        return False

    make_tpm_pki_dir('cert', name)
    if path != get_path_str('cert', 'pem', name):
        shutil.copy(path, get_path('cert', 'pem', name))
        shutil.copy(key_path, get_path('cert', 'key', name))
    else:
        print('Error: Import source and destination are the same')
        return False

    print(f"File imported to {get_path_str('cert', 'pem', name)}")
    print(f"File imported to {get_path_str('cert', 'key', name)}")

def show_csr(
    raw: bool, name: typing.Optional[str] = None, pem: typing.Optional[bool] = False
):
    headers = [
        'Name',
        'Subject',
        'Private Key',
    ]
    data = []
    csrs = get_tpm_list('csr')
    if csrs:
        for item in csrs:
            if name and name != item:
                continue

            if name and pem:
                content = get_path('csr', 'pem', item).read_text()
                print(content, end='')
                return

            lines = get_path('csr', 'pem', item).read_text().splitlines()

            clean = "".join(
                line.strip()
                for line in lines
                if "BEGIN CERTIFICATE REQUEST" not in line and "END CERTIFICATE REQUEST" not in line
            )
            csr = load_certificate_request(clean)

            if not csr:
                continue

            csr_subject_cn = csr.subject.rfc4514_string().split(',')[0]

            have_private = 'No'
            if get_path('csr', 'key', item).exists():
                key_info = check_pki_key_algorithm(get_path_str('csr', 'key', item), '--passin pass:', get_size=True, for_tpm=True)
                if key_info:
                    have_private = f'Yes ({key_info})'
                else:
                    return

            data.append(
                [
                    item,
                    csr_subject_cn,
                    have_private,
                ]
            )

    print('Certificate Signing Requests:')
    print(tabulate.tabulate(data, headers))

def show_certificate(
    raw: bool,
    name: typing.Optional[str] = None,
    pem: typing.Optional[bool] = False,
    fingerprint: typing.Optional[ArgsFingerprint] = None,
):
    headers = [
        'Name',
        'Type',
        'Subject CN',
        'Issuer CN',
        'Issued',
        'Expiry',
        'Private Key',
    ]
    data = []
    certs = get_tpm_list('cert')

    if certs:
        for item in certs:
            if name and name != item:
                continue

            lines = get_path('cert', 'pem', item).read_text().splitlines()

            clean = "".join(
                line.strip()
                for line in lines
                if "BEGIN CERTIFICATE" not in line and "END CERTIFICATE" not in line
            )
            cert = load_certificate(clean)

            if not cert:
                continue

            if name and pem:
                print(encode_certificate(cert))
                return
            elif name and fingerprint:
                print(get_certificate_fingerprint(cert, fingerprint))
                return

            cert_subject_cn = cert.subject.rfc4514_string().split(',')[0]
            cert_issuer_cn = cert.issuer.rfc4514_string().split(',')[0]
            cert_type = 'Unknown'

            try:
                ext = cert.extensions.get_extension_for_class(x509.ExtendedKeyUsage)
                if ext and ExtendedKeyUsageOID.SERVER_AUTH in ext.value:
                    cert_type = 'Server'
                elif ext and ExtendedKeyUsageOID.CLIENT_AUTH in ext.value:
                    cert_type = 'Client'
            except Exception:
                pass

            cert_path_str = get_path_str('cert', 'pem', item)
            if name and pem:
                content = get_path('cert', 'pem', item).read_text()
                print(content, end='')
                return
            elif name and fingerprint:
                print(get_certificate_fingerprint(cert_path_str, fingerprint))
                return

            have_private = 'No'
            if get_path('cert', 'key', item).exists():
                key_info = check_pki_key_algorithm(get_path_str('cert', 'key', item), '--passin pass:', get_size=True, for_tpm=True)
                if key_info:
                    have_private = f'Yes ({key_info})'
                else:
                    return

            data.append(
                [
                    item,
                    cert_type,
                    cert_subject_cn,
                    cert_issuer_cn,
                    cert.not_valid_before,
                    cert.not_valid_after,
                    have_private,
                ]
            )

    print('Certificates:')
    print(tabulate.tabulate(data, headers))

def show_kpair(
    raw: bool, name: typing.Optional[str] = None, pem: typing.Optional[bool] = False
):
    headers = [
        'Name',
        'Private Key',
    ]
    data = []
    kpairs = get_tpm_list('kpair')
    if kpairs:
        for item in kpairs:
            if name and name != item:
                continue

            if name and pem:
                content = get_path('kpair', 'key', item).read_text()
                print(content, end='')
                return

            have_private = 'No'
            if get_path('kpair', 'key', item).exists():
                key_info = check_pki_key_algorithm(get_path_str('kpair', 'key', item), '--passin pass:', get_size=True, for_tpm=True)
                if key_info:
                    have_private = f'Yes ({key_info})'
                else:
                    return

            data.append(
                [
                    item,
                    have_private,
                ]
            )

    print('Key-pairs:')
    print(tabulate.tabulate(data, headers))

def generate_tpm(
    raw: bool,
    tpm_pki_type: ArgsPkiType,
    name: typing.Optional[str],
    file: typing.Optional[bool],
    sign: typing.Optional[str],
    self_sign: typing.Optional[bool]
):
    if not tpm_enabled():
        print('Invalid action: TPM is disabled')
        return

    [(get_tpm_pki_dir() / d).mkdir(parents=True, exist_ok=True)
        for d in ('cert', 'csr', 'kpair')]

    try:
        if tpm_pki_type == 'cert':
            if self_sign:
                generate_certificate_selfsign(name)
        elif tpm_pki_type == 'csr':
            generate_tpm_csr(name)
        elif tpm_pki_type == 'kpair':
            generate_keypair(name)

    except KeyboardInterrupt:
        print('Aborted')
        sys.exit(0)

def import_tpm(
    tpm_pki_type: ArgsPkiType,
    name: typing.Optional[str],
    path: typing.Optional[str],
    kpath: typing.Optional[str]
):
    if not tpm_enabled():
        print('Invalid action: TPM is disabled')
        return

    [(get_tpm_pki_dir() / d).mkdir(parents=True, exist_ok=True)
        for d in ('cert', 'csr', 'kpair')]

    if not ensure_persistent_primary_handle():
        return

    try:
        if tpm_pki_type == 'cert_with_tpm':
            import_cert_with_tpm_key(name, path=path, key_path=kpath)
        else:
            import_routine(name, tpm_pki_type, path=path, key_path=kpath)
        return
    except KeyboardInterrupt:
        print('Aborted')
        sys.exit(0)

def show_all(raw):
    show_csr(raw)
    print('\n')
    show_certificate(raw)
    print('\n')
    show_kpair(raw)

if __name__ == '__main__':
    try:
        res = vyos.opmode.run(sys.modules[__name__])
        if res:
            print(res)
    except (ValueError, vyos.opmode.Error) as e:
        print(e)
        sys.exit(1)
