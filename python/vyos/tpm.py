# Copyright (C) 2024 VyOS maintainers and contributors
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
import tempfile

from vyos.utils.process import rc_cmd

default_pcrs = ['0','2','4','7']
tpm_handle = 0x81000000

def init_tpm(clear=False):
    """
    Initialize TPM
    """
    code, output = rc_cmd('tpm2_startup' + (' -c' if clear else ''))
    if code != 0:
        raise Exception('init_tpm: Failed to initialize TPM')

def clear_tpm_key():
    """
    Clear existing key on TPM
    """
    code, output = rc_cmd(f'tpm2_evictcontrol -C o -c {tpm_handle}')
    if code != 0:
        raise Exception('clear_tpm_key: Failed to clear TPM key')

def read_tpm_key(index=0, pcrs=default_pcrs):
    """
    Read existing key on TPM
    """
    with tempfile.TemporaryDirectory() as tpm_dir:
        pcr_str = ",".join(pcrs)

        tpm_key_file = os.path.join(tpm_dir, 'tpm_key.key')
        code, output = rc_cmd(f'tpm2_unseal -c {tpm_handle + index} -p pcr:sha256:{pcr_str} -o {tpm_key_file}')
        if code != 0:
            raise Exception('read_tpm_key: Failed to read key from TPM')

        with open(tpm_key_file, 'rb') as f:
            tpm_key = f.read()

        return tpm_key

def write_tpm_key(key, index=0, pcrs=default_pcrs):
    """
    Saves key to TPM
    """
    with tempfile.TemporaryDirectory() as tpm_dir:
        pcr_str = ",".join(pcrs)

        policy_file = os.path.join(tpm_dir, 'policy.digest')
        code, output = rc_cmd(f'tpm2_createpolicy --policy-pcr -l sha256:{pcr_str} -L {policy_file}')
        if code != 0:
            raise Exception('write_tpm_key: Failed to create policy digest')

        primary_context_file = os.path.join(tpm_dir, 'primary.ctx')
        code, output = rc_cmd(f'tpm2_createprimary -C e -g sha256 -G rsa -c {primary_context_file}')
        if code != 0:
            raise Exception('write_tpm_key: Failed to create primary key')

        key_file = os.path.join(tpm_dir, 'crypt.key')
        with open(key_file, 'wb') as f:
            f.write(key)

        public_obj = os.path.join(tpm_dir, 'obj.pub')
        private_obj = os.path.join(tpm_dir, 'obj.key')
        code, output = rc_cmd(
            f'tpm2_create -g sha256 \
            -u {public_obj} -r {private_obj} \
            -C {primary_context_file} -L {policy_file} -i {key_file}')

        if code != 0:
            raise Exception('write_tpm_key: Failed to create object')

        load_context_file = os.path.join(tpm_dir, 'load.ctx')
        code, output = rc_cmd(f'tpm2_load -C {primary_context_file} -u {public_obj} -r {private_obj} -c {load_context_file}')

        if code != 0:
            raise Exception('write_tpm_key: Failed to load object')

        code, output = rc_cmd(f'tpm2_evictcontrol -c {load_context_file} -C o {tpm_handle + index}')

        if code != 0:
            raise Exception('write_tpm_key: Failed to write object to TPM')
