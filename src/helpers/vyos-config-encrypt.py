#!/usr/bin/env python3
#
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
import shutil
import sys

from argparse import ArgumentParser
from cryptography.fernet import Fernet
from tempfile import NamedTemporaryFile
from tempfile import TemporaryDirectory

from vyos.tpm import clear_tpm_key
from vyos.tpm import read_tpm_key
from vyos.tpm import write_tpm_key
from vyos.utils.io import ask_input, ask_yes_no
from vyos.utils.process import cmd

persistpath_cmd = '/opt/vyatta/sbin/vyos-persistpath'
mount_paths = ['/config', '/opt/vyatta/etc/config']
dm_device = '/dev/mapper/vyos_config'

def is_opened():
    return os.path.exists(dm_device)

def get_current_image():
    with open('/proc/cmdline', 'r') as f:
        args = f.read().split(" ")
        for arg in args:
            if 'vyos-union' in arg:
                k, v = arg.split("=")
                path_split = v.split("/")
                return path_split[-1]
    return None

def load_config(key):
    if not key:
        return

    persist_path = cmd(persistpath_cmd).strip()
    image_name = get_current_image()
    image_path = os.path.join(persist_path, 'luks', image_name)

    if not os.path.exists(image_path):
        raise Exception("Encrypted config volume doesn't exist")

    if is_opened():
        print('Encrypted config volume is already mounted')
        return

    with NamedTemporaryFile(dir='/dev/shm', delete=False) as f:
        f.write(key)
        key_file = f.name

    cmd(f'cryptsetup -q open {image_path} vyos_config --key-file={key_file}')

    for path in mount_paths:
        cmd(f'mount /dev/mapper/vyos_config {path}')
        cmd(f'chgrp -R vyattacfg {path}')

    os.unlink(key_file)

    return True

def encrypt_config(key, recovery_key):
    if is_opened():
        raise Exception('An encrypted config volume is already mapped')

    # Clear and write key to TPM
    try:
        clear_tpm_key()
    except:
        pass
    write_tpm_key(key)

    persist_path = cmd(persistpath_cmd).strip()
    size = ask_input('Enter size of encrypted config partition (MB): ', numeric_only=True, default=512)

    luks_folder = os.path.join(persist_path, 'luks')

    if not os.path.isdir(luks_folder):
        os.mkdir(luks_folder)

    image_name = get_current_image()
    image_path = os.path.join(luks_folder, image_name)

    # Create file for encrypted config
    cmd(f'fallocate -l {size}M {image_path}')

    # Write TPM key for slot #1
    with NamedTemporaryFile(dir='/dev/shm', delete=False) as f:
        f.write(key)
        key_file = f.name

    # Format and add main key to volume
    cmd(f'cryptsetup -q luksFormat {image_path} {key_file}')

    if recovery_key:
        # Write recovery key for slot 2
        with NamedTemporaryFile(dir='/dev/shm', delete=False) as f:
            f.write(recovery_key)
            recovery_key_file = f.name

        cmd(f'cryptsetup -q luksAddKey {image_path} {recovery_key_file} --key-file={key_file}')

    # Open encrypted volume and format with ext4
    cmd(f'cryptsetup -q open {image_path} vyos_config --key-file={key_file}')
    cmd('mkfs.ext4 /dev/mapper/vyos_config')

    with TemporaryDirectory() as d:
        cmd(f'mount /dev/mapper/vyos_config {d}')

        # Move /config to encrypted volume
        shutil.copytree('/config', d, copy_function=shutil.move, dirs_exist_ok=True)

        cmd(f'umount {d}')

    os.unlink(key_file)

    if recovery_key:
        os.unlink(recovery_key_file)

    for path in mount_paths:
        cmd(f'mount /dev/mapper/vyos_config {path}')
        cmd(f'chgrp vyattacfg {path}')

    return True

def decrypt_config(key):
    if not key:
        return

    persist_path = cmd(persistpath_cmd).strip()
    image_name = get_current_image()
    image_path = os.path.join(persist_path, 'luks', image_name)

    if not os.path.exists(image_path):
        raise Exception("Encrypted config volume doesn't exist")

    key_file = None

    if not is_opened():
        with NamedTemporaryFile(dir='/dev/shm', delete=False) as f:
            f.write(key)
            key_file = f.name

        cmd(f'cryptsetup -q open {image_path} vyos_config --key-file={key_file}')

    # unmount encrypted volume mount points
    for path in mount_paths:
        if os.path.ismount(path):
            cmd(f'umount {path}')

    # If /config is populated, move to /config.old
    if len(os.listdir('/config')) > 0:
        print('Moving existing /config folder to /config.old')
        shutil.move('/config', '/config.old')

    # Temporarily mount encrypted volume and migrate files to /config on rootfs
    with TemporaryDirectory() as d:
        cmd(f'mount /dev/mapper/vyos_config {d}')

        # Move encrypted volume to /config
        shutil.copytree(d, '/config', copy_function=shutil.move, dirs_exist_ok=True)
        cmd(f'chgrp -R vyattacfg /config')

        cmd(f'umount {d}')

    # Close encrypted volume
    cmd('cryptsetup -q close vyos_config')

    # Remove encrypted volume image file and key
    if key_file:
        os.unlink(key_file)
    os.unlink(image_path)

    try:
        clear_tpm_key()
    except:
        pass

    return True

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Must specify action.")
        sys.exit(1)

    parser = ArgumentParser(description='Config encryption')
    parser.add_argument('--disable', help='Disable encryption', action="store_true")
    parser.add_argument('--enable', help='Enable encryption', action="store_true")
    parser.add_argument('--load', help='Load encrypted config volume', action="store_true")
    args = parser.parse_args()

    tpm_exists = os.path.exists('/sys/class/tpm/tpm0')

    key = None
    recovery_key = None
    need_recovery = False

    question_key_str = 'recovery key' if tpm_exists else 'key'

    if tpm_exists:
        if args.enable:
            key = Fernet.generate_key()
        elif args.disable or args.load:
            try:
                key = read_tpm_key()
                need_recovery = False
            except:
                print('Failed to read key from TPM, recovery key required')
                need_recovery = True
    else:
        need_recovery = True

    if args.enable and not tpm_exists:
        print('WARNING: VyOS will boot into a default config when encrypted without a TPM')
        print('You will need to manually login with default credentials and use "encryption load"')
        print('to mount the encrypted volume and use "load /config/config.boot"')

        if not ask_yes_no('Are you sure you want to proceed?'):
            sys.exit(0)

    if need_recovery or (args.enable and not ask_yes_no(f'Automatically generate a {question_key_str}?', default=True)):
        while True:
            recovery_key = ask_input(f'Enter {question_key_str}:', default=None).encode()

            if len(recovery_key) >= 32:
                break

            print('Invalid key - must be at least 32 characters, try again.')
    else:
        recovery_key = Fernet.generate_key()

    try:
        if args.disable:
            decrypt_config(key or recovery_key)

            print('Encrypted config volume has been disabled')
            print('Contents have been migrated to /config on rootfs')
        elif args.load:
            load_config(key or recovery_key)

            print('Encrypted config volume has been mounted')
            print('Use "load /config/config.boot" to load configuration')
        elif args.enable and tpm_exists:
            encrypt_config(key, recovery_key)

            print('Encrypted config volume has been enabled with TPM')
            print('Backup the recovery key in a safe place!')
            print('Recovery key: ' + recovery_key.decode())
        elif args.enable:
            encrypt_config(recovery_key)

            print('Encrypted config volume has been enabled without TPM')
            print('Backup the key in a safe place!')
            print('Key: ' + recovery_key.decode())
    except Exception as e:
        word = 'decrypt' if args.disable or args.load else 'encrypt'
        print(f'Failed to {word} config: {e}')
