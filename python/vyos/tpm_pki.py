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

import re
import shutil
import ipaddress

from pathlib import Path

from vyos.utils.io import ask_input
from vyos.utils.io import ask_yes_no
from vyos.utils.process import rc_cmd

TPM_PKI_ROOT_PATH = Path('/config/auth/tpm')

KEY_ENC_BEGIN='-----BEGIN ENCRYPTED PRIVATE KEY-----'

TPM_PRIMARY_CTX = TPM_PKI_ROOT_PATH/'primary.ctx'
TPM_PRIMARY_PUBKEY = TPM_PKI_ROOT_PATH/'primary.pub'
TMP_TPM_PRIMARY_PUBKEY = TPM_PKI_ROOT_PATH/'primary-pub.tmp'
TPM_PRIMARY_HANDLE = TPM_PKI_ROOT_PATH/'tpm_handle'

DNS_LABEL_REGEX = re.compile(r'^(?!-)[A-Za-z0-9-]{1,63}(?<!-)$')
EMAIL_REGEX = re.compile(r'^[^@]+@[^@]+\.[^@]+$')
URI_REGEX = re.compile(r'^[a-zA-Z][a-zA-Z0-9+.-]*://.+$')
RID_REGEX = re.compile(r'^(\d+\.)+\d+$')
OTHERNAME_REGEX = re.compile(r'^[\d\.]+;.+:.+$')

def make_tpm_pki_dir(pki_type, name):
    (TPM_PKI_ROOT_PATH/pki_type/name).mkdir(parents=True, exist_ok=True)

def get_tpm_pki_dir(pki_type: str = '') -> Path:
    return TPM_PKI_ROOT_PATH/pki_type

def get_path(pki_type: str = '', item: str = '', name: str = '', base_dir=TPM_PKI_ROOT_PATH, is_handle=False) -> Path:
    if is_handle:
        return TPM_PRIMARY_HANDLE
    if not pki_type or not item or not name:
        return False

    if item == 'cfg':
        return (base_dir/pki_type/name/f'{name}.cnf').absolute()
    elif item == 'key':
        return (base_dir/pki_type/name/f'{name}.key').absolute()
    else:
        return (base_dir/pki_type/name/f'{name}.pem').absolute()

def get_path_str(pki_type, item, name, base_dir=TPM_PKI_ROOT_PATH) -> str:
    if not pki_type or not item or not name:
        return False

    if item == 'cfg':
        return str((base_dir/pki_type/name/f'{name}.cnf').absolute())
    elif item == 'key':
        return str((base_dir/pki_type/name/f'{name}.key').absolute())
    else:
        return str((base_dir/pki_type/name/f'{name}.pem').absolute())

def get_tpm_list(pki_type):
    groups = []
    if not get_tpm_pki_dir(pki_type).exists() or not any(p.is_dir() for p in get_tpm_pki_dir(pki_type).iterdir()):
        return groups
    else:
        paths = [p for p in get_tpm_pki_dir(pki_type).glob("*") if p.is_dir()]
        paths.sort(key=lambda p: p.stat().st_mtime)

        groups = [p.name for p in paths]
        return groups

def clear_tpm_lockout():
    cmd = f'tpm2_dictionarylockout --clear-lockout'
    code, output = rc_cmd(cmd)

    if code != 0:
        if isinstance(output, str) and output.strip():
            print(f'Error: {output.splitlines()[0]}')
        return False
    else:
        return True

def is_valid_passphrase(passphrase: str):
    if not passphrase:
        return False
    if any(c.isspace() for c in passphrase):
        return False
    return passphrase

def ask_passphrase():
    passphrase = None
    if ask_yes_no('Do you want to encrypt the private key with a passphrase?'):
        passphrase = ask_input('Enter passphrase:')
        return is_valid_passphrase(passphrase)
    else:
        return passphrase

def get_passphrase(key_path):
    passphrase = ask_input(f'Enter pass phrase for {key_path}:')
    return is_valid_passphrase(passphrase)

def check_pki_key_algorithm(path, passwd_str, get_size=False, for_tpm=False):
    provider_str = ''
    if for_tpm:
        provider_str = "-provider tpm2 -provider default -propquery '?provider=tpm2'"
    cmd = f'openssl pkey {provider_str} -in {path} {passwd_str} -pubout -outform DER | openssl asn1parse -inform DER'
    code, output = rc_cmd(cmd)

    if code != 0:
        if isinstance(output, str) and output.strip():
            print(f'Error: {output.splitlines()[0]}')
        return False

    key_type = ''
    if 'rsaEncryption' in output:
        key_type = 'rsa'
    elif 'id-ecPublicKey' in output:
        key_type = 'ecc'

    cmd = f'openssl pkey {provider_str} -in {path} {passwd_str} -noout -text'
    code, output = rc_cmd(cmd)

    match = ''
    if for_tpm:
        if key_type == 'rsa':
            match = re.search(r'Private-Key: \(RSA (\d+) bit', output)
        elif key_type == 'ecc':
            match = re.search(r'Private-Key: \(EC P-(\d+)', output)
    else:
        match = re.search(r'Private-Key: \((\d+) bit', output)
    if not match:
        print('Error: Could not determine key size')
        return False

    size = int(match.group(1))

    if key_type == 'rsa':
        if size == 2048:
            if get_size:
                return 'RSA, 2048'
            else:
                return key_type
        else:
            print('Error: Could not import RSA key with key size other than 2048')
            return False
    elif key_type == 'ecc':
        if size == 256 or size == 384:
            if get_size:
                return f'EC, {size}'
            else:
                return key_type
        else:
            print('Error: Could not import EC key with key size other than 256 or 384')
            return False

    print('Error: Unsupported key type for TPM')
    return False

def validate_tpm_private_key(key_path, passwd_str):
    clear_tpm_lockout()

    if not passwd_str:
        passwd_str = '--passin pass:'

    cmd = f"openssl pkey\
        -provider tpm2\
        -provider default\
        -propquery '?provider=tpm2'\
        -in {key_path}\
        {passwd_str}\
        -check\
        -noout\
    "

    code, output = rc_cmd(cmd)

    if code != 0:
        if isinstance(output, str) and output.strip():
            print(f'Error: {output.splitlines()[0]}')
        return False
    else:
        return True

def validate_pki_private_key(key_path):
    passwd_str = ''
    with open(key_path, 'r', encoding='utf-8') as f:
        content = f.read()
        if KEY_ENC_BEGIN in content:
            passphrase = get_passphrase(key_path)
            if passphrase is False:
                print('Error: Invalid passphrase')
                return False
            passwd_str = f'--passin pass:{passphrase}'
    cmd = f'openssl pkey -in {key_path} {passwd_str} -check -noout'
    code, output = rc_cmd(cmd)

    if code != 0:
        if isinstance(output, str) and output.strip():
            print(f'Error: {output.splitlines()[0]}')
        return False
    else:
        return passwd_str

def validate_certificate(path):
    cmd = f'openssl x509 -in {path} -noout'
    code, output = rc_cmd(cmd)

    if code != 0:
        if isinstance(output, str) and output.strip():
            print(f'Error: {output.splitlines()[0]}')
        return False
    else:
        return True

def validate_csr(path):
    cmd = f'openssl req -verify -in {path} -noout'
    code, output = rc_cmd(cmd)

    if code != 0:
        if isinstance(output, str) and output.strip():
            print(f'Error: {output.splitlines()[0]}')
        return False
    else:
        return True

def validate_public_key(path):
    cmd = f'openssl pkey -pubin -in {path} -noout'
    code, output = rc_cmd(cmd)

    if code != 0:
        if isinstance(output, str) and output.strip():
            print(f'Error: {output.splitlines()[0]}')
        return False
    else:
        return True

def validate_pub_key_against_priv_key(pki_type, path, key_path, passwd_str):
    priv_pub = ''
    cmd = f'openssl pkey -in {key_path} {passwd_str} -pubout'
    code, output = rc_cmd(cmd)

    if code != 0:
        if isinstance(output, str) and output.strip():
            print(f'Error: {output.splitlines()[0]}')
        return False
    else:
        priv_pub = output

    if pki_type == 'cert':
        cmd = f'openssl x509 -in {path} -noout -pubkey'
        code, output = rc_cmd(cmd)

        if code != 0:
            if isinstance(output, str) and output.strip():
                print(f'Error: {output.splitlines()[0]}')
            return False
        else:
            return output == priv_pub
    elif pki_type == 'csr':
        cmd = f'openssl req -in {path} -noout -pubkey'
        code, output = rc_cmd(cmd)

        if code != 0:
            if isinstance(output, str) and output.strip():
                print(f'Error: {output.splitlines()[0]}')
            return False
        else:
            return output == priv_pub
    elif pki_type == 'kpair':
        pub_path = Path(path)
        pub_key = pub_path.read_text().strip()

        if not pub_key:
            if isinstance(output, str) and output.strip():
                print(f'Error: {output.splitlines()[0]}')
            return False
        else:
            return pub_key == priv_pub

def validate_certificate_against_tpm_priv_key(path, key_path):
    tpm_priv_pub = ''

    cmd = f"openssl pkey\
        -provider tpm2\
        -provider default\
        -propquery '?provider=tpm2'\
        --passin pass:\
        -in {key_path}\
        -pubout\
    "
    code, output = rc_cmd(cmd)

    if code != 0:
        if isinstance(output, str) and output.strip():
            print(f'Error: {output.splitlines()[0]}')
        return False
    else:
        tpm_priv_pub = output

    cmd = f'openssl x509 -in {path} -noout -pubkey'
    code, output = rc_cmd(cmd)

    if code != 0:
        if isinstance(output, str) and output.strip():
            print(f'Error: {output.splitlines()[0]}')
        return False
    else:
        return output == tpm_priv_pub

def cleanup_primary_handle(handle=None, on_error=False):
    TPM_PRIMARY_CTX.unlink(missing_ok=True)
    TMP_TPM_PRIMARY_PUBKEY.unlink(missing_ok=True)
    if on_error:
        if not handle and TPM_PRIMARY_HANDLE.exists():
            handle = TPM_PRIMARY_HANDLE.read_text().strip()

        if handle:
            cmd = f'tpm2_evictcontrol -C o -c {handle}'
            clear_tpm_lockout()
            code, output = rc_cmd(cmd)
            if code != 0:
                if isinstance(output, str) and output.strip():
                    print(f'Error: {output.splitlines()[0]}')
                return False
        TPM_PRIMARY_HANDLE.unlink(missing_ok=True)
        TPM_PRIMARY_PUBKEY.unlink(missing_ok=True)

def ensure_persistent_primary_handle():
    if not TPM_PRIMARY_HANDLE.exists():
        if not TPM_PRIMARY_CTX.exists():
            cmd = f'tpm2_createprimary -C o -g sha256 -G rsa -c {TPM_PRIMARY_CTX}'
            clear_tpm_lockout()
            code, output = rc_cmd(cmd)

            if code != 0:
                if isinstance(output, str) and output.strip():
                    print(f'Error: {output.splitlines()[0]}')
                return False

        cmd = f'tpm2_evictcontrol -C o -c {TPM_PRIMARY_CTX}'
        clear_tpm_lockout()
        code, output = rc_cmd(cmd)

        if code != 0:
            if isinstance(output, str) and output.strip():
                print(f'Error: {output.splitlines()[0]}')
            return False
        else:
            match = re.search(r'persistent-handle:\s*(0x[0-9a-fA-F]+)', output)
            if not match:
                print('Error: Persistent handle not found')
                return False

            handle = match.group(1)
            TPM_PRIMARY_HANDLE.write_text(handle + "\n")

            cmd = f'tpm2_readpublic -c {TPM_PRIMARY_CTX} -o {TPM_PRIMARY_PUBKEY} -f pem'
            clear_tpm_lockout()
            code, output = rc_cmd(cmd)

            if code != 0:
                if isinstance(output, str) and output.strip():
                    print(f'Error: {output.splitlines()[0]}')
                cleanup_primary_handle(handle, on_error=True)
                return False
            cleanup_primary_handle()
            return True
    else:
        saved_handle = TPM_PRIMARY_HANDLE.read_text().strip()
        if not saved_handle:
            print(f'TPM primary handle file at {TPM_PRIMARY_HANDLE} is empty')
            cleanup_primary_handle(handle, on_error=True)
            return False

        cmd = 'tpm2_getcap handles-persistent'
        clear_tpm_lockout()
        code, output = rc_cmd(cmd)
        if code != 0:
            if isinstance(output, str) and output.strip():
                print(f'Error: {output.splitlines()[0]}')
            return False
        else:
            if saved_handle not in output:
                print(f'TPM primary handle stored in {TPM_PRIMARY_HANDLE} does not exist in TPM')
                cleanup_primary_handle(handle, on_error=True)
                return False

            cmd = f'tpm2_readpublic -c {saved_handle} -f pem -o {TMP_TPM_PRIMARY_PUBKEY}'
            clear_tpm_lockout()
            code, output = rc_cmd(cmd)
            if code != 0:
                if isinstance(output, str) and output.strip():
                    print(f'Error: {output.splitlines()[0]}')
                cleanup_primary_handle(handle, on_error=True)
                return False
            else:
                saved_pubkey = TPM_PRIMARY_PUBKEY.read_text().strip()
                read_pubkey = TMP_TPM_PRIMARY_PUBKEY.read_text().strip()
                if read_pubkey != saved_pubkey:
                    print('TPM primary handle and saved public key mismatch')
    cleanup_primary_handle()
    return True

def validate_dns(value: str) -> bool:
    return all(DNS_LABEL_REGEX.match(label) for label in value.split('.'))

def validate_ip(value: str) -> bool:
    try:
        ipaddress.ip_address(value)
        return True
    except ValueError:
        return False

def validate_email(value: str) -> bool:
    return value.lower() in ('copy', 'move') or EMAIL_REGEX.match(value) is not None

def validate_uri(value: str) -> bool:
    return URI_REGEX.match(value) is not None

def validate_rid(value: str) -> bool:
    return RID_REGEX.match(value) is not None

def validate_othername(value: str) -> bool:
    return OTHERNAME_REGEX.match(value) is not None

def validate_dirname(value: str) -> bool:
    return bool(value.strip())

def validate_san_entry(entry: str) -> bool:
    if ':' not in entry:
        return False
    key, value = entry.split(':', 1)
    key = key.strip().lower()
    value = value.strip()

    if key == 'dns':
        return validate_dns(value)
    elif key in ['ip', 'ipv4', 'ipv6']:
        return validate_ip(value)
    elif key in ['email', 'rfc822']:
        return validate_email(value)
    # pki only supports above prefixs
    # elif key == 'uri':
    #     return validate_uri(value)
    # elif key == 'rid':
    #     return validate_rid(value)
    # elif key == 'dirname':
    #     return validate_dirname(value)
    # elif key == 'othername':
    #     return validate_othername(value)
    else:
        return False

def validate_san_list(san_input) -> bool:
    if isinstance(san_input, str):
        entries = [s.strip() for s in san_input.split(',') if s.strip()]
    elif isinstance(san_input, list):
        entries = san_input
    else:
        print('SAN input must be a string or a list of strings')
        print('Abort')
        return False

    for entry in entries:
        if not validate_san_entry(entry):
            print(f'SAN entry invalid: {entry}')
            print('Abort')
            return False
    return True

def remove_all_tpm_pki_handle_and_files():
    if get_tpm_list('cert') or get_tpm_list('csr') or get_tpm_list('kpair'):
        if not ask_yes_no(
            'Do you want to remove all Identity Certificates and tpm backed key files under /config/auth/tpm?'
        ):
            return False

    if TPM_PRIMARY_HANDLE.exists():
        saved_handle = TPM_PRIMARY_HANDLE.read_text().strip()
        if not saved_handle:
            print(f'TPM primary handle file at {TPM_PRIMARY_HANDLE} is empty')
            cleanup_primary_handle(saved_handle, on_error=True)
            return False

        cmd = f'tpm2_evictcontrol -C o -c {saved_handle}'
        clear_tpm_lockout()
        code, output = rc_cmd(cmd)

        if code != 0:
            if isinstance(output, str) and output.strip():
                print(f'Error: {output.splitlines()[0]}')
            return False

    if TPM_PKI_ROOT_PATH.exists():
        shutil.rmtree(TPM_PKI_ROOT_PATH)
